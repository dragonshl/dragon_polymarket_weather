#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每小时气象数据采集 - 导出环境变量
双数据源: AVWX (主) + Open-Meteo (备)
从 AVWX METAR 获取实时温度，备用 Open-Meteo 预报最高温
保存为: WEATHER_TEMPS_SHANGHAI, WEATHER_TEMPS_BEIJING 等
同时存储 JSON 供查询
"""

import requests
import json
import os
from datetime import datetime
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════════════
# AVWX API 配置 (METAR 实时数据)
# ═══════════════════════════════════════════════════════════════════════════
# API Key 存储在环境变量 AVWX_API_KEY
# 默认值来自 MEMORY.md 记录
AVWX_API_KEY = os.environ.get("AVWX_API_KEY", "Vg4o2ags87a5O3lxjmh7MqQmjziW1C_gLUA6-yLn56c")

# 城市机场代码映射 (AVWX METAR)
CITY_AIRPORTS = {
    "shanghai": {"zh": "上海", "code": "ZSSS"},  # 浦东
    "beijing": {"zh": "北京", "code": "ZBAA"},   # 首都
    "shenzhen": {"zh": "深圳", "code": "ZGSZ"},  # 宝安
    "chengdu": {"zh": "成都", "code": "ZUUU"},   # 双流
    "wuhan": {"zh": "武汉", "code": "ZHWH"},     # 天河
    "chongqing": {"zh": "重庆", "code": "ZUCK"},  # 江北
}

# 城市英文名到 airport key 的映射
CITY_TO_AIRPORT_KEY = {
    "Shanghai": "shanghai",
    "Beijing": "beijing",
    "Shenzhen": "shenzhen",
    "Chengdu": "chengdu",
    "Wuhan": "wuhan",
    "Chongqing": "chongqing",
}

# Open-Meteo 城市坐标 (用于备用数据源)
CITY_COORDS = {
    "上海": (31.23, 121.47),
    "北京": (39.91, 116.39),
    "深圳": (22.54, 114.06),
    "成都": (30.66, 104.07),
    "武汉": (30.58, 114.29),
    "重庆": (29.43, 106.55),
}

CITIES = {
    "上海": ("Shanghai", "SHANGHAI"),
    "北京": ("Beijing", "BEIJING"),
    "深圳": ("Shenzhen", "SHENZHEN"),
    "成都": ("Chengdu", "CHENGDU"),
    "武汉": ("Wuhan", "WUHAN"),
    "重庆": ("Chongqing", "CHONGQING")
}

def get_forecast_high_temp(city_en):
    """获取某城市当天预报最高温 (wttr.in, 已废弃 - 仅保留兼容)"""
    try:
        url = f"https://wttr.in/{city_en}?format=j1"
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        
        data = resp.json()
        today = data['weather'][0]
        high_temp = int(today['maxtempC'])
        
        return high_temp
    except Exception as e:
        print(f"❌ {city_en}: {e}", flush=True)
        return None


def fetch_weather_avwx(city_key: str) -> dict:
    """
    使用 AVWX REST API 获取 METAR 实时温度 (主数据源)
    
    Args:
        city_key: 城市key (shanghai, beijing, shenzhen, chengdu, wuhan, chongqing)
    
    Returns:
        {
            'success': True/False,
            'city': '城市名',
            'temperature': '25.0' (str, °C),
            'airport': 'ZBAA',
            'source': 'AVWX METAR',
            ...
        }
    """
    if city_key not in CITY_AIRPORTS:
        return {"success": False, "error": f"Unknown city: {city_key}"}
    
    airport_info = CITY_AIRPORTS[city_key]
    airport_code = airport_info["code"]
    
    try:
        url = f"https://avwx.rest/api/metar/{airport_code}"
        headers = {"Authorization": f"Bearer {AVWX_API_KEY}"}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        
        data = resp.json()
        
        if "error" in data or "temperature" not in data:
            return {
                "success": False,
                "city": airport_info["zh"],
                "error": str(data.get("error", "No temperature data")),
            }
        
        return {
            "success": True,
            "city": airport_info["zh"],
            "airport": airport_code,
            "temperature": data.get("temperature"),
            "dewpoint": data.get("dewpoint"),
            "wind_speed": data.get("wind_speed"),
            "wind_direction": data.get("wind_direction"),
            "timestamp": data.get("time", {}).get("dt"),
            "raw_metar": data.get("raw"),
            "source": "AVWX METAR",
            "precision": "±0.1°C",
        }
    except Exception as e:
        return {
            "success": False,
            "city": airport_info["zh"],
            "error": str(e)[:100],
        }


def fetch_weather_open_meteo(lat: float, lon: float, city_name: str) -> dict:
    """
    使用 Open-Meteo API 获取预报最高温度 (备用数据源)
    
    Args:
        lat: 纬度
        lon: 经度
        city_name: 城市环境变量名 (如 SHANGHAI)
    
    Returns:
        {
            'success': True/False,
            'high': 28,  # 预报最高温度
            'source': 'open-meteo',
            ...
        }
    """
    try:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": "temperature_2m",
            "forecast_days": 1,
            "timezone": "Asia/Shanghai",
        }
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        
        data = resp.json()
        temps = data["hourly"]["temperature_2m"]
        
        # 取今天 0-23 点的最高温度
        today_temps = temps[:24]
        high_temp = max(today_temps)
        
        return {
            "success": True,
            "high": int(high_temp) if high_temp == int(high_temp) else round(high_temp, 1),
            "source": "open-meteo",
            "city_name": city_name,
        }
    except Exception as e:
        return {"success": False, "error": str(e)[:100]}


def fetch_weather() -> dict:
    """
    双数据源获取天气: AVWX (主) + Open-Meteo (备)
    
    策略:
      - 优先使用 AVWX METAR 实时温度
      - AVWX 失败时使用 Open-Meteo 预报最高温
      - 完全失败时返回 None
    
    Returns:
        {
            '上海': {'high': 28, 'env_code': 'SHANGHAI', 'source': 'AVWX METAR', ...},
            ...
        }
    """
    results = {}
    
    for city_cn, (city_en, env_code) in CITIES.items():
        city_key = CITY_TO_AIRPORT_KEY.get(city_en)
        
        # Step 1: 尝试 AVWX (主数据源)
        avwx_result = None
        if city_key:
            avwx_result = fetch_weather_avwx(city_key)
        
        if avwx_result and avwx_result.get("success"):
            # AVWX 成功: 使用实时温度作为参考, 加上 Open-Meteo 预报来估算最高温
            real_temp = float(avwx_result.get("temperature", 0))
            lat, lon = CITY_COORDS.get(city_cn, (0, 0))
            om_result = fetch_weather_open_meteo(lat, lon, env_code)
            
            if om_result.get("success"):
                # 综合: 预报最高温 + 实时温度调整
                forecast_high = om_result["high"]
                # 如果实时温度已经很高, 可能今天已经过了最高点
                high = max(int(real_temp), forecast_high)
            else:
                high = int(real_temp) if real_temp else None
            
            results[city_cn] = {
                "high": high,
                "env_code": env_code,
                "source": "AVWX METAR",
                "avwx": avwx_result,
            }
        else:
            # Step 2: AVWX 失败, 尝试 Open-Meteo (备用数据源)
            lat, lon = CITY_COORDS.get(city_cn, (0, 0))
            om_result = fetch_weather_open_meteo(lat, lon, env_code)
            
            if om_result.get("success"):
                results[city_cn] = {
                    "high": om_result["high"],
                    "env_code": env_code,
                    "source": "open-meteo",
                }
            else:
                # Step 3: 完全失败, 尝试旧的 wttr.in
                high_temp = get_forecast_high_temp(city_en)
                results[city_cn] = {
                    "high": high_temp,
                    "env_code": env_code,
                    "source": "wttr.in" if high_temp else None,
                }
    
    return results

def save_env_file(temps_dict):
    """保存为 .env 文件格式"""
    env_path = r"C:\Users\Administrator\.openclaw\workspace\weather_temps.env"
    
    with open(env_path, 'w', encoding='utf-8') as f:
        f.write(f"# 天气预报最高温度环境变量\n")
        f.write(f"# 更新时间: {datetime.now().isoformat()}\n\n")
        
        for city_cn, temps in temps_dict.items():
            if temps['high']:
                env_var = f"WEATHER_TEMPS_{temps['env_code']}"
                f.write(f"{env_var}={temps['high']}\n")
        
        f.write(f"\n# 更新时戳\n")
        f.write(f"WEATHER_TEMPS_UPDATED_AT={datetime.now().isoformat()}\n")
    
    return env_path

def save_json(temps_dict):
    """保存为 JSON"""
    json_path = r"C:\Users\Administrator\.openclaw\workspace\weather_temps.json"
    
    data = {
        "timestamp": datetime.now().isoformat(),
        "hour": datetime.now().hour,
        "temperatures": {}
    }
    
    for city_cn, temps in temps_dict.items():
        data['temperatures'][city_cn] = {
            "high": temps['high'],
            "unit": "°C"
        }
    
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    return json_path

def update_dashboard(temps_dict):
    """更新实时看板"""
    dashboard_path = r"C:\Users\Administrator\.openclaw\workspace\weather_strategy_dashboard.md"
    
    md = f"""# 🌤️ Polymarket 天气套利策略看板

