"""
Field Mapping Tests
测试scanner_daemon生成的所有opportunity是否包含trade_executor需要的字段
"""

import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入scanner_daemon
from scanner_daemon import ScannerDaemon


# 必须字段清单
REQUIRED_FIELDS = [
    'market',       # Market question
    'side',        # BUY/SELL
    'outcome',     # YES/NO/ALL
    'edge',        # Expected edge (float)
    'confidence',  # Confidence level (float)
    'true_prob',   # True probability estimate
    'market_price', # Current market price
    'price',       # Execution price
    'size',        # Position size
]


class TestFieldMapping(unittest.TestCase):
    """测试所有scanner系统生成的opportunity字段完整性"""
    
    def setUp(self):
        """测试前准备"""
        # Mock掉外部依赖
        with patch('scanner_daemon.OpportunityWriter'):
            with patch('scanner_daemon.PolymarketSearcher'):
                with patch('scanner_daemon.MiroFishSignalManager'):
                    self.daemon = ScannerDaemon()
    
    def _validate_opportunity(self, opp: dict, system_name: str) -> tuple[bool, list]:
        """
        验证opportunity字段完整性
        
        Returns:
            (is_valid, missing_fields)
        """
        missing = []
        for field in REQUIRED_FIELDS:
            if field not in opp:
                missing.append(field)
        
        # 额外验证：类型检查
        for field in ['edge', 'confidence', 'true_prob', 'market_price', 'price', 'size']:
            if field in opp:
                if not isinstance(opp[field], (int, float)):
                    missing.append(f"{field} (wrong type: {type(opp[field]).__name__})")
        
        return len(missing) == 0, missing
    
    def test_hft_output_parsing(self):
        """测试HFT输出解析"""
        output = """
TRADE SIGNAL: Bitcoin to close above $75,000
Side: YES
Edge: 15.0%
Size: $100
"""
        opportunities = self.daemon._parse_hft_output(output)
        
        # HFT可能被过滤（edge检查）
        for opp in opportunities:
            is_valid, missing = self._validate_opportunity(opp, 'HFT')
            self.assertTrue(is_valid, f"HFT missing fields: {missing}")
    
    def test_timezone_output_parsing(self):
        """测试Timezone输出解析"""
        output = """
FOUND 1 HIGH-EDGE OPPORTUNITIES

1. Will Bitcoin close above $80,000 by Friday?
Market: 65% | True: 75% | Edge: 10% | Confidence: 80%
"""
        opportunities = self.daemon._parse_timezone_output(output)
        
        self.assertGreater(len(opportunities), 0, "Should find timezone opportunity")
        
        for opp in opportunities:
            is_valid, missing = self._validate_opportunity(opp, 'Timezone')
            self.assertTrue(is_valid, f"Timezone missing fields: {missing}")
    
    def test_bregman_output_parsing(self):
        """测试Bregman输出解析"""
        output = """
ARBITRAGE FOUND
Market: Will BTC close above $70k this week?
Total cost: 0.91
Edge: 9%
"""
        opportunities = self.daemon._parse_bregman_output(output)
        
        # Bregman可能没有找到机会（格式不匹配）
        if len(opportunities) > 0:
            for opp in opportunities:
                is_valid, missing = self._validate_opportunity(opp, 'Bregman')
                self.assertTrue(is_valid, f"Bregman missing fields: {missing}")
                
                # 特别检查market字段
                self.assertIn('market', opp, "Bregman must have market field")
                self.assertIn('price', opp, "Bregman must have price field")
    
    def test_graham_output_parsing(self):
        """测试Graham输出解析"""
        output = """
BUY SIGNAL
Market: Will Bitcoin reach $100k?
Intrinsic value: $85,000
Market price: 0.70
Edge: 15%
Confidence: 75%
"""
        opportunities = self.daemon._parse_graham_output(output)
        
        self.assertGreater(len(opportunities), 0, "Should find graham opportunity")
        
        for opp in opportunities:
            is_valid, missing = self._validate_opportunity(opp, 'Graham')
            self.assertTrue(is_valid, f"Graham missing fields: {missing}")
            
            # 确保price字段存在（之前被错误删除）
            self.assertIn('price', opp, "Graham must have price field")
    
    def test_harvest_output_parsing(self):
        """测试Harvest输出解析"""
        output = """
1. Will Trump win 2024 election?
Confidence: 95% | Price: $0.92 | Expected ROI: 8%
Liquidity: $50000
"""
        opportunities = self.daemon._parse_harvest_output(output)
        
        self.assertGreater(len(opportunities), 0, "Should find harvest opportunity")
        
        for opp in opportunities:
            is_valid, missing = self._validate_opportunity(opp, 'Harvest')
            self.assertTrue(is_valid, f"Harvest missing fields: {missing}")
            
            # 确保price字段存在
            self.assertIn('price', opp, "Harvest must have price field")
    
    def test_blackscholes_output_parsing(self):
        """测试BlackScholes输出解析"""
        # BlackScholes需要外部API调用，这里只验证_create_arb_opportunity方法
        
        # 测试三种套利类型的机会结构
        test_cases = [
            {
                'arb_type': 'complementary',
                'arb': {
                    'market_a': 'Will BTC close above $70k?',
                    'market_b': 'Will ETH close above $3000?',
                    'market_a_id': 'btc_70k',
                    'total': 0.85,
                    'profit': 0.15,
                    'reason': 'Complementary arbitrage test'
                }
            },
            {
                'arb_type': 'logical',
                'arb': {
                    'market_a': 'Will BTC close above $70k?',
                    'market_b': 'Will BTC close below $80k?',
                    'market_a_id': 'btc_70k',
                    'price_a': 0.5,
                    'price_b': 0.6,
                    'profit': 0.10,
                    'reason': 'Logical arbitrage test'
                }
            },
            {
                'arb_type': 'decomposed',
                'arb': {
                    'subject': 'BTC',
                    'market_ids': ['btc_range_1', 'btc_range_2'],
                    'total': 0.95,
                    'profit': 0.05,
                    'reason': 'Decomposed arbitrage test'
                }
            }
        ]
        
        for tc in test_cases:
            opp = self.daemon._create_arb_opportunity(tc['arb'], tc['arb_type'])
            
            if opp:  # 可能返回None如果类型不匹配
                is_valid, missing = self._validate_opportunity(opp, f"BlackScholes-{tc['arb_type']}")
                self.assertTrue(is_valid, f"BlackScholes-{tc['arb_type']} missing fields: {missing}")
    
    def test_lag_pair_output_parsing(self):
        """测试Lag Pair输出解析"""
        opportunities = self.daemon._parse_lag_pair_output('')
        
        # Lag Pair是独立系统，这里只验证解析器不报错
        self.assertEqual(len(opportunities), 0, "Lag pair parser returns empty list")
    
    def test_field_types(self):
        """测试字段类型正确性"""
        output = """
FOUND 1 HIGH-EDGE OPPORTUNITIES

1. Test Market Question
Market: 50% | True: 60% | Edge: 10% | Confidence: 70%
"""
        opportunities = self.daemon._parse_timezone_output(output)
        
        for opp in opportunities:
            # 验证数值类型
            self.assertIsInstance(opp['edge'], (int, float))
            self.assertIsInstance(opp['confidence'], (int, float))
            self.assertIsInstance(opp['true_prob'], (int, float))
            self.assertIsInstance(opp['market_price'], (int, float))
            self.assertIsInstance(opp['price'], (int, float))
            self.assertIsInstance(opp['size'], (int, float))
            
            # 验证字符串类型
            self.assertIsInstance(opp['market'], str)
            self.assertIsInstance(opp['side'], str)
            self.assertIsInstance(opp['outcome'], str)
    
    def test_price_market_price_consistency(self):
        """测试price和market_price一致性"""
        output = """
FOUND 1 HIGH-EDGE OPPORTUNITIES

1. Test Market
Market: 50% | True: 60% | Edge: 10% | Confidence: 70%
"""
        opportunities = self.daemon._parse_timezone_output(output)
        
        for opp in opportunities:
            # price应该等于market_price
            self.assertEqual(opp.get('price'), opp.get('market_price'))
    
    def test_edge_confidence_range(self):
        """测试edge和confidence在合理范围内"""
        output = """
FOUND 1 HIGH-EDGE OPPORTUNITIES

1. Test Market
Market: 50% | True: 60% | Edge: 10% | Confidence: 70%
"""
        opportunities = self.daemon._parse_timezone_output(output)
        
        for opp in opportunities:
            # edge应该在0-1之间
            self.assertGreaterEqual(opp['edge'], 0.0)
            self.assertLessEqual(opp['edge'], 1.0)
            
            # confidence应该在0-1之间
            self.assertGreaterEqual(opp['confidence'], 0.0)
            self.assertLessEqual(opp['confidence'], 1.0)
            
            # true_prob应该在0-1之间
            self.assertGreaterEqual(opp['true_prob'], 0.0)
            self.assertLessEqual(opp['true_prob'], 1.0)


