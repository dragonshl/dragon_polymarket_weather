"""
Unit Tests for Adaptive StopLoss System (ASL)
===============================================

Covers:
- Trigger price calculation
- Market health check
- Probe pricing
- Multi-tick confirmation
- Full execution flow

Author: Dragonclawbot
Date: 2026-03-17
"""

import pytest
import asyncio
from datetime import datetime
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'systems'))

from adaptive_stoploss_system import (
    calculate_trigger_price,
    is_market_healthy,
    get_probe_size,
    calculate_fak_price,
    should_trigger_stop_loss,
    ConfirmationEngine,
    StopLossExecutor,
    AdaptiveStopLossSystem,
    StopLossStatus,
    StopLossState,
    create_mock_order_book,
    simulate_market_decline
)


class TestTriggerPriceCalculation:
    """Test trigger price calculation"""
    
    def test_basic_trigger_price(self):
        """Test basic trigger price with 30% stop loss"""
        result = calculate_trigger_price(
            avg_buy_price=0.50,
            cycle_max_avg_buy=0.52,
            stop_loss_pct=-0.30
        )
        
        assert result['anchor_price'] == 0.52  # Uses cycle max
        assert result['trigger_price'] == 0.364  # 0.52 * 0.70
        assert result['cushion_pct'] == 0.30
    
    def test_anchor_uses_max(self):
        """Test anchor uses max of avg and cycle max"""
        # avg < cycle max
        result = calculate_trigger_price(0.50, 0.52, -0.20)
        assert result['anchor_price'] == 0.52
        
        # avg > cycle max
        result = calculate_trigger_price(0.55, 0.50, -0.20)
        assert result['anchor_price'] == 0.55
    
    def test_different_stop_loss_percentages(self):
        """Test various stop loss percentages"""
        result = calculate_trigger_price(0.50, 0.50, -0.10)
        assert result['trigger_price'] == 0.45
        
        result = calculate_trigger_price(0.50, 0.50, -0.50)
        assert result['trigger_price'] == 0.25
        
        result = calculate_trigger_price(0.50, 0.50, -0.05)
        assert result['trigger_price'] == 0.475


class TestMarketHealthCheck:
    """Test market health detection"""
    
    def test_market_healthy_above_trigger(self):
        """Test market healthy when fair ref > trigger"""
        assert is_market_healthy(0.40, 0.364) is True
        assert is_market_healthy(0.50, 0.40) is True
    
    def test_market_unhealthy_below_trigger(self):
        """Test market unhealthy when fair ref <= trigger"""
        assert is_market_healthy(0.36, 0.364) is False
        assert is_market_healthy(0.30, 0.364) is False
    
    def test_boundary_condition(self):
        """Test exact boundary"""
        # fair_ref == trigger
        assert is_market_healthy(0.364, 0.364) is False


class TestProbePricing:
    """Test probe pricing logic"""
    
    def test_probe_size_calculation(self):
        """Test probe size is 25% of position"""
        assert get_probe_size(1000) == 250
        assert get_probe_size(400) == 100
        assert get_probe_size(100) == 25
    
    def test_probe_size_custom_ratio(self):
        """Test custom probe ratio"""
        assert get_probe_size(1000, 0.10) == 100
        assert get_probe_size(1000, 0.50) == 500
    
    def test_fak_price_calculation(self):
        """Test FAK price from order book"""
        order_book = {
            'asks': [
                {'price': 0.50, 'size': 100},
                {'price': 0.51, 'size': 100},
                {'price': 0.52, 'size': 100}
            ]
        }
        
        # Fill 50 units at 0.50
        price = calculate_fak_price(50, order_book)
        assert price == 0.50
        
        # Fill 150 units (100 at 0.50, 50 at 0.51)
        price = calculate_fak_price(150, order_book)
        assert abs(price - 0.5033) < 0.001
    
    def test_fak_price_insufficient_liquidity(self):
        """Test FAK with insufficient liquidity"""
        order_book = {
            'asks': [{'price': 0.50, 'size': 10}]
        }
        
        # Try to fill more than available - should calculate weighted avg
        price = calculate_fak_price(50, order_book)
        # With only 10 units available, weighted avg is 0.50
        assert price == 0.50


