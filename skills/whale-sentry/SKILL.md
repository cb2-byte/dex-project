---
name: whale-sentry
description: "On-chain whale monitoring and alerting system using free APIs. Monitors whale wallets, large transfers, new token launches, and DeFi protocol changes across Ethereum, Solana, and Base chains."
version: "1.0.0"
author: "penny"
tags: ["crypto", "monitoring", "whale-tracking", "defi", "telegram", "alerts"]
---

# Whale Sentry Skill

## Overview
The Whale Sentry skill transforms your OpenClaw agent into an on-chain intelligence analyst. It monitors whale wallets, large transfers, new token launches, DeFi protocol changes, and unusual activity across Ethereum, Solana, and Base chains using free APIs.

## Features
- **Whale Wallet Monitoring** - Track specific wallet addresses for large movements
- **Large Transfer Detection** - Alert on transfers above configurable thresholds
- **New Token Launch Detection** - Monitor for new token deployments and liquidity additions
- **DeFi Protocol Monitoring** - Track TVL changes, new pools, governance proposals
- **Cross-Chain Support** - Ethereum, Solana, Base (via free APIs)
- **Telegram Alerts** - Real-time alerts to your Telegram
- **NVIDIA Nemotron Analysis** - AI-powered analysis of on-chain events
- **Zero Cost** - Uses only free API tiers

## Configuration
Create a `.env` file or set environment variables:

```bash
# Required - at least one
ETHERSCAN_API_KEY=your_etherscan_key_here      # Free: 5 calls/sec, 100k/day
SOLSCAN_API_KEY=your_solscan_key_here          # Free tier available
SOLANA_FM_API_KEY=your_solana_fm_key_here      # Free tier available
COVALENT_API_KEY=your_covalent_key_here        # Free: 1M calls/month
ALCHEMY_API_KEY=your_alchemy_key_here          # Free: 300M compute units/month

# Telegram (for alerts)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# NVIDIA (for analysis)
NVIDIA_API_KEY=your_nvidia_api_key             # Your nvapi-Mw7K... key

# Optional - Monitoring thresholds
WHALE_THRESHOLD_ETH=100          # ETH amount to trigger alert
WHALE_THRESHOLD_SOL=5000         # SOL amount to trigger alert
WHALE_THRESHOLD_USD=100000       # USD value to trigger alert
CHECK_INTERVAL=60                # Seconds between checks
```

## Free API Keys to Get
1. **Etherscan** - https://etherscan.io/apis (5 calls/sec, 100k/day free)
2. **Solscan** - https://solscan.io/api (free tier)
3. **Solana FM** - https://solana.fm/developers (free tier)
4. **Covalent** - https://www.covalenthq.com/ (1M calls/month free)
5. **Alchemy** - https://www.alchemy.com/ (300M CU/month free)

## Usage
Once configured and installed, the skill provides these tools to your agent:

### `whale_sentry_start_monitoring`
Start monitoring configured wallets and chains.

### `whale_sentry_add_wallet`
Add a wallet address to monitor:
```
chain: "ethereum" | "solana" | "base"
address: "0x..." | "..."
label: "Whale Wallet #1"
threshold_eth: 50
threshold_usd: 50000
```

### `whale_sentry_remove_wallet`
Remove a wallet from monitoring.

### `whale_sentry_list_wallets`
List all monitored wallets.

### `whale_sentry_check_now`
Run an immediate check on all monitored wallets.

### `whale_sentry_get_alerts`
Get recent alerts (last 24h, last 7d, etc.)

### `whale_sentry_analyze_event`
Get AI analysis of a specific on-chain event using NVIDIA Nemotron.

## Background Monitoring
The skill runs a background daemon that:
1. Checks all monitored wallets every `CHECK_INTERVAL` seconds
2. Fetches recent transactions via free APIs
3. Filters for transfers above thresholds
4. Uses NVIDIA Nemotron to analyze significant events
4. Sends Telegram alerts for significant events
5. Stores alerts in local database for history

## Installation
```bash
openclaw skills install whale-sentry
```

## Security Notes
- **Never store private keys** in the skill configuration
- Uses only **read-only** APIs (Etherscan, Solscan, etc.)
- No private keys or signing capabilities
- Safe for monitoring only

## Requirements
- Python 3.10+
- `requests`, `aiohttp`, `python-telegram-bot` (auto-installed)
- At least one free API key from the list above
- NVIDIA API key for analysis (your nvapi-Mw7K... key)
- Telegram bot token (optional, for alerts)

## Example Usage
Once installed, you can ask your agent:

> "Start monitoring Vitalik's wallet (0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045) on Ethereum for transfers over 100 ETH"

> "Add this Solana wallet to monitoring: 7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU with label 'Whale #1'"

> "Check all monitored wallets now and analyze any large transfers"

> "Show me alerts from the last 24 hours"

## Files
- `SKILL.md` - This file
- `whale_sentry.py` - Main skill implementation
- `config.py` - Configuration management
- `apis/` - API client modules
- `monitor.py` - Background monitoring daemon
- `alerts.py` - Alert formatting and Telegram integration
- `analysis.py` - NVIDIA Nemotron analysis integration
- `database.py` - Local SQLite storage for alerts/history
