#!/usr/local/bin/python3
import os
import json
from dotenv import load_dotenv
from py_clob_client.client import ClobClient

# Load config
BOT_DIR = '/Users/colinbrennan/.openclaw/workspace/bots'
load_dotenv(os.path.join(BOT_DIR, '.env'))

HOST = "https://clob.polymarket.com"
PRIVATE_KEY = os.getenv('PRIVATE_KEY')
FUNDER = os.getenv('WALLET_ADDRESS') # Use the wallet address as funder

print("=== Polymarket Test Trade ===")
print(f"Using Wallet: {FUNDER}")

# Initialize Client
# signature_type=1 for Magic wallets as seen in polymarket_auth.py
client = ClobClient(
    HOST,
    key=PRIVATE_KEY,
    chain_id=137,
    signature_type=1,
    funder=FUNDER,
)

# Market: Will Bitcoin reach $115,000 in May?
# Outcome: No
# Token ID from API: 16748857912398914355191833003518205315915666088521477047521226979492030162264
token_id = "16748857912398914355191833003518205315915666088521477047521226979492030162264"
price = 0.999 # Current price is ~0.9995, bidding 0.999 is a safe limit order
size = 5 # Minimum order size is 5 shares

print(f"Placing limit order for {size} shares of token {token_id} at ${price}...")

try:
    # create_order is the standard method for limit orders
    order = client.create_order(
        token_id=token_id,
        price=price,
        size=size,
        side="BUY",
    )
    print("\n✅ ORDER PLACED SUCCESSFULLY")
    print(json.dumps(order, indent=2))
except Exception as e:
    print(f"\n❌ TRADE FAILED: {e}")
