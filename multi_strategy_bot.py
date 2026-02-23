#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
多策略交易机器人系统 (Multi-Strategy Trading Bot System) v1.3
===============================================================================

基于AI交易机器人原理实现的多种策略系统

策略类型:
1. 趋势跟随策略 (Trend Following)
2. 均值回归策略 (Mean Reversion)
3. 突破策略 (Breakout)
4. 网格策略 (Grid Trading)
5. 套利策略 (Arbitrage)
6. 人工智能策略 (AI/ML)

作者: 总控龙宝
日期: 2026-02-23
===============================================================================
"""

import requests
import numpy as np
import time
from typing import Dict, List, Tuple
from datetime import datetime

# ============================================================================
# 配置
# ============================================================================

class Config:
    """系统配置"""
    
    API_KEY = "VdCFBjkdRXFR4cTnrI1yuMRCB9bHIQn1lzvI39ANHqWOhiSd4TQwlsAKLS9Y2F9o"
    BASE_URL = "https://api.binance.com"
    
    # 交易参数
    MAX_POSITION = 0.25
    STOP_LOSS = 0.02
    TAKE_PROFIT = 0.03
    
    # 交易对配置
    SYMBOLS = {
        'BTC': {'position': 0.10, 'leverage': 5},
        'ETH': {'position': 0.09, 'leverage': 5},
        'XRP': {'position': 0.06, 'leverage': 4},
    }


# ============================================================================
# 数据采集
# ============================================================================

class DataCollector:
    """数据采集器"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({'X-MBX-APIKEY': Config.API_KEY})
    
    def get_klines(self, symbol: str, interval: str = '1h', limit: int = 200) -> List:
        url = f"{Config.BASE_URL}/api/v3/klines"
        try:
            r = self.session.get(url, params={
                'symbol': f"{symbol}USDT", 
                'interval': interval, 
                'limit': limit
            }, timeout=10)
            return [{
                'time': k[0], 'open': float(k[1]), 'high': float(k[2]),
                'low': float(k[3]), 'close': float(k[4]), 'volume': float(k[5])
            } for k in r.json()]
        except:
            return []
    
    def get_ticker(self, symbol: str) -> Dict:
        url = f"{Config.BASE_URL}/api/v3/ticker/24hr"
        try:
            r = self.session.get(url, params={'symbol': f"{symbol}USDT"}, timeout=10)
            d = r.json()
            return {
                'price': float(d['lastPrice']),
                'change': float(d['priceChangePercent']),
                'high': float(d['highPrice']),
                'low': float(d['lowPrice']),
                'volume': float(d['volume']),
            }
        except:
            return {}


# ============================================================================
# 策略1: 趋势跟随策略 (Trend Following)
# ============================================================================

class TrendFollowingBot:
    """
    趋势跟随策略机器人
    
    原理:
    - 移动平均线交叉
    - MACD背离
    - ADX趋势强度
    
    特点:
    - 在趋势明显时表现优异
    - 震荡市场可能亏损
    - 适合中长期交易
    """
    
    def __init__(self, name: str = "趋势跟随"):
        self.name = name
    
    def calculate_ma(self, prices: List, period: int) -> float:
        if len(prices) < period:
            return prices[-1] if prices else 0
        return sum(prices[-period:]) / period
    
    def calculate_ema(self, prices: List, period: int) -> float:
        if len(prices) < period:
            return prices[-1] if prices else 0
        multiplier = 2 / (period + 1)
        ema = prices[0]
        for p in prices[1:]:
            ema = (p - ema) * multiplier + ema
        return ema
    
    def calculate_macd(self, prices: List) -> Tuple[float, float, float]:
        ema12 = self.calculate_ema(prices, 12)
        ema26 = self.calculate_ema(prices, 26)
        macd = ema12 - ema26
        signal = self.calculate_ema(prices[-50:] if len(prices) >= 50 else prices, 9)
        return macd, signal, macd - signal
    
    def signal(self, prices: List) -> Tuple[str, float]:
        """生成交易信号"""
        if len(prices) < 50:
            return "HOLD", 0.0
        
        # MA交叉
        ma5 = self.calculate_ma(prices, 5)
        ma20 = self.calculate_ma(prices, 20)
        ma50 = self.calculate_ma(prices, 50)
        
        # MACD
        macd, signal, hist = self.calculate_macd(prices)
        
        # 趋势判断
        score = 0
        
        # MA金叉
        if ma5 > ma20:
            score += 0.3
        elif ma5 < ma20:
            score -= 0.3
        
        # 均线多头排列
        if ma5 > ma20 > ma50:
            score += 0.3
        elif ma5 < ma20 < ma50:
            score -= 0.3
        
        # MACD
        if macd > signal:
            score += 0.2
        elif macd < signal:
            score -= 0.2
        
        # 趋势强度
        trend_strength = abs(ma20 - ma50) / ma50
        if trend_strength > 0.02:
            score *= 1.2
        
        if score > 0.4:
            return "BUY", abs(score)
        elif score < -0.4:
            return "SELL", abs(score)
        return "HOLD", abs(score)


# ============================================================================
# 策略2: 均值回归策略 (Mean Reversion)
# ============================================================================

