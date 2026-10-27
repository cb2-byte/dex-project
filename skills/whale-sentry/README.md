# 🐋 Whale Sentry Skill

**On-chain whale monitoring and alerting system using free APIs.**

Monitor whale wallets, large transfers, new token launches, and DeFi protocol changes across Ethereum, Solana, and Base chains - all using free API tiers.

## ✨ Features

- **Whale Wallet Monitoring** - Track specific wallet addresses for large movements
- **Large Transfer Detection** - Alert on transfers above configurable thresholds (ETH, SOL, USD)
- **New Token Launch Detection** - Monitor for new token deployments and liquidity additions
- **DeFi Protocol Monitoring** - Track TVL changes, new pools, governance proposals
- **Cross-Chain Support** - Ethereum, Solana, Base, Polygon, Arbitrum, Optimism, Avalanche, Fantom
- **Telegram Alerts** - Real-time alerts to your Telegram
- **NVIDIA Nemotron Analysis** - AI-powered analysis of on-chain events
- **Zero Cost** - Uses only free API tiers

## 🚀 Quick Start

### 1. Install the Skill

```bash
# From your OpenClaw workspace
openclaw skills install whale-sentry
```

### 2. Configure Environment Variables

Copy the example file and fill in your API keys:

```bash
cd skills/whale-sentry
cp .env.example .env
# Edit .env with your API keys
```

**Required API Keys (all free):**
- **Etherscan** - https://etherscan.io/apis (5 calls/sec, 100k/day)
- **Solscan** - https://solscan.io/api (free tier)
- **Covalent** - https://www.covalenthq.com/ (1M calls/month)
- **NVIDIA** - https://www.nvidia.com/en-us/ai/ (for AI analysis)
- **Telegram Bot** (optional) - https://t.me/BotFather

### 3. Configure in OpenClaw Dashboard

1. Go to Settings → Skills → Whale Sentry
2. Enter your API keys
3. Set monitoring thresholds
4. Save and restart gateway

## 📖 Usage

Once installed, you can use these commands in OpenClaw:

```python
# Add a wallet to monitor
whale_sentry_add_wallet(
    chain="ethereum",
    address="0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
    label="Vitalik Buterin",
    threshold_eth=50.0,
    threshold_usd=100000.0
)

# Add Solana wallet
whale_sentry_add_wallet(
    chain="solana",
    address="7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
    label="Whale #1",
    threshold_sol=1000.0,
    threshold_usd=50000.0
)

# List monitored wallets
whale_sentry_list_wallets()

# Start background monitoring
whale_sentry_start_monitoring()

# Get recent alerts
whale_sentry_get_alerts(hours=24, chain="ethereum")

# Get 24h summary
whale_sentry_get_summary(hours=24)

# Get stats
whale_sentry_get_stats()

# Update thresholds
whale_sentry_set_threshold(
    chain="ethereum",
    address="0x...",
    threshold_eth=25.0,
    threshold_usd=50000.0
)

# Get wallet info
whale_sentry_get_wallet("ethereum", "0x...")
```

## 🔧 Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `WHALE_THRESHOLD_ETH` | 100 | ETH amount to trigger alert |
| `WHALE_THRESHOLD_SOL` | 5000 | SOL amount to trigger alert |
| `WHALE_THRESHOLD_USD` | 100000 | USD value to trigger alert |
| `CHECK_INTERVAL` | 60 | Seconds between checks |

## 🏗️ Architecture

```
whale-sentry/
├── SKILL.md              # Skill manifest
├── whale_sentry.py       # Main skill entry point
├── config.py             # Configuration management
├── database.py           # SQLite storage
├── monitor.py            # Background monitoring daemon
├── alerts.py             # Alert formatting & Telegram
├── analysis.py           # NVIDIA Nemotron analysis
├── config.py             # Configuration management
├── apis/
│   ├── etherscan.py      # Ethereum & Base
│   ├── solscan.py        # Solana
│   ├── solana_fm.py      # Solana (alt)
│   ├── covalent.py       # Multi-chain
│   └── alchemy.py        # Enhanced Ethereum/Base
├── requirements.txt
├── .env.example
└── test_skill.py
```

## 🔑 Free API Keys Needed

| Service | Free Tier | Signup |
|---------|-----------|--------|
| Etherscan | 5 calls/sec, 100k/day | https://etherscan.io/apis |
| Solscan | Free tier | https://solscan.io/api |
| Solana FM | Free tier | https://solana.fm/developers |
| Covalent | 1M calls/month | https://www.covalenthq.com/ |
| Alchemy | 300M CU/month | https://www.alchemy.com/ |
| NVIDIA | Free tier | https://www.nvidia.com/en-us/ai/ |
| Telegram | Free | https://t.me/BotFather |

## 💡 Example Alerts

**Telegram Alert:**
```
🔷 Ethereum 🐋 Whale Alert
📍 Wallet: Vitalik Buterin (0xd8dA...A960)
💰 Value: 1,234.56 ETH ($2,456,789.00)
📤 From: 0xd8dA...A960
📥 To: 0xAbcD...1234
⚠️ Threshold: $2,456,789.00 USD
🔗 View on Etherscan
⏰ 2026-10-03 14:32:15 UTC

🤖 AI Analysis:
This appears to be a distribution move from a known whale wallet to a new address. 
The timing suggests possible OTC deal preparation. Low immediate market impact expected 
given current liquidity depth on major exchanges.
```

## 📊 Commands Reference

| Command | Description |
|---------|-------------|
| `whale_sentry_add_wallet` | Add wallet to monitor |
| `whale_sentry_remove_wallet` | Remove wallet |
| `whale_sentry_list_wallets` | List all monitored wallets |
| `whale_sentry_start_monitoring` | Start background monitoring |
| `whale_sentry_stop_monitoring` | Stop monitoring |
| `whale_sentry_get_alerts` | Get recent alerts |
| `whale_sentry_get_summary` | Get alert summary |
| `whale_sentry_get_stats` | Get skill statistics |
| `whale_sentry_set_threshold` | Update wallet thresholds |
| `whale_sentry_get_wallet` | Get wallet config |

## ⚠️ Security Notes

- **Never store private keys** in the skill configuration
- Uses only **read-only** APIs (Etherscan, Solscan, etc.)
- No private keys or signing capabilities
- Safe for monitoring only

## 🤝 Contributing

PRs welcome! The skill is designed to be extensible:
- New chains: Add client in `apis/`
- New alert types: Extend `alerts.py`
- New analysis: Extend `analysis.py`

## 📄 License

MIT License - See LICENSE file for details.

---

Built with ❤️ for the OpenClaw community. ⛵️💙