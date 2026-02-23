#!/usr/bin/env python3
"""
总控龙宝交易系统 v1.2 - ML增强版
Trading System with Machine Learning

目标:
- 年化收益: >60%
- 最大回撤: <10%
- ML融合所有策略
"""

import requests
import time
import json
import logging
import numpy as np
from datetime import datetime
from typing import Dict, List, Tuple, Optional

# ==================== 配置 ====================

class Config:
    """系统配置 - ML增强版"""
    
    API_KEY = "VdCFBjkdRXFR4cTnrI1yuMRCB9bHIQn1lzvI39ANHqWOhiSd4TQwlsAKLS9Y2F9o"
    API_SECRET = ""
    BASE_URL = "https://api.binance.com"
    
    # 交易参数
    MAX_POSITION = 0.25
    MAX_LEVERAGE = 5
    STOP_LOSS = 0.015
    TAKE_PROFIT = 0.025
    MAX_DRAWDOWN = 0.08
    
    # 交易对配置 (ML增强)
    SYMBOLS = {
        'BTC': {'position': 0.10, 'leverage': 5, 'stop_loss': 0.015},
        'ETH': {'position': 0.09, 'leverage': 5, 'stop_loss': 0.015},
        'XRP': {'position': 0.06, 'leverage': 4, 'stop_loss': 0.018},
        'SOL': {'position': 0.05, 'leverage': 4, 'stop_loss': 0.02},
        'BNB': {'position': 0.05, 'leverage': 4, 'stop_loss': 0.02},
        'ADA': {'position': 0.03, 'leverage': 3, 'stop_loss': 0.02},
    }


# ==================== 日志 ====================

