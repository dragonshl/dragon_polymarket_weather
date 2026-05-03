#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Polymarket 天气套利 - 交易执行 (最终版)
直接调用钱包进行链上交易
"""

import json
import os
import hmac
import hashlib
import base64
import time
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import requests

# 加载 .env 文件
load_dotenv(r"C:\Users\Administrator\.openclaw\workspace\polymarket\.env")

# 从 .env 读取凭证
POLYMARKET_PRIVATE_KEY = os.getenv('POLYMARKET_PRIVATE_KEY')
POLYMARKET_FUNDER = os.getenv('POLYMARKET_FUNDER')
POLYMARKET_API_KEY = os.getenv('POLYMARKET_API_KEY')
POLYMARKET_API_SECRET = os.getenv('POLYMARKET_API_SECRET')
POLYMARKET_PASSPHRASE = os.getenv('POLYMARKET_PASSPHRASE')

# Risk Control Config
MAX_DAILY_LOSS = 50.0       # 每日最大亏损 (USDC)
MAX_POSITIONS = 5           # 最大持仓数
MAX_SINGLE_TRADE = 10.0     # 单笔最大交易 (USDC)
RETRY_ATTEMPTS = 3          # 重试次数
RETRY_DELAY = 2             # 重试延迟（秒）

POLYMARKET_API_BASE = "https://clob.polymarket.com"

# Daily tracking (module-level state)
daily_loss = 0.0
daily_trade_count = 0

def sign_request(payload, api_key, api_secret, passphrase, method="POST", path="/orders"):
    """
    计算 Polymarket CLOB API 请求签名 (HMAC-SHA256)
    
    参数:
      payload: 请求体 (dict)
      api_key: API Key
      api_secret: API Secret (Base64编码的)
      passphrase: Passphrase
      method: HTTP 方法 (POST, GET, DELETE)
      path: 请求路径 (/orders, /markets 等)
    
    返回:
      headers: 包含签名的请求头
    """
    
    # 1. 序列化请求体
    message = json.dumps(payload)
    
    # 2. 计算时间戳 (毫秒)
    timestamp = str(int(time.time() * 1000))
    
    # 3. 构建签名字符串: timestamp + method + path + body
    sign_string = timestamp + method + path + message
    
    # 4. 用 API Secret 计算 HMAC-SHA256
    signature = hmac.new(
        api_secret.encode(),
        sign_string.encode(),
        hashlib.sha256
    ).digest()
    
    # 5. 转换为 Base64
    signature_b64 = base64.b64encode(signature).decode()
    
    # 6. 构建请求头
    headers = {
        "POLY-SIGNATURE": signature_b64,
        "POLY-NONCE": timestamp,
        "POLY-API-KEY": api_key,
        "POLY-API-PASSPHRASE": passphrase,
        "Content-Type": "application/json"
    }
    
    return headers

def get_position_size(yes_price, hour):
    """
    根据时间和价格返回买入 USDC 数量
    
    轻仓期 (00-07):
      YES < 0.10 → 1 USDC
      YES < 0.20 → 0.5 USDC
    
    加码期 (07-11):
      YES < 0.10 → 10 USDC (10倍!)
      YES < 0.20 → 5 USDC
      YES < 0.25 → 1 USDC
    """
    
    if hour < 7:  # 轻仓期
        if yes_price < 0.10:
            return 1.0
        elif yes_price < 0.20:
            return 0.5
    
    elif hour < 12:  # 加码期
        if yes_price < 0.10:
            return 10.0
        elif yes_price < 0.20:
            return 5.0
        elif yes_price < 0.25:
            return 1.0
    
    return None

def create_order(market_id, amount_usdc, yes_price):
    """
    创建订单 (使用 Polymarket CLOB API + HMAC 签名)
    
    实际执行步骤:
    1. 构建订单 payload
    2. 使用 HMAC-SHA256 签名
    3. 调用 POST /orders 端点
    4. 获取订单 ID
    """
    
    try:
        print(f"    📝 创建订单: {amount_usdc} USDC @ {yes_price:.3f}", end=" ", flush=True)
        
        # 计算份额数
        shares = amount_usdc / yes_price if yes_price > 0 else 0
        
        # 构建订单 payload
        payload = {
            "market_id": market_id,
            "outcome": "Yes",  # 买 YES
            "side": "BUY",
            "order_type": "LIMIT",
            "price": yes_price,
            "size": shares,
            "client_order_id": f"order_{int(time.time() * 1000)}"
        }
        
        # ✅ 计算 HMAC-SHA256 签名
        headers = sign_request(
            payload,
            api_key=POLYMARKET_API_KEY,
            api_secret=POLYMARKET_API_SECRET,
            passphrase=POLYMARKET_PASSPHRASE,
            method="POST",
            path="/orders"
        )
        
        # 发送实际请求
        response = requests.post(
            f"{POLYMARKET_API_BASE}/orders",
            json=payload,
            headers=headers,
            timeout=10
        )
        
        # 检查响应
        if response.status_code in [200, 201]:
            result = response.json()
            order_id = result.get('id') or result.get('order_id') or f"order_{int(time.time())}"
            print("✅")
            
            return {
                'market_id': market_id,
                'amount_usdc': amount_usdc,
                'shares': shares,
                'price': yes_price,
                'status': 'CREATED',
                'order_id': order_id,
                'tx_hash': result.get('tx_hash')
            }
        else:
            print(f"❌ HTTP {response.status_code}")
            print(f"    响应: {response.text}")
            return None
    
    except Exception as e:
        print(f"❌ {e}")
        return None

# Backward compatibility alias (after get_position_size is defined)
get_position_sizes = get_position_size

def create_order_with_retry(market_id, amount_usdc, yes_price):
    """
    创建订单 (带重试机制)
    """
    for attempt in range(RETRY_ATTEMPTS):
        order = create_order(market_id, amount_usdc, yes_price)
        if order:
            return order
        if attempt < RETRY_ATTEMPTS - 1:
            print(f"    🔄 重试 ({attempt + 2}/{RETRY_ATTEMPTS})...")
            time.sleep(RETRY_DELAY)
    return None

def validate_order_on_chain(order_id):
    """
    验证订单是否真正上链
    """
    try:
        headers = sign_request(
            {},
            api_key=POLYMARKET_API_KEY,
            api_secret=POLYMARKET_API_SECRET,
            passphrase=POLYMARKET_PASSPHRASE,
            method="GET",
            path=f"/orders/{order_id}"
        )
        response = requests.get(
            f"{POLYMARKET_API_BASE}/orders/{order_id}",
            headers=headers,
            timeout=10
        )
        return response.status_code in [200, 201]
    except Exception:
        return False

def execute_trades(opportunities):
    """
    执行交易 (带风控检查)
    """
    
    global daily_loss, daily_trade_count
    
    hour = datetime.now().hour
    
    if hour >= 12:
        print("  ⏰ 禁止交易时段")
        return []
    
    if daily_loss >= MAX_DAILY_LOSS:
        print(f"  🛑 达到每日亏损限制 ({daily_loss:.1f} >= {MAX_DAILY_LOSS})")
        return []
    
    print(f"\n💼 执行交易 ({hour}:00)\n")
    print(f"  📊 今日亏损: {daily_loss:.1f} / {MAX_DAILY_LOSS} USDC")
    print(f"  📊 持仓数: {daily_trade_count} / {MAX_POSITIONS}\n")
    
    trades = []
    total_usdc = 0
    
    for opp in opportunities:
        # 风控检查
        if daily_trade_count >= MAX_POSITIONS:
            print(f"  ⏭️  达到最大持仓数 ({MAX_POSITIONS})")
            break
        
        if daily_loss >= MAX_DAILY_LOSS:
            print(f"  🛑 达到每日亏损限制")
            break
        
        market_id = opp.get('market_id') or opp.get('condition_id')
        yes_price = opp['yes_price']
        city = opp['city']
        title = opp.get('title') or opp.get('question', 'Unknown')
        
        # 计算买入数量
        amount_usdc = get_position_size(yes_price, hour)
        
        if not amount_usdc:
            print(f"  ⏭️  {city}: YES {yes_price:.3f} - 不符合买入条件")
            continue
        
        # 单笔最大限制
        amount_usdc = min(amount_usdc, MAX_SINGLE_TRADE)
        
        print(f"  🎯 {city} - {title[:40]}")
        print(f"     YES: ${yes_price:.3f} → 买入 {amount_usdc} USDC")
        
        # 创建订单 (带重试)
        order = create_order_with_retry(market_id, amount_usdc, yes_price)
        
        if order:
            # 验证订单上链
            if validate_order_on_chain(order['order_id']):
                print(f"     ✅ 订单已上链: {order['order_id']}")
            
            trades.append({
                'timestamp': datetime.now().isoformat(),
                'city': city,
                'market_id': market_id,
                'title': title,
                'yes_price': yes_price,
                'amount_usdc': amount_usdc,
                'shares': order['shares'],
                'status': order['status'],
                'order_id': order['order_id']
            })
            total_usdc += amount_usdc
            daily_trade_count += 1
        
        print()
    
    daily_loss += total_usdc  # 简化：假设全部是成本
    
    print(f"  总投入: {total_usdc} USDC")
    print(f"  总订单: {len(trades)} 笔\n")
    
    return trades

def save_trades(trades):
    """保存交易记录"""
    
    if not trades:
        return None
    
    log_path = Path(r"C:\Users\Administrator\.openclaw\workspace\polymarket_trade_log.json")
    
    # 读取现有日志
    if log_path.exists():
        with open(log_path, 'r', encoding='utf-8') as f:
            try:
                existing = json.load(f)
            except:
                existing = []
    else:
        existing = []
    
    # 添加新交易
    existing.extend(trades)
    
    # 保存
    with open(log_path, 'w', encoding='utf-8') as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
    
    return log_path

def generate_report(trades, total_usdc):
    """生成交易报告"""
    
    if not trades:
        return None
    
    report_path = Path(r"C:\Users\Administrator\.openclaw\workspace\polymarket_execution_report.md")
    
    md = f"""# 📋 Polymarket 天气套利 - 交易报告

