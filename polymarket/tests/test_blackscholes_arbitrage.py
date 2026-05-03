# -*- coding: utf-8 -*-
"""
BlackScholes Arbitrage Scanner Test Suite

Strategy Source: @MrRyanChi Twitter

Test Cases:
1. Complementary Markets Arbitrage (P(A) + P(NOT A) < 100%)
2. Logical Arbitrage (P(A) > P(B) when A implies B)
3. Decomposed Markets Arbitrage (Sum of all outcomes > 100%)
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from arbitrage.blackscholes_arbitrage_scanner import BlackScholesArbitrageScanner


def test_complementary_arbitrage():
    """Test complementary markets arbitrage"""
    print("\n=== Test 1: Complementary Arbitrage ===\n")
    
    markets = [
        {
            'question': 'Bitcoin EOY 2025 above $150,000?',
            'price': 0.48,
            'market_id': 'test_btc_above_150k'
        },
        {
            'question': 'Bitcoin EOY 2025 below $150,000?',
            'price': 0.48,
            'market_id': 'test_btc_below_150k'
        },
    ]
    
    scanner = BlackScholesArbitrageScanner(min_profit=0.02)
    results = scanner.scan_complementary_markets(markets)
    
    assert len(results) == 1, f"Expected 1 opportunity, got {len(results)}"
    
    arb = results[0]
    assert arb['type'] == 'complementary'
    assert abs(arb['total'] - 0.96) < 0.01
    assert abs(arb['profit'] - 0.04) < 0.01
    
    print(f"[OK] Complementary arbitrage detected:")
    print(f"  Total: {arb['total']:.1%}, Profit: {arb['profit']:.1%}")
    print(f"  Market A: {arb['market_a'][:50]}")
    print(f"  Market B: {arb['market_b'][:50]}")


def test_logical_arbitrage():
    """Test logical arbitrage"""
    print("\n=== Test 2: Logical Arbitrage ===\n")
    
    markets = [
        {
            'question': 'Trump wins 2024 election?',
            'price': 0.52,
            'market_id': 'test_trump_wins'
        },
        {
            'question': 'Republican wins 2024 election?',
            'price': 0.48,
            'market_id': 'test_republican_wins'
        },
    ]
    
    scanner = BlackScholesArbitrageScanner(min_profit=0.02)
    results = scanner.scan_logical_arbitrage(markets)
    
    assert len(results) == 1, f"Expected 1 opportunity, got {len(results)}"
    
    arb = results[0]
    assert arb['type'] == 'logical'
    assert abs(arb['profit'] - 0.04) < 0.01
    
    print(f"[OK] Logical arbitrage detected:")
    print(f"  Violation: {arb['violation']}")
    print(f"  Profit: {arb['profit']:.1%}")
    print(f"  Strategy: Sell Trump, Buy Republican")


def test_decomposed_arbitrage():
    """Test decomposed markets arbitrage"""
    print("\n=== Test 3: Decomposed Arbitrage ===\n")
    
    markets = [
        {'question': 'BTC EOY 2025 price: below $50K', 'price': 0.10, 'market_id': 'range_1'},
        {'question': 'BTC EOY 2025 price: $50K-$100K', 'price': 0.35, 'market_id': 'range_2'},
        {'question': 'BTC EOY 2025 price: $100K-$150K', 'price': 0.30, 'market_id': 'range_3'},
        {'question': 'BTC EOY 2025 price: $150K-$200K', 'price': 0.20, 'market_id': 'range_4'},
        {'question': 'BTC EOY 2025 price: above $200K', 'price': 0.08, 'market_id': 'range_5'},
    ]
    
    scanner = BlackScholesArbitrageScanner(min_profit=0.02)
    results = scanner.scan_decomposed_markets(markets)
    
    assert len(results) == 1, f"Expected 1 opportunity, got {len(results)}"
    
    arb = results[0]
    assert arb['type'] == 'decomposed'
    assert abs(arb['total'] - 1.03) < 0.01
    assert abs(arb['profit'] - 0.03) < 0.01
    
    print(f"[OK] Decomposed arbitrage detected:")
    print(f"  Subject: {arb['subject']}")
    print(f"  Total: {arb['total']:.1%}, Profit: {arb['profit']:.1%}")
    print(f"  Markets: {len(arb['markets'])} ranges")


def test_scan_all():
    """Test full scan"""
    print("\n=== Test 4: Full Scan ===\n")
    
    markets = [
        # Complementary
        {'question': 'Bitcoin EOY 2025 above $150,000?', 'price': 0.48, 'market_id': 'btc_above'},
        {'question': 'Bitcoin EOY 2025 below $150,000?', 'price': 0.48, 'market_id': 'btc_below'},
        
        # Logical
        {'question': 'Trump wins 2024 election?', 'price': 0.52, 'market_id': 'trump'},
        {'question': 'Republican wins 2024 election?', 'price': 0.48, 'market_id': 'republican'},
        
        # Decomposed
        {'question': 'BTC EOY 2025 price: below $50K', 'price': 0.10, 'market_id': 'range_1'},
        {'question': 'BTC EOY 2025 price: $50K-$100K', 'price': 0.35, 'market_id': 'range_2'},
        {'question': 'BTC EOY 2025 price: $100K-$150K', 'price': 0.30, 'market_id': 'range_3'},
        {'question': 'BTC EOY 2025 price: $150K-$200K', 'price': 0.20, 'market_id': 'range_4'},
        {'question': 'BTC EOY 2025 price: above $200K', 'price': 0.08, 'market_id': 'range_5'},
    ]
    
    scanner = BlackScholesArbitrageScanner(min_profit=0.02)
    results = scanner.scan_all(markets)
    
    assert len(results['complementary']) == 1
    assert len(results['logical']) == 1
    assert len(results['decomposed']) == 1
    
    total = sum(len(opps) for opps in results.values())
    print(f"[OK] Full scan complete:")
    print(f"  Complementary: {len(results['complementary'])} found")
    print(f"  Logical: {len(results['logical'])} found")
    print(f"  Decomposed: {len(results['decomposed'])} found")
    print(f"  Total: {total} opportunities")


def test_min_profit_threshold():
    """Test min profit threshold"""
    print("\n=== Test 5: Min Profit Threshold ===\n")
    
    markets = [
        # Small profit (1%) should be filtered
        {'question': 'Bitcoin EOY 2025 above $150,000?', 'price': 0.495, 'market_id': 'btc_above'},
        {'question': 'Bitcoin EOY 2025 below $150,000?', 'price': 0.495, 'market_id': 'btc_below'},
    ]
    
    # Min profit 2%
    scanner = BlackScholesArbitrageScanner(min_profit=0.02)
    results = scanner.scan_complementary_markets(markets)
    assert len(results) == 0, "Should filter out 1% profit"
    
    # Min profit 0.5%
    scanner = BlackScholesArbitrageScanner(min_profit=0.005)
    results = scanner.scan_complementary_markets(markets)
    assert len(results) == 1, "Should accept 1% profit"
    
    print(f"[OK] Min profit threshold working correctly")
    print(f"  2% threshold: Filtered out 1% profit")
    print(f"  0.5% threshold: Accepted 1% profit")


if __name__ == '__main__':
    print("\n" + "="*70)
    print("BlackScholes Arbitrage Scanner Test Suite")
    print("Strategy Source: @MrRyanChi")
    print("="*70)
    
    try:
        test_complementary_arbitrage()
        test_logical_arbitrage()
        test_decomposed_arbitrage()
        test_scan_all()
        test_min_profit_threshold()
        
        print("\n" + "="*70)
        print("All Tests Passed!")
        print("="*70 + "\n")
    
    except AssertionError as e:
        print(f"\n[FAIL] Test Failed: {e}\n")
        sys.exit(1)
    
    except Exception as e:
        print(f"\n[ERROR] {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
