#!/usr/bin/env python3
"""Test Frank-Wolfe with multiple opportunities to show diversification"""

from frank_wolfe_optimizer import FrankWolfeOptimizer, TradeOpportunity

print("Test 1: Multiple strong signals")
print("=" * 60)

# Simulate multiple good opportunities firing at once
opportunities = [
    TradeOpportunity("eth_5m_up", "UP", "ETH", 0.12, 0.85),   # edge*conf = 0.102
    TradeOpportunity("btc_5m_up", "UP", "BTC", 0.10, 0.80),   # edge*conf = 0.080
    TradeOpportunity("link_5m_down", "DOWN", "LINK", 0.15, 0.70),  # edge*conf = 0.105
    TradeOpportunity("sol_5m_up", "UP", "SOL", 0.08, 0.75),   # edge*conf = 0.060
]

optimizer = FrankWolfeOptimizer(
    total_budget=100.0,
    max_daily_exposure=100.0,
    max_per_trade=50.0,
    max_bankroll_pct=0.50,  # Allow 50% allocation
    paper_mode=True
)

allocation, meta = optimizer.optimize(opportunities)

print(f"\nTotal allocated: ${meta['total_allocated']:.2f}")
print(f"Total EV: ${meta['total_expected_value']:.2f}")
print(f"Iterations: {meta['iterations']}\n")

print("Allocation:")
for i, opp in enumerate(opportunities):
    if allocation[i] > 0:
        print(f"  {opp.asset:4} {opp.direction:4}: ${allocation[i]:6.2f} (edge×conf = {opp.edge * opp.confidence:.3f})")

print("\n" + "=" * 60)
print("Test 2: Same signals, tighter constraints")
print("=" * 60)

optimizer2 = FrankWolfeOptimizer(
    total_budget=100.0,
    max_daily_exposure=60.0,      # Tighter daily limit
    max_per_trade=25.0,           # Tighter per-trade limit
    max_bankroll_pct=0.40,        # Only 40% of bankroll
    per_asset_caps={"ETH": 20.0, "BTC": 20.0, "LINK": 15.0},  # Per-asset caps
    paper_mode=True
)

allocation2, meta2 = optimizer2.optimize(opportunities)

print(f"\nTotal allocated: ${meta2['total_allocated']:.2f}")
print(f"Total EV: ${meta2['total_expected_value']:.2f}")
print(f"Iterations: {meta2['iterations']}\n")

print("Allocation:")
for i, opp in enumerate(opportunities):
    if allocation2[i] > 0:
        print(f"  {opp.asset:4} {opp.direction:4}: ${allocation2[i]:6.2f} (edge×conf = {opp.edge * opp.confidence:.3f})")

print("\n" + "=" * 60)
print("Test 3: Compare FW vs Kelly across scenarios")
print("=" * 60)

comparison = optimizer.compare_with_kelly(opportunities)
print(f"\nScenario 1 (loose constraints):")
print(f"  Kelly EV: ${comparison['kelly']['expected_value']:.2f}")
print(f"  FW EV:    ${comparison['frank_wolfe']['expected_value']:.2f}")
print(f"  Improvement: {comparison['improvement']:.1%}")

comparison2 = optimizer2.compare_with_kelly(opportunities)
print(f"\nScenario 2 (tight constraints):")
print(f"  Kelly EV: ${comparison2['kelly']['expected_value']:.2f}")
print(f"  FW EV:    ${comparison2['frank_wolfe']['expected_value']:.2f}")
print(f"  Improvement: {comparison2['improvement']:.1%}")
