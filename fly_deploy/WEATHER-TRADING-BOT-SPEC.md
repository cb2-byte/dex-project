# Weather Trading Bot — Build Spec

**Session Goal:** Build an automated weather trading bot for Polymarket that takes positions BEFORE settlement (not just settling post-close).

---

## 1. Target Markets

### Cities (Start with 5 liquid markets):
| City | Airport | ICAO | Typical Volume |
|------|---------|------|----------------|
| London | London City | EGLC | High |
| New York | LaGuardia | KLGA | High |
| Tokyo | Haneda | RJTT | Medium |
| Singapore | Changi | WSSS | Medium |
| Sydney | Kingsford Smith | YSSY | Medium |

**Expand to full 9 later** (Dubai, Frankfurt, Paris, Mumbai, Hong Kong)

### Market Types:
- **Daily High Temperature** (primary)
- **Daily Low Temperature** (secondary)
- **Precipitation Yes/No** (later)

---

## 2. Resolution Sources (CRITICAL)

Each market resolves against a SPECIFIC source. Must match exactly:

| City | Resolution Source | URL Pattern |
|------|-------------------|-------------|
| London | Weather Underground | `wunderground.com/history/daily/gb/london/EGLC` |
| New York | Weather Underground | `wunderground.com/history/daily/us/ny/new-york/KLGA` |
| Tokyo | Weather Underground | `wunderground.com/history/daily/jp/tokyo/RJTT` |
| Singapore | Weather Underground | `wunderground.com/history/daily/sg/singapore/WSSS` |
| Sydney | Weather Underground | `wunderground.com/history/daily/au/nsw/sydney/YSSY` |

**Key:** Model must predict what WU will report at that specific station, NOT city-center forecasts.

---

## 3. Forecast Data Sources

### Primary: Open-Meteo (Free, No API Key)
- **Why:** Free, ensemble data, global coverage, reliable
- **Endpoint:** `https://api.open-meteo.com/v1/forecast`
- **Models:** GFS, ECMWF, ICON ensemble members
- **Data Needed:**
  - Hourly temperature forecasts (7 days)
  - Ensemble spread (51 ECMWF members if available)
  - Precipitation probability

### Secondary: Weather Underground API (Existing Key)
- **API Key:** Already stored in `.weather-keys.json`
- **Use:** Cross-reference, airport-specific stations

### Fallback: NWS/NOAA (US cities only)
- **Endpoint:** `api.weather.gov`
- **Use:** Backup for NYC

---

## 4. Edge Calculation Logic

### Step 1: Get Market Prices
```python
# For each temperature bucket (e.g., 18-19°C, 20-21°C, etc.)
market_prices = {
    "18-19": 0.25,  # 25¢ = 25% implied probability
    "20-21": 0.35,
    "22-23": 0.20,
    # ...
}
```

### Step 2: Calculate Model Probabilities
```python
# Method A: Normal Distribution (simpler)
forecast_high = 20.5°C
forecast_std = 2.5°C  # Based on 48hr forecast error

# Calculate probability mass in each bucket
model_probabilities = {
    "18-19": 0.18,  # 18% model probability
    "20-21": 0.42,  # 42% model probability
    "22-23": 0.25,
    # ...
}

# Method B: Ensemble Counting (better)
# Count how many ensemble members fall in each bucket
# 51 members → 35 in 20-21°C bucket = 68% probability
```

### Step 3: Calculate Edge
```python
edge = (model_probability - market_price) * 100

# Example:
# Market: 20-21°C @ 35¢ (35% implied)
# Model: 42% probability
# Edge: (0.42 - 0.35) * 100 = 7% edge ✅ TRADE
```

### Step 4: Minimum Edge Threshold
- **Trade if edge ≥ 5%** (adjustable)
- **Pass if edge < 5%** (not worth the risk/spread)

---

## 5. Position Sizing (Kelly Criterion)

