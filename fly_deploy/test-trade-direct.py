#!/usr/bin/env python3
"""Direct test of trade execution without the portfolio wrapper"""
import sys, json, time
from types import SimpleNamespace
from py_clob_client_v2 import ClobClient

# Load keys
with open('.polymarket-keys.json') as f:
    keys = json.load(f)

creds = SimpleNamespace(api_key=keys['apiKey'], api_secret=keys['secret'], api_passphrase=keys['passphrase'])
client = ClobClient(
    host='https://clob.polymarket.com',
    chain_id=137,
    key='0xd2aad0f4a95a4e2b8d5090613fb95c278fcddb506616096d49df5d4c39859a3b',
    creds=creds
)

print("=== POLYMARKET DIRECT TEST ===\n")

# Step 1: Get markets
print("[1] Fetching markets...")
result = client.get_sampling_simplified_markets()
markets = result.get('data', []) if isinstance(result, dict) else result
print(f"    Found {len(markets)} total markets")

# Step 2: Find first valid market
print("\n[2] Finding first active market with 2+ outcomes...")
market = None
for m in markets:
    if m.get('active') and m.get('accepting_orders'):
        outcomes = m.get('outcomes', [])
        if len(outcomes) >= 2:
            market = m
            break

if not market:
    print("    FAILED - No valid market found!")
    sys.exit(1)

print(f"    Found: {market.get('condition_id')}")
print(f"    Outcomes: {len(market.get('outcomes', []))}")

# Step 3: Get token IDs
outcomes = market.get('outcomes', [])
token_up = outcomes[0].get('token_id')
token_down = outcomes[1].get('token_id')
print(f"    Token UP: {token_up}")
print(f"    Token DOWN: {token_down}")

# Step 4: Try to place a test order
print("\n[3] Attempting to place TEST order...")
print(f"    Order: stake=$1.00, price=0.5, token={token_up}")

try:
    order = client.create_and_post_order(
        {
            'tokenID': token_up,
            'price': 0.5,
            'size': 1.0,
            'side': 0,
            'expiration': 0
        },
        {
            'tickSize': '0.01',
            'negRisk': False
        }
    )
    
    print(f"\n    SUCCESS! Response:")
    print(f"    {json.dumps(order, indent=2)}")
    
    order_id = order.get('orderID')
    if order_id:
        print(f"\n✅ ORDER PLACED: {order_id}")
    else:
        print(f"\n⚠️ Order created but no orderID in response")
        
except Exception as e:
    print(f"\n    FAILED: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