**实时更新:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## 📊 当日最高温度预报

| 城市 | 当日最高温 | 状态 | 环境变量 |
|------|----------|------|---------|
"""
    
    for city_cn, temps in temps_dict.items():
        env_code = temps['env_code']
        if temps['high']:
            status = f"✅ {temps['high']}°C"
            env_var = f"`WEATHER_TEMPS_{env_code}`"
        else:
            status = "❌ 获取失败"
            env_var = "-"
        
        md += f"| {city_cn} | {status} | ✓ | {env_var} |\n"
    
    md += f"""
---

## 🎯 Polymarket 机会扫描

**下一步:** 对比这些最高温度与 Polymarket 市场价格

### 查询示例

```
市场: "北京明天最高温 > {temps_dict['北京']['high'] - 2}°C?"
预报: {temps_dict['北京']['high']}°C (确定性 90%+)
Polymarket 查询: https://polymarket.com/market/...
```

---

## 📈 交易规则

```
IF Polymarket YES < 0.31:
  IF YES < 0.25: 买 2 份 (20 USDC)
  IF YES < 0.20: 买 10 份 (100 USDC)
  IF YES < 0.10: 买 50 份 (500 USDC)
ELSE:
  WAIT
```

---

## 📝 最近交易日志

*(待补充)*