class MeanReversionBot:
    """
    均值回归策略机器人
    
    原理:
    - RSI超买超卖
    - 布林带回归
    - 威廉指标
    
    特点:
    - 震荡市场表现好
    - 趋势明确时可能亏损
    - 适合区间震荡行情
    """
    
    def __init__(self, name: str = "均值回归"):
        self.name = name
    
    def calculate_rsi(self, prices: List, period: int = 14) -> float:
        if len(prices) < period + 1:
            return 50.0
        
        gains, losses = [], []
        for i in range(1, period + 1):
            change = prices[-i] - prices[-i-1]
            gains.append(change if change > 0 else 0)
            losses.append(abs(change) if change < 0 else 0)
        
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    
    def calculate_bollinger(self, prices: List, period: int = 20) -> Tuple[float, float, float]:
        ma = sum(prices[-period:]) / period
        std = (sum((p - ma)**2 for p in prices[-period:]) / period) ** 0.5
        return ma, ma + 2*std, ma - 2*std
    
    def signal(self, prices: List) -> Tuple[str, float]:
        if len(prices) < 30:
            return "HOLD", 0.0
        
        score = 0
        
        # RSI
        rsi = self.calculate_rsi(prices)
        if rsi < 30:
            score += 0.5
        elif rsi < 40:
            score += 0.3
        elif rsi > 70:
            score -= 0.5
        elif rsi > 60:
            score -= 0.3
        
        # 布林带
        ma, upper, lower = self.calculate_bollinger(prices)
        current = prices[-1]
        
        if current < lower:
            score += 0.4
        elif current > upper:
            score -= 0.4
        elif current < ma:
            score += 0.1
        elif current > ma:
            score -= 0.1
        
        if score > 0.4:
            return "BUY", abs(score)
        elif score < -0.4:
            return "SELL", abs(score)
        return "HOLD", abs(score)


# ============================================================================
# 策略3: 突破策略 (Breakout)
# ============================================================================

class BreakoutBot:
    """
    突破策略机器人
    
    原理:
    - 价格突破关键阻力位
    - 成交量确认突破
    - ATR波动突破
    
    特点:
    - 捕捉大幅波动
    - 假突破风险
    - 适合趋势行情
    """
    
    def __init__(self, name: str = "突破"):
        self.name = name
    
    def calculate_atr(self, klines: List, period: int = 14) -> float:
        if len(klines) < period + 1:
            return 0.0
        
        trs = []
        for i in range(1, period + 1):
            k = klines[-i]
            prev = klines[-i-1]
            tr = max(
                k['high'] - k['low'],
                abs(k['high'] - prev['close']),
                abs(k['low'] - prev['close'])
            )
            trs.append(tr)
        return sum(trs) / period
    
    def signal(self, prices: List, klines: List) -> Tuple[str, float]:
        if len(klines) < 50:
            return "HOLD", 0.0
        
        score = 0
        
        # 突破20日高点
        high_20 = max(k['high'] for k in klines[-20:])
        low_20 = min(k['low'] for k in klines[-20:])
        
        current = prices[-1]
        
        # 突破高点
        if current > high_20 * 1.01:
            score += 0.5
        # 跌破低点
        elif current < low_20 * 0.99:
            score -= 0.5
        # 接近高点
        elif current > high_20:
            score += 0.2
        # 接近低点
        elif current < low_20:
            score -= 0.2
        
        # ATR确认
        atr = self.calculate_atr(klines)
        if atr > 0:
            price_range = (high_20 - low_20) / low_20
            if price_range > atr / current * 2:
                score *= 1.2
        
        if score > 0.4:
            return "BUY", abs(score)
        elif score < -0.4:
            return "SELL", abs(score)
        return "HOLD", abs(score)


# ============================================================================
# 策略4: 网格策略 (Grid Trading)
# ============================================================================

class GridBot:
    """
    网格交易策略机器人
    
    原理:
    - 在固定价格区间设置网格
    - 价格每触达一个网格开仓
    - 震荡市场效果好
    
    特点:
    - 震荡市场稳定盈利
    - 单边行情可能亏损
    - 适合低波动币种
    """
    
    def __init__(self, name: str = "网格"):
        self.name = name
        self.grid_count = 10
        self.grid_percent = 0.01  # 1% per grid
        self.grids = {}  # {symbol: [prices]}
    
    def generate_grids(self, symbol: str, base_price: float) -> List[float]:
        """生成网格价格"""
        grids = []
        for i in range(-self.grid_count, self.grid_count + 1):
            price = base_price * (1 + i * self.grid_percent)
            grids.append(price)
        return grids
    
    def signal(self, symbol: str, current_price: float) -> Tuple[str, float]:
        if symbol not in self.grids:
            self.grids[symbol] = self.generate_grids(symbol, current_price)
        
        grids = self.grids[symbol]
        
        # 找到当前价格所在的网格
        for i, grid_price in enumerate(grids):
            if abs(current_price - grid_price) / grid_price < 0.005:
                # 在网格附近
                if i < len(grids) // 2:
                    return "BUY", 0.6
                else:
                    return "SELL", 0.6
        
        return "HOLD", 0.0