### Formula:
```python
f = (q - p) / (1 - p)

# Where:
# q = model probability (e.g., 0.42)
# p = market price (e.g., 0.35)
# f = fraction of bankroll to bet
```

### Example:
```python
q = 0.42  # Model says 42%
p = 0.35  # Market priced at 35%
f = (0.42 - 0.35) / (1 - 0.35) = 0.108 = 10.8%

# Full Kelly = 10.8% of bankroll
# Quarter Kelly = 2.7% of bankroll (RECOMMENDED)
```

### Position Caps:
- **Max per trade:** $50 (until proven track record)
- **Max per city per day:** $100
- **Total exposure cap:** $500 across all weather markets

---

## 6. Trading Logic Flow

```
┌─────────────────────────────────┐
│  Check for active weather markets │
└───────────────┬─────────────────┘
                │
                ▼
┌─────────────────────────────────┐
│  Pull forecast data (Open-Meteo) │
│  - Hourly temps for next 7 days  │
│  - Ensemble spread               │
└───────────────┬─────────────────┘
                │
                ▼
┌─────────────────────────────────┐
│  Calculate daily high for each city │
│  - Extract max temp from forecast   │
│  - Build probability distribution   │
└───────────────┬─────────────────┘
                │
                ▼
┌─────────────────────────────────┐
│  Get current market prices       │
│  - Polymarket API or scrape      │
│  - All temperature buckets       │
└───────────────┬─────────────────┘
                │
                ▼
┌─────────────────────────────────┐
│  Calculate edge for each bucket  │
│  - Edge = (model_prob - price)   │
│  - Filter: edge >= 5%            │
└───────────────┬─────────────────┘
                │
                ▼
┌─────────────────────────────────┐
│  Size positions (Quarter Kelly)  │
│  - Apply caps ($50 max/trade)    │
│  - Check total exposure          │
└───────────────┬─────────────────┘
                │
                ▼
┌─────────────────────────────────┐
│  Place orders on Polymarket      │
│  - Use Polymarket API            │
│  - Limit orders preferred        │
└───────────────┬─────────────────┘
                │
                ▼
┌─────────────────────────────────┐
│  Log trade + send Telegram alert │
│  - City, bucket, price, edge     │
│  - Position size, order ID       │
└─────────────────────────────────┘
```

---

## 7. Forecast Update Monitoring

### Model Run Schedule:
| Model | Frequency | Typical Update Times (UTC) |
|-------|-----------|---------------------------|
| GFS (US) | Every 6 hrs | 00:00, 06:00, 12:00, 18:00 |
| ECMWF (EU) | Twice daily | 00:00, 12:00 |
| HRRR (US, short-range) | Hourly | Every hour |

### Bot Should:
1. **Re-check forecasts** after each major model update
2. **Recalculate edge** — new data may create/kill opportunities
3. **Adjust positions** if edge changes significantly
4. **Exit early** if thesis breaks (e.g., forecast shifts 5°C against you)

---

## 8. Risk Management

### Hard Limits:
- **Max loss per day:** $100
- **Max loss per week:** $400
- **Stop trading if:** Down 20% from peak bankroll

### Position Rules:
- **No trading < 12 hours to close** (too much variance)
- **No trading illiquid markets** (< $5k volume)
- **No more than 3 positions per city per day**

### Exit Conditions:
- **Hold to settlement** (primary strategy)
- **Early exit if:** Edge reverses by >10 percentage points
- **Early exit if:** Market price moves >50% in your favor (take profit)

---

## 9. Tech Stack

### Existing (Reuse):
- ✅ Weather API keys (`.weather-keys.json`)
- ✅ Telegram bot (same token/chat_id as crypto bots)
- ✅ Polymarket API credentials (same as crypto traders)
- ✅ Python 3, launchd for 24/7 running