---

**数据源:** 气象局 (wttr.in) | **环境变量:** weather_temps.env
"""
    
    with open(dashboard_path, 'w', encoding='utf-8') as f:
        f.write(md)
    
    return dashboard_path

def main():
    print(f"⏰ {datetime.now().strftime('%H:%M:%S')} - 气象数据采集开始...")
    print("   数据源: AVWX (主) + Open-Meteo (备)")
    
    # 使用双数据源获取天气
    temps_dict = fetch_weather()
    
    for city_cn, temps in temps_dict.items():
        if temps['high'] is not None:
            print(f"  📍 {city_cn}: ✅ {temps['high']}°C (来源: {temps.get('source', 'N/A')})")
        else:
            print(f"  📍 {city_cn}: ❌")
    
    # 保存环境变量文件
    print(f"  💾 保存 .env 文件...", end=" ", flush=True)
    env_path = save_env_file(temps_dict)
    print(f"✅ ({env_path})")
    
    # 保存 JSON
    print(f"  💾 保存 JSON 文件...", end=" ", flush=True)
    json_path = save_json(temps_dict)
    print(f"✅ ({json_path})")
    
    # 更新看板
    print(f"  📊 更新看板...", end=" ", flush=True)
    dashboard_path = update_dashboard(temps_dict)
    print(f"✅ ({dashboard_path})")
    
    # 输出环境变量信息
    print(f"\n✅ {datetime.now().strftime('%H:%M:%S')} - 采集完成!")
    print(f"\n环境变量导出:")
    for city_cn, temps in temps_dict.items():
        if temps['high']:
            env_code = temps['env_code']
            print(f"  WEATHER_TEMPS_{env_code}={temps['high']}")
    
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
