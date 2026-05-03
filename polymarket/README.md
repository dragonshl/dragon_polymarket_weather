# Polymarket Weather Trading System

> AI-driven weather arbitrage on Polymarket

## System Architecture

```
Step 1: Weather Data Collection (weather_temps_hourly.py)
  → Fetch 6 cities' daily high temperature forecast
  → Dual-source: AVWX METAR (primary) + Open-Meteo (fallback)

Step 2: Market Scanner (polymarket_weather_scanner_final.py)
  → Scan Polymarket CLOB API for weather markets
  → Find YES < 0.25 opportunities

Step 3: Trade Execution (polymarket_weather_trader_final.py)
  → Execute trades based on position sizing rules
  → Time-based risk management
```

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your Polymarket API credentials
```

## Run

```bash
# Step 1: Fetch weather
python weather_temps_hourly.py

# Step 2: Scan markets
python polymarket_weather_scanner_final.py

# Step 3: Execute trades
python polymarket_weather_trader_final.py
```

## Testing

```bash
pytest tests/ -v
```

## Data Sources

`weather_temps_hourly.py` uses a **dual-source** approach for reliability:

1. **AVWX METAR** (primary): Real-time airport weather data with ±0.1°C precision
2. **Open-Meteo** (fallback): Forecast high temperature when AVWX is unavailable
3. **wttr.in** (last resort): Legacy forecast data if both fail

AVWX API key is read from environment variable `AVWX_API_KEY`.

City airport codes used:
- 上海 → ZSSS (浦东)
- 北京 → ZBAA (首都)
- 深圳 → ZGSZ (宝安)
- 成都 → ZUUU (双流)
- 武汉 → ZHWH (天河)
- 重庆 → ZUCK (江北)

## GraphQL Dynamic Market Discovery

The scanner uses **GraphQL** (`https://clob.polymarket.com/graphql`) to dynamically discover weather markets, with automatic fallback to REST API.

```python
from polymarket_weather_scanner_final import fetch_weather_markets_via_graphql

# Returns dict: {"markets": [...]} or {} on failure
gql_result = fetch_weather_markets_via_graphql()
```

The GraphQL query filters by:
- Keywords: temperature, rain, snow, weather, celsius
- Chinese cities: 上海, 北京, 深圳, 成都, 武汉, 重庆
- Status: `open`
- Then applies `WEATHER_KEYWORDS` for secondary filtering

## Risk Control

The trading system implements multiple layers of risk control:

### Position Sizing
- **Light period (00:00-07:00)**: YES < 0.10 → 1 USDC, YES < 0.20 → 0.5 USDC
- **Aggressive period (07:00-12:00)**: YES < 0.10 → 10 USDC, YES < 0.20 → 5 USDC, YES < 0.25 → 1 USDC

### Risk Limits
- `MAX_DAILY_LOSS = 50.0` USDC - Daily loss limit stops all trading
- `MAX_POSITIONS = 5` - Maximum number of concurrent positions
- `MAX_SINGLE_TRADE = 10.0` USDC - Maximum single trade size

### Order Protection
- `RETRY_ATTEMPTS = 3` - Retry failed orders 3 times
- `RETRY_DELAY = 2` seconds - Delay between retries
- `validate_order_on_chain()` - Verifies order is confirmed on-chain

### Time-Based Controls
- No trading after 12:00 (noon)
- Position sizes adjusted based on time of day

## CI/CD

GitHub Actions runs on every push/PR to main branch.
