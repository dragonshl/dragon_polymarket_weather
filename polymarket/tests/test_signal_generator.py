"""
信号生成器单元测试
"""

import unittest
from datetime import datetime, timedelta
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from signal_generator import SignalGenerator, TradeSignal
from disagreement_detector import Disagreement, Market


class TestSignalGenerator(unittest.TestCase):
    """测试SignalGenerator类"""
    
    def setUp(self):
        """测试前准备"""
        self.generator = SignalGenerator(capital=1000.0, max_risk=0.3)
        
        # 创建测试矛盾
        self.test_markets = [
            Market(
                id="m1",
                question="Test Q1",
                description="D",
                tags=["test"],
                outcomes=[{"name": "Yes", "price": 0.55}],
                end_date=datetime.now() + timedelta(days=30),
                volume=100000,
                liquidity=50000
            ),
            Market(
                id="m2",
                question="Test Q2",
                description="D",
                tags=["test"],
                outcomes=[{"name": "Yes", "price": 0.50}],
                end_date=datetime.now() + timedelta(days=30),
                volume=90000,
                liquidity=45000
            ),
        ]
        
        self.test_disagreement = Disagreement(
            cluster_id="test_cluster",
            markets=self.test_markets,
            mutex_outcomes=[
                ("m1", "Yes", 0.55),
                ("m2", "Yes", 0.50)
            ],
            total_probability=1.05,
            profit_potential=0.05,
            confidence=0.8,
            reasoning="Test disagreement"
        )
    
    def test_initialization(self):
        """测试初始化"""
        self.assertEqual(self.generator.capital, 1000.0)
        self.assertEqual(self.generator.max_risk, 0.3)
        self.assertEqual(len(self.generator.generated_signals), 0)
    
    def test_generate_signals(self):
        """测试信号生成"""
        signals = self.generator.generate_signals([self.test_disagreement])
        
        self.assertIsInstance(signals, list)
        
        if signals:
            signal = signals[0]
            self.assertIsInstance(signal, TradeSignal)
            self.assertTrue(hasattr(signal, 'expected_profit'))
            self.assertTrue(hasattr(signal, 'risk_score'))
    
    def test_calculate_risk(self):
        """测试风险计算"""
        trades = [
            {"market_id": "m1", "cost": 500},
            {"market_id": "m2", "cost": 500}
        ]
        
        risk = self.generator._calculate_risk(self.test_disagreement, trades)
        
        self.assertIsInstance(risk, float)
        self.assertGreaterEqual(risk, 0.0)
        self.assertLessEqual(risk, 1.0)
    
    def test_determine_urgency(self):
        """测试紧迫性判断"""
        urgency = self.generator._determine_urgency(self.test_disagreement)
        
        self.assertIn(urgency, ["HIGH", "MEDIUM", "LOW"])
    
    def test_filter_signals(self):
        """测试信号过滤"""
        signals = self.generator.generate_signals([self.test_disagreement])
        
        filtered = self.generator.filter_signals(
            min_profit=10,
            max_risk=0.5
        )
        
        self.assertIsInstance(filtered, list)
        
        for signal in filtered:
            self.assertGreaterEqual(signal.expected_profit, 10)
            self.assertLessEqual(signal.risk_score, 0.5)
    
    def test_format_signal_for_execution(self):
        """测试信号格式化"""
        signals = self.generator.generate_signals([self.test_disagreement])
        
        if signals:
            order = self.generator.format_signal_for_execution(signals[0])
            
            self.assertIn("signal_id", order)
            self.assertIn("orders", order)
            self.assertIn("expected_profit", order)
            self.assertIsInstance(order["orders"], list)


class TestEdgeCasesSignalGenerator(unittest.TestCase):
    """测试边缘情况"""
    
    def test_empty_disagreements(self):
        """测试空矛盾列表"""
        generator = SignalGenerator()
        signals = generator.generate_signals([])
        
        self.assertEqual(len(signals), 0)
    
    def test_high_risk_filtered(self):
        """测试高风险信号被过滤"""
        generator = SignalGenerator(max_risk=0.1)
        
        # 创建一个高风险矛盾（低流动性）
        markets = [
            Market(
                id="m1", question="Q", description="D", tags=[],
                outcomes=[{"name": "Yes", "price": 0.55}],
                end_date=datetime.now() + timedelta(days=1),
                volume=100,  # 低交易量
                liquidity=10  # 低流动性
            ),
        ]
        
        disagreement = Disagreement(
            cluster_id="high_risk",
            markets=markets,
            mutex_outcomes=[("m1", "Yes", 0.55)],
            total_probability=1.1,
            profit_potential=0.1,
            confidence=0.5,  # 低置信度
            reasoning="Test"
        )
        
        signals = generator.generate_signals([disagreement])
        
        # 高风险应该被过滤
        self.assertEqual(len(signals), 0)
    
    def test_zero_profit_filtered(self):
        """测试零利润信号被过滤"""
        generator = SignalGenerator()
        
        markets = [
            Market(
                id="m1", question="Q", description="D", tags=[],
                outcomes=[{"name": "Yes", "price": 0.50}],
                end_date=datetime.now() + timedelta(days=30),
                volume=100000, liquidity=50000
            ),
        ]
        
        disagreement = Disagreement(
            cluster_id="zero_profit",
            markets=markets,
            mutex_outcomes=[("m1", "Yes", 0.50), ("m1", "No", 0.50)],
            total_probability=1.0,  # 刚好100%，无利可图
            profit_potential=0.0,
            confidence=0.9,
            reasoning="Test"
        )
        
        signals = generator.generate_signals([disagreement])
        
        # 无利润应该被过滤
        self.assertEqual(len(signals), 0)


if __name__ == "__main__":
    unittest.main()
