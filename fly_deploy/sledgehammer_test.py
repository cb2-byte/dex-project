#!/usr/bin/env python3
import json
import requests
import time
import os
from py_clob_client_v2 import ClobClient
from py_clob_client_v2.clob_types import ApiCreds, OrderArgsV2

# Configuration
SPEND_AMOUNT = 0.10  # Smallest meaningful test trade

def main():
    print("🚀 SLEDGEHAMMER TEST: Verifying pUSD / V2 Bridge")
    
    # 1. Load Keys
    try:
        with open('.polymarket-keys.json') as f:
            keys = json.load(f)
    except Exception as e:
        print(f"❌ Could not load .polymarket-keys.json: {e}")
        return

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

    # 2. Check Server Time (Health Check)
    print("\n[1/4] Checking server connection...")
    try:
        server_time = client.get_server_time()
        print(f" ✅ Server time: {server_time}")
    except Exception as e:
        print(f" ⚠ get_server_time failed: {e} (continuing anyway)")

    # 3. Find a market
    print("\n[2/4] Scanning active markets for a tradeable ask...")
    result_markets = client.get_markets()
    markets = result_markets.get('data', []) if isinstance(result_markets, dict) else result_markets
    print(f" Got {len(markets)} markets to scan...")

    tradeable_token = None
    for m in markets:
        if not m.get('accepting_orders'):
            continue
        
        tokens = m.get('tokens', [])
        if not tokens:
            continue
            
        token_id = tokens[0].get('token_id') if isinstance(tokens[0], dict) else tokens[0]
        if not token_id:
            continue
            
        try:
            ob = requests.get(f'https://clob.polymarket.com/orderbook?token_id={token_id}', timeout=3).json()
            asks = ob.get('asks', [])
            if asks:
                tradeable_token = {
                    'token': token_id,
                    'ask': float(asks[0]['price']),
                    'slug': m.get('slug', 'unknown')
                }
                print(f" ✅ Found tradeable token: {tradeable_token['slug']} (Ask: {tradeable_token['ask']})")
                break
        except:
            continue

    if not tradeable_token:
        print("\n❌ No tradeable token found in the current market list.")
        return

    # 4. Fire the order
    print(f"\n[3/4] Firing a ${SPEND_AMOUNT} test order @ {tradeable_token['ask']}...")
    try:
        order_args = OrderArgsV2(
            token_id=tradeable_token['token'],
            price=tradeable_token['ask'],
            size=SPEND_AMOUNT,
            side='BUY',
            expiration=0
        )
        
        signed_order = client.create_order(order_args)
        response = client.post_order(signed_order)
        
        print("\n✅ ORDER RESPONSE:")
        print(json.dumps(response, indent=2, default=str))

        if isinstance(response, dict):
            status = response.get("status", "")
            order_id = response.get("orderID") or response.get("id", "")
            error_msg = response.get("errorMsg") or response.get("error", "")

            print("\n── VERDICT ──────────────────────────────────────────────")
            if status in ("matched", "live"):
                print(f"🎉 SUCCESS! Order placed (status={status})")
                print(f" Order ID : {order_id}")
                print(" Funds are present and V2 bridge is working.")
            elif error_msg:
                print(f"❌ FAILED — API error: {error_msg}")
                if "insufficient" in error_msg.lower() or "funds" in error_msg.lower():
                    print(" → Wallet has no pUSD / insufficient balance.")
                elif "allowance" in error_msg.lower():
                    print(" → CTF allowance not set. Run the approval script first.")
                else:
                    print(" → Something else went wrong (see error above).")
            else:
                print(f"⚠ Unexpected response (status='{status}').")
            print("─────────────────────────────────────────────────────────")

    except Exception as e:
        print(f"\n❌ Exception while placing order: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