class TestStopLossTrigger:
    """Test stop loss trigger conditions"""
    
    def test_trigger_conditions_met(self):
        """Test when both conditions are met"""
        assert should_trigger_stop_loss(0.30, 0.32, 0.364) is True
        assert should_trigger_stop_loss(0.35, 0.34, 0.364) is True
    
    def test_trigger_probe_above(self):
        """Test when probe price is above trigger"""
        # fair_ref < trigger, but probe > trigger - no trigger
        assert should_trigger_stop_loss(0.36, 0.40, 0.364) is False
    
    def test_trigger_fair_ref_above(self):
        """Test when fair ref is above trigger"""
        # fair_ref > trigger - no trigger
        assert should_trigger_stop_loss(0.40, 0.35, 0.364) is False


class TestConfirmationEngine:
    """Test multi-tick confirmation"""
    
    def test_first_tick_armed(self):
        """Test first tick triggers ARMED state"""
        engine = ConfirmationEngine(required_ticks=2)
        
        is_confirmed, count = engine.check_condition(
            fair_ref=0.36,
            trigger_price=0.364,
            probe_price=0.35
        )
        
        assert is_confirmed is False
        assert count == 1
    
    def test_consecutive_ticks_confirm(self):
        """Test consecutive ticks lead to confirmation"""
        engine = ConfirmationEngine(required_ticks=2)
        
        # First tick
        is_confirmed, count = engine.check_condition(
            fair_ref=0.36, trigger_price=0.364, probe_price=0.35
        )
        assert is_confirmed is False
        
        # Second tick - should confirm
        is_confirmed, count = engine.check_condition(
            fair_ref=0.35, trigger_price=0.364, probe_price=0.34
        )
        assert is_confirmed is True
        assert count == 2
    
    def test_broken_confirmation(self):
        """Test broken confirmation resets"""
        engine = ConfirmationEngine(required_ticks=2)
        
        # First tick - conditions met
        engine.check_condition(0.36, 0.364, 0.35)
        
        # Second tick - conditions NOT met (recovery)
        engine.check_condition(0.40, 0.364, 0.38)
        
        # Third tick - conditions met again
        is_confirmed, count = engine.check_condition(0.36, 0.364, 0.35)
        
        # Should only count 1 (reset)
        assert is_confirmed is False
        assert count == 1
    
    def test_reset(self):
        """Test engine reset"""
        engine = ConfirmationEngine(required_ticks=2)
        
        engine.check_condition(0.36, 0.364, 0.35)
        engine.check_condition(0.35, 0.364, 0.34)
        
        engine.reset()
        
        assert len(engine.state_history) == 0
    
    def test_single_tick_confirmation(self):
        """Test with required_ticks=1"""
        engine = ConfirmationEngine(required_ticks=1)
        
        is_confirmed, count = engine.check_condition(
            fair_ref=0.36, trigger_price=0.364, probe_price=0.35
        )
        
        assert is_confirmed is True
        assert count == 1


class TestStopLossExecutor:
    """Test stop loss executor"""
    
    @pytest.mark.asyncio
    async def test_execute_mock(self):
        """Test execution with mock client"""
        executor = StopLossExecutor(client=None)
        
        result = await executor.execute_stop_loss(
            position_id="TEST_001",
            position_size=100,
            current_price=0.35,
            market_data={}
        )
        
        assert result['success'] is True
        assert result['orders_cancelled'] is True
        assert result['fak_submitted'] is True
        assert result['filled_price'] == 0.35
        assert len(executor.execution_log) == 1
    
    def test_get_execution_history(self):
        """Test execution history retrieval"""
        executor = StopLossExecutor()
        
        # No executions yet
        history = executor.get_execution_history()
        assert len(history) == 0


