#!/Library/Frameworks/Python.framework/Versions/3.14/bin/python3
"""
Polymarket Loop Executor
The "Hands". Watches trades/approved and pushes them to the CLOB.
"""

import os
import json
import shutil
import time
from datetime import datetime
from py_clob_client_v2 import ClobClient, OrderArgsV2
from types import SimpleNamespace

# Setup Clob Client (Matches the trader config)
KEYS_FILE = os.path.join(os.path.dirname(__file__), '.polymarket-keys.json')
with open(KEYS_FILE) as f:
    keys = json.load(f)

creds = SimpleNamespace(api_key=keys['apiKey'], api_secret=keys['secret'], api_passphrase=keys['passphrase'])
client = ClobClient(
    host='https://clob.polymarket.com',
    chain_id=137,
    key='0xd2aad0f4a95a4e2b8d5090613fb95c278fcddb506616096d49df5d4c39859a3b',
    creds=creds,
    signature_type=1,
    funder='0x98D9Dbd34d0156E6385D08d5263467601BE5e972'
)

APPROVED_DIR = "trades/approved"
HISTORY_DIR = "trades/history"

def execute_trade(proposal):
    try:
        # Determine price based on direction (Simplified for pilot)
        price = 0.65 if proposal['direction'] == 'UP' else 0.35
        
        order_args = OrderArgsV2(
            token_id=proposal['token_id'],
            price=price,
            size=proposal['stake'],
            side='BUY'
        )
        
        result = client.create_and_post_order(order_args, {})
        return result
    except Exception as e:
        print(f"Execution failed: {e}")
        return None

def run_executor():
    print(f"[{datetime.now()}] Executor Loop started...")
    
    while True:
        files = [f for f in os.listdir(APPROVED_DIR) if f.endswith('.json')]
        
        for filename in files:
            path = os.path.join(APPROVED_DIR, filename)
            try:
                with open(path, 'r') as f:
                    proposal = json.load(f)
                
                print(f"[{datetime.now()}] Executing approved trade: {filename}")
                res = execute_trade(proposal)
                
                if res:
                    proposal['execution_result'] = res
                    proposal['executed_at'] = datetime.now().isoformat()
                    print(f"[SUCCESS] Trade pushed to CLOB: {res}")
                else:
                    proposal['execution_result'] = "FAILED"
                
                with open(path, 'w') as f:
                    json.dump(proposal, f, indent=4)
                
                shutil.move(path, os.path.join(HISTORY_DIR, filename))
                
            except Exception as e:
                print(f"[ERROR] Execution loop error: {e}")
        
        time.sleep(5)

if __name__ == "__main__":
    run_executor()
