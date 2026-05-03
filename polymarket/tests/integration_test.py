"""
Integration tests for Polymarket trading system.
Tests basic functionality of all core modules.
"""

import sys
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Add workspace to path for imports
workspace_path = Path(__file__).parent.parent.parent
if str(workspace_path) not in sys.path:
    sys.path.insert(0, str(workspace_path))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_api_client():
    """Test PolymarketAPIClient initialization"""
    try:
        from polymarket.core import PolymarketAPIClient
        
        logger.info("✅ Testing PolymarketAPIClient...")
        
        client = PolymarketAPIClient(
            rate_limit_calls=100,
            rate_limit_period=60,
            timeout=10
        )
        
        # Test health check would fail without real API, but structure is valid
        assert client.BASE_URL == "https://gamma-api.polymarket.com"
        assert client.timeout == 10
        assert client.rate_limit_calls == 100
        
        logger.info("✅ PolymarketAPIClient initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ PolymarketAPIClient test failed: {e}")
        return False


def test_account_manager():
    """Test AccountManager initialization and operations"""
    try:
        from polymarket.core import AccountManager
        
        logger.info("✅ Testing AccountManager...")
        
        account = AccountManager("0x1234567890abcdef1234567890abcdef12345678")
        
        # Validate wallet
        assert account.validate_wallet()
        
        # Set balance
        account.set_balance(50.0)
        balance = account.get_balance()
        assert balance["total"] == 50.0
        assert balance["available"] == 50.0
        
        # Set risk limits
        account.set_risk_limits(
            max_position_size=10.0,
            max_single_trade=5.0,
            daily_loss_limit=2.5
        )
        
        # Test affordability
        can_afford, reason = account.can_afford_trade(3.0)
        assert can_afford
        
        can_afford, reason = account.can_afford_trade(100.0)
        assert not can_afford
        
        # Record a trade
        tx = account.record_trade(
            market_id="TEST_001",
            outcome="YES",
            side="buy",
            quantity=10,
            price=0.35
        )
        
        assert tx.total == 3.5
        assert tx.status == "confirmed"
        
        # Check position
        qty = account.get_position("TEST_001", "YES")
        assert qty == 10
        
        logger.info("✅ AccountManager tests passed")
        return True
        
    except Exception as e:
        logger.error(f"❌ AccountManager test failed: {e}")
        return False


def test_momentum_calculator():
    """Test MomentumCalculator signal generation"""
    try:
        from polymarket.strategy import MomentumCalculator
        
        logger.info("✅ Testing MomentumCalculator...")
        
        calc = MomentumCalculator(min_signal_strength=0.6)
        
        # Add sample price data with upward trend
        base_price = 0.45
        for i in range(35):
            days_ago = 35 - i
            ts = datetime.now() - timedelta(days=days_ago)
            # Simulate upward trend
            price = base_price + (0.05 * (35 - days_ago) / 35)
            calc.add_price_reading("TEST_MARKET", "YES", price, ts)
        
        # Calculate single timeframe
        signal_7d = calc.calculate_momentum_single("TEST_MARKET", "YES", 7)
        assert signal_7d.direction in ["up", "down", "neutral"]
        assert 0 <= signal_7d.strength <= 1.0
        
        # Calculate composite
        composite = calc.calculate_momentum_composite("TEST_MARKET", "YES")
        assert composite.consensus_signal in ["buy", "sell", "hold"]
        assert 0 <= composite.consensus_strength <= 1.0
        assert 0 <= composite.confidence <= 1.0
        
        # Get signals
        signals = calc.get_market_signals("TEST_MARKET")
        assert "YES" in signals
        
        logger.info("✅ MomentumCalculator tests passed")
        return True
        
    except Exception as e:
        logger.error(f"❌ MomentumCalculator test failed: {e}")
        return False


