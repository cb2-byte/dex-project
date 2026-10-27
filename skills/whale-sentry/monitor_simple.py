#!/usr/bin/env python3
"""
Whale Sentry - Simple Continuous Monitor (standalone, no imports)
"""
import os
import sys
import time
import signal
import logging
import sqlite3
import requests
from datetime import datetime, timedelta
from pathlib import Path

# Load .env
skill_dir = Path(__file__).parent
env_path = skill_dir / '.env'
with open(env_path, 'r') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            os.environ[key] = value

# Config
ETHERSCAN_KEY = os.getenv('ETHERSCAN_API_KEY')
SOLSCAN_KEY = os.getenv('SOLSCAN_API_KEY')
COVALENT_KEY = os.getenv('COVALENT_API_KEY')
ALCHEMY_KEY = os.getenv('ALCHEMY_API_KEY')
NVIDIA_KEY = os.getenv('NVIDIA_API_KEY')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

DB_PATH = skill_dir / 'whale_sentry.db'
CHECK_INTERVAL = 60

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(skill_dir / 'monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

shutdown = False

def signal_handler(sig, frame):
    global shutdown
    logger.info("Shutdown signal received...")
    shutdown = True

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_wallets():
    conn = get_db()
    with conn:
        cursor = conn.execute("SELECT * FROM wallets WHERE enabled = 1 ORDER BY created_at DESC")
        return [dict(row) for row in cursor.fetchall()]

def save_alert(alert_data):
    conn = get_db()
    with conn:
        conn.execute("""
            INSERT INTO alerts 
            (alert_type, chain, hash, from_address, to_address, value, value_usd, 
             token_symbol, token_value, timestamp, block_number, slot, chain_name,
             wallet_label, wallet_address, threshold_triggered, analysis)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            alert_data.get('alert_type'), alert_data.get('chain'), alert_data.get('hash'),
            alert_data.get('from_address'), alert_data.get('to_address'), alert_data.get('value'),
            alert_data.get('value_usd'), alert_data.get('token_symbol'), alert_data.get('token_value'),
            alert_data.get('timestamp'), alert_data.get('block_number'), alert_data.get('slot'),
            alert_data.get('chain_name'), alert_data.get('wallet_label'), alert_data.get('wallet_address'),
            alert_data.get('threshold_triggered'), alert_data.get('analysis')
        ))

def send_telegram(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, json={'chat_id': TELEGRAM_CHAT_ID, 'text': text, 'parse_mode': 'Markdown'}, timeout=10)
    except Exception as e:
        logger.error(f"Telegram send failed: {e}")

def analyze_with_nvidia(prompt):
    if not NVIDIA_KEY:
        return "Analysis unavailable (no NVIDIA key)"
    try:
        url = "https://integrate.api.nvidia.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {NVIDIA_KEY}", "Content-Type": "application/json"}
        data = {
            "model": "nvidia/nemotron-3-ultra-550b-a55b",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 500,
            "temperature": 0.3
        }
        resp = requests.post(url, headers=headers, json=data, timeout=30)
        return resp.json()['choices'][0]['message']['content']
    except Exception as e:
        return f"Analysis failed: {e}"

def check_ethereum_wallet(wallet):
    if not ETHERSCAN_KEY:
        return
    address = wallet['address']
    try:
        url = f"https://api.etherscan.io/api?module=account&action=txlist&address={address}&sort=desc&apikey={ETHERSCAN_KEY}"
        resp = requests.get(url, timeout=15)
        data = resp.json()
        if data.get('status') != '1':
            return
        
        for tx in data['result'][:10]:
            value_eth = int(tx['value']) / 1e18
            if value_eth >= wallet['threshold_eth']:
                # Check if already alerted
                conn = get_db()
                with conn:
                    cursor = conn.execute("SELECT 1 FROM alerts WHERE hash = ? AND chain = 'ethereum'", (tx['hash'],))
                    if cursor.fetchone():
                        continue
                
                # Get ETH price for USD
                eth_price = 2500  # fallback
                try:
                    price_resp = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd", timeout=5)
                    eth_price = price_resp.json().get('ethereum', {}).get('usd', 2500)
                except:
                    pass
                
                value_usd = value_eth * eth_price
                
                if value_usd >= wallet['threshold_usd']:
                    alert = {
                        'alert_type': 'large_transfer',
                        'chain': 'ethereum',
                        'hash': tx['hash'],
                        'from_address': tx['from'],
                        'to_address': tx['to'],
                        'value': value_eth,
                        'value_usd': value_usd,
                        'token_symbol': 'ETH',
                        'token_value': value_eth,
                        'timestamp': datetime.fromtimestamp(int(tx['timeStamp'])).isoformat(),
                        'block_number': int(tx['blockNumber']),
                        'slot': None,
                        'chain_name': 'Ethereum',
                        'wallet_label': wallet['label'],
                        'wallet_address': wallet['address'],
                        'threshold_triggered': f"ETH={wallet['threshold_eth']}, USD={wallet['threshold_usd']}",
                        'analysis': analyze_with_nvidia(f"Analyze this Ethereum whale transfer: {wallet['label']} ({address}) sent {value_eth:.2f} ETH (${value_usd:,.0f}) from {tx['from'][:10]}... to {tx['to'][:10]}... What might this mean?")
                    }
                    save_alert(alert)
                    send_telegram(f"🐋 *WHALE ALERT* - {wallet['label']} (ETH)\n{value_eth:.2f} ETH (${value_usd:,.0f})\nFrom: {tx['from'][:10]}...\nTo: {tx['to'][:10]}...\n\n{alert['analysis'][:200]}...")
                    logger.info(f"Alert: {wallet['label']} sent {value_eth:.2f} ETH")
    except Exception as e:
        logger.error(f"Ethereum check failed for {wallet['label']}: {e}")

def check_solana_wallet(wallet):
    # Solana monitoring - optional, skip if APIs unavailable
    logger.debug(f"Solana monitoring skipped for {wallet['label']} - no working API")
    return

def main():
    logger.info("=" * 50)
    logger.info("Whale Sentry Monitor Starting (Simple)")
    logger.info("=" * 50)
    
    wallets = get_wallets()
    logger.info(f"Monitoring {len(wallets)} wallets:")
    for w in wallets:
        logger.info(f"  - {w['label']} ({w['chain']}): {w['address'][:10]}...")
    
    logger.info(f"Check interval: {CHECK_INTERVAL}s")
    logger.info("Press Ctrl+C to stop")
    
    while not shutdown:
        start = time.time()
        
        for wallet in wallets:
            if shutdown:
                break
            if wallet['chain'] == 'ethereum':
                check_ethereum_wallet(wallet)
            elif wallet['chain'] == 'solana':
                check_solana_wallet(wallet)
        
        elapsed = time.time() - start
        sleep_time = max(CHECK_INTERVAL - elapsed, 1)
        logger.debug(f"Cycle took {elapsed:.1f}s, sleeping {sleep_time:.1f}s")
        time.sleep(sleep_time)
    
    logger.info("Whale Sentry Monitor Stopped")

if __name__ == "__main__":
    main()