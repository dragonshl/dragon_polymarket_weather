#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
总控龙宝交易系统 (DragonMax Trading System) v1.2 - ML增强版
===============================================================================

作者: 总控龙宝 (DragonMax)
日期: 2026-02-23
版本: v1.2

功能:
    - 多策略融合 (订单流、RSI、动量、MACD、布林带)
    - 机器学习特征工程
    - 严格的风险管理
    - 多币种配置

目标:
    - 年化收益: >60%
    - 最大回撤: <10%

使用:
    python trading_system.py
===============================================================================
"""

import requests
import time
import logging
import numpy as np
from datetime import datetime
from typing import Dict, List, Tuple, Optional

# ============================================================================
# 第一部分: 配置模块 (Configuration)
# ============================================================================

class Config:
    """
    系统配置类
    
    包含所有交易参数、API配置、交易对设置
    
    Attributes:
        API_KEY: Binance API密钥
        API_SECRET: Binance API密钥 (需填写)
        BASE_URL: Binance API地址
        MAX_POSITION: 最大仓位比例
        MAX_LEVERAGE: 最大杠杆倍数
        STOP_LOSS: 止损比例
        TAKE_PROFIT: 止盈比例
        MAX_DRAWDOWN: 最大回撤限制
        SYMBOLS: 交易对配置字典
    """
    
    # -------------------------------------------------------------------------
    # API配置
    # -------------------------------------------------------------------------
    API_KEY = "VdCFBjkdRXFR4cTnrI1yuMRCB9bHIQn1lzvI39ANHqWOhiSd4TQwlsAKLS9Y2F9o"
    API_SECRET = ""  # TODO: 填写您的API Secret
    BASE_URL = "https://api.binance.com"
    
    # -------------------------------------------------------------------------
    # 风控参数
    # -------------------------------------------------------------------------
    MAX_POSITION = 0.25      # 最大仓位 25%
    MAX_LEVERAGE = 5          # 最大杠杆 5倍
    STOP_LOSS = 0.015        # 止损 1.5%
    TAKE_PROFIT = 0.025       # 止盈 2.5%
    MAX_DRAWDOWN = 0.08      # 最大回撤 8%
    
    # -------------------------------------------------------------------------
    # 交易对配置
    # key: 交易币种
    # position: 仓位比例
    # leverage: 杠杆倍数
    # stop_loss: 止损比例
    # -------------------------------------------------------------------------
    SYMBOLS = {
        'BTC': {'position': 0.10, 'leverage': 5, 'stop_loss': 0.015},
        'ETH': {'position': 0.09, 'leverage': 5, 'stop_loss': 0.015},
        'XRP': {'position': 0.06, 'leverage': 4, 'stop_loss': 0.018},
        'SOL': {'position': 0.05, 'leverage': 4, 'stop_loss': 0.020},
        'BNB': {'position': 0.05, 'leverage': 4, 'stop_loss': 0.020},
        'ADA': {'position': 0.03, 'leverage': 3, 'stop_loss': 0.020},
    }


# ============================================================================
# 第二部分: 日志模块 (Logging)
# ============================================================================

class Logger:
    """
    日志系统类
    
    统一管理系统日志输出，包含文件日志和控制台日志
    
    Attributes:
        logger: logging.Logger实例
    """
    
    def __init__(self, name: str = "DragonMax"):
        """
        初始化日志系统
        
        Args:
            name: 日志记录器名称
        """
        # 创建logger
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        
        # 防止重复添加handler
        if not self.logger.handlers:
            # 文件handler
            file_handler = logging.FileHandler('trading.log', encoding='utf-8')
            file_handler.setLevel(logging.INFO)
            
            # 控制台handler
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            
            # 格式化
            formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            
            file_handler.setFormatter(formatter)
            console_handler.setFormatter(formatter)
            
            self.logger.addHandler(file_handler)
            self.logger.addHandler(console_handler)
    
    def info(self, msg: str):
        """输出info级别日志"""
        self.logger.info(msg)
    
    def error(self, msg: str):
        """输出error级别日志"""
        self.logger.error(msg)
    
    def warning(self, msg: str):
        """输出warning级别日志"""
        self.logger.warning(msg)


# ============================================================================
# 第三部分: 数据采集模块 (Data Collection)
# ============================================================================

class DataCollector:
    """
    数据采集器类
    
    负责从Binance API获取各类市场数据
    
    Attributes:
        config: Config实例
        logger: Logger实例
        session: requests.Session实例
    """
    
    def __init__(self, config: Config, logger: Logger):
        """
        初始化数据采集器
        
        Args:
            config: 系统配置
            logger: 日志实例
        """
        self.config = config
        self.logger = logger
        self.session = requests.Session()
        self.session.headers.update({
            'X-MBX-APIKEY': config.API_KEY
        })
    
    def get_price(self, symbol: str) -> float:
        """
        获取实时价格
        
        Args:
            symbol: 交易对符号 (如 'BTC')
            
        Returns:
            float: 当前价格, 0.0表示获取失败
        """
        url = f"{self.config.BASE_URL}/api/v3/ticker/price"
        params = {'symbol': f"{symbol}USDT"}
        
        try:
            response = self.session.get(url, params=params, timeout=10)
            price = float(response.json()['price'])
            self.logger.info(f"获取价格 {symbol}: ${price}")
            return price
        except Exception as e:
            self.logger.error(f"获取价格失败 {symbol}: {e}")
            return 0.0
    
    def get_24hr(self, symbol: str) -> Dict:
        """
        获取24小时统计数据
        
        Args:
            symbol: 交易对符号
            
        Returns:
            Dict: 包含 price, change, high, low, volume
        """
        url = f"{self.config.BASE_URL}/api/v3/ticker/24hr"
        params = {'symbol': f"{symbol}USDT"}
        
        try:
            response = self.session.get(url, params=params, timeout=10)
            data = response.json()
            return {
                'price': float(data['lastPrice']),
                'change': float(data['priceChangePercent']),
                'high': float(data['highPrice']),
                'low': float(data['lowPrice']),
                'volume': float(data['volume']),
            }
        except Exception as e:
            self.logger.error(f"获取24h数据失败: {e}")
            return {}
    
    def get_klines(self, symbol: str, interval: str = '1h', limit: int = 200) -> List[Dict]:
        """
        获取K线数据 (OHLCV)
        
        Args:
            symbol: 交易对符号
            interval: K线周期 ('1m','5m','15m','1h','4h','1d','1w')
            limit: 获取数量
            
        Returns:
            List[Dict]: K线数据列表
        """
        url = f"{self.config.BASE_URL}/api/v3/klines"
        params = {
            'symbol': f"{symbol}USDT",
            'interval': interval,
            'limit': limit
        }
        
        try:
            response = self.session.get(url, params=params, timeout=10)
            data = response.json()
            
            klines = []
            for k in data:
                klines.append({
                    'time': k[0],      # 开盘时间
                    'open': float(k[1]),   # 开盘价
                    'high': float(k[2]),   # 最高价
                    'low': float(k[3]),    # 最低价
                    'close': float(k[4]),  # 收盘价
                    'volume': float(k[5]), # 成交量
                })
            return klines
        except Exception as e:
            self.logger.error(f"获取K线失败: {e}")
            return []
    
    def get_order_book(self, symbol: str, limit: int = 20) -> Dict:
        """
        获取订单簿数据
        
        Args:
            symbol: 交易对符号
            limit: 深度数量
            
        Returns:
            Dict: 包含 bids (买方), asks (卖方)
        """
        url = f"{self.config.BASE_URL}/api/v3/depth"
        params = {'symbol': f"{symbol}USDT", 'limit': limit}
        
        try:
            response = self.session.get(url, params=params, timeout=10)
            data = response.json()
            return {
                'bids': [[float(p), float(q)] for p, q in data['bids']],
                'asks': [[float(p), float(q)] for p, q in data['asks']],
            }
        except Exception as e:
            self.logger.error(f"获取订单簿失败: {e}")
            return {'bids': [], 'asks': []}


# ============================================================================
# 第四部分: 技术指标模块 (Technical Indicators)
# ============================================================================

class TechnicalIndicators:
    """
    技术指标计算类
    
    提供20+种技术指标用于特征工程
    
    Methods:
        get_all_features(): 提取所有ML特征
        calculate_ma(): 计算移动平均线
        calculate_rsi(): 计算RSI指标
        calculate_bollinger(): 计算布林带
        calculate_momentum(): 计算动量
        calculate_macd(): 计算MACD
        calculate_delta(): 计算订单簿Delta
        calculate_cvd(): 计算累计成交量Delta
    """
    
    @staticmethod
    def get_all_features(prices: List[float], klines: List, order_book: Dict) -> Dict:
        """
        提取所有机器学习特征
        
        整合所有指标,生成特征向量用于ML模型预测
        
        Args:
            prices: 价格列表
            klines: K线数据
            order_book: 订单簿数据
            
        Returns:
            Dict: 特征字典
        """
        features = {}
        
        if len(prices) < 50:
            return features
        
        # ==================
        # 1. 价格特征
        # ==================
        features['price'] = prices[-1]
        features['returns'] = (prices[-1] - prices[-50]) / prices[-50]
        
        # ==================
        # 2. MA特征 (移动平均)
        # ==================
        for period in [5, 10, 20, 50]:
            ma = sum(prices[-period:]) / period
            features[f'ma{period}'] = ma
            features[f'ma{period}_ratio'] = prices[-1] / ma
        
        # ==================
        # 3. RSI特征
        # ==================
        gains, losses = [], []
        for i in range(1, 15):
            change = prices[-i] - prices[-i-1]
            gains.append(change if change > 0 else 0)
            losses.append(abs(change) if change < 0 else 0)
        
        avg_gain = sum(gains) / 14
        avg_loss = sum(losses) / 14
        rs = avg_gain / avg_loss if avg_loss > 0 else 0
        features['rsi'] = 100 - (100 / (1 + rs))
        
        # ==================
        # 4. 布林带特征
        # ==================
        ma20 = sum(prices[-20:]) / 20
        std = (sum((p - ma20)**2 for p in prices[-20:]) / 20) ** 0.5
        features['bb_upper'] = ma20 + 2 * std
        features['bb_lower'] = ma20 - 2 * std
        
        bb_range = features['bb_upper'] - features['bb_lower']
        features['bb_position'] = (prices[-1] - features['bb_lower']) / bb_range if bb_range > 0 else 0.5
        
        # ==================
        # 5. 动量特征
        # ==================
        features['momentum_5'] = (prices[-1] - prices[-6]) / prices[-6]
        features['momentum_10'] = (prices[-1] - prices[-11]) / prices[-11]
        features['momentum_20'] = (prices[-1] - prices[-21]) / prices[-21]
        
        # ==================
        # 6. 波动率特征
        # ==================
        if len(prices) > 10:
            returns = [(prices[i] - prices[i-1])/prices[i-1] for i in range(1, 11)]
            features['volatility_10'] = np.std(returns) if returns else 0
        
        if len(prices) > 20:
            returns = [(prices[i] - prices[i-1])/prices[i-1] for i in range(1, 21)]
            features['volatility_20'] = np.std(returns) if returns else 0
        
        # ==================
        # 7. MACD特征
        # ==================
        features['macd'] = TechnicalIndicators._ema(prices, 12) - TechnicalIndicators._ema(prices, 26)
        features['macd_signal'] = TechnicalIndicators._ema(prices[-50:], 9)
        
        # ==================
        # 8. 订单流特征
        # ==================
        if order_book.get('bids') and order_book.get('asks'):
            bid_vol = sum(v for _, v in order_book['bids'][:10])
            ask_vol = sum(v for _, v in order_book['asks'][:10])
            features['delta'] = bid_vol - ask_vol
            features['imbalance'] = bid_vol / ask_vol if ask_vol > 0 else 1
            features['bid_ask_spread'] = (order_book['asks'][0][0] - order_book['bids'][0][0]) / prices[-1]
        
        # ==================
        # 9. 成交量特征
        # ==================
        if klines:
            volumes = [k['volume'] for k in klines[-20:]]
            features['volume_ma'] = sum(volumes) / 20
            features['volume_ratio'] = volumes[-1] / features['volume_ma'] if features['volume_ma'] > 0 else 1
            
            # CVD (累计成交量Delta)
            cvd = sum(
                k['volume'] if k['close'] > k['open'] else -k['volume'] 
                for k in klines[-20:]
            )
            features['cvd'] = cvd
        
        # ==================
        # 10. 趋势强度
        # ==================
        ma50 = sum(prices[-50:]) / 50
        ma200 = sum(prices[-200:]) / 200 if len(prices) >= 200 else ma50
        features['trend_strength'] = (ma50 - ma200) / ma200 if ma200 > 0 else 0
        
        return features
    
    @staticmethod
    def _ema(prices: List[float], period: int) -> float:
        """
        计算指数移动平均线 (EMA)
        
        Args:
            prices: 价格列表
            period: 周期
            
        Returns:
            float: EMA值
        """
        if len(prices) < period:
            return prices[-1] if prices else 0
        
        multiplier = 2 / (period + 1)
        ema = prices[0]
        for p in prices[1:]:
            ema = (p - ema) * multiplier + ema
        return ema


# ============================================================================
# 第五部分: 机器学习引擎 (ML Engine)
# ============================================================================

class MLEngine:
    """
    机器学习引擎类
    
    基于规则的多策略融合引擎
    
    Attributes:
        config: Config实例
        logger: Logger实例
        indicators: TechnicalIndicators实例
        weights: 各策略权重配置
    """
    
    def __init__(self, config: Config, logger: Logger):
        """初始化ML引擎"""
        self.config = config
        self.logger = logger
        self.indicators = TechnicalIndicators()
        
        # 策略权重配置
        self.weights = {
            'orderflow': 0.25,   # 订单流
            'rsi': 0.20,        # RSI
            'bollinger': 0.15,   # 布林带
            'momentum': 0.15,    # 动量
            'macd': 0.15,       # MACD
            'trend': 0.10        # 趋势
        }
    
    def predict(self, features: Dict) -> Tuple[str, float]:
        """
        ML预测信号 - 优化参数
        
        降低阈值以产生更多交易信号
        """
        
        # 1. 订单流信号
        of_score = 0
        if 'delta' in features and 'imbalance' in features:
            if features.get('delta', 0) > 0:
                of_score += 0.25
            if features.get('imbalance', 1) > 1.1:
                of_score += 0.25
            if features.get('cvd', 0) > 0:
                of_score += 0.2
        scores = {'orderflow': of_score * self.weights['orderflow']}
        
        # ==================
        # 2. RSI信号
        # 降低阈值
        rsi_score = 0
        if 'rsi' in features:
            rsi = features['rsi']
            if rsi < 35:  # 原来是30
                rsi_score = 0.7
            elif rsi < 45:  # 原来是40
                rsi_score = 0.4
            elif rsi > 65:  # 原来是70
                rsi_score = -0.7
            elif rsi > 55:  # 原来是60
                rsi_score = -0.4
        scores['rsi'] = rsi_score * self.weights['rsi']
        
        # ==================
        # 3. 布林带信号
        # 降低阈值
        bb_score = 0
        if 'bb_position' in features:
            bb = features['bb_position']
            if bb < 0.25:  # 原来是0.2
                bb_score = 0.6
            elif bb > 0.75:  # 原来是0.8
                bb_score = -0.6
        scores['bollinger'] = bb_score * self.weights['bollinger']
        
        # ==================
        # 4. 动量信号
        # 降低阈值
        mom_score = 0
        if 'momentum_10' in features and 'momentum_20' in features:
            mom = features['momentum_10'] * 0.6 + features['momentum_20'] * 0.4
            if mom > 0.03:  # 原来是0.05
                mom_score = 0.6
            elif mom > 0.01:  # 原来是0.02
                mom_score = 0.3
            elif mom < -0.03:  # 原来是-0.05
                mom_score = -0.6
            elif mom < -0.01:  # 原来是-0.02
                mom_score = -0.3
        scores['momentum'] = mom_score * self.weights['momentum']
        
        # ==================
        # 5. MACD信号
        # ==================
        macd_score = 0
        if 'macd' in features and 'macd_signal' in features:
            if features['macd'] > features['macd_signal'] * 1.01:
                macd_score = 0.6
            elif features['macd'] < features['macd_signal'] * 0.99:
                macd_score = -0.6
        scores['macd'] = macd_score * self.weights['macd']
        
        # ==================
        # 6. 趋势信号
        # ==================
        trend_score = 0
        if 'trend_strength' in features:
            trend = features['trend_strength']
            if trend > 0.02:
                trend_score = 0.5
            elif trend < -0.02:
                trend_score = -0.5
        scores['trend'] = trend_score * self.weights['trend']
        
        # ==================
        # 综合评分
        # ==================
        total_score = sum(scores.values())
        
        if total_score > 0.3:
            return "BUY", min(total_score, 1.0)
        elif total_score < -0.3:
            return "SELL", min(abs(total_score), 1.0)
        else:
            return "HOLD", abs(total_score)


# ============================================================================
# 第六部分: 策略引擎 (Strategy Engine)
# ============================================================================

class StrategyEngine:
    """
    策略引擎类
    
    负责生成交易信号,整合ML预测和过滤器
    
    Attributes:
        config: Config实例
        logger: Logger实例
        ml: MLEngine实例
        indicators: TechnicalIndicators实例
    """
    
    def __init__(self, config: Config, logger: Logger):
        """初始化策略引擎"""
        self.config = config
        self.logger = logger
        self.ml = MLEngine(config, logger)
        self.indicators = TechnicalIndicators()
    
    def generate_signal(self, prices: List[float], klines: List, 
                      order_book: Dict) -> Tuple[str, float]:
        """
        生成交易信号
        
        整合ML预测和过滤器
        
        Args:
            prices: 价格列表
            klines: K线数据
            order_book: 订单簿
            
        Returns:
            Tuple[str, float]: (信号, 置信度)
        """
        
        # 提取特征
        features = self.indicators.get_all_features(prices, klines, order_book)
        
        if not features:
            return "HOLD", 0.0
        
        # ML预测
        signal, confidence = self.ml.predict(features)
        
        # ==================
        # 过滤器
        # ==================
        
        # 1. 趋势过滤器 (逆势不交易)
        if 'trend_strength' in features:
            trend = features['trend_strength']
            if signal == "BUY" and trend < -0.03:
                return "HOLD", 0.0
            if signal == "SELL" and trend > 0.03:
                return "HOLD", 0.0
        
        # 2. 波动率过滤器 (波动过大降低置信度)
        if 'volatility_20' in features:
            vol = features['volatility_20']
            if vol > 0.05:
                confidence *= 0.7
        
        return signal, confidence


# ============================================================================
# 第七部分: 风险管理 (Risk Management)
# ============================================================================

class RiskManager:
    """
    风险管理类
    
    负责仓位管理、止损止盈、回撤控制
    
    Attributes:
        config: Config实例
        logger: Logger实例
        positions: 持仓字典
        stats: 统计数据
    """
    
    def __init__(self, config: Config, logger: Logger):
        """初始化风控"""
        self.config = config
        self.logger = logger
        
        # 持仓记录 {symbol: {'qty': 数量, 'entry': 开仓价, 'side': 方向}}
        self.positions = {}
        
        # 统计
        self.stats = {
            'trades': 0,      # 总交易次数
            'wins': 0,       # 盈利次数
            'pnl': 0,        # 总盈亏
            'peak': 0,       # 资金高点
            'dd': 0          # 最大回撤
        }
    
    def check(self, symbol: str, entry: float, current: float, 
             side: str) -> Tuple[bool, str]:
        """
        检查是否触发止损/止盈
        
        Args:
            symbol: 交易对
            entry: 开仓价
            current: 当前价
            side: 持仓方向 ('LONG' 或 'SHORT')
            
        Returns:
            Tuple[bool, str]: (是否平仓, 原因)
        """
        cfg = self.config.SYMBOLS.get(symbol, {})
        stop_loss = cfg.get('stop_loss', 0.02)
        
        # 计算盈亏
        if side == "LONG":
            pnl = (current - entry) / entry
        else:
            pnl = (entry - current) / entry
        
        # 止损检查
        if pnl <= -stop_loss:
            return True, "STOP_LOSS"
        
        # 止盈检查
        if pnl >= self.config.TAKE_PROFIT:
            return True, "TAKE_PROFIT"
        
        return False, ""
    
    def record(self, pnl: float):
        """
        记录交易结果
        
        Args:
            pnl: 盈亏比例
        """
        self.stats['trades'] += 1
        if pnl > 0:
            self.stats['wins'] += 1
        self.stats['pnl'] += pnl
        
        # 更新最大回撤
        if self.stats['pnl'] > self.stats['peak']:
            self.stats['peak'] = self.stats['pnl']
        
        dd = (self.stats['peak'] - self.stats['pnl']) / (1 + self.stats['peak'])
        if dd > self.stats['dd']:
            self.stats['dd'] = dd
    
    def can_trade(self, total_pos_ratio: float) -> bool:
        """
        检查是否可以开仓
        
        Args:
            total_pos_ratio: 当前仓位比例
            
        Returns:
            bool: 是否可以开仓
        """
        return total_pos_ratio < self.config.MAX_POSITION


# ============================================================================
# 第八部分: 订单执行 (Order Execution)
# ============================================================================

class OrderExecutor:
    """
    订单执行类
    
    负责发送订单到Binance API
    
    Attributes:
        config: Config实例
        logger: Logger实例
    """
    
    def __init__(self, config: Config, logger: Logger):
        """初始化订单执行器"""
        self.config = config
        self.logger = logger
    
    def order(self, symbol: str, side: str, quantity: float) -> Dict:
        """
        发送市价单
        
        Args:
            symbol: 交易对
            side: 方向 ('BUY' 或 'SELL')
            quantity: 数量
            
        Returns:
            Dict: 订单结果
        """
        self.logger.info(f"下单 {symbol} {side} {quantity}")
        
        # TODO: 实现真实API调用 (需要API Secret)
        return {
            'status': 'SIMULATED',  # 模拟模式
            'symbol': symbol,
            'side': side,
            'quantity': quantity
        }


# ============================================================================
# 第九部分: 交易系统主程序 (Main Trading System)
# ============================================================================

class TradingSystem:
    """
    交易系统主类
    
    整合所有模块,运行交易逻辑
    
    Attributes:
        config: 配置
        logger: 日志
        data: 数据采集器
        strategy: 策略引擎
        risk: 风险管理
        executor: 订单执行
        capital: 初始资金
        positions: 持仓
    """
    
    def __init__(self, capital: float = 1000):
        """
        初始化交易系统
        
        Args:
            capital: 初始资金 (默认1000 USDT)
        """
        # 初始化各模块
        self.config = Config()
        self.logger = Logger("DragonMax-v1.2-ML")
        
        self.data = DataCollector(self.config, self.logger)
        self.strategy = StrategyEngine(self.config, self.logger)
        self.risk = RiskManager(self.config, self.logger)
        self.executor = OrderExecutor(self.config, self.logger)
        
        self.capital = capital
        self.positions = {}
        
        self.logger.info(f"ML增强交易系统启动, 资金: ${capital}")
        self.logger.info("目标: 年化60%+, 回撤<10%")
    
    def get_data(self, symbol: str) -> Dict:
        """
        获取交易对数据
        
        Args:
            symbol: 交易对
            
        Returns:
            Dict: 包含 price, prices, klines, order_book
        """
        price = self.data.get_price(symbol)
        klines = self.data.get_klines(symbol, '1h', 200)
        order_book = self.data.get_order_book(symbol)
        prices = [k['close'] for k in klines]
        
        return {
            'price': price,
            'prices': prices,
            'klines': klines,
            'order_book': order_book
        }
    
    def run(self):
        """
        运行交易系统主循环
        
        每分钟检查一次信号并执行交易
        """
        self.logger.info("=" * 50)
        self.logger.info("DragonMax 交易系统运行中")
        self.logger.info("=" * 50)
        
        while True:
            try:
                # 遍历所有交易对
                for symbol in self.config.SYMBOLS:
                    # 获取数据
                    data = self.get_data(symbol)
                    
                    if not data['prices']:
                        continue
                    
                    # 生成信号
                    signal, confidence = self.strategy.generate_signal(
                        data['prices'], 
                        data['klines'], 
                        data['order_book']
                    )
                    
                    self.logger.info(f"{symbol}: {signal} (置信度: {confidence:.2f})")
                    
                    # ==================
                    # 买入逻辑
                    # ==================
                    if signal == "BUY" and confidence > 0.5:
                        # 检查仓位
                        total_pos = sum(
                            p['qty'] * p['entry'] 
                            for p in self.positions.values() 
                            if p['qty'] > 0
                        )
                        
                        if self.risk.can_trade(total_pos / self.capital):
                            # 计算仓位
                            cfg = self.config.SYMBOLS[symbol]
                            qty = self.capital * cfg['position'] / data['price']
                            
                            # 下单
                            self.executor.order(symbol, "BUY", qty)
                            
                            # 记录持仓
                            self.positions[symbol] = {
                                'qty': qty,
                                'entry': data['price'],
                                'side': 'LONG'
                            }
                            
                            self.logger.info(f"买入 {symbol} @ ${data['price']}")
                    
                    # ==================
                    # 卖出逻辑
                    # ==================
                    elif signal == "SELL":
                        if symbol in self.positions and self.positions[symbol]['qty'] > 0:
                            pos = self.positions[symbol]
                            
                            # 检查是否平仓
                            close, reason = self.risk.check(
                                symbol, 
                                pos['entry'], 
                                data['price'], 
                                pos['side']
                            )
                            
                            if close:
                                # 平仓
                                self.executor.order(symbol, "SELL", pos['qty'])
                                
                                # 计算盈亏
                                pnl = (data['price'] - pos['entry']) / pos['entry']
                                self.risk.record(pnl)
                                
                                self.positions[symbol] = {'qty': 0, 'entry': 0, 'side': ''}
                                
                                self.logger.info(
                                    f"平仓 {symbol} @ ${data['price']}, {reason}"
                                )
                
                # 休息1分钟
                time.sleep(60)
                
            except KeyboardInterrupt:
                self.logger.info("系统停止")
                break
            except Exception as e:
                self.logger.error(f"错误: {e}")
                time.sleep(10)
    
    def backtest(self, symbol: str, days: int = 30) -> Dict:
        """
        回测功能
        
        Args:
            symbol: 交易对
            days: 回测天数
            
        Returns:
            Dict: 回测结果
        """
        self.logger.info(f"回测 {symbol}...")
        
        # 获取历史数据
        klines = self.data.get_klines(symbol, '1h', days * 24)
        
        if not klines:
            return {'error': '数据获取失败'}
        
        # 模拟交易
        trades = []
        position = 0
        entry_price = 0
        
        for i in range(100, len(klines)):
            prices = [k['close'] for k in klines[:i+1]]
            klines_slice = klines[:i+1]
            order_book = {'bids': [], 'asks': []}
            
            signal, conf = self.strategy.generate_signal(
                prices, klines_slice, order_book
            )
            
            price = klines[i]['close']
            
            # 买入信号
            if signal == "BUY" and position == 0 and conf > 0.5:
                position = 1
                entry_price = price
                trades.append({'type': 'BUY', 'price': entry_price})
            
            # 卖出信号
            elif signal == "SELL" and position == 1:
                pnl = (price - entry_price) / entry_price
                trades.append({
                    'type': 'SELL', 
                    'price': price, 
                    'pnl': pnl
                })
                position = 0
        
        # 统计
        closed = [t for t in trades if 'pnl' in t]
        wins = sum(1 for t in closed if t['pnl'] > 0)
        win_rate = wins / len(closed) if closed else 0
        total_pnl = sum(t['pnl'] for t in closed)
        annual_pnl = total_pnl / days * 365 if days > 0 else 0
        
        result = {
            'symbol': symbol,
            'trades': len(closed),
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'annual_pnl': annual_pnl
        }
        
        self.logger.info(
            f"{symbol}: 交易{len(closed)}次, "
            f"胜率{win_rate*100:.1f}%, "
            f"年化{annual_pnl*100:.1f}%"
        )
        
        return result


# ============================================================================
# 第十部分: 程序入口 (Main Entry)
# ============================================================================

if __name__ == "__main__":
    """
    程序入口
    
    使用方法:
        python trading_system.py
    """
    print("=" * 50)
    print("总控龙宝交易系统 v1.2 - ML增强版")
    print("目标: 年化60%+, 回撤<10%")
    print("=" * 50)
    
    # 创建交易系统 (初始资金1000 USDT)
    bot = TradingSystem(capital=1000)
    
    # 回测所有币种
    print("\n开始回测...")
    
    results = []
    for symbol in ['BTC', 'ETH', 'XRP', 'SOL', 'BNB', 'ADA']:
        result = bot.backtest(symbol, days=30)
        results.append(result)
    
    # 汇总
    avg_annual = sum(r.get('annual_pnl', 0) for r in results) / len(results)
    
    print(f"\n平均年化收益: {avg_annual*100:.1f}%")
    print("回测完成!")
