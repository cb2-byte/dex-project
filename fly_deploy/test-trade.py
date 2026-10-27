#!/usr/bin/env python3
"""Quick test trade to verify execution"""

import json
from py_clob_client_v2 import ClobClient
from py_clob_client_v2.clob_types import ApiCreds, OrderArgsV2

# Load API keys
with open('.polymarket-keys.json') as f:
    keys = json.load(f)

creds = ApiCreds(
    api_key=keys['apiKey'],
    api_secret=keys['secret'],
    api_passphrase=keys['passphrase']
)

# Same config as traders
PRIVATE_KEY = "0xd2aad0f4a95a4e2b8d5090613fb95c278fcddb506616096d49df5d4c39859a3b"
FUNDER = "0x98D9Dbd34d0156E6385D08d5263467601BE5e972"

client = ClobClient(
    host="https://clob.polymarket.com",
    chain_id=137,
    key=PRIVATE_KEY,
    creds=creds,
    signature_type=1,  # POLY_PROXY
    funder=FUNDER
)

print(f"Testing trade with:")
print(f"  Wallet: {FUNDER}")
print(f"  Key derives to: (will check)")

# First check balance
print("\n📊 Checking balance...")
try:
    from py_clob_client_v2.clob_types import BalanceAllowanceParams, AssetType
    params = BalanceAllowanceParams(asset_type=AssetType.COLLATERAL)
    balance = client.get_balance_allowance(params=params)
    print(f"  Balance: {balance}")
except Exception as e:
    print(f"  ❌ Balance check failed: {e}")

# Find an active market to test with
print("\n🔍 Finding active market...")
try:
    result = client.get_markets()
    markets = result.get('data', []) if isinstance(result, dict) else result
    
    # Find first market with liquidity
    test_market = None
    for m in markets:
        if m.get('accepting_orders') and m.get('active'):
            tokens = m.get('tokens', [])
            if len(tokens) >= 2:
                # Handle dict-based tokens
                token_ids = []
                for t in tokens:
                    if isinstance(t, dict):
                        token_ids.append(t.get('token_id'))
                    else:
                        token_ids.append(t)
                
                if token_ids[0]:
                    test_market = {
                        'slug': m.get('slug', 'unknown'),
                        'token': token_ids[0],
                        'name': m.get('question', m.get('slug', 'unknown'))
                    }
                    break
    
    if test_market:
        print(f"  Found: {test_market['name']}")
        print(f"  Token: {test_market['token']}")
        
        # Check orderbook
        print("\n📖 Checking orderbook...")
        try:
            import httpx
            ob_resp = httpx.get(f'https://clob.polymarket.com/orderbook?token_id={test_market["token"]}', timeout=5)
            print(f"  Status: {ob_resp.status_code}")
            print(f"  Raw response: {ob_resp.text[:200] if ob_resp.text else 'EMPTY'}")
            ob = ob_resp.json()
            if ob.get('bids') and len(ob['bids']) > 0:
                best_bid = ob['bids'][0]
                print(f"  Best bid: {best_bid.get('price')} @ {best_bid.get('size')}")
                
                # Try to place a tiny order (0.01)
                print("\n🎯 Placing test order (0.01)...")
                order = OrderArgsV2(
                    token_id=test_market['token'],
                    price=float(best_bid.get('price', 0.5)),
                    size=0.01,
                    side='BUY',
                    expiration=0
                )
                
                signed = client.create_order(order)
                print(f"  Order signed: {signed}")
                
                response = client.post_order(signed)
                print(f"  ✅ ORDER SUBMITTED: {response}")
                
            else:
                print("  No bids in orderbook")
        except Exception as e:
            print(f"  ❌ Order failed: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("  No active markets found")
        
except Exception as e:
    print(f"  ❌ Market lookup failed: {e}")
    import traceback
    traceback.print_exc()

print("\n--- Done ---")
