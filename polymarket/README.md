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
# Unit tests
pytest tests/ -v

# E2E browser tests (requires browser-use + langchain-openai + OpenAI API key)
cd polymarket
.venv\Scripts\activate
pip install browser-use langchain-openai
pytest tests/e2e/ -v
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
- Position sizes adjusted based of time of day

## E2E Testing (Browser)

The E2E tests use **browser-use** — an AI-driven browser automation library — to run real browser interactions against Polymarket.

### Setup

```bash
# Install browser-use and AI dependencies in the .venv
cd polymarket
.venv\Scripts\activate
pip install browser-use langchain-openai

# Set your OpenAI API key for AI-driven browser agent
# Add to .env:
# OPENAI_API_KEY=sk-...
```

### Run

```bash
# Run all E2E tests (will skip if API key not set)
pytest tests/e2e/ -v

# Run in headed mode (see browser window)
HEADLESS=false pytest tests/e2e/ -v

# Run only the full workflow test
pytest tests/e2e/test_weather_trading_flow.py::TestFullWorkflowE2E -v
```

### How it works

browser-use wraps an AI agent that drives a real Chrome browser:
- `Agent(task=..., llm=ChatOpenAI(...), browser_profile=...)`
- The agent receives natural language instructions and executes browser actions
- Headless mode (`HEADLESS=true`) runs without a visible window (CI/default)
- Headed mode (`HEADLESS=false`) shows the browser for debugging

### Test classes

| Class | What it tests |
|---|---|
| `TestBrowserUseSetup` | browser-use + Chrome + langchain-openai installed |
| `TestBrowserUseImports` | All browser-use imports work |
| `TestMarketScannerE2E` | Open Polymarket, search weather markets, verify list non-empty |
| `TestPriceLoadsE2E` | Open a weather market, verify YES/NO prices load and are in [0,1] |
| `TestFullWorkflowE2E` | Run scanner → opportunities.json → browser-verify Polymarket loads |

## CI/CD

GitHub Actions runs on every push/PR to main branch.