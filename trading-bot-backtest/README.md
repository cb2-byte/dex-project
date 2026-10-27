# Trading Bot Backtester 🪙

Simple backtesting framework for Coinbase and Polymarket strategies.

**For:** Colin (no coding experience, learning as we go)
**Budget:** £100 each platform
**Data-conscious:** Works on 5G tether

## Quick Start

1. **Check Python is working:**
   ```bash
   python3 --version
   ```

2. **Install dependencies (one-time):**
   ```bash
   pip3 install requests
   ```

3. **Run a backtest:**
   ```bash
   python3 backtest_coinbase_dca.py
   ```

## What's Included

| File | What it does |
|------|--------------|
| `backtest_coinbase_dca.py` | Tests DCA strategy on BTC/ETH historical data |
| `backtest_polymarket_simple.py` | Tests prediction strategy (uses sample data) |
| `fetch_coinbase_data.py` | Gets real price data from Coinbase (caches locally) |
| `utils.py` | Helper functions (don't touch) |

## How It Works

1. **Fetches data** (or uses cached data to save bandwidth)
2. **Runs your strategy** against historical prices
3. **Shows results** - what you'd have made/lost

## Strategies

**DCA (Dollar Cost Average):** Buy £10 of BTC every week, regardless of price. Boring but historically works.

**Polymarket Simple:** Bet on outcomes with >60% confidence (sample data for learning).

## Tips

- Cache files save data — don't delete them
- Start small, learn patterns
- Backtesting ≠ guaranteed profits
- Real trading has fees, slippage, emotions

---

Questions? Ask Penny 🐱