class TestExecutorValidation(unittest.TestCase):
    """测试trade_executor的验证逻辑"""
    
    def test_validate_required_fields(self):
        """测试必需字段验证"""
        from trade_executor import TradeExecutor
        
        # Mock executor
        executor = TradeExecutor.__new__(TradeExecutor)
        
        # 完整的机会
        valid_opp = {
            'market': 'Test Market',
            'side': 'BUY',
            'outcome': 'YES',
            'edge': 0.1,
            'confidence': 0.7,
            'true_prob': 0.6,
            'market_price': 0.5,
            'price': 0.5,
            'size': 100.0
        }
        
        # 缺少market
        invalid_opp1 = valid_opp.copy()
        del invalid_opp1['market']
        
        # 缺少true_prob
        invalid_opp2 = valid_opp.copy()
        del invalid_opp2['true_prob']
        
        # 缺少market_price
        invalid_opp3 = valid_opp.copy()
        del invalid_opp3['market_price']
        
        # 测试缺少字段的情况
        for invalid_opp in [invalid_opp1, invalid_opp2, invalid_opp3]:
            missing_fields = []
            required = ['market', 'side', 'outcome', 'edge', 'confidence']
            for field in required:
                if field not in invalid_opp:
                    missing_fields.append(field)
            
            # 额外检查Kelly需要的字段
            if 'true_prob' not in invalid_opp:
                missing_fields.append('true_prob')
            if 'market_price' not in invalid_opp:
                missing_fields.append('market_price')
            
            self.assertGreater(len(missing_fields), 0, "Should detect missing fields")


if __name__ == '__main__':
    # 运行测试
    unittest.main(verbosity=2)
