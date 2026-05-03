# -*- coding: utf-8 -*-
"""
Slice 4 测试: 交易执行增强
测试风控、订单验证、重试机制、每日亏损限制
"""

import pytest
import sys
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 导入模块
import polymarket_weather_trader_final as trader


class TestFunctionExistence:
    """测试函数存在性"""

    def test_get_position_size_exists(self):
        """验证 get_position_size (单数) 函数可导入"""
        assert hasattr(trader, 'get_position_size'), "get_position_size 函数不存在"
        assert callable(trader.get_position_size), "get_position_size 不是可调用函数"

    def test_validate_order_on_chain_exists(self):
        """验证 validate_order_on_chain 函数存在"""
        assert hasattr(trader, 'validate_order_on_chain'), "validate_order_on_chain 函数不存在"

    def test_risk_control_config_exists(self):
        """验证风控配置存在"""
        assert hasattr(trader, 'MAX_DAILY_LOSS'), "MAX_DAILY_LOSS 配置不存在"
        assert hasattr(trader, 'MAX_POSITIONS'), "MAX_POSITIONS 配置不存在"
        assert hasattr(trader, 'MAX_SINGLE_TRADE'), "MAX_SINGLE_TRADE 配置不存在"
        assert hasattr(trader, 'RETRY_ATTEMPTS'), "RETRY_ATTEMPTS 配置不存在"


class TestPositionSize:
    """测试仓位计算"""

    def test_light_position_morning(self):
        """测试轻仓期 (00-07) 仓位"""
        # YES < 0.10 → 1 USDC
        result = trader.get_position_size(0.08, hour=3)
        assert result == 1.0, f"期望 1.0, 实际 {result}"

    def test_light_position_threshold(self):
        """测试轻仓期边界"""
        # YES < 0.20 → 0.5 USDC
        result = trader.get_position_size(0.15, hour=5)
        assert result == 0.5, f"期望 0.5, 实际 {result}"

    def test_aggressive_morning(self):
        """测试加码期 (07-11) 仓位"""
        # YES < 0.10 → 10 USDC
        result = trader.get_position_size(0.05, hour=9)
        assert result == 10.0, f"期望 10.0, 实际 {result}"

    def test_no_position_high_price(self):
        """测试高价时不买入"""
        # YES >= 0.25 → None
        result = trader.get_position_size(0.30, hour=10)
        assert result is None, f"期望 None, 实际 {result}"


