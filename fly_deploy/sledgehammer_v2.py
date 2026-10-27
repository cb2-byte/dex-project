#!/usr/bin/env python3
"""
Sledgehammer Trade Test V2.2
Targets specific high-volume evergreen markets to definitively verify pUSD funds.
"""

import json
import requests
import time
import os
from py_clob_client_v2 import ClobClient
from py_clob_client_v2.clob_types import ApiCreds, OrderArgsV2

# ── CONFIG ─────────────────────────────────────────────────────────────────────
POLYMARKET_HOST = "https://clob.polymarket.com"
CHAIN_ID = 137
SPEND_AMOUNT = 0.10
MAX_PRICE = 0.95 
MIN_PRICE = 0.05

# Evergreen Market IDs from the updated list
LIQUID_TOKEN_IDS = [
    "21742633143463906290569050155826241533067272736897614950488156847949938836455", # BTC $100k
    "69236923620077691027083946871148646972011131466059644796654161903044801372610", # ETH $4k
    "44670774686369565670997197464975962329625195015010305314994556229941652117023", # Fed Cut
]

# ───────────────────────────────────────────────────────────────────────────────

def load_keys():
    path = os.path.join(os.path.dirname(__file__), '.polymarket-keys.json')
    with open(path) as f:
        return json.load(f)

def build_client(keys):
    return ClobClient(
        host=POLYMARKET_HOST,
        chain_id=CHAIN_ID,
        key='0xd2aad0f4a95a4e2b8d5090613fb95c278fcddb506616096d49df5d4c39859a3b',
        creds=ApiCreds(
            api_key=keys['apiKey'],
            api_secret=keys['secret'],
            api_passphrase=keys['passphrase']
        ),
        signature_type=1,
        funder='0x98D9Dbd34d0156E6385D08d5263467601BE5e972'
    )

def fetch_backup_tokens():
    try:
        url = "https://gamma-api.polymarket.com/markets?active=true&limit=50"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            markets = r.json()
            tokens = []
            for m in markets:
                t_list = m.get("tokens", [])
                for t in t_list:
                    tid = t.get("token_id") if isinstance(t, dict) else t
                    if tid: tokens.append(tid)
            return tokens
    except:
        pass
    return []

def find_tradeable(token_ids, label=""):
    for tid in token_ids:
        try:
            r = requests.get(f"{POLYMARKET_HOST}/orderbook?token_id={tid}", timeout=5)
            if r.status_code != 200: continue
            book = r.json()
            asks = book.get("asks", [])
            if not asks: continue
            best_ask = float(asks[0]["price"])
            if MIN_PRICE <= best_ask <= MAX_PRICE:
                print(f" ✅ Found {label}tradeable token: {tid[:10]}... Ask: ${best_ask:.4f}")
                return tid, best_ask
        except:
            continue
    return None, None

def place_order(client, token_id, price):
    size = round(SPEND_AMOUNT / price, 4)
    print(f"\n🔨 Firing order: {size} shares @ ${price:.4f} (~${SPEND_AMOUNT})")
    order_args = OrderArgsV2(
        token_id=token_id,
        price=price,
        size=size,
        side='BUY',
        expiration=0
    )
    signed_order = client.create_order(order_args)
    return client.post_order(signed_order)

def interpret(response):
    if not isinstance(response, dict):
        print(f"⚠ Unexpected response type: {type(response)}")
        return
    status = response.get("status", "")
    order_id = response.get("orderID") or response.get("id", "")
    error_msg = response.get("errorMsg") or response.get("error", "")
    print("\n── VERDICT ──────────────────────────────────────────────")
    if status in ("matched", "live", "delayed"):
        print(f"🎉 SUCCESS! Order placed (status={status})")
        print(f" Order ID : {order_id}")
        print(" Funds confirmed ✅ V2 bridge working ✅")
    elif error_msg:
        low = error_msg.lower()
        print(f"❌ API error: {error_msg}")
        if any(w in low for w in ("insufficient", "funds", "balance")):
            print(" → Wallet has no pUSD. Need to fund it.")
        elif "allowance" in low or "approval" in low:
            print(" → CTF allowance not set. Need to run approval tx.")
        elif "not approved" in low:
            print(" → Operator not approved. Need to call approveOperator().")
        else:
            print(" → Unknown error.")
    else:
        print(f"⚠ Unexpected status='{status}'.")
    print("─────────────────────────────────────────────────────────")

def main():
    print("=" * 60)
    print(" SLEDGEHAMMER v2.2 — EVERGREEN TARGETS")
    print("=" * 60)
    try:
        keys = load_keys()
    except Exception as e:
        print(f"❌ Key error: {e}"); return
    
    client = build_client(keys)
    print("\n[1/4] Connecting... Server time:", client.get_server_time())
    
    print("\n[2/4] Checking high-vol tokens...")
    token_id, ask_price = find_tradeable(LIQUID_TOKEN_IDS, label="hardcoded ")
    if not token_id:
        print(" Hardcoded stale. Trying backup...")
        backup = fetch_backup_tokens()
        token_id, ask_price = find_tradeable(backup, label="backup ")

    if not token_id:
        print("\n❌ No liquid ask found. Cannot execute test trade."); return

    print("\n[3/4] Placing $0.10 test order...")
    try:
        response = place_order(client, token_id, ask_price)
        print("\n✅ RAW RESPONSE:\n", json.dumps(response, indent=2, default=str))
        interpret(response)
    except Exception as e:
        print(f"\n❌ Exception: {e}")

if __name__ == "__main__":
    main()
