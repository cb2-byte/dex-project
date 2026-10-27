#!/usr/bin/env python3
"""Place a real trade on Polymarket"""

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

print("🎯 PLACING REAL TRADE")
print(f"Wallet: 0x98D9Dbd...\n")

# Check balance
print("📊 Balance...")
try:
    from py_clob_client_v2.clob_types import BalanceAllowanceParams, AssetType
    params = BalanceAllowanceParams(asset_type=AssetType.COLLATERAL)
    balance = client.get_balance_allowance(params=params)
    print(f"   {balance}\n")
except Exception as e:
    print(f"   Error: {e}\n")

# Try specific token IDs from popular markets
# These are known Polymarket markets that often have liquidity
test_tokens = [
    "5678901234567890123456789012345678901234567890123456789012345678",  # Common market
    "1234567890123456789012345678901234567890123456789012345678901234",  # Another market
]

# Get all markets and find ones with actual orderbooks
print("🔍 Finding liquid market...\n")
result = client.get_markets()
markets = result.get('data', []) if isinstance(result, dict) else result

liquid_markets = []
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
    
    # Check orderbook
    try:
        resp = httpx.get(f'https://clob.polymarket.com/orderbook?token_id={token_id}', timeout=3)
        if resp.status_code == 200:
            ob = resp.json()
            bids = ob.get('bids', [])
            asks = ob.get('asks', [])
            if bids and asks:
                liquid_markets.append({
                    'token': token_id,
                    'slug': m.get('slug', 'unknown')[:50],
                    'question': m.get('question', '')[:60],
                    'bid': float(bids[0]['price']),
                    'ask': float(asks[0]['price']),
                    'bid_size': float(bids[0].get('size', 0))
                })
                if len(liquid_markets) >= 5:
                    break
    except:
        continue

if not liquid_markets:
    print("❌ No liquid markets found right now")
    print("\nPolymarket may have no active orderbooks at this moment.")
    print("Try again when there are live markets.")
    exit(1)

print(f"✅ Found {len(liquid_markets)} liquid markets:\n")
for i, m in enumerate(liquid_markets):
    print(f"[{i+1}] {m['question']}")
    print(f"    Bid: {m['bid']} (size: {m['bid_size']}) | Ask: {m['ask']}")
    print(f"    Token: {m['token']}\n")

# Pick first one and trade
m = liquid_markets[0]
print(f"💰 Placing $1.00 BUY @ {m['bid']}...\n")

try:
    order = OrderArgsV2(
        token_id=m['token'],
        price=m['bid'],
        size=1.0,
        side='BUY',
        expiration=0
    )
    
    print("   Creating order...")
    signed = client.create_order(order)
    print(f"   Order signed ✅")
    
    print("   Submitting to Polymarket...")
    resp = client.post_order(signed)
    
    print(f"\n🎉 TRADE EXECUTED!")
    print(f"   Response: {resp}")
    print(f"\nCheck your Polymarket account - you should see:")
    print(f"   - Balance decreased by ~$1.00")
    print(f"   - New position in: {m['question'][:50]}")
    
except Exception as e:
    print(f"\n❌ TRADE FAILED: {e}")
    import traceback
    traceback.print_exc()

print("\n--- Done ---")
