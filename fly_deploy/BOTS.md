# Bot Monitoring Config

Use this file to configure which bots should be monitored and how to check their health.

## Template

For each bot, specify:

```markdown
### Bot Name
- **Type:** (e.g., Polymarket trader, data scraper, API service)
- **Location:** localhost:PORT | ssh://host | http://url
- **Health check command:** (shell command or API call to verify it's alive)
- **Log file:** (path to logs, if applicable)
- **Stale threshold:** (hours without activity before alerting)
- **Alert on failure:** (yes/no)
```

## Your Bots

### Polymarket Trading Bot (@pennypolymarketbot)
- **Type:** Polymarket/crypto price alert bot
- **Location:** Telegram bot @pennypolymarketbot
- **Status:** ✅ Active (sending alerts)
- **Tracking:** ETH, LINK, SOL price movements
- **Alert types:** JUMP DETECTED, directional changes (UP/DOWN), strength ratings (STRONG/MODERATE)
- **Last seen:** May 2, 2026 00:20 (SOL alert)
- **Health check:** Monitor Telegram bot responsiveness
- **Stale threshold:** 2 hours without alerts during active trading
- **Alert on failure:** yes

---

**Backend details TBD:** Where the bot is hosted (localhost/remote) and health check endpoints need to be added for automated monitoring.
