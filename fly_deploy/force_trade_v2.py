#!/usr/local/bin/python3
import os
import json
from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds, OrderArgs

# Load config
BOT_DIR = '/Users/colinbrennan/.openclaw/workspace/bots'
load_dotenv(os.path.join(BOT_DIR, '.env'))

HOST = "https://clob.polymarket.com"
PRIVATE_KEY = os.getenv('PRIVATE_KEY')
FUNDER = os.getenv('WALLET_ADDRESS')
API_KEY = os.getenv('API_KEY')
API_SECRET = os.getenv('API_SECRET')
API_PASSPHRASE = os.getenv('API_PASSPHRASE')

print("=== Polymarket Force Trade v2 ===")
print(f"Using Wallet: {FUNDER}")

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

token_id = "101621467528934283632456704600301715153811143182972337673199813033850688585771"
size = 5 
price = 0.998 

# We'll try a few common argument patterns until one works
patterns = [
    {"token_id": token_id, "price": price, "size": size, "side": "BUY"},
    {"tokenId": token_id, "price": price, "size": size, "side": "BUY"}, # Already failed, but for completeness
    {"order_args": OrderArgs(token_id=token_id, price=price, size=size, side="BUY")},
    {OrderArgs(token_id=token_id, price=price, size=size, side="BUY")} # Positional
]

for i, pattern in enumerate(patterns):
    try:
        print(f"Attempt {i+1}: Using pattern {list(pattern.keys()) if isinstance(pattern, dict) else 'OrderArgs'}")
        if isinstance(pattern, dict):
            result = client.post_order(**pattern)
        else:
            result = client.post_order(pattern[0])
        
        print(f"\n✅ SUCCESS with pattern {i+1}!")
        print(json.dumps(result, indent=2))
        break
    except Exception as e:
        print(f"❌ Attempt {i+1} failed: {e}")
