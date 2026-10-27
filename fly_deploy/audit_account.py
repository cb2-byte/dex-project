#!/usr/local/bin/python3
import os
import json
from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds

# Load config
BOT_DIR = '/Users/colinbrennan/.openclaw/workspace/bots'
load_dotenv(os.path.join(BOT_DIR, '.env'))

# Correct path to .env
env_path = os.path.join(BOT_DIR, '.env')
load_dotenv(env_path)

HOST = "https://clob.polymarket.com"
PRIVATE_KEY = os.getenv('PRIVATE_KEY')
FUNDER = os.getenv('WALLET_ADDRESS')
API_KEY = os.getenv('API_KEY')
API_SECRET = os.getenv('API_SECRET')
API_PASSPHRASE = os.getenv('API_PASSPHRASE')

print("=== Polymarket Comprehensive Account Audit ===")

client = ClobClient(
    HOST,
    key=PRIVATE_KEY,
    chain_id=137,
    signature_type=1,
    funder=FUNDER,
)

if API_KEY and API_SECRET and API_PASSPHRASE:
    try:
        client.set_api_creds(ApiCreds(api_key=API_KEY, api_secret=API_SECRET, api_passphrase=API_PASSPHRASE))
    except Exception as e:
        print(f"Creds error: {e}")

try:
    # 1. Check Open Orders
    print("\n🔎 Checking Open Orders...")
    orders = client.get_orders()
    if not orders:
        print("No open orders found.")
    else:
        for o in orders:
            t_id = getattr(o, 'tokenId', None) or o.get('tokenId') if isinstance(o, dict) else None
            p = getattr(o, 'price', None) or o.get('price') if isinstance(o, dict) else None
            s = getattr(o, 'size', None) or o.get('size') if isinstance(o, dict) else None
            print(f"Order ID: {getattr(o, 'orderId', 'N/A')} | Token: {t_id} | Price: {p} | Size: {s}")

    # 2. Check Positions
    print("\n📦 Checking Positions...")
    # The CLOB client doesn't have a simple 'get_positions' method.
    # We can try to use the a la carte get_position method or just check the gamma api.
    # For a quick check, we'll use the Gamma API if possible, but since that's tricky,
    # we'll check the ClobClient for any relevant method.
    
    # Actually, let's use the Gamma API via httpx for positions
    import httpx
    gamma_url = f"https://gamma-api.polymarket.com/positions?user={FUNDER}"
    r = httpx.get(gamma_url, timeout=10)
    if r.status_code == 200:
        positions = r.json()
        if not positions:
            print("No positions found.")
        else:
            for pos in positions:
                print(f"Token: {pos.get('token')} | Size: {pos.get('size')} | Avg Price: {pos.get('avgPrice')}")
    else:
        print(f"Failed to fetch positions from Gamma API (Status {r.status_code})")

except Exception as e:
    print(f"\n❌ AUDIT FAILED: {e}")
