# Polymarket Weather Markets - Station ID Reference

**Settlement Source:** Weather Underground (Wunderground.com)  
**Last Updated:** 2026-04-29

---

## Active Markets & Station IDs

| City | Station Name | ICAO Code | Wunderground Path | Unit |
|------|--------------|-----------|-------------------|------|
| **New York City** | LaGuardia Airport | `KLGA` | `/history/daily/us/ny/new-york-city/KLGA` | °F |
| **London** | London City Airport | `EGLC` | `/history/daily/gb/london/EGLC` | °C |
| **Paris** | Charles de Gaulle Airport | `LFPG` | `/history/daily/fr/paris/LFPG` | °C |
| **Tokyo** | Tokyo Haneda Airport | `RJTT` | `/history/daily/jp/tokyo/RJTT` | °C |
| **Chicago** | O'Hare Intl Airport | `KORD` | `/history/daily/us/il/chicago/KORD` | °F |
| **Jeddah** | King Abdulaziz Intl | `OEJN` | `/history/daily/sa/jeddah/OEJN` | °C |
| **Seattle** | Seattle-Tacoma Intl | `KSEA` | `/history/daily/us/wa/seattle/KSEA` | °F |
| **Los Angeles** | LAX Intl | `KLAX` | `/history/daily/us/ca/los-angeles/KLAX` | °F |
| **Seoul** | Incheon Intl | `RKSI` | `/history/daily/kr/seoul/RKSI` | °C |

---

## Wunderground URL Pattern

```
https://www.wunderground.com/history/daily/{country}/{region}/{city}/{STATION_ID}
```

**Examples:**
- NYC: `https://www.wunderground.com/history/daily/us/ny/new-york-city/KLGA`
- London: `https://www.wunderground.com/history/daily/gb/london/EGLC`
- Paris: `https://www.wunderground.com/history/daily/fr/paris/LFPG`
- Tokyo: `https://www.wunderground.com/history/daily/jp/tokyo/RJTT`

---

## API Integration Notes

### Weather Underground API
- **Docs:** https://www.wunderground.com/weather/api/
- **Endpoint:** `/history/daily` for historical settlement data
- **Rate Limits:** Free tier ~500 calls/day; Paid tiers available

### Open-Meteo (Alternative/Forecast)
- **Docs:** https://open-meteo.com/
- **No API key required** for basic usage
- Supports ICAO station lookups
- Good for ensemble forecasts (GFS, ECMWF)

### Polymarket CLOB API
- **Docs:** https://polymarket.github.io/polymarket-docs/
- **Requires:** API Key, Secret, Passphrase
- **Network:** Polygon (USDC for trading, POL for gas)

---

## Bot Logic Checklist

### Pre-Trade Validation
- [ ] Verify market uses expected station ID (check Polymarket rules)
- [ ] Confirm current daily high from Wunderground
- [ ] Check forecast probability (Open-Meteo/Meteomatics)
- [ ] Validate time window (7 PM local = snipe zone)

### "Hairdryer Filter" (Tampering Detection)
- [ ] Reject if temp spikes >3°C in <10 minutes at single station
- [ ] Cross-check with nearby stations (same city, different airport)
- [ ] Pause trading if Polymarket disputes market resolution

### Settlement Tracking
- [ ] Monitor UMA oracle for resolution proposals
- [ ] Watch for station switches (e.g., CDG → Le Bourget)
- [ ] Track dispute windows (usually 24-48h post-resolution)

---

## Time Zone Reference

| City | Local Time | UTC Offset | Settlement Window Ends |
|------|------------|------------|------------------------|
| NYC | EST/EDT | UTC-5/-4 | 23:59 local (~04:00 UTC next day) |
| Chicago | CST/CDT | UTC-6/-5 | 23:59 local (~05:00 UTC next day) |
| London | GMT/BST | UTC+0/+1 | 23:59 local (~23:00 UTC same day) |
| Paris | CET/CEST | UTC+1/+2 | 23:59 local (~22:00 UTC same day) |
| Tokyo | JST | UTC+9 | 23:59 local (~15:00 UTC same day) |
| Seoul | KST | UTC+9 | 23:59 local (~15:00 UTC same day) |
| Jeddah | AST | UTC+3 | 23:59 local (~21:00 UTC same day) |

**Bot Scheduling:** Run 24/7 or schedule scans around each city's 19:00-23:59 local window.

---

## Notes

- Polymarket settles on **whole degrees** only (no decimals)
- Markets resolve to **temperature ranges** (e.g., "60-61°F" or "16°C")
- Some markets use "X or below" / "X or higher" as boundary outcomes
- Volume varies significantly: NYC/London/Tokyo = high liquidity; smaller cities = thin books

---

## TODO: After Weekend

1. [ ] Get Weather Underground API key
2. [ ] Test station data pulls for all 9 cities
3. [ ] Build forecast vs. odds comparison script
4. [ ] Set up Polygon RPC node (QuickNode/Alchemy)
5. [ ] Start with 1-2 cities (NYC + London recommended for liquidity)