class TestAdaptiveStopLossSystem:
    """Test main ASL system"""
    
    @pytest.mark.asyncio
    async def test_add_position(self):
        """Test adding a position"""
        asl = AdaptiveStopLossSystem()
        
        state = asl.add_position(
            position_id="POS_001",
            avg_buy_price=0.50,
            cycle_max_avg_buy=0.52,
            stop_loss_pct=-0.30,
            position_size=1000
        )
        
        assert state.position_id == "POS_001"
        assert state.trigger_price == 0.364
        assert state.status == StopLossStatus.INACTIVE
    
    @pytest.mark.asyncio
    async def test_remove_position(self):
        """Test removing a position"""
        asl = AdaptiveStopLossSystem()
        
        asl.add_position("POS_001", 0.50, 0.52, -0.30, 1000)
        
        assert asl.remove_position("POS_001") is True
        assert asl.remove_position("POS_999") is False
    
    @pytest.mark.asyncio
    async def test_market_healthy_reset(self):
        """Test market recovery resets armed state"""
        asl = AdaptiveStopLossSystem()
        
        asl.add_position("POS_001", 0.50, 0.52, -0.30, 1000)
        
        # First tick - ARMED
        order_book = create_mock_order_book(0.36)
        result = await asl.check_tick(
            "POS_001", 0.36, order_book, 0.36
        )
        assert result['action'] == 'ARMED'
        
        # Second tick - market recovers
        order_book = create_mock_order_book(0.40)
        result = await asl.check_tick(
            "POS_001", 0.40, order_book, 0.40
        )
        assert result['action'] == 'RESET'
    
    @pytest.mark.asyncio
    async def test_successful_stop_loss(self):
        """Test successful stop loss execution"""
        asl = AdaptiveStopLossSystem()
        
        asl.add_position("POS_001", 0.50, 0.52, -0.30, 1000)
        
        # Tick 1: ARMED
        order_book = create_mock_order_book(0.36)
        result = await asl.check_tick(
            "POS_001", 0.36, order_book, 0.36
        )
        
        # Tick 2: CONFIRMED & EXECUTED
        order_book = create_mock_order_book(0.35)
        result = await asl.check_tick(
            "POS_001", 0.35, order_book, 0.35
        )
        
        assert result['action'] == 'EXECUTED'
        assert result['triggered'] is True
    
    @pytest.mark.asyncio
    async def test_position_not_found(self):
        """Test handling of non-existent position"""
        asl = AdaptiveStopLossSystem()
        
        result = await asl.check_tick(
            "NONEXISTENT", 0.30, {}, 0.30
        )
        
        assert 'error' in result
        assert result['error'] == 'Position not found'
    
    @pytest.mark.asyncio
    async def test_already_executed(self):
        """Test already executed position"""
        asl = AdaptiveStopLossSystem()
        
        asl.add_position("POS_001", 0.50, 0.52, -0.30, 1000)
        
        # First execute: Tick 1 ARMED, Tick 2 EXECUTED
        order_book = create_mock_order_book(0.35)
        
        # Tick 1: ARMED
        await asl.check_tick("POS_001", 0.36, order_book, 0.36)
        
        # Tick 2: EXECUTED
        result = await asl.check_tick("POS_001", 0.35, order_book, 0.35)
        assert result['triggered'] is True
        
        # Now check again - should say already executed
        result = await asl.check_tick("POS_001", 0.30, order_book, 0.30)
        assert result['action'] == 'ALREADY_EXECUTED'
    
    @pytest.mark.asyncio
    async def test_summary(self):
        """Test system summary"""
        asl = AdaptiveStopLossSystem()
        
        asl.add_position("POS_001", 0.50, 0.52, -0.30, 1000)
        asl.add_position("POS_002", 0.60, 0.60, -0.20, 500)
        
        asl.start_monitoring()
        
        summary = asl.get_summary()
        
        assert summary['total_positions'] == 2
        assert summary['monitoring'] is True


class TestUtilityFunctions:
    """Test utility functions"""
    
    def test_create_mock_order_book(self):
        """Test mock order book creation"""
        order_book = create_mock_order_book(mid_price=0.50, spread=0.01)
        
        assert 'bids' in order_book
        assert 'asks' in order_book
        assert len(order_book['asks']) == 5
        
        # First ask should be at mid + spread
        assert order_book['asks'][0]['price'] == 0.51
    
    def test_simulate_market_decline(self):
        """Test market decline simulation"""
        result = simulate_market_decline(0.50, 0.20)
        
        assert result['market_price'] == 0.40
        assert result['fair_ref'] == 0.396  # Slightly below


class TestEdgeCases:
    """Test edge cases"""
    
    def test_zero_position(self):
        """Test with zero position size"""
        result = calculate_trigger_price(0.50, 0.50, -0.30)
        assert result['trigger_price'] == 0.35
        
        probe_size = get_probe_size(0)
        assert probe_size == 0
    
    def test_large_stop_loss(self):
        """Test with 100% stop loss"""
        result = calculate_trigger_price(0.50, 0.50, -1.00)
        assert result['trigger_price'] == 0.0
    
    def test_negative_stop_loss(self):
        """Test with positive stop loss (theoretically)"""
        result = calculate_trigger_price(0.50, 0.50, 0.10)
        # Should still work - trigger above entry
        assert result['trigger_price'] == 0.55


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def sample_position():
    """Sample position for testing"""
    return {
        'avg_buy_price': 0.50,
        'cycle_max_avg_buy': 0.52,
        'stop_loss_pct': -0.30,
        'position_size': 1000
    }


@pytest.fixture
def sample_order_book():
    """Sample order book for testing"""
    return create_mock_order_book(mid_price=0.36)


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
