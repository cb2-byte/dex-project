#!/Library/Frameworks/Python.framework/Versions/3.14/bin/python3
"""Check for any live crypto markets"""

import requests

resp = requests.get('https://clob.polymarket.com/markets', timeout=10)
data = resp.json()
markets = data.get('data', []) if isinstance(data, dict) else data

# Look for ANY market accepting orders with crypto/finance keywords
keywords = ['bitcoin', 'btc', 'ethereum', 'eth', 'crypto', 'solana', 'sol', 
            'chainlink', 'link', 'price', 'trump', 'election', 'fed', 'rate']

print("=== MARKETS ACCEPTING ORDERS ===\n")
accepting = [m for m in markets if m.get('accepting_orders')]
print(f"Total accepting: {len(accepting)}\n")

for m in accepting[:20]:  # Show first 20
    slug = m.get('market_slug', '')
    title = m.get('title', '') or m.get('question', '')
    
    # Check if any keyword matches
    text = f"{slug} {title}".lower()
    matched = [k for k in keywords if k in text]
    
    if matched:
        print(f"✅ {slug}")
        print(f"   Title: {title[:70]}")
        print(f"   Keywords: {matched}")
        tokens = m.get('tokens', [])
        if tokens:
            token_ids = [t.get('token_id') if isinstance(t, dict) else t for t in tokens[:2]]
            print(f"   Tokens: {token_ids}")
        print()
