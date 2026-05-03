#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import os
os.environ['PYTHONIOENCODING'] = 'utf-8'
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
"""
Polymarket 天气市场扫描 - 最终版
直接使用 Polymarket CLOB API (官方API)
"""

import requests
import json
import os
from datetime import datetime
from pathlib import Path

# Polymarket API 配置
POLYMARKET_API_BASE = "https://clob.polymarket.com"
POLYMARKET_GRAPHQL_ENDPOINT = "https://clob.polymarket.com/graphql"

# 天气相关关键词
WEATHER_KEYWORDS = {
    "上海": ["shanghai", "上海", "高温"],
    "北京": ["beijing", "北京", "高温"],
    "深圳": ["shenzhen", "深圳", "高温"],
    "成都": ["chengdu", "成都", "高温"],
    "武汉": ["wuhan", "武汉", "高温"],
    "重庆": ["chongqing", "重庆", "高温"]
}

def get_polymarket_markets(limit=100):
    """
    从 Polymarket 获取市场列表

    API: GET https://clob.polymarket.com/markets?limit=100
    """

    try:
        url = f"{POLYMARKET_API_BASE}/markets"
        params = {"limit": limit, "status": "open"}

        print(f"  📡 查询 Polymarket REST API...", end=" ", flush=True)
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()

        data = resp.json()
        # API 返回格式: {'data': [...], 'next_cursor': ..., 'count': ...}
        markets = data.get('data', [])
        print(f"✅ 获得 {len(markets)} 个市场")

        return markets

    except Exception as e:
        print(f"❌ {e}")
        return None


def fetch_weather_markets_via_graphql():
    """
    通过 GraphQL 动态查询 Polymarket 天气市场

    使用 Polymarket CLOB GraphQL API 直接搜索天气相关市场，
    而非先获取全部市场再过滤。

    Returns:
        dict: {"markets": [...]} 或 {} (失败时)
    """
    query = """
    {{
        markets(
            where: {{
                or: [
                    {{titleContains: "temperature"}}
                    {{titleContains: "rain"}}
                    {{titleContains: "snow"}}
                    {{titleContains: "weather"}}
                    {{titleContains: "celsius"}}
                    {{titleContains: "上海"}}
                    {{titleContains: "北京"}}
                    {{titleContains: "深圳"}}
                    {{titleContains: "成都"}}
                    {{titleContains: "武汉"}}
                    {{titleContains: "重庆"}}
                    {{titleContains: "高温"}}
                    {{titleContains: "ShangHai"}}
                    {{titleContains: "BeiJing"}}
                ]
                status: {{equals: open}}
            }}
            limit: 100
        ) {{
            id
            question
            condition_id
            title
            tokens {{
                outcome
                price
            }}
            liquidity
        }}
    }}
    """

    try:
        print(f"  📡 查询 Polymarket GraphQL...", end=" ", flush=True)
        resp = requests.post(
            POLYMARKET_GRAPHQL_ENDPOINT,
            json={"query": query},
            headers={"Content-Type": "application/json"},
            timeout=15
        )
        resp.raise_for_status()
        result = resp.json()

        if "errors" in result:
            print(f"❌ GraphQL errors: {result['errors']}")
            return {}

        markets = result.get("data", {}).get("markets", [])
        print(f"✅ GraphQL 返回 {len(markets)} 个市场")
        return {"markets": markets}

    except Exception as e:
        print(f"❌ GraphQL 查询失败: {e}")
        return {}


def is_weather_market(market):
    """检查市场是否是天气相关"""

    question = str(market.get('question', '')).lower()
    description = str(market.get('description', '')).lower()

    # 排除加密货币市场
    crypto_keywords = ['btc', 'bitcoin', 'eth', 'ethereum', 'usdt', 'token',
                       'fdv', 'market cap', 'candle', 'crypto', 'coin']
    if any(kw in question or kw in description for kw in crypto_keywords):
        return False

    # 天气相关关键词 (更精确)
    weather_keywords = [
        'temperature will exceed',
        'temperature to exceed',
        'temperature exceed',
        'degrees or higher',
        'degrees or more',
        'rain in',
        'snow in',
        'weather',
        'celsius',
        'fahrenheit',
        '最高温',
        '高温超过',
        '降雨',
        '降雪'
    ]

    return any(kw in question or kw in description for kw in weather_keywords)

def find_city_from_market(market):
    """从市场标题中识别城市"""

    question = str(market.get('question', '')).lower()
    description = str(market.get('description', '')).lower()
    full_text = f"{question} {description}".lower()

    # 扩展城市列表 (包括美国城市)
    all_cities = {
        "New York": ["new york", "nyc", "manhattan"],
        "Chicago": ["chicago"],
        "Dallas": ["dallas"],
        "Atlanta": ["atlanta"],
        "Los Angeles": ["los angeles", "la"],
        "Shanghai": ["shanghai", "上海"],
        "Beijing": ["beijing", "北京"],
        **WEATHER_KEYWORDS  # 包括原有的中国城市
    }

    for city, keywords in all_cities.items():
        if any(kw in full_text for kw in keywords):
            return city

    return "Unknown City"

