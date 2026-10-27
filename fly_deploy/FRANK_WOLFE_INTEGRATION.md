# Frank-Wolfe Portfolio Optimizer - Integration Guide

## What This Does

Replaces independent Kelly sizing with **portfolio-level optimization** across all simultaneous trading signals.

**Benefits:**
- Better capital allocation when multiple signals fire at once
- Respects all constraints (daily limits, per-asset caps, bankroll %)
- Projection-free = fast enough for real-time trading
- Adaptive step-size for better convergence

## Files Created

```
/Users/colinbrennan/.openclaw/workspace/
├── frank_wolfe_optimizer.py    # Core FW algorithm
├── portfolio_trader.py          # Trading wrapper
├── .portfolio-config.json       # Configuration
└── .portfolio-state.json        # Daily state (auto-created)
```

## Quick Start

### 1. Test the optimizer

```bash
cd /Users/colinbrennan/.openclaw/workspace
python3 frank_wolfe_optimizer.py
python3 portfolio_trader.py
```

### 2. Integrate into existing bots

**Option A: Full portfolio mode** (recommended)

Replace individual bot sizing logic with:

```python
from portfolio_trader import PortfolioTrader

# Initialize once at bot startup
trader = PortfolioTrader()

# In your trading loop, collect signals
trader.add_signal(
    asset="ETH",
    direction="UP",
    edge=0.08,  # Your edge calculation
    confidence=0.75,  # Your signal confidence
    market_id="eth_5m_up_abc123"
)

# After collecting all signals (e.g., every 60s)
def execute_trade(market_id, stake, direction):
    # Your existing execution logic here
    order = client.create_and_post_order({...})
    return order['orderID']

result = trader.optimize_and_execute(execution_callback=execute_trade)
```

**Option B: Hybrid mode**

Keep existing bots running independently, but use FW for sizing:

```python
from frank_wolfe_optimizer import FrankWolfeOptimizer, TradeOpportunity

# When you have a signal
opportunities = [
    TradeOpportunity(
        market_id="eth_5m_up",
        direction="UP",
        asset="ETH",
        edge=0.08,
        confidence=0.75,
        max_stake=50.0
    )
]

optimizer = FrankWolfeOptimizer(
    total_budget=100.0,
    max_daily_exposure=100.0,
    paper_mode=True  # Start in paper mode!
)

allocation, metadata = optimizer.optimize(opportunities)
stake = allocation[0]  # Use FW-calculated stake
```

### 3. Configuration

Edit `.portfolio-config.json`:

```json
{
  "paper_mode": true,        // ← Set to false when ready for live
  "max_daily_exposure": 100.0,
  "max_per_trade": 50.0,
  "kelly_fraction": 0.25
}
```

### 4. Flip to live mode

Once you've tested in paper mode:

1. Check paper trading results (compare FW vs Kelly EV)
2. Set `"paper_mode": false` in `.portfolio-config.json`
3. Restart bots

## Migration Plan for Existing Bots

### ETH/BTC/LINK Traders

Current flow:
```
Price signal → Kelly sizing → Execute
```

New flow:
```
Price signal → Add to portfolio → Optimize → Execute all
```

**Changes needed:**
1. Import `PortfolioTrader` at top
2. Replace `place_trade()` calls with `trader.add_signal()`
3. Call `trader.optimize_and_execute()` once per cycle
4. Keep existing Telegram alerts

### Weather Trading Bot

Same pattern, but weather markets can be batched by city:

```python
# For each city with edge >= 5%
trader.add_signal(
    asset="WEATHER",
    direction="UP" if edge > 0 else "DOWN",
    edge=abs(edge),
    confidence=0.8,
    market_id=market_id,
    max_stake=20.0  # Lower cap for weather
)
```

## Monitoring

### Paper mode logs

```
[PAPER] Would execute: ETH UP $12.50
[PAPER] Would execute: BTC UP $8.30
Total expected value: $2.45
```

### Live mode logs

```
✅ EXECUTED: ETH UP $12.50 (order: abc123...)
✅ EXECUTED: BTC UP $8.30 (order: def456...)
Total stake: $20.80
```

### Daily state

Check `.portfolio-state.json` for:
- `total_traded_today`: Running total
- `trade_count`: Number of trades
- Auto-resets at midnight

## Comparison: FW vs Kelly

Run this to see the difference:

```python
trader = PortfolioTrader()
# ... add signals ...
comparison = trader.get_comparison()

print(f"Kelly EV: ${comparison['kelly']['expected_value']:.2f}")
print(f"FW EV: ${comparison['frank_wolfe']['expected_value']:.2f}")
print(f"Improvement: {comparison['improvement']:.1%}")
```

Expected: 5-15% EV improvement when multiple correlated signals fire.

## Troubleshooting

**"No signals to optimize"**
- Make sure you're calling `add_signal()` before `optimize()`

**"Daily exposure limit reached"**
- Check `.portfolio-state.json`
- Resets at midnight, or call `trader.reset_daily_state()`

**Optimization too slow**
- Reduce `max_iterations` in optimizer (default 50)
- Should be <10ms for <10 signals

**Paper mode not logging**
- Check `paper_mode: true` in config
- Logs go to stdout, check bot logs

## Next Steps

1. ✅ Test optimizer standalone (`python3 portfolio_trader.py`)
2. ⏳ Integrate into one bot first (ETH trader)
3. ⏳ Run in paper mode for 24-48h
4. ⏳ Compare results vs Kelly
5. ⏳ Flip to live mode
6. ⏳ Roll out to other bots

---

**Questions?** The optimizer is fully documented in the code. Key methods:
- `FrankWolfeOptimizer.optimize()` - Core algorithm
- `PortfolioTrader.optimize_and_execute()` - Full pipeline
- `PortfolioTrader.get_comparison()` - FW vs Kelly
