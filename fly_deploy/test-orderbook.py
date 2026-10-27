#!/Library/Frameworks/Python.framework/Versions/3.14/bin/python3
"""Test orderbook API directly"""

import requests

# Test if orderbook endpoint works
result = requests.get('https://clob.polymarket.com/orderbook?token_id=14407587149607649930148663675171068494265586931331224774282394443605115689380')
print(f"Status: {result.status_code}")
print(f"Response: {result.json()[:500] if result.text else 'Empty'}")

# Get markets and check accepting_orders
result2 = requests.get('https://clob.polymarket.com/markets')
data = result2.json()
markets = data.get('data', []) if isinstance(data, dict) else data

accepting = [m for m in markets if m.get('accepting_orders')]
print(f"\nTotal markets: {len(markets)}")
print(f"Accepting orders: {len(accepting)}")

if accepting:
    print("\nFirst accepting market:")
    m = accepting[0]
    print(f"  Slug: {m.get('market_slug')}")
    print(f"  Title: {m.get('title', '')[:60]}")
    tokens = m.get('tokens', [])
    if tokens:
        print(f"  Token IDs: {[t.get('token_id') if isinstance(t, dict) else t for t in tokens[:2]]}")