def get_market_prices(market):
    """
    从市场数据中提取 YES/NO 价格

    Polymarket API 直接返回 tokens 中的价格
    """

    try:
        tokens = market.get('tokens', [])
        if not tokens or len(tokens) < 2:
            return None

        # 找到 Yes 和 No token
        yes_price = None
        no_price = None

        for token in tokens:
            outcome = str(token.get('outcome', '')).lower()
            price = float(token.get('price', 0))

            if outcome == 'yes':
                yes_price = price
            elif outcome == 'no':
                no_price = price

        if yes_price is None or no_price is None:
            return None

        return {
            'yes_price': yes_price,
            'no_price': no_price,
            'liquidity': market.get('liquidity', 0)  # 使用市场流动性
        }

    except Exception as e:
        print(f"    ⚠️ 获取价格失败: {e}")
        return None

def scan_opportunities():
    """
    扫描 Polymarket 寻找天气套利机会
    """

    print(f"\n🔍 扫描 Polymarket 天气市场 ({datetime.now().strftime('%H:%M:%S')})\n")

    # Step 1: 优先通过 GraphQL 动态查询天气市场
    gql_result = fetch_weather_markets_via_graphql()
    markets = []

    if gql_result and gql_result.get("markets"):
        # GraphQL 返回结果，进行关键字二次过滤
        raw_markets = gql_result["markets"]
        print(f"  🔎 GraphQL 预筛选...", end=" ", flush=True)
        markets = [m for m in raw_markets if is_weather_market(m)]
        print(f"✅ 发现 {len(markets)} 个天气市场 (via GraphQL)")
    else:
        # Fallback: 使用 REST API 获取全部市场再过滤
        print(f"  📡 GraphQL 未返回结果，回退到 REST API...")
        all_markets = get_polymarket_markets(200)
        if not all_markets:
            return None
        markets = [m for m in all_markets if is_weather_market(m)]
        print(f"  ✅ 发现 {len(markets)} 个天气市场 (via REST fallback)")

    # 分析机会
    print(f"  📊 分析机会...", end=" ", flush=True)

    opportunities = []

    for market in markets:
        condition_id = market.get('condition_id')
        question = market.get('question', '')
        city = find_city_from_market(market)
        
        if not city:
            continue
        
        # 获取价格 (直接从 market 中提取)
        prices = get_market_prices(market)
        if not prices or prices['yes_price'] is None:
            continue
        
        yes_price = prices['yes_price']

        # 判断是否是套利机会 (YES < 0.31)
        is_opportunity = yes_price < 0.31

        # 分级 (根据时间)
        hour = datetime.now().hour
        tier = None

        if is_opportunity:
            if hour < 7:  # 轻仓期
                if yes_price < 0.10:
                    tier = "light_1usdc"
                elif yes_price < 0.20:
                    tier = "light_0.5usdc"
            elif hour < 12:  # 加码期
                if yes_price < 0.10:
                    tier = "aggressive_10usdc"
                elif yes_price < 0.20:
                    tier = "aggressive_5usdc"
                elif yes_price < 0.25:
                    tier = "aggressive_1usdc"

        if tier:
            opportunities.append({
                'condition_id': condition_id,
                'city': city,
                'question': question,
                'yes_price': yes_price,
                'no_price': prices['no_price'],
                'liquidity': prices['liquidity'],
                'tier': tier,
                'timestamp': datetime.now().isoformat()
            })

    print(f"✅ 发现 {len(opportunities)} 个机会")

    return opportunities

def save_opportunities(opportunities):
    """保存发现的机会"""

    if not opportunities:
        print("\n  ⏳ 暂无机会")
        return None

    # 保存到 JSON
    output_path = Path(r"C:\Users\Administrator\.openclaw\workspace\polymarket_opportunities.json")

    data = {
        'timestamp': datetime.now().isoformat(),
        'hour': datetime.now().hour,
        'opportunities': opportunities
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # 打印机会
    print("\n✅ 发现的机会:\n")

    for opp in opportunities:
        q = opp.get('question', opp.get('title', 'Unknown'))[:60]
        print(f"  🎯 {opp['city']} - {q}")
        print(f"     YES价: ${opp['yes_price']:.3f}")
        print(f"     分级: {opp['tier']}")
        print(f"     流动: {opp.get('liquidity', 0)}\n")

    return output_path

def main() -> int:

    hour = datetime.now().hour

    # 检查时间
    if hour >= 12 or hour < 0:
        print(f"⏰ 时间 {hour}:00 - 禁止交易段")
        return 1

    # 扫描机会
    opportunities = scan_opportunities()

    if opportunities:
        output_path = save_opportunities(opportunities)
        print(f"📁 数据保存: {output_path}")
        return 0
    else:
        print("\n⏳ 暂无机会")
        return 0

if __name__ == "__main__":
    import sys
    import os
    # 修复 Windows 编码问题
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(main())