class Logger:
    def __init__(self, name: str = "TradingBot"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        self.logger.addHandler(handler)
    
    def info(self, msg): self.logger.info(msg)
    def error(self, msg): self.logger.error(msg)
    def warning(self, msg): self.logger.warning(msg)


# ==================== 数据采集 ====================

class DataCollector:
    def __init__(self, config: Config, logger: Logger):
        self.config = config
        self.logger = logger
        self.session = requests.Session()
        self.session.headers.update({'X-MBX-APIKEY': config.API_KEY})
    
    def get_price(self, symbol: str) -> float:
        try:
            url = f"{self.config.BASE_URL}/api/v3/ticker/price"
            r = self.session.get(url, params={'symbol': f"{symbol}USDT"}, timeout=10)
            return float(r.json()['price'])
        except:
            return 0.0
    
    def get_24hr(self, symbol: str) -> Dict:
        try:
            url = f"{self.config.BASE_URL}/api/v3/ticker/24hr"
            r = self.session.get(url, params={'symbol': f"{symbol}USDT"}, timeout=10)
            d = r.json()
            return {'price': float(d['lastPrice']), 'change': float(d['priceChangePercent'])}
        except:
            return {}
    
    def get_klines(self, symbol: str, interval: str = '1h', limit: int = 200) -> List:
        try:
            url = f"{self.config.BASE_URL}/api/v3/klines"
            r = self.session.get(url, params={'symbol': f"{symbol}USDT", 'interval': interval, 'limit': limit}, timeout=10)
            return [{'time': k[0], 'open': float(k[1]), 'high': float(k[2]), 'low': float(k[3]), 
                    'close': float(k[4]), 'volume': float(k[5])} for k in r.json()]
        except:
            return []
    
    def get_order_book(self, symbol: str, limit: int = 20) -> Dict:
        try:
            url = f"{self.config.BASE_URL}/api/v3/depth"
            r = self.session.get(url, params={'symbol': f"{symbol}USDT", 'limit': limit}, timeout=10)
            d = r.json()
            return {'bids': [[float(p), float(q)] for p, q in d['bids']],
                    'asks': [[float(p), float(q)] for p, q in d['asks']]}
        except:
            return {'bids': [], 'asks': []}


# ==================== 技术指标 (ML特征) ====================

class TechnicalIndicators:
    """技术指标 + ML特征"""
    
    @staticmethod
    def get_all_features(prices: List[float], klines: List, order_book: Dict) -> Dict:
        """提取所有ML特征"""
        features = {}
        
        if len(prices) < 50:
            return features
        
        # 1. 价格特征
        features['price'] = prices[-1]
        features['returns'] = (prices[-1] - prices[-50]) / prices[-50]
        
        # 2. MA特征
        for period in [5, 10, 20, 50]:
            ma = sum(prices[-period:]) / period
            features[f'ma{period}'] = ma
            features[f'ma{period}_ratio'] = prices[-1] / ma
        
        # 3. RSI
        gains, losses = [], []
        for i in range(1, 15):
            c = prices[-i] - prices[-i-1]
            gains.append(c if c > 0 else 0)
            losses.append(abs(c) if c < 0 else 0)
        avg_gain = sum(gains) / 14
        avg_loss = sum(losses) / 14
        rs = avg_gain / avg_loss if avg_loss > 0 else 0
        features['rsi'] = 100 - (100 / (1 + rs))
        
        # 4. 布林带
        ma20 = sum(prices[-20:]) / 20
        std = (sum((p - ma20)**2 for p in prices[-20:]) / 20) ** 0.5
        features['bb_upper'] = ma20 + 2 * std
        features['bb_lower'] = ma20 - 2 * std
        features['bb_position'] = (prices[-1] - features['bb_lower']) / (features['bb_upper'] - features['bb_lower']) if features['bb_upper'] != features['bb_lower'] else 0.5
        
        # 5. 动量
        features['momentum_5'] = (prices[-1] - prices[-6]) / prices[-6]
        features['momentum_10'] = (prices[-1] - prices[-11]) / prices[-11]
        features['momentum_20'] = (prices[-1] - prices[-21]) / prices[-21]
        
        # 6. 波动率
        features['volatility_10'] = np.std([(prices[i] - prices[i-1])/prices[i-1] for i in range(1, 11)]) if len(prices) > 10 else 0
        features['volatility_20'] = np.std([(prices[i] - prices[i-1])/prices[i-1] for i in range(1, 21)]) if len(prices) > 20 else 0
        
        # 7. MACD
        ema12 = TechnicalIndicators._ema(prices, 12)
        ema26 = TechnicalIndicators._ema(prices, 26)
        features['macd'] = ema12 - ema26
        features['macd_signal'] = TechnicalIndicators._ema(prices[-50:], 9)
        
        # 8. 订单流特征
        if order_book.get('bids') and order_book.get('asks'):
            bid_vol = sum(v for _, v in order_book['bids'][:10])
            ask_vol = sum(v for _, v in order_book['asks'][:10])
            features['delta'] = bid_vol - ask_vol
            features['imbalance'] = bid_vol / ask_vol if ask_vol > 0 else 1
            features['bid_ask_spread'] = (order_book['asks'][0][0] - order_book['bids'][0][0]) / prices[-1]
        
        # 9. 成交量特征
        if klines:
            volumes = [k['volume'] for k in klines[-20:]]
            features['volume_ma'] = sum(volumes) / 20
            features['volume_ratio'] = volumes[-1] / features['volume_ma'] if features['volume_ma'] > 0 else 1
            
            # 成交量变化
            cvd = 0
            for k in klines[-20:]:
                if k['close'] > k['open']:
                    cvd += k['volume']
                else:
                    cvd -= k['volume']
            features['cvd'] = cvd
        
        # 10. 趋势强度
        ma50 = sum(prices[-50:]) / 50
        ma200 = sum(prices[-200:]) / 200 if len(prices) >= 200 else ma50
        features['trend_strength'] = (ma50 - ma200) / ma200 if ma200 > 0 else 0
        
        return features
    
    @staticmethod
    def _ema(prices: List[float], period: int) -> float:
        if len(prices) < period:
            return prices[-1] if prices else 0
        multiplier = 2 / (period + 1)
        ema = prices[0]
        for p in prices[1:]:
            ema = (p - ema) * multiplier + ema
        return ema


# ==================== ML模型 ====================

class MLEngine:
    """机器学习引擎 - 多策略融合"""
    
    def __init__(self, config: Config, logger: Logger):
        self.config = config
        self.logger = logger
        self.indicators = TechnicalIndicators()
        
        # 简单的加权模型 (可替换为真实ML模型)
        self.weights = {
            'orderflow': 0.25,
            'rsi': 0.20,
            'bollinger': 0.15,
            'momentum': 0.15,
            'macd': 0.15,
            'trend': 0.10
        }
    
    def predict(self, features: Dict) -> Tuple[str, float]:
        """ML预测信号"""
        
        scores = {}
        
        # 1. 订单流信号
        if 'delta' in features and 'imbalance' in features:
            of_score = 0
            if features.get('delta', 0) > 0:
                of_score += 0.3
            if features.get('imbalance', 1) > 1.2:
                of_score += 0.3
            if features.get('cvd', 0) > 0:
                of_score += 0.2
            scores['orderflow'] = of_score * self.weights['orderflow']
        
        # 2. RSI信号
        if 'rsi' in features:
            rsi = features['rsi']
            rsi_score = 0
            if rsi < 30:
                rsi_score = 0.8
            elif rsi < 40:
                rsi_score = 0.5
            elif rsi > 70:
                rsi_score = -0.8
            elif rsi > 60:
                rsi_score = -0.5
            scores['rsi'] = rsi_score * self.weights['rsi']
        
        # 3. 布林带信号
        if 'bb_position' in features:
            bb = features['bb_position']
            bb_score = 0
            if bb < 0.2:
                bb_score = 0.7
            elif bb > 0.8:
                bb_score = -0.7
            scores['bollinger'] = bb_score * self.weights['bollinger']
        
        # 4. 动量信号
        if 'momentum_10' in features and 'momentum_20' in features:
            mom = features['momentum_10'] * 0.6 + features['momentum_20'] * 0.4
            mom_score = 0
            if mom > 0.05:
                mom_score = 0.7
            elif mom > 0.02:
                mom_score = 0.4
            elif mom < -0.05:
                mom_score = -0.7
            elif mom < -0.02:
                mom_score = -0.4
            scores['momentum'] = mom_score * self.weights['momentum']
        
        # 5. MACD信号
        if 'macd' in features and 'macd_signal' in features:
            macd = features['macd']
            macd_score = 0
            if macd > features['macd_signal'] * 1.01:
                macd_score = 0.6
            elif macd < features['macd_signal'] * 0.99:
                macd_score = -0.6
            scores['macd'] = macd_score * self.weights['macd']
        
        # 6. 趋势信号
        if 'trend_strength' in features:
            trend = features['trend_strength']
            trend_score = 0
            if trend > 0.02:
                trend_score = 0.5
            elif trend < -0.02:
                trend_score = -0.5
            scores['trend'] = trend_score * self.weights['trend']
        
        # 7. 成交量确认
        if 'volume_ratio' in features and 'cvd' in features:
            vol_score = 0
            if features['volume_ratio'] > 1.5 and features['cvd'] > 0:
                vol_score = 0.2
            elif features['volume_ratio'] > 1.5 and features['cvd'] < 0:
                vol_score = -0.2
            if 'volume' in scores:
                scores['volume'] = vol_score
            else:
                scores['volume'] = vol_score
        
        # 综合评分
        total_score = sum(scores.values())
        
        # 输出信号
        if total_score > 0.3:
            return "BUY", min(total_score, 1.0)
        elif total_score < -0.3:
            return "SELL", min(abs(total_score), 1.0)
        else:
            return "HOLD", abs(total_score)


# ==================== 策略引擎 ====================

class StrategyEngine:
    """策略引擎 - ML驱动"""
    
    def __init__(self, config: Config, logger: Logger):
        self.config = config
        self.logger = logger
        self.ml = MLEngine(config, logger)
        self.indicators = TechnicalIndicators()
    
    def generate_signal(self, prices: List[float], klines: List, 
                      order_book: Dict) -> Tuple[str, float]:
        """生成信号 - ML驱动"""
        
        # 提取特征
        features = self.indicators.get_all_features(prices, klines, order_book)
        
        if not features:
            return "HOLD", 0.0
        
        # ML预测
        signal, confidence = self.ml.predict(features)
        
        # 附加过滤
        # 1. 趋势过滤
        if 'trend_strength' in features:
            trend = features['trend_strength']
            # 逆势不交易
            if signal == "BUY" and trend < -0.03:
                return "HOLD", 0.0
            if signal == "SELL" and trend > 0.03:
                return "HOLD", 0.0
        
        # 2. 波动率过滤
        if 'volatility_20' in features:
            vol = features['volatility_20']
            # 波动过大降低置信度
            if vol > 0.05:
                confidence *= 0.7
        
        return signal, confidence


# ==================== 风险管理 ====================

class RiskManager:
    def __init__(self, config: Config, logger: Logger):
        self.config = config
        self.logger = logger
        self.positions = {}
        self.stats = {'trades': 0, 'wins': 0, 'pnl': 0, 'peak': 0, 'dd': 0}
    
    def check(self, symbol: str, entry: float, current: float, 
             side: str) -> Tuple[bool, str]:
        """检查止损止盈"""
        cfg = self.config.SYMBOLS.get(symbol, {})
        stop = cfg.get('stop_loss', 0.02)
        
        if side == "LONG":
            pnl = (current - entry) / entry
        else:
            pnl = (entry - current) / entry
        
        if pnl <= -stop:
            return True, "STOP_LOSS"
        if pnl >= self.config.TAKE_PROFIT:
            return True, "TAKE_PROFIT"
        return False, ""
    
    def record(self, pnl: float):
        self.stats['trades'] += 1
        if pnl > 0:
            self.stats['wins'] += 1
        self.stats['pnl'] += pnl
        
        # 回撤
        if self.stats['pnl'] > self.stats['peak']:
            self.stats['peak'] = self.stats['pnl']
        dd = (self.stats['peak'] - self.stats['pnl']) / (1 + self.stats['peak'])
        if dd > self.stats['dd']:
            self.stats['dd'] = dd
    
    def can_trade(self, total_pos: float) -> bool:
        return total_pos < self.config.MAX_POSITION


# ==================== 订单执行 ====================

class OrderExecutor:
    def __init__(self, config: Config, logger: Logger):
        self.config = config
        self.logger = logger
    
    def order(self, symbol: str, side: str, qty: float) -> Dict:
        self.logger.info(f"下单 {symbol} {side} {qty}")
        return {'status': 'SIMULATED', 'symbol': symbol, 'side': side, 'qty': qty}


# ==================== 交易系统主程序 ====================

class TradingSystem:
    """交易系统 - ML增强版"""
    
    def __init__(self, capital: float = 1000):
        self.config = Config()
        self.logger = Logger("总控龙宝-v1.2-ML")
        
        self.data = DataCollector(self.config, self.logger)
        self.strategy = StrategyEngine(self.config, self.logger)
        self.risk = RiskManager(self.config, self.logger)
        self.executor = OrderExecutor(self.config, self.logger)
        
        self.capital = capital
        self.positions = {}
        
        self.logger.info(f"ML增强交易系统启动, 资金: ${capital}")
        self.logger.info("目标: 年化60%+, 回撤<10%")
    
    def get_data(self, symbol: str) -> Dict:
        price = self.data.get_price(symbol)
        klines = self.data.get_klines(symbol, '1h', 200)
        order_book = self.data.get_order_book(symbol)
        prices = [k['close'] for k in klines]
        
        return {'price': price, 'prices': prices, 'klines': klines, 'order_book': order_book}
    
    def run(self):
        self.logger.info("=" * 50)
        self.logger.info("总控龙宝 ML交易系统运行中")
        self.logger.info("=" * 50)
        
        while True:
            try:
                for symbol in self.config.SYMBOLS:
                    data = self.get_data(symbol)
                    
                    if not data['prices']:
                        continue
                    
                    # ML信号
                    signal, confidence = self.strategy.generate_signal(
                        data['prices'], data['klines'], data['order_book']
                    )
                    
                    self.logger.info(f"{symbol}: {signal} (置信度: {confidence:.2f})")
                    
                    # 处理信号
                    if signal == "BUY" and confidence > 0.5:
                        total_pos = sum(p['qty'] * p['entry'] for p in self.positions.values() if p['qty'] > 0)
                        if self.risk.can_trade(total_pos / self.capital):
                            cfg = self.config.SYMBOLS[symbol]
                            qty = self.capital * cfg['position'] / data['price']
                            
                            self.executor.order(symbol, "BUY", qty)
                            self.positions[symbol] = {'qty': qty, 'entry': data['price'], 'side': 'LONG'}
                            self.logger.info(f"买入 {symbol} @ ${data['price']}")
                    
                    elif signal == "SELL":
                        if symbol in self.positions and self.positions[symbol]['qty'] > 0:
                            pos = self.positions[symbol]
                            close, reason = self.risk.check(symbol, pos['entry'], data['price'], pos['side'])
                            
                            if close:
                                self.executor.order(symbol, "SELL", pos['qty'])
                                pnl = (data['price'] - pos['entry']) / pos['entry']
                                self.risk.record(pnl)
                                self.positions[symbol] = {'qty': 0, 'entry': 0, 'side': ''}
                                self.logger.info(f"平仓 {symbol} @ ${data['price']}, {reason}")
                
                time.sleep(60)
                
            except KeyboardInterrupt:
                self.logger.info("系统停止")
                break
            except Exception as e:
                self.logger.error(f"错误: {e}")
                time.sleep(10)
    
    def backtest(self, symbol: str, days: int = 30) -> Dict:
        self.logger.info(f"回测 {symbol}...")
        
        klines = self.data.get_klines(symbol, '1h', days * 24)
        
        if not klines:
            return {'error': '数据获取失败'}
        
        trades = []
        position = 0
        entry = 0
        
        for i in range(100, len(klines)):
            prices = [k['close'] for k in klines[:i+1]]
            klines_slice = klines[:i+1]
            order_book = {'bids': [], 'asks': []}
            
            signal, conf = self.strategy.generate_signal(prices, klines_slice, order_book)
            price = klines[i]['close']
            
            if signal == "BUY" and position == 0 and conf > 0.5:
                position = 1
                entry = price
                trades.append({'type': 'BUY', 'price': entry})
            
            elif signal == "SELL" and position == 1:
                pnl = (price - entry) / entry
                trades.append({'type': 'SELL', 'price': price, 'pnl': pnl})
                position = 0
        
        closed = [t for t in trades if 'pnl' in t]
        wins = sum(1 for t in closed if t['pnl'] > 0)
        win_rate = wins / len(closed) if closed else 0
        total_pnl = sum(t['pnl'] for t in closed)
        annual_pnl = total_pnl / days * 365 if days > 0 else 0
        
        self.logger.info(f"{symbol}: 交易{len(closed)}次, 胜率{win_rate*100:.1f}%, 年化{annual_pnl*100:.1f}%")
        
        return {'symbol': symbol, 'trades': len(closed), 'win_rate': win_rate, 
                'total_pnl': total_pnl, 'annual_pnl': annual_pnl}


# ==================== 主程序 ====================

if __name__ == "__main__":
    print("=" * 50)
    print("总控龙宝交易系统 v1.2 - ML增强版")
    print("目标: 年化60%+, 回撤<10%")
    print("=" * 50)
    
    bot = TradingSystem(capital=1000)
    
    # 回测
    print("\n开始回测...")
    
    results = []
    for symbol in ['BTC', 'ETH', 'XRP', 'SOL', 'BNB', 'ADA']:
        r = bot.backtest(symbol, days=30)
        results.append(r)
    
    avg_annual = sum(r.get('annual_pnl', 0) for r in results) / len(results)
    print(f"\n平均年化收益: {avg_annual*100:.1f}%")
    print("回测完成!")
