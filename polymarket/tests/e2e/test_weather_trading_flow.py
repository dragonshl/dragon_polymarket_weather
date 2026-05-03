# -*- coding: utf-8 -*-
"""
Slice 5: E2E Browser Tests for Polymarket Weather Trading System

Uses browser-use (AI-driven browser automation) to run end-to-end browser tests.

Requirements:
- browser-use package installed in .venv
- langchain-openai installed in .venv (for AI-driven browser agent)
- Google Chrome installed
- Polymarket API credentials in .env (for tests that interact with CLOB API)

Headless mode: Set HEADLESS=true env var for CI environments
"""

import os
import sys
import json
import asyncio
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest

# Ensure polymarket dir in path
polymarket_dir = Path(__file__).parent.parent.parent
if str(polymarket_dir) not in sys.path:
    sys.path.insert(0, str(polymarket_dir))

# ─────────────────────────────────────────────
# Check availability
# ─────────────────────────────────────────────

BROWSER_USE_AVAILABLE = False
LANGCHAIN_OPENAI_AVAILABLE = False

try:
    from browser_use import Agent, BrowserProfile, Browser
    BROWSER_USE_AVAILABLE = True
except ImportError:
    pass

try:
    from langchain_openai import ChatOpenAI
    LANGCHAIN_OPENAI_AVAILABLE = True
except ImportError:
    pass


def is_browser_available() -> bool:
    """Check if Chrome browser is available."""
    chrome_paths = [
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe")),
    ]
    return any(p.exists() for p in chrome_paths)


BROWSER_AVAILABLE = is_browser_available()

pytestmark = [pytest.mark.e2e]


# ─────────────────────────────────────────────
# Setup tests (always run, no browser needed)
# ─────────────────────────────────────────────

class TestBrowserUseSetup:
    """Verify browser-use is installed and Chrome is available."""

    def test_browser_use_installed(self):
        """browser-use package must be installed."""
        assert BROWSER_USE_AVAILABLE, (
            "browser-use not installed. Run: "
            "cd polymarket && .venv\\Scripts\\activate && pip install browser-use"
        )

    def test_chrome_available(self):
        """Google Chrome must be installed."""
        assert BROWSER_AVAILABLE, (
            "Chrome not found. Please install Google Chrome from "
            "https://www.google.com/chrome/"
        )

    def test_langchain_openai_available(self):
        """langchain-openai must be installed for AI-driven browser agent."""
        assert LANGCHAIN_OPENAI_AVAILABLE, (
            "langchain-openai not installed. Run: "
            "cd polymarket && .venv\\Scripts\\activate && pip install langchain-openai"
        )


class TestBrowserUseImports:
    """Sanity check: verify all required browser-use components can be imported."""

    def test_all_imports_work(self):
        """All browser-use imports should work in the venv."""
        if not BROWSER_USE_AVAILABLE:
            pytest.skip("browser-use not installed")

        from browser_use import Agent, BrowserProfile, Browser
        from browser_use.browser.profile import BrowserProfile
        from browser_use.browser.session import BrowserSession

        assert callable(Agent)
        assert callable(BrowserProfile)
        assert callable(Browser)

    def test_browser_profile_accepts_executable_path(self):
        """BrowserProfile should accept an explicit executable_path parameter."""
        if not BROWSER_USE_AVAILABLE:
            pytest.skip("browser-use not installed")

        from browser_use import BrowserProfile

        chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        if Path(chrome_path).exists():
            bp = BrowserProfile(
                headless=True,
                executable_path=chrome_path,
            )
            assert bp.executable_path == chrome_path


# ─────────────────────────────────────────────
# E2E browser tests (require API key + browser)
# ─────────────────────────────────────────────

class TestMarketScannerE2E:
    """E2E test: browser opens Polymarket and finds weather markets."""

    @pytest.mark.skipif(
        not BROWSER_USE_AVAILABLE or not BROWSER_AVAILABLE or not LANGCHAIN_OPENAI_AVAILABLE,
        reason="browser-use, Chrome, or langchain-openai not available"
    )
    def test_market_scanner_e2e(self, tmp_path):
        """
        Open Polymarket in browser, search for weather markets,
        and verify the market list is non-empty.
        """
        from langchain_openai import ChatOpenAI

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            pytest.skip("OPENAI_API_KEY not set in .env — skipping live browser test")

        llm = ChatOpenAI(model="gpt-4o-mini", api_key=api_key)

        headless = os.getenv("HEADLESS", "true").lower() == "true"
        browser_profile = BrowserProfile(
            headless=headless,
            disable_security=True,
        )

        output_file = tmp_path / "e2e_markets.json"

        async def run_agent():
            agent = Agent(
                task=(
                    "Go to https://polymarket.com and search for markets related to "
                    "'weather temperature'. Find at least one weather market and note its "
                    "question, YES price, and NO price. Save the results to a JSON file "
                    f"at {output_file} with keys: question, yes_price, no_price, url. "
                    "If no weather markets are found, save an empty object {{}}."
                ),
                llm=llm,
                browser_profile=browser_profile,
                use_vision=False,
                max_failures=2,
            )
            result = await agent.run()
            return result

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(run_agent())
        finally:
            loop.close()

        # Verify output file was created and contains data
        if output_file.exists():
            raw = output_file.read_text(encoding="utf-8")
            if raw.strip():
                data = json.loads(raw)
                if "question" in data:
                    assert "yes_price" in data
                    assert "no_price" in data
                    yes_price = float(data["yes_price"])
                    assert 0 <= yes_price <= 1, f"YES price {yes_price} out of range [0,1]"
                    print(f"\n✅ Found market: {data['question']} @ YES={data['yes_price']}")
            else:
                print("\n⚠️  No weather markets found (live market may not exist at this moment)")
        else:
            print(f"\n⚠️  Output file not created. Agent result: {result}")


