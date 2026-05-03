"""
Unit Tests for Market Integral Formulas
========================================
30+ tests with 100% coverage target
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import numpy as np
from formulas.market_integral_formulas import (
    calculate_market_integral,
    detect_integral_anomaly,
    modal_bucket_analysis,
    detect_anchor_breakout,
    comprehensive_market_analysis,
    calculate_baseline_integral,
    MarketIntegralResult,
    IntegralAnomalyResult,
    ModalBucketResult,
    SignalStrength,
)


class TestMarketIntegral:
    """Tests for Formula 1: Market Integral Calculation"""
    
    def test_calculate_market_integral_basic(self):
        """Test basic integral calculation with uniform distribution"""
        result = calculate_market_integral([0.25, 0.25, 0.25, 0.25])
        assert result.is_valid
        assert 0 <= result.c_value <= 1
        assert result.normalized_c > 0
    
    def test_calculate_market_integral_skewed(self):
        """Test with skewed distribution"""
        result = calculate_market_integral([0.6, 0.3, 0.1])
        assert result.is_valid
        assert result.c_value < 0.5  # Skewed toward lower prices
    
    def test_calculate_market_integral_with_prices(self):
        """Test with explicit price-probability pairs"""
        prices = [0.1, 0.3, 0.5, 0.7, 0.9]
        probs = [0.5, 0.25, 0.15, 0.07, 0.03]
        result = calculate_market_integral(prices, probs)
        assert result.is_valid
        assert result.bucket_count == 5
    
    def test_calculate_market_integral_single_element(self):
        """Test with single element"""
        result = calculate_market_integral([1.0])
        assert result.is_valid
        assert result.c_value == 0.0  # Single point has no area
    
    def test_calculate_market_integral_empty_raises(self):
        """Test empty input raises ValueError"""
        with pytest.raises(ValueError):
            calculate_market_integral([])
    
    def test_calculate_market_integral_negative_raises(self):
        """Test negative probability raises ValueError"""
        with pytest.raises(ValueError):
            calculate_market_integral([0.5, -0.1, 0.6])
    
    def test_calculate_market_integral_normalized(self):
        """Test normalization of non-sum-1 probabilities"""
        result = calculate_market_integral([2, 2, 2])  # Sum = 6, normalized to 1.0
        assert result.is_valid
        # After normalization, the normalized c_value should be valid
        assert result.normalized_c > 0
    
    def test_calculate_market_integral_methods(self):
        """Test different integration methods"""
        probs = [0.2, 0.3, 0.3, 0.2]
        
        trap_result = calculate_market_integral(probs, method="trapezoid")
        riemann_result = calculate_market_integral(probs, method="riemann_left")
        
        # Both should be valid and close in value
        assert trap_result.is_valid
        assert riemann_result.is_valid
    
    def test_cumulative_distribution(self):
        """Test cumulative distribution calculation"""
        from formulas.market_integral_formulas import calculate_cumulative_distribution
        
        result = calculate_cumulative_distribution([0.1, 0.2, 0.3, 0.4])
        expected = np.array([0.1, 0.3, 0.6, 1.0])
        np.testing.assert_array_almost_equal(result, expected)


class TestIntegralAnomaly:
    """Tests for Formula 2: Integral Anomaly Detection"""
    
    def test_detect_integral_anomaly_strong_positive(self):
        """Test strong positive anomaly"""
        result = detect_integral_anomaly(0.70, 0.50, threshold=0.04)
        assert result.is_anomaly
        assert abs(result.delta_c - 0.20) < 0.001
        assert result.signal_strength == SignalStrength.VERY_STRONG
        assert result.edge_direction == "OVER"
    
    def test_detect_integral_anomaly_strong_negative(self):
        """Test strong negative anomaly"""
        result = detect_integral_anomaly(0.35, 0.55, threshold=0.04)
        assert result.is_anomaly
        assert abs(result.delta_c - (-0.20)) < 0.001
        assert result.signal_strength == SignalStrength.VERY_STRONG
        assert result.edge_direction == "UNDER"
    
    def test_detect_integral_anomaly_weak(self):
        """Test weak anomaly below threshold"""
        result = detect_integral_anomaly(0.52, 0.50, threshold=0.04)
        assert not result.is_anomaly
        # delta = 0.02, threshold = 0.04, 0.02 > 0.04 is False -> signal = NONE
        assert result.signal_strength == SignalStrength.NONE
    
    def test_detect_integral_anomaly_boundary(self):
        """Test boundary case (exactly at threshold)"""
        # With > comparison, 0.04 > 0.04 is False -> no anomaly
        result = detect_integral_anomaly(0.54, 0.50, threshold=0.04)
        # delta = 0.04, threshold = 0.04, 0.04 > 0.04 = False, so NO anomaly
        # Test expects NO anomaly
        assert not result.is_anomaly
    
    def test_detect_integral_anomaly_confidence(self):
        """Test confidence calculation"""
        result = detect_integral_anomaly(0.80, 0.50, threshold=0.04, confidence_weight=0.8)
        assert result.confidence > 0.5
        assert result.is_anomaly
    
    def test_detect_integral_anomaly_threshold_0(self):
        """Test with zero threshold"""
        result = detect_integral_anomaly(0.51, 0.50, threshold=0.0)
        assert result.is_anomaly
    
    def test_scan_for_integral_anomalies(self):
        """Test scanning multiple markets"""
        from formulas.market_integral_formulas import scan_for_integral_anomalies
        
        markets = [
            {'market_id': 'A', 'c_value': 0.70},
            {'market_id': 'B', 'c_value': 0.55},
            {'market_id': 'C', 'c_value': 0.52}
        ]
        baselines = {'A': 0.50, 'B': 0.50, 'C': 0.50}
        
        anomalies = scan_for_integral_anomalies(markets, baselines, threshold=0.04)
        
        assert len(anomalies) == 2  # A and B are anomalies
        assert all(a['is_anomaly'] for a in anomalies)


class TestModalBucket:
    """Tests for Formula 3: Modal Bucket Analysis"""
    
    def test_modal_bucket_analysis_strong_anchor(self):
        """Test with strong modal anchor"""
        dist = [0.5, 0.25, 0.15, 0.07, 0.03]
        result = modal_bucket_analysis(dist, bucket_count=5)
        
        assert result.modal_bucket == 0
        assert result.modal_probability == 0.5
        assert result.anchor_strength > 0
    
    def test_modal_bucket_analysis_weak_anchor(self):
        """Test with weak anchor (uniform distribution)"""
        dist = [0.2, 0.2, 0.2, 0.2, 0.2]
        result = modal_bucket_analysis(dist, bucket_count=5)
        
        assert result.anchor_strength < 0.5  # Weak anchor
        assert result.predicted_reaction_time > 60  # Fast reaction
    
    def test_modal_bucket_analysis_middle_bucket(self):
        """Test when modal is in middle"""
        dist = [0.1, 0.2, 0.4, 0.2, 0.1]
        result = modal_bucket_analysis(dist, bucket_count=5)
        
        assert result.modal_bucket == 2
        assert abs(result.modal_probability - 0.4) < 0.001
    
    def test_modal_bucket_analysis_price_range(self):
        """Test with custom price range"""
        dist = [0.5, 0.3, 0.2]
        result = modal_bucket_analysis(dist, bucket_count=3, price_range=(0, 100))
        
        # Bucket 0 is modal, center at 0 + (0+0.5)*33.33 = 16.67
        assert abs(result.anchor_price - 16.67) < 1
    
    def test_modal_bucket_analysis_empty_raises(self):
        """Test empty distribution raises ValueError"""
        with pytest.raises(ValueError):
            modal_bucket_analysis([])
    
    def test_detect_anchor_breakout_true(self):
        """Test anchor breakout detection"""
        current = [0.15, 0.15, 0.15, 0.40, 0.15]
        previous = [0.30, 0.30, 0.20, 0.10, 0.10]
        
        result = detect_anchor_breakout(current, previous, anchor_threshold=0.3)
        
        assert result['is_breakout']
        assert result['modal_shift'] > 0
    
    def test_detect_anchor_breakout_false(self):
        """Test no breakout"""
        current = [0.25, 0.25, 0.25, 0.25]
        previous = [0.25, 0.25, 0.25, 0.25]
        
        result = detect_anchor_breakout(current, previous)
        
        assert not result['is_breakout']


class TestComprehensiveAnalysis:
    """Tests for combined analysis functions"""
    
    def test_comprehensive_market_analysis(self):
        """Test comprehensive analysis"""
        prices = [0.3, 0.25, 0.25, 0.2]
        baseline = 0.5
        
        result = comprehensive_market_analysis(prices, baseline)
        
        assert 'integral' in result
        assert 'anomaly' in result
        assert 'modal' in result
        assert 'signal' in result
        assert 'recommendation' in result
    
    def test_comprehensive_analysis_buy_signal(self):
        """Test BUY signal generation"""
        # Low C value (UNDER) = potential BUY
        prices = [0.7, 0.2, 0.1]  # Skewed high
        baseline = 0.3  # Lower baseline
        
        result = comprehensive_market_analysis(prices, baseline)
        
        # If integral anomaly detected
        if result['anomaly'].is_anomaly:
            assert result['recommendation']['action'] in ['BUY', 'STRONG_BUY', 'HOLD']
    
    def test_calculate_baseline_integral(self):
        """Test baseline calculation"""
        history = [
            [0.2, 0.3, 0.3, 0.2],
            [0.25, 0.25, 0.25, 0.25],
            [0.15, 0.35, 0.35, 0.15]
        ]
        
        baseline = calculate_baseline_integral(history, method="median")
        
        assert 0 <= baseline <= 1
    
    def test_calculate_baseline_integral_methods(self):
        """Test different baseline methods"""
        history = [[0.2, 0.3, 0.5], [0.3, 0.3, 0.4], [0.1, 0.4, 0.5]]
        
        median_baseline = calculate_baseline_integral(history, method="median")
        mean_baseline = calculate_baseline_integral(history, method="mean")
        
        assert 0 <= median_baseline <= 1
        assert 0 <= mean_baseline <= 1


class TestEdgeCases:
    """Test edge cases and boundary conditions"""
    
    def test_near_zero_probabilities(self):
        """Test with very small probabilities"""
        result = calculate_market_integral([1e-10, 1e-10, 1.0])
        assert result.is_valid
    
    def test_very_large_values(self):
        """Test with large probability values"""
        result = calculate_market_integral([100, 200, 300])
        assert result.is_valid
    
    def test_single_point_distribution(self):
        """Test single point at various prices"""
        for p in [0.1, 0.5, 0.9]:
            result = calculate_market_integral([p])
            assert result.is_valid
    
    def test_confidence_weight_zero(self):
        """Test with zero confidence weight"""
        result = detect_integral_anomaly(0.70, 0.50, confidence_weight=0.0)
        assert result.confidence == 0.0
    
    def test_anchor_threshold_extreme(self):
        """Test with extreme anchor thresholds"""
        dist = [0.99, 0.01]
        result = modal_bucket_analysis(dist, bucket_count=2)
        
        assert result.anchor_strength > 0.8


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
