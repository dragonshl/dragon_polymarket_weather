"""
集成测试：Kelly系统完整流程
"""
import unittest
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from kelly_calculator import KellyCalculator
from bankroll_manager import BankrollManager

class TestKellyIntegration(unittest.TestCase):
    """测试Kelly系统完整流程"""
    
    def setUp(self):
        """设置测试环境"""
        self.kelly = KellyCalculator(k=0.25)
        self.bankroll_mgr = BankrollManager(state_file="data/test_integration.json")
    
    def test_graham_opportunity_flow(self):
        """测试Graham机会完整流程"""
        
        # 模拟Graham扫描器输出
        opportunity = {
            'market': 'Will Bitcoin reach $100k by 2025?',
            'market_price': 0.45,  # 市场价45%
            'true_prob': 0.75,     # 真实估计75%
            'edge': 0.30,          # Edge 30%
            'confidence': 0.70,
            '_meta': {
                'system': 'graham',
                'status': 'pending'
            }
        }
        
        # 1. 获取当前资金
        bankroll = self.bankroll_mgr.get_current_bankroll('graham')
        self.assertEqual(bankroll, 300)  # 初始资金$300
        
        # 2. Kelly计算仓位
        size, f_star, edge = self.kelly.calculate_size(
            p=opportunity['true_prob'],
            m=opportunity['market_price'],
            bankroll=bankroll,
            min_edge=0.05
        )
        
        # 验证计算结果
        self.assertAlmostEqual(edge, 0.30, places=2)
        self.assertGreater(size, 0)
        self.assertLess(size, bankroll)  # 仓位小于总资金
        
        print(f"\nGraham Flow Test:")
        print(f"  Bankroll: ${bankroll:.2f}")
        print(f"  Kelly Size: ${size:.2f}")
        print(f"  Edge: {edge:.1%}")
        print(f"  Full Kelly: {f_star:.1%}")
        
        # 3. 模拟交易执行并盈利
        estimated_pnl = size * edge
        self.bankroll_mgr.update_after_trade('graham', pnl=estimated_pnl, won=True)
        
        # 4. 验证资金更新
        new_bankroll = self.bankroll_mgr.get_current_bankroll('graham')
        self.assertEqual(new_bankroll, bankroll + estimated_pnl)
        
        # 5. 验证连败计数重置
        stats = self.bankroll_mgr.get_stats('graham')
        self.assertEqual(stats['consecutive_losses'], 0)
        
        print(f"  After Trade: ${new_bankroll:.2f} (PnL: ${estimated_pnl:+.2f})")
    
    def test_daily_stop_loss_protection(self):
        """测试日止损保护"""
        
        # 模拟多次亏损
        for i in range(3):
            self.bankroll_mgr.update_after_trade('timezone', pnl=-50, won=False)
        
        # 检查日止损是否触发
        triggered, reason = self.bankroll_mgr.check_daily_stop_loss('timezone', threshold=0.10)
        
        print(f"\nStop Loss Test:")
        print(f"  Triggered: {triggered}")
        print(f"  Reason: {reason}")
        
        # 应该触发 (3*50 = 150, 150/400 = 37.5% > 10%)
        self.assertTrue(triggered)
    
    def test_consecutive_loss_pause(self):
        """测试连续亏损暂停"""
        
        # 连续3次亏损
        for i in range(3):
            self.bankroll_mgr.update_after_trade('bregman', pnl=-20, won=False)
        
        # 检查是否暂停
        should_pause, reason = self.bankroll_mgr.check_consecutive_losses('bregman')
        
        print(f"\nConsecutive Loss Test:")
        print(f"  Should Pause: {should_pause}")
        print(f"  Reason: {reason}")
        
        self.assertTrue(should_pause)
    
    def test_edge_filter(self):
        """测试Edge过滤"""
        
        # 低Edge机会
        low_edge_opp = {
            'market_price': 0.51,
            'true_prob': 0.52,  # Edge只有1%
        }
        
        size, _, edge = self.kelly.calculate_size(
            p=low_edge_opp['true_prob'],
            m=low_edge_opp['market_price'],
            bankroll=300,
            min_edge=0.05  # 5%最小阈值
        )
        
        print(f"\nEdge Filter Test:")
        print(f"  Edge: {edge:.1%}")
        print(f"  Size: ${size:.2f}")
        print(f"  Decision: {'REJECTED' if size == 0 else 'APPROVED'}")
        
        # 应该被拒绝
        self.assertEqual(size, 0)
        self.assertLess(edge, 0.05)
    
    def test_multiple_systems_independence(self):
        """测试多系统独立性"""
        
        systems = ['graham', 'timezone', 'bregman', 'hft_btc', 'harvest']
        
        # 记录初始总资金
        initial_total = self.bankroll_mgr.get_stats()['total_bankroll']
        
        # 每个系统执行一笔交易
        for system in systems:
            initial = self.bankroll_mgr.get_current_bankroll(system)
            self.bankroll_mgr.update_after_trade(system, pnl=10, won=True)
            updated = self.bankroll_mgr.get_current_bankroll(system)
            
            # 验证独立更新
            self.assertAlmostEqual(updated, initial + 10, places=2)
        
        # 验证总资金增加
        stats = self.bankroll_mgr.get_stats()
        total = stats['total_bankroll']
        expected_increase = 10 * len(systems)
        
        print(f"\nMulti-System Test:")
        print(f"  Initial Total: ${initial_total:.2f}")
        print(f"  Final Total: ${total:.2f}")
        print(f"  Increase: ${total - initial_total:.2f}")
        print(f"  Expected Increase: ${expected_increase:.2f}")
        
        self.assertAlmostEqual(total - initial_total, expected_increase, places=2)

if __name__ == '__main__':
    # 运行测试并显示详细信息
    unittest.main(verbosity=2)
