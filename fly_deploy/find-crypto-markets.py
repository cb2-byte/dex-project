#!/Library/Frameworks/Python.framework/Versions/3.14/bin/python3
"""Find crypto markets that are actually accepting orders"""

import requests

# Direct API call
resp = requests.get('https://clob.polymarket.com/markets', timeout=10)
data = resp.json()
markets = data.get('data', []) if isinstance(data, dict) else data

crypto_keywords = ['bitcoin', 'btc', 'ethereum', 'eth', 'chainlink', 'link', 'solana', 'sol', 'crypto']
weather_keywords = ['weather', 'rain', 'temperature', 'snow', 'forecast']

print("=== CRYPTO MARKETS ===")
crypto_markets = []
for m in markets:
    slug = (m.get('market_slug', '') or m.get('slug', '')).lower()
    title = (m.get('title', '') or m.get('question', '')).lower()
    accepting = m.get('accepting_orders', False)
    
    if any(kw in slug or kw in title for kw in crypto_keywords):
        crypto_markets.append({
            'slug': slug,
            'title': title[:60],
            'accepting': accepting,
            'active': m.get('active', False),
            'tokens': m.get('tokens', [])
        })

print(f"Found {len(crypto_markets)} crypto-related markets")
for m in crypto_markets[:10]:
    status = "✅ ACCEPTING" if m['accepting'] else "❌ CLOSED"
    print(f"{status} | {m['slug']}")
    if m['accepting'] and m['tokens']:
        tokens = m['tokens'][:2]
        token_ids = [t.get('token_id') if isinstance(t, dict) else t for t in tokens]
        print(f"         Tokens: {token_ids}")

print("\n=== WEATHER MARKETS ===")
weather_markets = []
for m in markets:
    slug = (m.get('market_slug', '') or m.get('slug', '')).lower()
    title = (m.get('title', '') or m.get('question', '')).lower()
    accepting = m.get('accepting_orders', False)
    
    if any(kw in slug or kw in title for kw in weather_keywords):
        weather_markets.append({
            'slug': slug,
            'title': title[:60],
            'accepting': accepting
        })

print(f"Found {len(weather_markets)} weather-related markets")
for m in weather_markets[:10]:
    status = "✅ ACCEPTING" if m['accepting'] else "❌ CLOSED"
    print(f"{status} | {m['slug']}")

print(f"\n=== SUMMARY ===")
print(f"Total markets: {len(markets)}")
print(f"Crypto markets: {len(crypto_markets)} ({sum(1 for m in crypto_markets if m['accepting'])} accepting)")
print(f"Weather markets: {len(weather_markets)} ({sum(1 for m in weather_markets if m['accepting'])} accepting)")
