# twscrape HTTP Wrapper for PennyShield

A FastAPI wrapper around `twscrape` that exposes a simple HTTP endpoint for fetching tweets about token symbols. Designed to integrate with PennyShield's `SocialDataCollector`.

## Quick Start

```bash
cd /home/ubuntu/.openclaw/workspace/pennyshield/twscrape_wrapper

# 1. Create accounts.json with your Twitter credentials (or use env var)
cp accounts.json.example accounts.json
# Edit accounts.json with your Twitter credentials

# 2. Build and run
docker-compose up -d --build

# 3. Test
curl http://localhost:8080/health
curl "http://localhost:8080/tweets?symbol=PEPE&limit=20"
```

## Environment Variables

Create a `.env` file or export:

```bash
export TWITTER_ACCOUNTS="user1:pass1:email1:email_pass1,user2:pass2:email2:email_pass2"
```

Or use the `accounts.json` file (see `accounts.json.example`).

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Health check - returns account load status |
| `GET /tweets?symbol=PEPE&limit=50&hours=24` | Fetch tweets mentioning `$SYMBOL` |
| `GET /tweets/user/{username}?limit=50&hours=24` | Fetch tweets from a specific user |
| `POST /accounts/reload` | Reload accounts from environment |

## Example Response

```json
{
  "symbol": "PEPE",
  "count": 25,
  "tweets": [
    {
      "id": "1234567890",
      "username": "crypto_trader",
      "display_name": "Crypto Trader",
      "content": "$PEPE looking strong today! 🐸🚀",
      "created_at": "2026-10-22T17:30:00+00:00",
      "url": "https://x.com/crypto_trader/status/1234567890",
      "retweet_count": 42,
      "like_count": 128,
      "reply_count": 12,
      "quote_count": 3,
      "hashtags": ["PEPE", "crypto"],
      "mentions": [],
      "is_retweet": false,
      "is_reply": false,
      "language": "en"
    }
  ],
  "fetched_at": "2026-10-22T17:35:00.123456"
}
```

## PennyShield Integration

See `pennyshield_client.py` for a ready-to-use client that feeds tweets into PennyShield's `SocialDataCollector`.

## Account Setup

You need Twitter accounts (username:password[:email:email_password]) for twscrape to work. Add multiple for rotation.

```json
[
  {"username": "user1", "password": "pass1", "email": "email1@example.com", "email_password": "emailpass1"},
  {"username": "user2", "password": "pass2", "email": "", "email_password": ""}
]
```

## Health Check

```bash
curl http://localhost:8080/health
# {"status":"healthy","accounts_loaded":true,"accounts_count":3,"timestamp":"2026-10-22T17:40:00.123456"}
```

## Example Queries

```bash
# Get tweets for PEPE
curl "http://localhost:8080/tweets?symbol=PEPE&limit=50&hours=24"

# Get tweets from a specific user
curl "http://localhost:8080/tweets/user/cz_binance?limit=20&hours=48"

# Reload accounts
curl -X POST http://localhost:8080/accounts/reload
```

## Notes

- Requires Twitter accounts with valid credentials
- Accounts may get rate-limited or locked - use multiple accounts
- twscrape uses Playwright/Chromium under the hood
- First run downloads Chromium (~100MB)
- Accounts may need 2FA disabled or app passwords