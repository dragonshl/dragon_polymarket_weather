"""
MiroFish Integration Tests
测试市场匹配、概率调整、信号管理
"""

import os
import sys
import json
import unittest
from datetime import datetime, timezone, timedelta

# Add parent directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from polymarket_search import PolymarketSearcher
from mirofish_signal_manager import MiroFishSignalManager


class TestPolymarketSearch(unittest.TestCase):
    """测试Polymarket搜索工具"""
    
    def setUp(self):
        self.searcher = PolymarketSearcher()
    
    def test_extract_price_from_question(self):
        """测试从问题文本提取价格"""
        test_cases = [
            ("Will Bitcoin close above $75,000 this week?", 75000),
            ("BTC > $80k by March?", 80000),
            ("Bitcoin price above $100,000?", 100000),
            ("Will BTC reach $50000 before April?", 50000),
            ("Ethereum > $3k?", 3000),
            ("No price here", None)
        ]
        
        for question, expected in test_cases:
            result = self.searcher._extract_price_from_question(question)
            self.assertEqual(result, expected, f"Failed for: {question}")
    
    def test_adjust_probability_threshold_higher(self):
        """测试概率调整 - 市场阈值更高"""
        # MiroFish预测BTC > $79k (100%置信)
        # 市场问BTC > $85k（更高阈值）
        # 预期: 概率降低
        
        mirofish_prob = 1.0
        mirofish_target = 79116
        market_strike = 85000
        
        adjusted = self.searcher.adjust_probability_for_price_gap(
            mirofish_prob, mirofish_target, market_strike
        )
        
        # gap = (85000 - 79116) / 79116 = 7.4%
        # adjusted = 1.0 * (1 - 0.074 * 0.5) = 0.963
        expected = 0.963
        
        self.assertAlmostEqual(adjusted, expected, places=2)
        self.assertLess(adjusted, mirofish_prob, "Probability should decrease")
    
    def test_adjust_probability_threshold_lower(self):
        """测试概率调整 - 市场阈值更低"""
        # MiroFish预测BTC > $79k (100%置信)
        # 市场问BTC > $75k（更低阈值）
        # 预期: 概率提升（但限制到99%）
        
        mirofish_prob = 1.0
        mirofish_target = 79116
        market_strike = 75000
        
        adjusted = self.searcher.adjust_probability_for_price_gap(
            mirofish_prob, mirofish_target, market_strike
        )
        
        # gap = (79116 - 75000) / 79116 = 5.2%
        # adjusted = min(0.99, 1.0 * (1 + 0.052 * 0.3)) = 0.99
        expected = 0.99
        
        self.assertEqual(adjusted, expected)
    
    def test_adjust_probability_exact_match(self):
        """测试概率调整 - 精确匹配"""
        # MiroFish预测BTC > $79k
        # 市场问BTC > $79k（精确匹配）
        # 预期: 几乎无调整
        
        mirofish_prob = 1.0
        mirofish_target = 79116
        market_strike = 79000
        
        adjusted = self.searcher.adjust_probability_for_price_gap(
            mirofish_prob, mirofish_target, market_strike
        )
        
        # 差距很小，调整后应该接近99%
        self.assertGreater(adjusted, 0.98)
    
    def test_probability_bounds(self):
        """测试概率边界限制"""
        # 测试极端情况
        
        # 极低概率
        adjusted = self.searcher.adjust_probability_for_price_gap(
            mirofish_prob=0.10,
            mirofish_target=50000,
            market_strike=100000
        )
        self.assertGreaterEqual(adjusted, 0.01, "Should not go below 1%")
        
        # 极高概率
        adjusted = self.searcher.adjust_probability_for_price_gap(
            mirofish_prob=1.0,
            mirofish_target=100000,
            market_strike=50000
        )
        self.assertLessEqual(adjusted, 0.99, "Should not exceed 99%")