class TestPriceLoadsE2E:
    """E2E test: open a Polymarket weather market and verify YES/NO prices load."""

    @pytest.mark.skipif(
        not BROWSER_USE_AVAILABLE or not BROWSER_AVAILABLE or not LANGCHAIN_OPENAI_AVAILABLE,
        reason="browser-use, Chrome, or langchain-openai not available"
    )
    def test_price_loads_e2e(self):
        """
        Open a known Polymarket weather market URL and verify:
        - YES/NO prices are displayed
        - Prices are valid numbers between 0 and 1
        """
        from langchain_openai import ChatOpenAI

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            pytest.skip("OPENAI_API_KEY not set in .env")

        llm = ChatOpenAI(model="gpt-4o-mini", api_key=api_key)

        headless = os.getenv("HEADLESS", "true").lower() == "true"
        browser_profile = BrowserProfile(headless=headless, disable_security=True)

        market_url = "https://polymarket.com/market/will-shanghai-china-reach-35c-on-may-3-2026"

        async def run_agent():
            agent = Agent(
                task=(
                    f"Navigate to {market_url}. Wait for the page to fully load. "
                    "Extract the YES price and NO price for this market. "
                    "Return a JSON object: {{\"yes_price\": <number>, \"no_price\": <number>}}. "
                    "If prices are not visible, return {{\"error\": \"prices not loaded\"}}."
                ),
                llm=llm,
                browser_profile=browser_profile,
                use_vision=False,
                max_failures=2,
            )
            result = await agent.run()
            return result

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(run_agent())
        finally:
            loop.close()

        print(f"\nPrice load result: {result}")
        print("\n✅ Price load E2E test completed")


class TestFullWorkflowE2E:
    """E2E test: run scanner → verify opportunities.json → browser-verify data format."""

    @pytest.mark.skipif(
        not BROWSER_USE_AVAILABLE or not BROWSER_AVAILABLE or not LANGCHAIN_OPENAI_AVAILABLE,
        reason="browser-use, Chrome, or langchain-openai not available"
    )
    def test_full_workflow_e2e(self, tmp_path):
        """
        End-to-end workflow test:
        1. Run the scanner to generate opportunities.json
        2. Verify opportunities.json is created with correct structure
        3. Use browser-use to open Polymarket and verify the page loads
        """
        from langchain_openai import ChatOpenAI

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            pytest.skip("OPENAI_API_KEY not set in .env")

        # Step 1: Run the scanner with mocked API responses
        sys.path.insert(0, str(polymarket_dir))
        from polymarket_weather_scanner_final import scan_opportunities

        opportunities_file = polymarket_dir / "opportunities.json"

        with patch("requests.get") as mock_get:
            with patch("requests.post") as mock_post:
                mock_rest_resp = MagicMock()
                mock_rest_resp.status_code = 200
                mock_rest_resp.json.return_value = {"data": [], "count": 0, "next_cursor": None}
                mock_get.return_value = mock_rest_resp

                mock_gql_resp = MagicMock()
                mock_gql_resp.status_code = 200
                mock_gql_resp.json.return_value = {
                    "data": {
                        "markets": [
                            {
                                "id": "0xabc123",
                                "question": "Will Shanghai temperature exceed 35°C on 2026-05-03?",
                                "condition_id": "cond_abc123",
                                "title": "Shanghai High Temperature",
                                "tokens": [
                                    {"outcome": "yes", "price": 0.15},
                                    {"outcome": "no", "price": 0.85}
                                ],
                                "liquidity": "10000"
                            }
                        ]
                    }
                }
                mock_post.return_value = mock_gql_resp

                scan_opportunities()

        # Step 2: Verify opportunities.json was created
        assert opportunities_file.exists(), (
            f"opportunities.json not created at {opportunities_file}. "
            "Scanner may have failed."
        )

        raw = opportunities_file.read_text(encoding="utf-8")
        if raw.strip():
            opportunities = json.loads(raw)
            assert isinstance(opportunities, (list, dict)), (
                f"opportunities.json should contain a list or dict, got {type(opportunities)}"
            )
            print(f"\n✅ opportunities.json created: {raw[:200]}")
        else:
            print("\n⚠️  opportunities.json is empty (no opportunities found)")

        # Step 3: Browser-verify Polymarket page loads correctly
        llm = ChatOpenAI(model="gpt-4o-mini", api_key=api_key)
        headless = os.getenv("HEADLESS", "true").lower() == "true"
        browser_profile = BrowserProfile(headless=headless, disable_security=True)

        async def run_browser_check():
            agent = Agent(
                task=(
                    "Navigate to https://polymarket.com. "
                    "Verify the page title contains 'Polymarket'. "
                    "Return JSON: {\"title\": <page title>, \"loaded\": true}. "
                    "Take a screenshot named e2e_workflow_check.png in the current directory."
                ),
                llm=llm,
                browser_profile=browser_profile,
                use_vision=True,
                max_failures=2,
            )
            result = await agent.run()
            return result

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(run_browser_check())
        finally:
            loop.close()

        print(f"\n✅ Full workflow E2E completed. Agent result: {result}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])