### New Dependencies:
```bash
pip install open-meteo  # If available, or just use requests
pip install beautifulsoup4  # For scraping WU if needed
pip install polycrv  # Polymarket Python SDK (if exists)
```

### Files to Create:
- `weather-trading-bot.py` — Main bot logic
- `weather-trading-bot.plist` — launchd service
- `.weather-trading-config.json` — Edge thresholds, position limits
- `logs/weather-trades.json` — Trade log
- `logs/weather-pnl.json` — P&L tracking

---

## 10. Success Metrics (Track from Day 1)

### Log Every Trade:
```json
{
  "timestamp": "2026-05-03T14:30:00Z",
  "city": "London",
  "market": "High Temp 4 May 2026",
  "bucket": "20-21°C",
  "action": "BUY",
  "outcome": "YES",
  "shares": 50,
  "price": 0.35,
  "cost": 17.50,
  "model_probability": 0.42,
  "edge": 7.0,
  "kelly_fraction": 0.027,
  "order_id": "abc123...",
  "settlement_price": null,
  "pnl": null
}
```

### Weekly Review:
- Total trades
- Win rate (%)
- Average edge per trade
- P&L
- Best/worst city
- Best/worst forecast lead time

---

## 11. Build Session Agenda (4-5 Hours)

### Hour 1: Foundation
- [ ] Set up Open-Meteo API integration
- [ ] Pull forecast data for 5 cities
- [ ] Test against known historical data

### Hour 2: Edge Calculation
- [ ] Build probability distribution logic
- [ ] Compare model probs vs. market prices
- [ ] Implement edge filtering (≥5%)

### Hour 3: Position Sizing
- [ ] Implement Kelly criterion
- [ ] Add position caps and exposure limits
- [ ] Build config file for thresholds

### Hour 4: Trade Execution
- [ ] Integrate Polymarket API for order placement
- [ ] Add Telegram alerts
- [ ] Build trade logging

### Hour 5: Testing + Launch
- [ ] Paper trade test (no real money)
- [ ] Verify all 5 cities working
- [ ] Deploy via launchd
- [ ] Monitor first live signals

---

## 12. Known Gotchas

### Calibration Takes Time
- First 100 trades = data collection, not profit
- Model edge is real but needs calibration per city
- Track everything, adjust thresholds based on actuals

### Resolution Source Mismatch
- City-center forecast ≠ airport station
- Always verify against the EXACT resolution source
- WU airport stations can differ from city by 3-8°F

### Market Liquidity
- Some cities have thin order books
- Spreads can eat 5-10% of edge
- Stick to high-volume markets initially

### Forecast Model Bias
- GFS runs warm/cold depending on region
- ECMWF generally more accurate but not perfect
- Track model accuracy per city over time

---

## 13. Future Enhancements (Post-MVP)

### Phase 2:
- [ ] Add precipitation markets
- [ ] Expand to all 9 cities
- [ ] Multi-model ensemble (weight ECMWF higher)

### Phase 3:
- [ ] Paid ECMWF API access (if ROI proven)
- [ ] Machine learning calibration (train on historical errors)
- [ ] Auto-hedge across correlated cities

### Phase 4:
- [ ] Copy trading for other users
- [ ] Dashboard for live positions
- [ ] Discord/Telegram signal channel

---

## Notes from Penny (Session Prep)

**Before we start:**
1. Confirm Polymarket API access for order placement
2. Test Open-Meteo endpoints for all 5 cities
3. Have `.weather-keys.json` ready (already exists)
4. Decide on starting bankroll for weather trading

**During build:**
- Start simple — get ONE city working end-to-end first
- Then replicate pattern to other 4 cities
- Don't over-engineer — MVP first, optimize later

**After launch:**
- Monitor closely for first week
- Adjust edge threshold based on actual win rate
- Log EVERYTHING for calibration

---

**Ready to build? Let's make weather markets our ATM.** 🌤️💰

*— Penny 🐯*
