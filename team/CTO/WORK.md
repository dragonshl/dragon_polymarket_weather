# CTO 工作日志 - 优化后策略代码

## 2026-02-22 18:40 - 策略更新

### 优化后的MA策略 v3.0

```python
class OptimizedStrategy:
    def __init__(self):
        # 基础参数
        self.ma_short = 5
        self.ma_long = 20
        self.ma_trend_short = 50
        self.ma_trend_long = 200
        
        # 优化参数
        self.trend_threshold = 0.02  # 趋势阈值2%
        self.position_ratio = 0.5     # 仓位50%
        
    def get_trend_strength(self, prices):
        """计算趋势强度"""
        ma50 = self.calculate_ma(prices, 50)
        ma200 = self.calculate_ma(prices, 200)
        return (ma50 - ma200) / ma200
    
    def should_trade(self, prices, day_of_week):
        """是否应该交易"""
        # 1. 检查趋势强度
        strength = self.get_trend_strength(prices)
        if abs(strength) < self.trend_threshold:
            return False, "趋势不够强"
        
        # 2. 检查交易时段 (周二-周四)
        if day_of_week in [1, 2, 3]:  # 周二=1, 周三=2, 周四=3
            pass  # 最佳时段
        elif day_of_week in [0, 4]:   # 周一, 周五
            return False, "非最佳时段"
        else:
            return False, "周末不交易"
        
        return True, "OK"
    
    def signal(self, prices, day_of_week):
        """生成交易信号"""
        # 检查是否应该交易
        should_trade, reason = self.should_trade(prices, day_of_week)
        if not should_trade:
            return "HOLD", reason
        
        # 计算MA
        ma5 = self.calculate_ma(prices, 5)
        ma20 = self.calculate_ma(prices, 20)
        ma50 = self.calculate_ma(prices, 50)
        ma200 = self.calculate_ma(prices, 200)
        
        # 趋势判断
        is_uptrend = ma50 > ma200
        trend_strength = self.get_trend_strength(prices)
        
        # 多头趋势 (65%配置)
        if is_uptrend and trend_strength > self.trend_threshold:
            if ma5 > ma20:
                return "BUY", "多头趋势+金叉"
            elif ma5 < ma20:
                return "SELL", "多头趋势+死叉(止盈)"
        
        # 空头趋势 (35%配置)
        elif not is_uptrend and trend_strength < -self.trend_threshold:
            if ma5 < ma20:
                return "SELL", "空头趋势+死叉"
            elif ma5 > ma20:
                return "BUY", "空头趋势+金叉(止盈)"
        
        return "HOLD", "无信号"
    
    def position_sizing(self, trend_type):
        """仓位配置"""
        if trend_type == "UP":
            return 0.65  # 多头65%
        else:
            return 0.35  # 空头35%
```

### 风控模块

```python
class RiskManager:
    def __init__(self):
        self.stop_loss = 0.02      # 2%止损
        self.max_holding_days = 28  # 最大28天(4周)
        self.min_holding_days = 14  # 最小14天(2周)
        
    def should_close(self, entry_date, current_date, pnl):
        """是否应该平仓"""
        days_held = (current_date - entry_date).days
        
        # 最小持仓期
        if days_held < self.min_holding_days:
            return False, "未到最短持仓期"
        
        # 止损
        if pnl <= -self.stop_loss:
            return True, "止损"
        
        # 最大持仓期
        if days_held >= self.max_holding_days:
            return True, "到最大持仓期"
        
        # 移动止盈 (持有-4周)
        if days_held >= self.min_holding_days:
            if p2nl >= 0.03:  # 3%以上
                return True, "止盈"
        
        return False, "继续持有"
```
