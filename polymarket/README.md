# Polymarket Weather Trading System

> AI-driven weather arbitrage on Polymarket

## System Architecture

```
Step 1: Weather Data Collection (weather_temps_hourly.py)
  → Fetch 6 cities' daily high temperature forecast

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

## CI/CD

GitHub Actions runs on every push/PR to main branch.
