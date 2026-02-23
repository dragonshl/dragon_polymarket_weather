# 总控龙宝交易系统 - 代码说明文档

## 目录
1. [系统架构](#系统架构)
2. [数据层](#数据层)
3. [策略层](#策略层)
4. [风控层](#风控层)
5. [执行层](#执行层)
6. [配置说明](#配置说明)

---

## 1. 系统架构

### 1.1 整体架构图

```
┌─────────────────────────────────────────────────────────────┐
│                    总控龙宝交易系统                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  数据层 ─── 策略层 ─── 风控层 ─── 执行层                   │
│                                                             │
│  • API数据    • 信号生成    • 仓位管理   • 订单执行        │
│  • 订单簿     • 信号融合    • 止损止盈   • 日志记录        │
│  • K线        • ML模型      • 动态调整   • 报告生成        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 模块关系

```python
# 模块调用关系
DataCollector.get_data()     # 获取数据
    ↓
StrategyEngine.generate_signal()  # 生成信号
    ↓
RiskManager.check_risk()     # 风控检查
    ↓
OrderExecutor.place_order()  # 执行订单
```

---

## 2. 数据层

### 2.1 数据获取模块

**文件**: 主要通过 Binance API 获取

```python
class DataCollector:
    """
    数据采集器
    
    功能:
    - 获取实时价格
    - 获取K线数据
    - 获取订单簿数据
    - 获取24小时统计
    """
    
    # API端点
    PRICE_ENDPOINT = "/api/v3/ticker/price"
    KLINE_ENDPOINT = "/api/v3/klines"
    ORDERBOOK_ENDPOINT = "/api/v3/depth"
    STATS_ENDPOINT = "/api/v3/ticker/24hr"
    
    def get_price(self, symbol: str) -> float:
        """
        获取实时价格
        
        参数:
            symbol: 交易对，如 'BTCUSDT'
            
        返回:
            float: 最新价格
        """
        response = requests.get(BASE_URL + self.PRICE_ENDPOINT, 
                              params={"symbol": symbol})
        return float(response.json()["price"])
    
    def get_klines(self, symbol: str, interval: str, limit: int) -> list:
        """
        获取K线数据
        
        参数:
            symbol: 交易对
            interval: 时间周期 ('1h', '4h', '1d', '1w')
            limit: 数据条数
            
        返回:
            list: K线数据数组
        """
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        }
        return requests.get(BASE_URL + self.KLINE_ENDPOINT, 
                           params=params).json()
```

### 2.2 订单簿数据

```python
class OrderBookData:
    """
    订单簿数据处理
    
    属性:
        bids: 买单列表 [(价格, 数量), ...]
        asks: 卖单列表 [(价格, 数量), ...]
    """
    
    def calculate_imbalance(self) -> float:
        """
        计算订单簿不平衡度
        
        公式:
            imbalance = 买单总量 / 卖单总量
            
        返回:
            >1: 买方主导
            <1: 卖方主导
        """
        bid_volume = sum(vol for _, vol in self.bids[:10])
        ask_volume = sum(vol for _, vol in self.asks[:10])
        
        if ask_volume == 0:
            return 999  # 极端情况
        
        return bid_volume / ask_volume
```

---

## 3. 策略层

### 3.1 订单流策略模块

#### 3.1.1 Delta 指标

```python
class OrderFlowFeatures:
    """
    订单流特征工程
    
    用于从订单簿和成交数据中提取特征
    """
    
    def calculate_delta(self, order_book: dict) -> float:
        """
        计算Delta (买卖流量差)
        
        原理:
            Delta = 主动买入成交量 - 主动卖出成交量
            
        正值: 买方主导，价格可能上涨
        负值: 卖方主导，价格可能下跌
        
        参数:
            order_book: 订单簿数据
            
        返回:
            float: Delta值
        """
        # 简化的Delta计算
        bid_volume = sum(b['volume'] for b in order_book['bids'])
        ask_volume = sum(a['volume'] for a in order_book['asks'])
        
        return bid_volume - ask_volume
    
    def calculate_cvd(self, trades: list) -> float:
        """
        计算CVD (累计成交量Delta)
        
        原理:
            CVD = 累计(买入量 - 卖出量)
            
        用于判断趋势方向:
            CVD持续上升: 多头趋势
            CVD持续下降: 空头趋势
        """
        cvd = 0
        for trade in trades:
            volume = trade['volume']
            # 假设 trade['is_buyer_maker'] 表示是否买方成交
            if trade.get('is_buyer_maker', False):
                cvd += volume
            else:
                cvd -= volume
        
        return cvd
```

#### 3.1.2 Stop Hunt 策略

```python
class StopHuntStrategy:
    """
    扫止损策略
    
    原理:
        当价格快速跌破支撑位(止损集中区)后又快速收回，
        表明是机构扫止损行为，之后价格往往会反转。
        
    信号:
        BUY: 检测到扫止损后反转
        SELL: 高位扫止损
    """
    
    def detect_stop_hunt(self, prices: list, stop_levels: list) -> bool:
        """
        检测扫止损行为
        
        参数:
            prices: 价格序列
            stop_levels: 止损价位列表
            
        返回:
            bool: 是否检测到扫止损
        """
        if len(prices) < 3:
            return False
        
        # 价格快速跌破止损位又收回
        recent_prices = prices[-3:]
        
        # 条件1: 价格快速下跌
        if recent_prices[0] - recent_prices[2] > 0.02:  # 2%以上
            
            # 条件2: 接近止损位
            for stop in stop_levels:
                if min(recent_prices) < stop < recent_prices[0]:
                    # 条件3: 快速收回
                    if recent_prices[-1] > stop:
                        return True
        
        return False
```

#### 3.1.3 Absorption 策略

```python
class AbsorptionStrategy:
    """
    吸筹策略
    
    原理:
        当市场出现大量被动买单(挂在bid侧)但价格不下跌，
        说明有主力吸筹，后市看涨。
        
    信号:
        BUY: 检测到吸筹行为
    """
    
    def detect_absorption(self, trades: list, threshold: float = 0.7) -> tuple:
        """
        检测吸筹行为
        
        参数:
            trades: 成交记录列表
            threshold: 被动成交比例阈值
            
        返回:
            (bool, float): (是否吸筹, 被动成交比例)
        """
        passive_volume = 0  # 被动成交(挂单成交)
        aggressive_volume = 0  # 主动成交
        
        for trade in trades:
            volume = trade['volume']
            # 通过价格判断主动/被动
            # 略复杂，这里简化处理
            
            if trade.get('is_passive', False):
                passive_volume += volume
            else:
                aggressive_volume += volume
        
        total = passive_volume + aggressive_volume
        if total == 0:
            return False, 0
        
        ratio = passive_volume / total
        
        # 70%以上被动成交认为是吸筹
        return ratio > threshold, ratio
```

### 3.2 传统技术指标

#### 3.2.1 RSI 策略

```python
class RSIStrategy:
    """
    RSI 超买超卖策略
    
    原理:
        RSI > 70: 超买，后市可能下跌
        RSI < 30: 超卖，后市可能上涨
        
    参数:
        period: RSI周期 (默认14)
        overbought: 超买阈值 (默认70)
        oversold: 超卖阈值 (默认30)
    """
    
    def __init__(self, period: int = 14, 
                 overbought: float = 70, 
                 oversold: float = 30):
        self.period = period
        self.overbought = overbought
        self.oversold = oversold
    
    def calculate_rsi(self, prices: list) -> float:
        """
        计算RSI
        
        公式:
            RSI = 100 - (100 / (1 + RS))
            RS = 平均涨幅 / 平均跌幅
        """
        if len(prices) < self.period + 1:
            return 50  # 数据不足返回中性值
        
        gains = []
        losses = []
        
        for i in range(1, len(prices)):
            change = prices[i] - prices[i-1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))
        
        avg_gain = sum(gains[-self.period:]) / self.period
        avg_loss = sum(losses[-self.period:]) / self.period
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def signal(self, prices: list) -> tuple:
        """
        生成交易信号
        
        返回:
            (str, str): (信号, 原因)
        """
        rsi = self.calculate_rsi(prices)
        
        if rsi < self.oversold:
            return "BUY", f"RSI超卖({rsi:.1f})"
        elif rsi > self.overbought:
            return "SELL", f"RSI超买({rsi:.1f})"
        else:
            return "HOLD", f"RSI中性({rsi:.1f})"
```

#### 3.2.2 动量策略

```python
class MomentumStrategy:
    """
    动量策略
    
    原理:
        过去上涨的资产未来继续上涨
        过去下跌的资产未来继续下跌
        
    参数:
        lookback: 回看周期
        threshold: 动量阈值
    """
    
    def __init__(self, lookback: int = 20, threshold: float = 0.05):
        self.lookback = lookback
        self.threshold = threshold
    
    def calculate_momentum(self, prices: list) -> float:
        """
        计算动量
        
        公式:
            momentum = (当前价格 - N日前价格) / N日前价格
        """
        if len(prices) < self.lookback:
            return 0
        
        current = prices[-1]
        past = prices[-self.lookback]
        
        return (current - past) / past
    
    def signal(self, prices: list) -> tuple:
        momentum = self.calculate_momentum(prices)
        
        if momentum > self.threshold:
            return "BUY", f"正动量+{momentum*100:.1f}%"
        elif momentum < -self.threshold:
            return "SELL", f"负动量{momentum*100:.1f}%"
        else:
            return "HOLD", "动量不足"
```

### 3.3 机器学习模块

```python
class EnsembleModel:
    """
    集成学习模型
    
    原理:
        结合多个机器学习模型的预测，
        通过加权投票得到最终信号。
        
    模型:
        - 随机森林: 适合分类，稳定性好
        - XGBoost: 梯度提升，精度高
        - LSTM: 时序数据，效果好
    """
    
    def __init__(self):
        # 初始化各模型
        self.rf_model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10
        )
        self.xgb_model = XGBClassifier(
            n_estimators=100,
            max_depth=6,
            learning_rate=0.1
        )
        self.lstm_model = self._build_lstm()
        
        # 模型权重 (根据历史表现)
        self.weights = {
            'rf': 0.25,
            'xgb': 0.35,
            'lstm': 0.40
        }
    
    def predict(self, features: dict) -> tuple:
        """
        预测交易信号
        
        参数:
            features: 特征字典
            
        返回:
            (str, float): (信号, 置信度)
        """
        # 各模型预测
        rf_pred = self.rf_model.predict([features])[0]
        rf_prob = self.rf_model.predict_proba([features])[0]
        
        xgb_pred = self.xgb_model.predict([features])[0]
        xgb_prob = self.xgb_model.predict_proba([features])[0]
        
        lstm_pred = self.lstm_model.predict([features])[0]
        lstm_prob = self.lstm_model.predict_proba([features])[0]
        
        # 加权投票
        buy_score = (
            rf_prob[1] * self.weights['rf'] +
            xgb_prob[1] * self.weights['xgb'] +
            lstm_prob[1] * self.weights['lstm']
        )
        
        sell_score = (
            rf_prob[0] * self.weights['rf'] +
            xgb_prob[0] * self.weights['xgb'] +
            lstm_prob[0] * self.weights['lstm']
        )
        
        confidence = max(buy_score, sell_score)
        
        if buy_score > sell_score and confidence > 0.6:
            return "BUY", confidence
        elif sell_score > buy_score and confidence > 0.6:
            return "SELL", confidence
        else:
            return "HOLD", confidence
```

---

## 4. 风控层

### 4.1 风控管理器

```python
class RiskManager:
    """
    风险管理器
    
    功能:
    - 仓位计算
    - 止损止盈
    - 风险检查
    - 动态调整
    """
    
    def __init__(self):
        # 基础参数
        self.max_position = 0.30    # 最大仓位30%
        self.stop_loss = 0.02       # 2%止损
        self.take_profit = 0.03      # 3%止盈
        self.max_leverage = 10       # 最大杠杆10x
        
        # 动态参数
        self.kelly_fraction = 0.25  # 凯利系数
    
    def calculate_position(self, 
                         win_rate: float, 
                         avg_win: float, 
                         avg_loss: float,
                         volatility: float = 0.03) -> float:
        """
        计算最佳仓位 (凯利公式)
        
        公式:
            K% = W - (1-W)/R
            K% = 胜率 - (1-胜率) / 盈亏比
            
        参数:
            win_rate: 胜率 (0-1)
            avg_win: 平均盈利比例
            avg_loss: 平均亏损比例
            volatility: 当前波动率
            
        返回:
            float: 建议仓位比例
        """
        if avg_loss == 0:
            return self.max_position
        
        reward_ratio = avg_win / avg_loss
        
        # 凯利公式
        kelly = win_rate - ((1 - win_rate) / reward_ratio)
        
        # 使用分数凯利降低风险
        optimal_kelly = kelly * self.kelly_fraction
        
        # 限制范围
        position = max(0, min(optimal_kelly, self.max_position))
        
        # 根据波动率调整
        if volatility > 0.05:
            position *= 0.7  # 高波动减仓
        
        return position
    
    def check_stop_loss(self, entry_price: float, 
                       current_price: float, 
                       direction: str) -> bool:
        """
        检查是否触发止损
        
        参数:
            entry_price: 开仓价格
            current_price: 当前价格
            direction: 'LONG' 或 'SHORT'
            
        返回:
            bool: 是否触发止损
        """
        if direction == "LONG":
            pnl = (current_price - entry_price) / entry_price
        else:
            pnl = (entry_price - current_price) / entry_price
        
        return pnl <= -self.stop_loss
    
    def calculate_leverage(self, 
                         symbol: str, 
                         volatility: float,
                         market Regime: str) -> int:
        """
        计算动态杠杆
        
        参数:
            symbol: 币种
            volatility: 波动率
            market_regime: 市场状态 ('bull', 'bear', 'neutral')
            
        返回:
            int: 推荐杠杆
        """
        # 基础杠杆
        base_leverage = 5
        
        # 波动率调整
        if volatility > 0.05:
            base_leverage -= 2
        elif volatility > 0.03:
            base_leverage -= 1
        
        # 市场状态调整
        if market_regime == "bull":
            base_leverage += 1
        elif market_regime == "bear":
            base_leverage -= 2
        
        # 币种调整
        high_volatility_coins = ['DOGE', 'SOL', 'XRP']
        if symbol in high_volatility_coins:
            base_leverage = min(base_leverage, 3)
        
        return max(1, min(base_leverage, self.max_leverage))
```

### 4.2 风险平价组合

```python
class RiskParity:
    """
    风险平价组合
    
    原理:
        各资产对组合风险的贡献相等
        权重 = 1/波动率
    """
    
    def __init__(self, target_volatility: float = 0.15):
        self.target_volatility = target_volatility
    
    def calculate_weights(self, returns_dict: dict) -> dict:
        """
        计算风险平价权重
        
        参数:
            returns_dict: {币种: 收益率列表}
            
        返回:
            dict: {币种: 权重}
        """
        # 计算各币种波动率 (年化)
        volatilities = {}
        for symbol, returns in returns_dict.items():
            if len(returns) > 0:
                volatilities[symbol] = np.std(returns) * np.sqrt(252)
            else:
                volatilities[symbol] = 0.5  # 默认
        
        # 风险平价权重 = 1/波动率
        inv_vol = {s: 1/v for s, v in volatilities.items() if v > 0}
        total = sum(inv_vol.values())
        weights = {s: v/total for s, v in inv_vol.items()}
        
        # 调整到目标波动率
        current_vol = sum(
            w * v for w, v in zip(weights.values(), volatilities.values())
            if w > 0 and v > 0
        )
        
        if current_vol > 0:
            leverage = self.target_volatility / current_vol
        else:
            leverage = 1
        
        return {s: w * leverage for s, w in weights.items()}
```

---

## 5. 执行层

### 5.1 订单执行器

```python
class OrderExecutor:
    """
    订单执行器
    
    功能:
    - 下单
    - 取消订单
    - 查询订单状态
    - 日志记录
    """
    
    def __init__(self, api_key: str, secret_key: str):
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_url = "https://api.binance.com"
        
    def place_order(self, 
                   symbol: str, 
                   side: str,  # 'BUY' or 'SELL'
 str,  #                   order_type: 'LIMIT' or 'MARKET'
                   quantity: float,
                   price: float = None) -> dict:
        """
        下单
        
        参数:
            symbol: 交易对 (如 'BTCUSDT')
            side: 买卖方向
            order_type: 订单类型
            quantity: 数量
            price: 价格 (LIMIT单需要)
            
        返回:
            dict: 订单结果
        """
        # 签名生成 (省略)
        # ...
        
        # 发送请求
        # response = requests.post(...)
        
        # 记录日志
        self._log_order(symbol, side, order_type, quantity, price)
        
        return {"orderId": "xxx", "status": "FILLED"}
    
    def _log_order(self, symbol, side, order_type, quantity, price):
        """
        记录订单日志
        """
        log = {
            "time": datetime.now().isoformat(),
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": quantity,
            "price": price
        }
        # 写入日志文件
        print(f"Order logged: {log}")
```

---

## 6. 配置说明

### 6.1 配置文件结构

```json
{
  "system": {
    "name": "总控龙宝交易系统",
    "version": "1.0",
    "mode": "simulation"  // simulation / live
  },
  
  "trading": {
    "symbols": ["BTC", "ETH", "XRP", "SOL", "ADA", "DOGE"],
    "max_position": 0.30,
    "max_leverage": 10,
    "stop_loss": 0.02,
    "take_profit": 0.03
  },
  
  "strategies": {
    "order_flow": {
      "enabled": true,
      "weight": 0.30
    },
    "ml_ensemble": {
      "enabled": true,
      "weight": 0.25
    },
    "momentum": {
      "enabled": true,
      "weight": 0.20
    },
    "arbitrage": {
      "enabled": true,
      "weight": 0.15
    },
    "grid": {
      "enabled": true,
      "weight": 0.10
    }
  },
  
  "api": {
    "binance": {
      "api_key": "YOUR_API_KEY",
      "secret_key": "YOUR_SECRET_KEY"
    }
  }
}
```

### 6.2 启动配置

```python
# 初始化系统
def initialize_system():
    """
    初始化交易系统
    """
    # 1. 加载配置
    config = load_config('config.json')
    
    # 2. 初始化数据收集器
    data_collector = DataCollector(config['api'])
    
    # 3. 初始化策略引擎
    strategy_engine = StrategyEngine(config['strategies'])
    
    # 4. 初始化风控
    risk_manager = RiskManager(config['trading'])
    
    # 5. 初始化订单执行器
    order_executor = OrderExecutor(
        config['api']['binance']['api_key'],
        config['api']['binance']['secret_key']
    )
    
    return TradingSystem(
        data_collector,
        strategy_engine,
        risk_manager,
        order_executor
    )
```

---

## 附录: 函数索引

| 模块 | 函数 | 说明 |
|------|------|------|
| DataCollector | get_price() | 获取实时价格 |
| DataCollector | get_klines() | 获取K线数据 |
| OrderFlow | calculate_delta() | 计算Delta |
| OrderFlow | calculate_cvd() | 计算CVD |
| OrderFlow | detect_stop_hunt() | 检测扫止损 |
| OrderFlow | detect_absorption() | 检测吸筹 |
| Strategy | calculate_rsi() | 计算RSI |
| Strategy | calculate_momentum() | 计算动量 |
| ML | predict() | ML预测 |
| Risk | calculate_position() | 计算仓位 |
| Risk | check_stop_loss() | 检查止损 |
| Risk | calculate_leverage() | 计算杠杆 |
| Executor | place_order() | 下单 |

---

**文档版本**: v1.0  
**更新日期**: 2026-02-23  
**维护者**: 总控龙宝 🐉
