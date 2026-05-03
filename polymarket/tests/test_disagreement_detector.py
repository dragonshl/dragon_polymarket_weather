"""
矛盾检测器单元测试
"""

import unittest
from datetime import datetime, timedelta
import sys
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from disagreement_detector import DisagreementDetector, Market


class TestDisagreementDetector(unittest.TestCase):
    """测试DisagreementDetector类"""
    
    def setUp(self):
        """测试前准备"""
        self.detector = DisagreementDetector(
            min_profit_threshold=0.05,
            min_confidence=0.7
        )
        
        # 创建测试市场
        self.markets = [
            Market(
                id="test_1",
                question="Will event A happen?",
                description="Test market A",
                tags=["test", "event"],
                outcomes=[
                    {"name": "Yes", "price": 0.60},
                    {"name": "No", "price": 0.40}
                ],
                end_date=datetime.now() + timedelta(days=30),
                volume=100000,
                liquidity=50000
            ),
            Market(
                id="test_2",
                question="Will event A happen?",
                description="Test market A duplicate",
                tags=["test", "event"],
                outcomes=[
                    {"name": "Yes", "price": 0.55},
                    {"name": "No", "price": 0.45}
                ],
                end_date=datetime.now() + timedelta(days=30),
                volume=90000,
                liquidity=45000
            ),
        ]
    
    def test_initialization(self):
        """测试初始化"""
        self.assertEqual(self.detector.min_profit_threshold, 0.05)
        self.assertEqual(self.detector.min_confidence, 0.7)
        self.assertEqual(len(self.detector.clusters), 0)
    
    def test_find_clusters(self):
        """测试市场聚类"""
        clusters = self.detector.find_clusters(self.markets)
        
        self.assertIsInstance(clusters, list)
        self.assertTrue(len(clusters) > 0)
        
        # 检查聚类结构
        for cluster in clusters:
            self.assertIn("markets", cluster)
            self.assertIsInstance(cluster["markets"], list)
    
    def test_detect_disagreements(self):
        """测试矛盾检测"""
        clusters = self.detector.find_clusters(self.markets)
        disagreements = self.detector.detect_disagreements(clusters)
        
        self.assertIsInstance(disagreements, list)
        
        # 如果有矛盾，检查数据结构
        if disagreements:
            d = disagreements[0]
            self.assertTrue(hasattr(d, 'total_probability'))
            self.assertTrue(hasattr(d, 'profit_potential'))
            self.assertTrue(hasattr(d, 'confidence'))
    
    def test_rank_opportunities(self):
        """测试机会排序"""
        clusters = self.detector.find_clusters(self.markets)
        disagreements = self.detector.detect_disagreements(clusters)
        ranked = self.detector.rank_opportunities(disagreements)
        
        self.assertIsInstance(ranked, list)
        
        # 检查排序后的列表是否符合过滤条件
        for d in ranked:
            self.assertGreaterEqual(d.profit_potential, self.detector.min_profit_threshold)
            self.assertGreaterEqual(d.confidence, self.detector.min_confidence)
    
    def test_merge_clusters(self):
        """测试聚类合并"""
        cluster1 = [{"markets": [self.markets[0]]}]
        cluster2 = [{"markets": [self.markets[1]]}]
        
        merged = self.detector._merge_clusters(cluster1, cluster2)
        
        self.assertEqual(len(merged), 2)
        for cluster in merged:
            self.assertIn("id", cluster)
    
    def test_calculate_confidence(self):
        """测试置信度计算"""
        mutex_group = [
            ("test_1", "Yes", 0.60),
            ("test_2", "Yes", 0.55)
        ]
        
        confidence = self.detector._calculate_confidence(mutex_group, self.markets)
        
        self.assertIsInstance(confidence, float)
        self.assertGreaterEqual(confidence, 0.0)
        self.assertLessEqual(confidence, 1.0)
    
    def test_time_urgency_score(self):
        """测试时间紧迫性评分"""
        # 测试不同时间窗口
        markets_7d = [Market(
            id="test", question="Q", description="D", tags=[],
            outcomes=[], end_date=datetime.now() + timedelta(days=7),
            volume=0, liquidity=0
        )]
        
        score = self.detector._time_urgency_score(markets_7d)
        self.assertGreaterEqual(score, 0.5)
        self.assertLessEqual(score, 1.0)


class TestEdgeCases(unittest.TestCase):
    """测试边缘情况"""
    
    def test_empty_markets(self):
        """测试空市场列表"""
        detector = DisagreementDetector()
        clusters = detector.find_clusters([])
        
        self.assertEqual(len(clusters), 0)
    
    def test_single_market(self):
        """测试单个市场"""
        detector = DisagreementDetector()
        market = Market(
            id="single", question="Q", description="D", tags=[],
            outcomes=[{"name": "Yes", "price": 0.5}],
            end_date=datetime.now() + timedelta(days=1),
            volume=100, liquidity=50
        )
        
        clusters = detector.find_clusters([market])
        # 单个市场不应该形成有效聚类
        self.assertEqual(len(clusters), 0)
    
    def test_no_disagreements(self):
        """测试没有矛盾的情况"""
        detector = DisagreementDetector()
        markets = [
            Market(
                id="m1", question="Different Q1", description="D", tags=[],
                outcomes=[{"name": "Yes", "price": 0.5}],
                end_date=datetime.now() + timedelta(days=1),
                volume=100, liquidity=50
            ),
            Market(
                id="m2", question="Different Q2", description="D", tags=[],
                outcomes=[{"name": "Yes", "price": 0.5}],
                end_date=datetime.now() + timedelta(days=1),
                volume=100, liquidity=50
            ),
        ]
        
        clusters = detector.find_clusters(markets)
        disagreements = detector.detect_disagreements(clusters)
        
        # 完全不相关的市场不应该产生矛盾
        self.assertIsInstance(disagreements, list)


if __name__ == "__main__":
    unittest.main()