class TestMiroFishSignalManager(unittest.TestCase):
    """测试MiroFish信号管理器"""
    
    def setUp(self):
        # 使用测试文件
        self.test_signal_file = 'data/test_mirofish_signals.json'
        self.manager = MiroFishSignalManager(signal_file=self.test_signal_file)
        
        # 清理测试文件
        if os.path.exists(self.test_signal_file):
            os.remove(self.test_signal_file)
    
    def tearDown(self):
        # 清理测试文件
        if os.path.exists(self.test_signal_file):
            os.remove(self.test_signal_file)
    
    def test_save_and_get_signal(self):
        """测试保存和读取信号"""
        prediction = {
            'coin': 'Bitcoin',
            'symbol': 'BTC-USD',
            'target_price': 79116,
            'current_price': 71923,
            'direction': 'BULLISH',
            'confidence': 100.0,
            'technical_snapshot': {
                'rsi': 57.07,
                'ema_trend': 'BULLISH'
            }
        }
        
        # 保存
        success = self.manager.save_signal(prediction)
        self.assertTrue(success)
        
        # 读取
        signal = self.manager.get_signal('BTC')
        self.assertIsNotNone(signal)
        self.assertEqual(signal['direction'], 'BULLISH')
        self.assertLessEqual(signal['confidence'], 0.90, "Should be calibrated to max 90%")
        self.assertEqual(signal['target_price'], 79116)
    
    def test_signal_expiry(self):
        """测试信号过期"""
        prediction = {
            'coin': 'Ethereum',
            'symbol': 'ETH-USD',
            'target_price': 2500,
            'current_price': 2100,
            'direction': 'BULLISH',
            'confidence': 85.0
        }
        
        # 保存信号
        self.manager.save_signal(prediction)
        
        # 手动修改过期时间为过去
        signals = self.manager._load_signals()
        signals['ETH']['valid_until'] = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        self.manager._save_signals(signals)
        
        # 尝试读取 - 应该返回None（已过期）
        signal = self.manager.get_signal('ETH')
        self.assertIsNone(signal, "Expired signal should return None")
    
    def test_enhance_opportunity_bullish_match(self):
        """测试信号增强 - 方向一致（看涨）"""
        # 保存信号
        prediction = {
            'coin': 'Bitcoin',
            'symbol': 'BTC-USD',
            'direction': 'BULLISH',
            'confidence': 85.0,
            'target_price': 80000,
            'current_price': 72000
        }
        self.manager.save_signal(prediction)
        
        # 创建机会（YES + BTC市场）
        opportunity = {
            'market': 'Will Bitcoin close above $75,000?',
            'outcome': 'YES',
            'confidence': 0.70,
            'reason': 'Graham intrinsic value'
        }
        
        # 增强
        enhanced = self.manager.enhance_opportunity(opportunity)
        
        # 检查: confidence应该提升
        self.assertGreater(enhanced['confidence'], 0.70, "Confidence should increase")
        self.assertIn('MiroFish bullish', enhanced['reason'])
    
    def test_enhance_opportunity_bearish_conflict(self):
        """测试信号增强 - 方向冲突（看跌信号 vs YES仓位）"""
        # 保存看跌信号
        prediction = {
            'coin': 'Bitcoin',
            'symbol': 'BTC-USD',
            'direction': 'BEARISH',
            'confidence': 80.0,
            'target_price': 65000,
            'current_price': 72000
        }
        self.manager.save_signal(prediction)
        
        # 创建看涨机会（YES + BTC市场）
        opportunity = {
            'market': 'Will Bitcoin close above $75,000?',
            'outcome': 'YES',
            'confidence': 0.70,
            'reason': 'Graham intrinsic value'
        }
        
        # 增强
        enhanced = self.manager.enhance_opportunity(opportunity)
        
        # 检查: confidence应该降低
        self.assertLess(enhanced['confidence'], 0.70, "Confidence should decrease")
        self.assertIn('warning', enhanced['reason'])
    
    def test_enhance_opportunity_no_crypto(self):
        """测试信号增强 - 非加密货币市场"""
        # 保存BTC信号
        prediction = {
            'coin': 'Bitcoin',
            'symbol': 'BTC-USD',
            'direction': 'BULLISH',
            'confidence': 85.0,
            'target_price': 80000,
            'current_price': 72000
        }
        self.manager.save_signal(prediction)
        
        # 创建非加密市场机会
        opportunity = {
            'market': 'Will Trump win 2024 election?',
            'outcome': 'YES',
            'confidence': 0.60,
            'reason': 'Poll analysis'
        }
        
        # 增强
        enhanced = self.manager.enhance_opportunity(opportunity)
        
        # 检查: 不应该被修改（非加密市场）
        self.assertEqual(enhanced['confidence'], 0.60)
        self.assertNotIn('MiroFish', enhanced.get('reason', ''))
    
    def test_cleanup_expired(self):
        """测试清理过期信号"""
        # 保存两个信号
        for coin in ['BTC', 'ETH']:
            prediction = {
                'coin': coin,
                'symbol': f'{coin}-USD',
                'direction': 'BULLISH',
                'confidence': 80.0,
                'target_price': 75000,
                'current_price': 70000
            }
            self.manager.save_signal(prediction)
        
        # 手动设置BTC信号为过期
        signals = self.manager._load_signals()
        signals['BTC']['valid_until'] = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        self.manager._save_signals(signals)
        
        # 清理
        removed = self.manager.cleanup_expired()
        
        # 检查
        self.assertEqual(removed, 1, "Should remove 1 expired signal")
        
        # BTC应该被删除，ETH还在
        self.assertIsNone(self.manager.get_signal('BTC'))
        self.assertIsNotNone(self.manager.get_signal('ETH'))


