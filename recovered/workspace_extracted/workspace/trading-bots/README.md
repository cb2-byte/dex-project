# Trading Bots - Colin's Setup 🪙

**Your wallets are organized and ready!**

## Quick Summary

| Platform | Status | What it does |
|----------|--------|--------------|
| **Coinbase** | ✅ Ready | DCA + dip buying BTC (£100 budget) |
| **Bankr** | ✅ Ready | Monitor your main wallet + prices |
| **Polymarket** | ⚠️ Setup | Copy trading (wallet ready, haven't used yet) |
| **Polytrade** | ⚠️ Unused | API key saved, wallet not set yet |

## Your Wallets (All in one place)

```
🏦 Bankr (main):      0x841cc80C5f5820EBB2223fb22Cc7A6d60FE0effc
💾 Bankr (backup):    0xbbcd8e2261628c001e020e9e3d045c51d800411f
🎯 Polymarket:        0x98D9Dbd34d0156E6385D08d5263467601BE5e972
₿ Bitcoin:            bc1q2cx3kw88muflslj38rfjulrpvv823ym9en02al
```

## Quick Commands

```bash
cd ~/workspace/trading-bots

# Bankr - Check your wallet
python3 bankr_bot.py --check

# Coinbase - Test with live prices (no trades)
python3 coinbase_dca.py --live-test

# Polymarket - See top traders
python3 polymarket_copy.py --check
```

## What's Working NOW

### ✅ Bankr Bot
- Shows your wallet addresses
- Fetches live BTC/ETH prices
- Ready to monitor balances

### ✅ Coinbase Bot  
- Live BTC price: £50,667
- Dip detection: Will buy if BTC drops 3%
- DCA: £10/week scheduled
- Your API keys loaded

### ⚠️ Polymarket Bot
- Wallet configured: `0x98D9...e972`
- Mode: Alerts (sends you Telegram messages)
- **Note:** You haven't traded on Polymarket yet

## Before Live Trading

1. **Add money to Coinbase** (if not already)
2. **Edit config.json**: Set `"dry_run": false`
3. **Enable bot**: Set `"enabled": true` for Coinbase
4. **Test**: Run `--live-test` first to see what it would do

## Config File

All your keys and settings are in `config.json`:
- Clean structure
- Comments explaining each section
- All wallets listed
- Safety limits set (£100 max)

## Need Help?

Just ask Penny! 🐱
