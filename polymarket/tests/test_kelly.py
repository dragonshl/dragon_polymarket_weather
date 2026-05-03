import unittest
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from kelly_calculator import KellyCalculator
from bankroll_manager import BankrollManager

class TestKellyCalculator(unittest.TestCase):
    def setUp(self):
        self.kelly = KellyCalculator(k=0.25)
    
    def test_large_edge(self):
        """测试大Edge案例（文章示例）"""
        size, f_star, edge = self.kelly.calculate_size(
            p=0.58, m=0.42, bankroll=1000
        )
        
        self.assertAlmostEqual(edge, 0.16, places=2)
        self.assertAlmostEqual(f_star, 0.276, places=2)
        self.assertGreater(size, 0)
    
    def test_small_edge(self):
        """测试小Edge案例"""
        size, f_star, edge = self.kelly.calculate_size(
            p=0.55, m=0.51, bankroll=1000
        )
        
        self.assertAlmostEqual(edge, 0.04, places=2)
        # Edge < 5% threshold, should be skipped
        self.assertEqual(size, 0)
    
    def test_below_threshold(self):
        """测试低于阈值（应跳过）"""
        size, f_star, edge = self.kelly.calculate_size(
            p=0.52, m=0.51, bankroll=1000, min_edge=0.05
        )
        
        self.assertEqual(size, 0)  # 应该跳过
        self.assertLess(edge, 0.05)
    
    def test_graham_typical(self):
        """测试Graham典型案例"""
        size, f_star, edge = self.kelly.calculate_size(
            p=0.75, m=0.45, bankroll=300
        )
        
        self.assertAlmostEqual(edge, 0.30, places=2)
        self.assertGreater(size, 17.50)  # 应该大于旧系统固定值

class TestBankrollManager(unittest.TestCase):
    def setUp(self):
        self.mgr = BankrollManager(state_file="data/test_bankroll.json")
    
    def test_update_after_win(self):
        """测试盈利后更新"""
        initial = self.mgr.get_current_bankroll('graham')
        self.mgr.update_after_trade('graham', pnl=50, won=True)
        updated = self.mgr.get_current_bankroll('graham')
        
        self.assertEqual(updated, initial + 50)
    
    def test_update_after_loss(self):
        """测试亏损后更新"""
        initial = self.mgr.get_current_bankroll('graham')
        self.mgr.update_after_trade('graham', pnl=-20, won=False)
        updated = self.mgr.get_current_bankroll('graham')
        
        self.assertEqual(updated, initial - 20)
    
    def test_daily_stop_loss(self):
        """测试日止损"""
        # 模拟大亏损
        initial = self.mgr.get_current_bankroll('graham')
        self.mgr.update_after_trade('graham', pnl=-50, won=False)
        
        triggered, reason = self.mgr.check_daily_stop_loss('graham', threshold=0.10)
        
        # 判断是否超过阈值
        loss_pct = 50 / initial
        if loss_pct >= 0.10:
            self.assertTrue(triggered)
        else:
            self.assertFalse(triggered)
    
    def test_consecutive_losses(self):
        """测试连续亏损"""
        # 连续3次亏损
        self.mgr.update_after_trade('graham', pnl=-10, won=False)
        self.mgr.update_after_trade('graham', pnl=-10, won=False)
        self.mgr.update_after_trade('graham', pnl=-10, won=False)
        
        should_pause, reason = self.mgr.check_consecutive_losses('graham')
        self.assertTrue(should_pause)
    
    def test_reset_consecutive_on_win(self):
        """测试盈利后重置连败计数"""
        # 2次亏损
        self.mgr.update_after_trade('graham', pnl=-10, won=False)
        self.mgr.update_after_trade('graham', pnl=-10, won=False)
        
        # 1次盈利
        self.mgr.update_after_trade('graham', pnl=20, won=True)
        
        stats = self.mgr.get_stats('graham')
        self.assertEqual(stats['consecutive_losses'], 0)

if __name__ == '__main__':
    unittest.main()