class TestIntegrationFlow(unittest.TestCase):
    """集成测试 - 完整流程"""
    
    def setUp(self):
        self.searcher = PolymarketSearcher()
        self.signal_manager = MiroFishSignalManager(signal_file='data/test_integration_signals.json')
        
        # 清理
        if os.path.exists('data/test_integration_signals.json'):
            os.remove('data/test_integration_signals.json')
    
    def tearDown(self):
        if os.path.exists('data/test_integration_signals.json'):
            os.remove('data/test_integration_signals.json')
    
    def test_full_workflow_with_match(self):
        """测试完整工作流 - 找到匹配市场"""
        # 模拟MiroFish预测
        prediction = {
            'symbol': 'BTC-USD',
            'target_price': 79116,
            'confidence': 100.0,
            'direction': 'BULLISH',
            'current_price': 71923
        }
        
        # 搜索市场（注意: 需要真实市场数据或mock）
        # 这里只测试逻辑，实际搜索可能返回空
        match_type, market = self.searcher.find_matching_polymarket(prediction)
        
        # 如果找到匹配
        if match_type in ['exact', 'range']:
            print(f"✅ Found {match_type} match: {market.get('question', 'unknown')}")
            
            # 提取价格
            market_strike = self.searcher._extract_price_from_question(market['question'])
            self.assertIsNotNone(market_strike)
            
            # 调整概率
            adjusted_prob = self.searcher.adjust_probability_for_price_gap(
                mirofish_prob=min(0.85, prediction['confidence'] / 100.0),
                mirofish_target=prediction['target_price'],
                market_strike=market_strike
            )
            
            self.assertGreater(adjusted_prob, 0.0)
            self.assertLess(adjusted_prob, 1.0)
            
            print(f"   Adjusted probability: {adjusted_prob:.2%}")
        
        else:
            # 没找到匹配 → 保存信号
            print("No match found, saving signal...")
            
            success = self.signal_manager.save_signal(prediction)
            self.assertTrue(success)
            
            # 验证信号
            signal = self.signal_manager.get_signal('BTC')
            self.assertIsNotNone(signal)
            self.assertEqual(signal['direction'], 'BULLISH')


def run_tests():
    """运行所有测试"""
    print("="*70)
    print("MiroFish Integration Tests")
    print("="*70)
    
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestPolymarketSearch))
    suite.addTests(loader.loadTestsFromTestCase(TestMiroFishSignalManager))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegrationFlow))
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 总结
    print("\n" + "="*70)
    print("Test Summary")
    print("="*70)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {(result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100:.1f}%")
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
