#!/usr/bin/env python3
"""
Telegram Webhook Handler for Bot Trade Approvals
Handles approve/deny button callbacks from trading bots
"""

import json
import os
from flask import Flask, request
import requests

app = Flask(__name__)

TELEGRAM_TOKEN = '8527377021:AAFfUppTGj8EU8v4GBtMztAoOVbYVKNcQ4s'
CHAT_ID = '868123037'

# Load pending trades from file
PENDING_TRADES_FILE = os.path.join(os.path.dirname(__file__), 'pending-trades.json')

def load_pending_trades():
    if os.path.exists(PENDING_TRADES_FILE):
        try:
            with open(PENDING_TRADES_FILE) as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_pending_trades(trades):
    with open(PENDING_TRADES_FILE, 'w') as f:
        json.dump(trades, f, indent=2)

def execute_trade(trade_data):
    """Execute the approved trade via Polymarket API"""
    try:
        from py_clob_client_v2 import ClobClient
        from types import SimpleNamespace
        
        # Load API keys
        KEYS_FILE = os.path.join(os.path.dirname(__file__), '.polymarket-keys.json')
        with open(KEYS_FILE) as f:
            keys = json.load(f)
        
        creds = SimpleNamespace(
            api_key=keys['apiKey'],
            api_secret=keys['secret'],
            api_passphrase=keys['passphrase']
        )
        
        client = ClobClient(
            host='https://clob.polymarket.com',
            chain_id=137,
            key='0xd2aad0f4a95a4e2b8d5090613fb95c278fcddb506616096d49df5d4c39859a3b',
            creds=creds
        )
        
        order = client.create_and_post_order(
            {
                'tokenID': trade_data['token_id'],
                'price': trade_data['price'],
                'size': trade_data['size'],
                'side': 0,
                'expiration': 0
            },
            {
                'tickSize': '0.01',
                'negRisk': False
            }
        )
        
        order_id = order.get('orderID', 'N/A')
        if isinstance(order_id, str):
            order_id = order_id[:8] + '...'
        
        return True, order_id
        
    except Exception as e:
        return False, str(e)

@app.route('/webhook', methods=['POST'])
def webhook():
    update = request.get_json()
    
    # Handle callback query (button clicks)
    if 'callback_query' in update:
        callback = update['callback_query']
        chat_id = callback['message']['chat']['id']
        message_id = callback['message']['message_id']
        data = callback['data']  # e.g., "trade_approve_1" or "trade_deny_1"
        callback_id = callback['id']
        
        # Parse callback data
        parts = data.split('_')
        action = parts[1]  # "approve" or "deny"
        trade_id = int(parts[2])
        
        # Load pending trades
        pending_trades = load_pending_trades()
        
        if trade_id not in pending_trades:
            # Trade already processed or expired
            requests.post(
                f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery',
                json={'callback_query_id': callback_id, 'text': 'Trade already processed'}
            )
            return 'OK'
        
        trade_data = pending_trades[trade_id]
        
        if action == 'approve':
            # Execute the trade
            success, result = execute_trade(trade_data)
            
            if success:
                response_msg = f"✅ Trade APPROVED & EXECUTED!\nOrder ID: {result}"
            else:
                response_msg = f"❌ Trade execution failed: {result}"
            
            # Remove from pending
            del pending_trades[trade_id]
            save_pending_trades(pending_trades)
            
        elif action == 'deny':
            response_msg = f"❌ Trade DENIED"
            
            # Remove from pending
            del pending_trades[trade_id]
            save_pending_trades(pending_trades)
        
        # Answer callback query
        requests.post(
            f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery',
            json={'callback_query_id': callback_id, 'text': response_msg}
        )
        
        # Edit original message to show result
        original_text = callback['message']['text']
        updated_text = f"{original_text}\n\n**RESULT: {response_msg}**"
        
        requests.post(
            f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/editMessageText',
            json={
                'chat_id': chat_id,
                'message_id': message_id,
                'text': updated_text
            }
        )
        
        return 'OK'
    
    return 'OK'

if __name__ == '__main__':
    # Run webhook server on port 5000
    app.run(host='0.0.0.0', port=5000)
