#!/usr/local/bin/python3
import os
import json
from dotenv import load_dotenv
from py_clob_client_v2 import ClobClient, OrderArgsV2

# Load config
BOT_DIR = '/Users/colinbrennan/.openclaw/workspace/bots'
load_dotenv(os.path.join(BOT_DIR, '.env'))

HOST = "https://clob.polymarket.com"
PRIVATE_KEY = os.getenv('PRIVATE_KEY')
FUNDER = os.getenv('WALLET_ADDRESS')
API_KEY = os.getenv('API_KEY')
API_SECRET = os.getenv('API_SECRET')
API_PASSPHRASE = os.getenv('API_PASSPHRASE')

print("=== Polymarket Buy-Back ===")
print(f"Using Wallet: {FUNDER}")

from types import SimpleNamespace
creds = SimpleNamespace(api_key=API_KEY, api_secret=API_SECRET, api_passphrase=API_PASSPHRASE)

client = ClobClient(
    host=HOST,
    chain_id=137,
    key=PRIVATE_KEY,
    creds=creds,
    signature_type=1, 
    funder=FUNDER
)

token_id = "101621467528934283632456704600301715153811143182972337673199813033850688585771"
size = 5 
price = 0.998 

try:
    print(f"Buying back {size} shares at ${price}...")
    order_args = OrderArgsV2(
        token_id=token_id,
        price=price,
        size=size,
        side='BUY'
    )
    result = client.create_and_post_order(order_args, {})
    print("\n✅ BUY-BACK EXECUTED")
    print(json.dumps(result, indent=2))
except Exception as e:
    print(f"\n❌ FAILED: {e}")
