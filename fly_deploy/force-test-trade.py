#!/usr/bin/env python3
"""Force a test trade - find active market with liquidity"""

import json
import httpx
from py_clob_client_v2 import ClobClient
from py_clob_client_v2.clob_types import ApiCreds, OrderArgsV2

with open('.polymarket-keys.json') as f:
    keys = json.load(f)

creds = ApiCreds(
    api_key=keys['apiKey'],
    api_secret=keys['secret'],
    api_passphrase=keys['passphrase']
)

client = ClobClient(
    host="https://clob.polymarket.com",
    chain_id=137,
    key='0xd2aad0f4a95a4e2b8d5090613fb95c278fcddb506616096d49df5d4c39859a3b',
    creds=creds,
    signature_type=1,
    funder='0x98D9Dbd34d0156E6385D08d5263467601BE5e972'
)

print("🧪 TEST TRADE")
print(f"Wallet: 0x98D9Dbd...")
print("")

# Check balance
print("📊 Checking balance...")
try:
    from py_clob_client_v2.clob_types import BalanceAllowanceParams, AssetType
    params = BalanceAllowanceParams(asset_type=AssetType.COLLATERAL)
    balance = client.get_balance_allowance(params=params)
    print(f"   Balance: {balance}")
except Exception as e:
    print(f"   Error: {e}")

# Find markets with actual orderbook liquidity
print("\n🔍 Finding market with liquidity...")
result = client.get_markets()
markets = result.get('data', []) if isinstance(result, dict) else result

test_market = None
for m in markets[:100]:
    if not m.get('accepting_orders'):
        continue
    
    tokens = m.get('tokens', [])
    if len(tokens) < 2:
        continue
    
    token_id = None
    for t in tokens:
        if isinstance(t, dict):
            token_id = t.get('token_id')
        else:
            token_id = t
        if token_id:
            break
    
    if not token_id:
        continue
    
    # Check if orderbook exists via API
    try:
        ob_resp = httpx.get(f'https://clob.polymarket.com/orderbook?token_id={token_id}', timeout=3)
        if ob_resp.status_code == 200:
            ob = ob_resp.json()
            bids = ob.get('bids', [])
            asks = ob.get('asks', [])
            if bids and asks:
                test_market = {
                    'slug': m.get('slug', 'unknown')[:60],
                    'token': token_id,
                    'question': m.get('question', 'Unknown')[:50],
                    'best_bid': float(bids[0]['price']),
                    'best_ask': float(asks[0]['price'])
                }
                print(f"   ✅ Found: {test_market['question']}")
                print(f"   Token: {token_id}")
                print(f"   Bid: {test_market['best_bid']} | Ask: {test_market['best_ask']}")
                break
    except:
        continue

if not test_market:
    print("   ❌ No markets with liquidity found")
    exit(1)

# Place order at bid price
print(f"\n💰 Placing test order: $1.00 @ {test_market['best_bid']}...")
try:
    order = OrderArgsV2(
        token_id=test_market['token'],
        price=test_market['best_bid'],
        size=1.0,
        side='BUY',
        expiration=0
    )
    
    print("   Creating order...")
    signed = client.create_order(order)
    print(f"   Order signed ✅")
    
    print("   Submitting order...")
    resp = client.post_order(signed)
    print(f"\n🎉 ORDER RESULT:")
    print(f"   {resp}")
except Exception as e:
    print(f"\n❌ ORDER FAILED:")
    print(f"   {e}")
    import traceback
    traceback.print_exc()

print("\n--- Done ---")
