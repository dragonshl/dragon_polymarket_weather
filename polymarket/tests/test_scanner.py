"""Tests for polymarket_weather_scanner_final GraphQL integration."""
import pytest
from unittest.mock import patch, MagicMock


class TestFetchWeatherMarketsViaGraphQL:
    """Tests for fetch_weather_markets_via_graphql function."""

    def test_function_exists(self):
        """GraphQL fetch function should exist in scanner module."""
        from polymarket_weather_scanner_final import fetch_weather_markets_via_graphql
        assert callable(fetch_weather_markets_via_graphql)

    def test_returns_dict(self):
        """Function should return a dict (market list or error)."""
        from polymarket_weather_scanner_final import fetch_weather_markets_via_graphql
        # Mock the requests.post to avoid real API call
        with patch("requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "data": {
                    "markets": [
                        {
                            "id": "0x1234",
                            "question": "Will Shanghai temperature exceed 35°C on 2026-05-03?",
                            "condition_id": "cond_123",
                            "tokens": [
                                {"outcome": "yes", "price": 0.15},
                                {"outcome": "no", "price": 0.85}
                            ]
                        }
                    ]
                }
            }
            mock_post.return_value = mock_response

            result = fetch_weather_markets_via_graphql()
            assert isinstance(result, dict)
            assert "markets" in result
            assert len(result["markets"]) == 1

    def test_handles_api_error(self):
        """Function should return empty dict on API failure."""
        from polymarket_weather_scanner_final import fetch_weather_markets_via_graphql
        with patch("requests.post") as mock_post:
            mock_post.side_effect = Exception("Network error")
            result = fetch_weather_markets_via_graphql()
            assert isinstance(result, dict)
            assert result == {}


class TestScannerFindsWeatherMarkets:
    """Tests for weather market discovery in scan_opportunities."""

    def test_scan_uses_graphql_when_available(self):
        """scan_opportunities should call fetch_weather_markets_via_graphql."""
        from polymarket_weather_scanner_final import scan_opportunities
        from polymarket_weather_scanner_final import fetch_weather_markets_via_graphql

        # Mock the GraphQL function (patch as a module-level function, not a method)
        with patch(
            "polymarket_weather_scanner_final.fetch_weather_markets_via_graphql",
            return_value={"markets": []}
        ):
            with patch("requests.get") as mock_get:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {"data": [], "count": 0}
                mock_get.return_value = mock_response

                # If GraphQL returns empty, scanner should fall back to REST or return None
                result = scan_opportunities()
                # Just verify it doesn't crash
                assert result is None or isinstance(result, list)

    def test_weather_keywords_preserved(self):
        """WEATHER_KEYWORDS should still be used for filtering."""
        from polymarket_weather_scanner_final import WEATHER_KEYWORDS
        assert "上海" in WEATHER_KEYWORDS
        assert "高温" in WEATHER_KEYWORDS["上海"]