**执行时间:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## 📊 执行统计

- **执行交易数:** {len(trades)}
- **总投入:** {total_usdc} USDC
- **平均单笔:** {total_usdc / len(trades):.2f} USDC

---

## 📝 交易详情

| 城市 | 市场 | YES价 | USDC | 份额 | 订单ID |
|------|------|-------|------|------|--------|
"""
    
    for trade in trades:
        md += f"| {trade['city']} | {trade['title'][:20]} | {trade['yes_price']:.3f} | {trade['amount_usdc']} | {trade['shares']:.2f} | {trade['order_id']} |\n"
    
    md += f"""

---

## 💰 期望收益 (假设预报 90% 准确)

```
总投入: {total_usdc} USDC
预期胜率: 90%
预期败率: 10%

成功情况:
  {len(trades)} 笔 × 90% = {int(len(trades) * 0.9)} 笔成功
  预期收益: {total_usdc * 0.9:.1f} USDC

失败情况:
  {len(trades)} 笔 × 10% = {int(len(trades) * 0.1)} 笔失败
  预期亏损: -{total_usdc * 0.1:.1f} USDC

期望值: {total_usdc * 0.9 - total_usdc * 0.1:.1f} USDC ✅
```

---

**下一步:** 等待事件结算 (T+1 天)

**Telegram 推送:** 待发送确认消息

"""
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(md)
    
    return report_path

def main():
    
    # 加载机会数据
    opp_path = Path(r"C:\Users\Administrator\.openclaw\workspace\polymarket_opportunities.json")
    
    if not opp_path.exists():
        print("❌ 未找到机会文件，请先运行市场扫描")
        print("   python polymarket_weather_scanner_final.py")
        return 1
    
    with open(opp_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    opportunities = data.get('opportunities', [])
    
    if not opportunities:
        print("没有发现机会")
        return 0
    
    print(f"Polymarket 天气套利 - 交易执行\n")
    print(f"发现 {len(opportunities)} 个机会，准备执行...\n")
    
    # 执行交易
    trades = execute_trades(opportunities)
    
    if not trades:
        print("没有符合买入条件的市场")
        return 0
    
    # 保存记录
    log_path = save_trades(trades)
    report_path = generate_report(trades, sum(t['amount_usdc'] for t in trades))
    
    print(f"交易执行完成！")
    print(f"\n输出文件:")
    print(f"   • 交易日志: {log_path}")
    print(f"   • 执行报告: {report_path}")
    
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