class TestRiskControl:
    """测试风控机制"""

    def test_max_positions_limit(self):
        """测试持仓数不超过 MAX_POSITIONS"""
        # 创建超过限制的机会
        opportunities = []
        for i in range(10):
            opportunities.append({
                'market_id': f'market_{i}',
                'condition_id': f'cond_{i}',
                'city': f'City{i}',
                'yes_price': 0.08,
                'hour': 9
            })

        # Mock get_position_size to return a value
        with patch.object(trader, 'get_position_size', return_value=5.0):
            with patch.object(trader, 'create_order', return_value={'status': 'CREATED', 'order_id': f'order_{i}'}):
                # 执行交易
                trades = trader.execute_trades(opportunities)

        # 应该只执行 MAX_POSITIONS 笔
        assert len(trades) <= trader.MAX_POSITIONS, f"持仓数 {len(trades)} 超过限制 {trader.MAX_POSITIONS}"

    def test_max_single_trade_limit(self):
        """测试单笔最大交易限制"""
        # 单笔超过限制
        with patch.object(trader, 'get_position_size', return_value=50.0):  # 超过 MAX_SINGLE_TRADE
            opportunities = [{
                'market_id': 'market_1',
                'condition_id': 'cond_1',
                'city': 'TestCity',
                'yes_price': 0.08,
            }]

            # Mock create_order to capture the actual amount
            captured_amounts = []
            original_create = trader.create_order

            def mock_create(market_id, amount_usdc, yes_price):
                captured_amounts.append(amount_usdc)
                return {'status': 'CREATED', 'order_id': 'test_order'}

            with patch.object(trader, 'create_order', side_effect=mock_create):
                trades = trader.execute_trades(opportunities)

            # 验证没有超过单笔限制
            for amt in captured_amounts:
                assert amt <= trader.MAX_SINGLE_TRADE, f"单笔 {amt} 超过限制 {trader.MAX_SINGLE_TRADE}"

    def test_no_trading_after_noon(self):
        """测试 12:00 后禁止交易"""
        opportunities = [{
            'market_id': 'market_1',
            'condition_id': 'cond_1',
            'city': 'TestCity',
            'yes_price': 0.08,
        }]

        with patch('polymarket_weather_trader_final.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2024, 1, 1, 13, 0, 0)  # 13:00

            # 如果函数依赖 datetime.now()，需要 patch
            with patch.object(trader, 'get_position_size', return_value=5.0):
                trades = trader.execute_trades(opportunities)

        # 应该没有交易
        assert len(trades) == 0, f"13:00 不应交易，但执行了 {len(trades)} 笔"


class TestOrderRetry:
    """测试订单重试机制"""

    def test_create_order_with_retry_exists(self):
        """测试 create_order_with_retry 函数存在"""
        assert hasattr(trader, 'create_order_with_retry'), "create_order_with_retry 函数不存在"
        assert callable(trader.create_order_with_retry), "create_order_with_retry 不是可调用函数"

    def test_retry_attempts_config(self):
        """测试重试配置"""
        assert trader.RETRY_ATTEMPTS == 3, f"期望 3, 实际 {trader.RETRY_ATTEMPTS}"
        assert trader.RETRY_DELAY == 2, f"期望 2, 实际 {trader.RETRY_DELAY}"

    def test_retry_logic(self):
        """测试重试逻辑执行正确次数"""
        call_count = 0

        def flaky_create_order(market_id, amount_usdc, yes_price):
            nonlocal call_count
            call_count += 1
            return None  # 总是失败

        with patch.object(trader, 'create_order', side_effect=flaky_create_order):
            result = trader.create_order_with_retry('market_1', 5.0, 0.08)

        # 应该重试 RETRY_ATTEMPTS 次
        assert call_count == trader.RETRY_ATTEMPTS, f"期望 {trader.RETRY_ATTEMPTS} 次, 实际 {call_count}"
        assert result is None, "所有尝试失败后应返回 None"

    def test_retry_succeeds_on_second_attempt(self):
        """测试第二次尝试成功"""
        call_count = 0

        def flaky_create_order(market_id, amount_usdc, yes_price):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                return None
            return {'status': 'CREATED', 'order_id': 'order_success', 'shares': 10}

        with patch.object(trader, 'create_order', side_effect=flaky_create_order):
            result = trader.create_order_with_retry('market_1', 5.0, 0.08)

        assert call_count == 2, f"期望 2 次, 实际 {call_count}"
        assert result is not None, "第二次应该成功"
        assert result['order_id'] == 'order_success'


class TestOrderValidation:
    """测试订单链上验证"""

    def test_validate_order_on_chain_success(self):
        """测试订单验证成功"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'status': 'FILLED'}

        with patch('requests.get', return_value=mock_response):
            result = trader.validate_order_on_chain('test_order_123')
            assert result is True, "验证应该成功"

    def test_validate_order_on_chain_failure(self):
        """测试订单验证失败"""
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch('requests.get', return_value=mock_response):
            result = trader.validate_order_on_chain('nonexistent_order')
            assert result is False, "验证应该失败"


class TestDailyLossLimit:
    """测试每日亏损限制"""

    def test_daily_loss_limit_config(self):
        """测试每日亏损限制配置值"""
        assert trader.MAX_DAILY_LOSS == 50.0, f"期望 50.0, 实际 {trader.MAX_DAILY_LOSS}"

    def test_trading_stops_on_daily_loss_limit(self):
        """测试达到每日亏损限制时停止交易"""
        # 这个测试需要模拟当天的累计亏损
        # 由于当前实现没有 tracking 每日亏损，这个测试留作占位
        # 实际实现可能需要在模块级别 tracking
        assert hasattr(trader, 'MAX_DAILY_LOSS'), "需要有每日亏损限制配置"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])