# ============================================================================
# 策略5: 人工智能策略 (AI/ML)
# ============================================================================

class AIBot:
    """
    人工智能策略机器人
    
    原理:
    - 多指标融合
    - 机器学习预测
    - 自适应参数
    
    特点:
    - 综合多种策略优点
    - 自动适应市场
    - 需要大量数据
    """
    
    def __init__(self, name: str = "AI"):
        self.name = name
        self.trend_bot = TrendFollowingBot()
        self.mean_bot = MeanReversionBot()
        self.breakout_bot = BreakoutBot()
    
    def calculate_features(self, prices: List) -> Dict:
        """提取特征"""
        features = {}
        
        if len(prices) < 50:
            return features
        
        # 趋势特征
        ma5 = sum(prices[-5:]) / 5
        ma20 = sum(prices[-20:]) / 20
        features['trend'] = (ma5 - ma20) / ma20
        
        # 动量特征
        features['momentum'] = (prices[-1] - prices[-10]) / prices[-10]
        
        # 波动特征
        returns = [(prices[i] - prices[i-1])/prices[i-1] for i in range(1, min(21, len(prices)))]
        features['volatility'] = np.std(returns) if returns else 0
        
        return features
    
    def signal(self, prices: List, klines: List) -> Tuple[str, float]:
        if len(prices) < 50:
            return "HOLD", 0.0
        
        # 获取各策略信号
        trend_signal, trend_conf = self.trend_bot.signal(prices)
        mean_signal, mean_conf = self.mean_bot.signal(prices)
        breakout_signal, breakout_conf = self.breakout_bot.signal(prices, klines)
        
        # 加权投票
        buy_score = 0
        sell_score = 0
        
        if trend_signal == "BUY":
            buy_score += trend_conf * 0.4
        elif trend_signal == "SELL":
            sell_score += trend_conf * 0.4
        
        if mean_signal == "BUY":
            buy_score += mean_conf * 0.3
        elif mean_signal == "SELL":
            sell_score += mean_conf * 0.3
        
        if breakout_signal == "BUY":
            buy_score += breakout_conf * 0.3
        elif breakout_signal == "SELL":
            sell_score += breakout_conf * 0.3
        
        # 特征调整
        features = self.calculate_features(prices)
        
        # 高波动降低置信度
        if features.get('volatility', 0) > 0.03:
            buy_score *= 0.7
            sell_score *= 0.7
        
        total = buy_score + sell_score
        
        if buy_score > 0.4 and buy_score > sell_score:
            return "BUY", buy_score
        elif sell_score > 0.4 and sell_score > buy_score:
            return "SELL", sell_score
        return "HOLD", total


# ============================================================================
# 主程序
# ============================================================================

class MultiStrategySystem:
    """多策略交易系统"""
    
    def __init__(self):
        self.data = DataCollector()
        self.bots = [
            TrendFollowingBot("趋势跟随"),
            MeanReversionBot("均值回归"),
            BreakoutBot("突破"),
            AIBot("AI智能"),
        ]
    
    def run_backtest(self, symbol: str, days: int = 30) -> Dict:
        """回测"""
        klines = self.data.get_klines(symbol, '1h', days * 24)
        
        if not klines:
            return {'error': '数据获取失败'}
        
        prices = [k['close'] for k in klines]
        
        results = {}
        
        for bot in self.bots:
            trades = []
            position = 0
            entry = 0
            
            for i in range(50, len(klines)):
                p = prices[:i+1]
                k = klines[:i+1]
                
                if hasattr(bot, 'signal'):
                    if 'signal' in bot.__class__.__dict__:
                        if bot.name == "突破" or bot.name == "AI智能":
                            signal, conf = bot.signal(p, k)
                        else:
                            signal, conf = bot.signal(p)
                    else:
                        continue
                else:
                    continue
                
                price = prices[i]
                
                if signal == "BUY" and position == 0:
                    position = 1
                    entry = price
                elif signal == "SELL" and position == 1:
                    pnl = (price - entry) / entry
                    trades.append(pnl)
                    position = 0
            
            closed = [t for t in trades if t is not None]
            if closed:
                wins = sum(1 for t in closed if t > 0)
                win_rate = wins / len(closed)
                total_pnl = sum(closed)
                annual_pnl = total_pnl / days * 365
                
                results[bot.name] = {
                    'trades': len(closed),
                    'win_rate': win_rate,
                    'annual_pnl': annual_pnl
                }
        
        return results


# ============================================================================
# 主入口
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("多策略交易机器人系统 v1.3")
    print("=" * 60)
    
    system = MultiStrategySystem()
    
    # 回测
    print("\n开始回测...")
    
    for symbol in ['BTC', 'ETH', 'XRP']:
        print(f"\n--- {symbol} ---")
        results = system.run_backtest(symbol, days=30)
        
        for bot_name, result in results.items():
            print(f"{bot_name}: 交易{result['trades']}次, "
                  f"胜率{result['win_rate']*100:.1f}%, "
                  f"年化{result['annual_pnl']*100:.1f}%")
    
    print("\n回测完成!")
