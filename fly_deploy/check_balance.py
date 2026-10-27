#!/usr/local/bin/python3
import os
import json
from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds

# Load config
BOT_DIR = '/Users/colinbrennan/.openclaw/workspace/bots'
load_dotenv(os.path.join(BOT_DIR, '.env'))

HOST = "https://clob.polymarket.com"
PRIVATE_KEY = os.getenv('PRIVATE_KEY')
FUNDER = os.getenv('WALLET_ADDRESS')
API_KEY = os.getenv('API_KEY')
API_SECRET = os.getenv('API_SECRET')
API_PASSPHRASE = os.getenv('API_PASSPHRASE')

print("=== Polymarket Account Check ===")

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
    # Get balance
    # The client usually has get_balance or similar. 
    # Let's try get_balance() or check common method names.
    balance = client.get_balance()
    print(f"\n💰 Current Balance: {balance}")
    
    # Check open orders
    print("\n🔎 Checking Open Orders...")
    orders = client.get_orders()
    if not orders:
        print("No open orders found.")
    else:
        for o in orders:
            print(f"Order ID: {getattr(o, 'orderId', 'N/A')} | Token: {getattr(o, 'tokenId', 'N/A')} | Price: {getattr(o, 'price', 'N/A')} | Size: {getattr(o, 'size', 'N/A')}")

except Exception as e:
    print(f"\n❌ FAILED to fetch account info: {e}")
