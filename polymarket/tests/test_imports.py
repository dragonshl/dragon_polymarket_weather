"""Test imports for all core modules."""
import pytest

from weather_temps_hourly import CITIES
from polymarket_weather_scanner_final import POLYMARKET_API_BASE, WEATHER_KEYWORDS, scan_opportunities
from polymarket_weather_trader_final import get_position_sizes, execute_trades


def test_weather_temps_hourly_cities():
    """Test weather_temps_hourly module has CITIES dict."""
    assert isinstance(CITIES, dict)
    assert "\u5317\u4eac" in CITIES  # Beijing in Chinese


def test_scanner_api_base():
    """Test scanner module has POLYMARKET_API_BASE and WEATHER_KEYWORDS."""
    assert POLYMARKET_API_BASE == "https://clob.polymarket.com"
    assert isinstance(WEATHER_KEYWORDS, dict)


def test_scanner_function():
    """Test scanner module has scan_opportunities function."""
    assert callable(scan_opportunities)


def test_trader_functions():
    """Test trader module has expected functions."""
    assert callable(get_position_sizes)
    assert callable(execute_trades)


def test_trader_get_position_sizes():
    """Test position sizing logic."""
    # Light period (hour < 7): YES<0.10 → 1USDC
    result = get_position_sizes(0.05, 3)
    assert result == 1.0

    # Light period: YES<0.20 → 0.5USDC
    result = get_position_sizes(0.15, 3)
    assert result == 0.5

    # Aggressive period (07:00-11:00): YES<0.10 → 10USDC
    result = get_position_sizes(0.05, 9)
    assert result == 10.0

    # Aggressive period: YES<0.20 → 5USDC
    result = get_position_sizes(0.15, 9)
    assert result == 5.0

    # Aggressive period: YES<0.25 → 1USDC
    result = get_position_sizes(0.22, 9)
    assert result == 1.0

    # No trading after 12:00
    result = get_position_sizes(0.05, 12)
    assert result is None

    # Price too high: no position
    result = get_position_sizes(0.50, 9)
    assert result is None
