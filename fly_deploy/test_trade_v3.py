#!/usr/local/bin/python3
import os
import json
from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs

# Load config
BOT_DIR = '/Users/colinbrennan/.openclaw/workspace/bots'
load_dotenv(os.path.join(BOT_DIR, '.env'))

HOST = "https://clob.polymarket.com"
PRIVATE_KEY = os.getenv('PRIVATE_KEY')
FUNDER = os.getenv('WALLET_ADDRESS')

print("=== Polymarket Test Trade v3 ===")
print(f"Using Wallet: {FUNDER}")

client = ClobClient(
    HOST,
    key=PRIVATE_KEY,
    chain_id=137,
    signature_type=1,
    funder=FUNDER,
)

# Market: Will Bitcoin reach $115,000 in May?
# Outcome: No
token_id = "16748857912398914355191833003518205315915666088521477047521226979492030162264"
price = 0.999 
size = 5 

print(f"Placing limit order for {size} shares of {token_id} at ${price}...")

try:
    # The a-hoc create_order(tokenId=...) was a guess.
    # The help output says create_order(self, order_args: OrderArgs, ...)
    # So we must use the OrderArgs dataclass.
    args = OrderArgs(
        token_id=token_id, # Note: checking if it is token_id or tokenId
        price=price,
        size=size,
        side="BUY"
    )
    
    order = client.create_order(args)
    print("\n✅ ORDER PLACED SUCCESSFULLY")
    print(json.dumps(order, indent=2))
except Exception as e:
    print(f"\n❌ TRADE FAILED: {e}")
    # Debugging the OrderArgs fields if it fails again
    try:
        import py_clob_client.clob_types as types
        print("\nAvailable OrderArgs fields:", dir(types.OrderArgs))
    except:
        pass
