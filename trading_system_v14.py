#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
总控龙宝交易系统 v1.4 - 安全加固版
"""

import os
import requests
import numpy as np
import logging
from typing import Dict, List, Tuple

class Config:
    API_KEY = os.getenv("BINANCE_API_KEY", "")
    API_SECRET = os.getenv("BINANCE_SECRET", "")
    BASE_URL = "https://api.binance.com"
    
    MAX_POSITION = 0.20
    MAX_LEVERAGE = 3
    STOP_LOSS = 0.015
    TAKE_PROFIT = 0.025
    MAX_DRAWDOWN = 0.10
    DAILY_LOSS_LIMIT = 0.05
    
    SYMBOLS = {
        'BTC': {'position': 0.08, 'leverage': 3},
        'ETH': {'position': 0.06, 'leverage': 3},
        'BNB': {'position': 0.04, 'leverage': 2},
    }

class Logger:
    def __init__(self):
        self.logger = logging.getLogger("DragonMax")
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            h = logging.StreamHandler()
            h.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
            self.logger.addHandler(h)
    
    def info(self, m): self.logger.info(m)
    def error(self, m): self.logger.error(m)
    def warning(self, m): self.logger.warning(m)

class DataCollector:
    def __init__(self):
        self.session = requests.Session()
    
    def get_klines(self, symbol, interval='1d', limit=365):
        try:
            r = self.session.get(
                f"{Config.BASE_URL}/api/v3/klines",
                params={'symbol': f"{symbol}USDT", 'interval': interval, 'limit': limit},
                timeout=10
            )
            return [{'close': float(k[4])} for k in r.json()]
        except:
            return []

class Strategy:
    def signal(self, prices):
        if len(prices) < 50:
            return "HOLD", 0.0
        
        # RSI
        gains = []
        losses = []
        for i in range(1, 15):
            c = prices[-i] - prices[-i-1]
            gains.append(c if c > 0 else 0)
            losses.append(abs(c) if c < 0 else 0)
        
        avg_g = sum(gains) / 14
        avg_l = sum(losses) / 14
        rsi = 100 - (100 / (1 + avg_g/avg_l)) if avg_l > 0 else 50
        
        # MA
        ma20 = sum(prices[-20:]) / 20
        ma50 = sum(prices[-50:]) / 50
        
        score = 0
        if rsi < 35: score += 0.5
        elif rsi > 65: score -= 0.5
        if ma20 > ma50: score += 0.3
        elif ma20 < ma50: score -= 0.3
        
        if score > 0.6: return "BUY", abs(score)
        elif score < -0.6: return "SELL", abs(score)
        return "HOLD", abs(score)

class Backtest:
    def run(self, symbol, days=365):
        dc = DataCollector()
        st = Strategy()
        
        klines = dc.get_klines(symbol, '1d', days)
        if not klines:
            return {'error': '数据获取失败'}
        
        prices = [k['close'] for k in klines]
        
        trades = []
        position = 0
        entry = 0
        
        for i in range(50, len(prices)):
            signal, conf = st.signal(prices[:i+1])
            price = prices[i]
            
            if signal == "BUY" and position == 0:
                position = 1
                entry = price
                trades.append(('BUY', entry))
            
            elif signal == "SELL" and position == 1:
                pnl = (price - entry) / entry
                
                # 止损检查
                if abs(pnl) >= Config.STOP_LOSS:
                    trades.append(('SELL', price, pnl))
                    position = 0
                # 止盈检查
                elif pnl >= Config.TAKE_PROFIT:
                    trades.append(('SELL', price, Config.TAKE_PROFIT))
                    position = 0
        
        closed = [t for t in trades if len(t) == 3]
        wins = sum(1 for t in closed if t[2] > 0)
        win_rate = wins / len(closed) if closed else 0
        total_pnl = sum(t[2] for t in closed)
        annual_pnl = total_pnl / days * 365
        
        return {
            'trades': len(closed),
            'win_rate': win_rate,
            'annual_pnl': annual_pnl
        }

if __name__ == "__main__":
    print("=" * 50)
    print("总控龙宝 v1.4 安全加固版")
    print("=" * 50)
    
    bt = Backtest()
    
    print("\n真实历史回测 (1年)")
    print("-" * 50)
    
    total = 0
    for sym in ['BTC', 'ETH', 'BNB']:
        r = bt.run(sym, 365)
        if 'error' not in r:
            print(f"{sym}: {r['trades']}次, 胜率{r['win_rate']*100:.1f}%, 年化{r['annual_pnl']*100:.1f}%")
            total += r['annual_pnl']
    
    avg = total / 3
    print("-" * 50)
    print(f"平均年化: {avg*100:.1f}%")
    print("=" * 50)