def test_value_screener():
    """Test ValueScreener fair value estimation"""
    try:
        from polymarket.strategy import ValueScreener
        
        logger.info("✅ Testing ValueScreener...")
        
        screener = ValueScreener(edge_threshold_percentage=2.0)
        
        # Estimate fair value
        estimate = screener.estimate_fair_value(
            market_id="TEST_MARKET",
            outcome="YES",
            current_price=0.35,
            data_sources={
                "news_analysis": 0.45,
                "historical_frequency": 0.40,
                "expert_consensus": 0.42,
                "volume_analysis": 0.38
            }
        )
        
        assert 0 < estimate.my_estimate < 1.0
        assert estimate.edge_type is not None
        assert estimate.kelly_fraction >= 0
        
        # Screen market
        result = screener.screen_market(
            market_id="TEST_MARKET",
            market_title="Test Market",
            outcomes=["YES", "NO"],
            current_prices={"YES": 0.35, "NO": 0.65},
            data_sources={
                "YES": {
                    "news_analysis": 0.45,
                    "historical_frequency": 0.40,
                    "expert_consensus": 0.42,
                    "volume_analysis": 0.38
                },
                "NO": {
                    "news_analysis": 0.55,
                    "historical_frequency": 0.60,
                    "expert_consensus": 0.58,
                    "volume_analysis": 0.62
                }
            }
        )
        
        assert len(result.estimates) == 2
        assert result.edge_quality in ["poor", "fair", "good", "excellent"]
        assert 0 <= result.market_efficiency <= 1.0
        
        logger.info("✅ ValueScreener tests passed")
        return True
        
    except Exception as e:
        logger.error(f"❌ ValueScreener test failed: {e}")
        return False


def test_correlation_analyzer():
    """Test CorrelationAnalyzer portfolio analysis"""
    try:
        from polymarket.strategy import CorrelationAnalyzer
        
        logger.info("✅ Testing CorrelationAnalyzer...")
        
        analyzer = CorrelationAnalyzer(max_allowed_correlation=0.3)
        
        # Add price data for two markets
        base_price = 0.5
        for i in range(30):
            days_ago = 30 - i
            ts = datetime.now() - timedelta(days=days_ago)
            
            # Market 1: upward trend
            price1 = base_price + (0.05 * (30 - days_ago) / 30)
            analyzer.add_price_reading("MARKET_1", "YES", price1, ts)
            
            # Market 2: independent
            price2 = 0.50  # Constant
            analyzer.add_price_reading("MARKET_2", "YES", price2, ts)
        
        # Get correlation
        corr = analyzer.get_correlation(
            "MARKET_1", "YES",
            "MARKET_2", "YES",
            timeframe_days=30
        )
        
        assert -1.0 <= corr.correlation <= 1.0
        assert corr.data_points > 0
        
        # Analyze portfolio
        positions = {
            "MARKET_1_YES": 1.0,
            "MARKET_2_YES": 1.0
        }
        
        analysis = analyzer.analyze_portfolio(positions)
        assert 0 <= analysis.diversification_score <= 1.0
        assert 0 <= analysis.concentration_risk <= 1.0
        assert analysis.portfolio_efficiency in ["poor", "fair", "good", "excellent"]
        assert len(analysis.recommendations) > 0
        
        # Check if can add position
        can_add, reason = analyzer.can_add_position(
            "MARKET_3", "YES",
            positions
        )
        assert isinstance(can_add, bool)
        
        logger.info("✅ CorrelationAnalyzer tests passed")
        return True
        
    except Exception as e:
        logger.error(f"❌ CorrelationAnalyzer test failed: {e}")
        return False


def test_config_loading():
    """Test configuration file loading"""
    try:
        logger.info("✅ Testing configuration loading...")
        
        config_path = Path(__file__).parent.parent / "config" / "polymarket_50usd_trial_config.json"
        
        with open(config_path) as f:
            config = json.load(f)
        
        # Verify key sections
        assert "account" in config
        assert config["account"]["capital"] == 50.0
        
        assert "risk_management" in config
        assert config["risk_management"]["max_position_size"] == 10.0
        
        assert "strategy" in config
        assert config["strategy"]["momentum"]["enabled"]
        
        logger.info("✅ Configuration loading tests passed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Configuration test failed: {e}")
        return False


def main():
    """Run all integration tests"""
    logger.info("\n" + "=" * 70)
    logger.info("🚀 Polymarket Trading System - Integration Tests")
    logger.info("=" * 70 + "\n")
    
    tests = [
        ("API Client", test_api_client),
        ("Account Manager", test_account_manager),
        ("Momentum Calculator", test_momentum_calculator),
        ("Value Screener", test_value_screener),
        ("Correlation Analyzer", test_correlation_analyzer),
        ("Configuration", test_config_loading),
    ]
    
    results = []
    for name, test_fn in tests:
        try:
            passed = test_fn()
            results.append((name, passed))
        except Exception as e:
            logger.error(f"❌ Test {name} crashed: {e}")
            results.append((name, False))
    
    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("📊 Test Results Summary")
    logger.info("=" * 70)
    
    passed_count = sum(1 for _, p in results if p)
    total_count = len(results)
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        logger.info(f"  {status:10s} - {name}")
    
    logger.info("=" * 70)
    logger.info(f"✅ Total: {passed_count}/{total_count} tests passed")
    logger.info("=" * 70 + "\n")
    
    return passed_count == total_count


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
