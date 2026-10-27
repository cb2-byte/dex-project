#!/usr/bin/env python3
"""
Bankr Wallet Bot - LIVE DATA VERSION

Monitors your Bankr wallet and shows balances, prices, opportunities.
Uses your real API key but no automated trading yet.

Usage:
    python3 bankr_bot.py --check       # Show wallet status
    python3 bankr_bot.py --prices    # Show token prices
    python3 bankr_bot.py --portfolio # Full portfolio view
"""
import argparse
import sys
import os
import requests
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from trading_utils import load_config, format_money, setup_logging

BANKR_API = "https://api.bankr.bot"

def get_wallet_balance(wallet_address, api_key):
    """Get Bankr wallet balance"""
    try:
        url = f"{BANKR_API}/wallet/{wallet_address}"
        headers = {"Authorization": f"Bearer {api_key}"}
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"⚠️  Bankr API returned {response.status_code}")
            return None
    except Exception as e:
        print(f"⚠️  Couldn't fetch Bankr balance: {e}")
        return None

def get_token_prices():
    """Get current token prices"""
    try:
        # Use Coinbase for BTC/ETH prices
        btc_response = requests.get(
            "https://api.coinbase.com/v2/exchange-rates?currency=BTC",
            timeout=10
        )
        eth_response = requests.get(
            "https://api.coinbase.com/v2/exchange-rates?currency=ETH",
            timeout=10
        )
        
        btc_gbp = float(btc_response.json()['data']['rates']['GBP'])
        eth_gbp = float(eth_response.json()['data']['rates']['GBP'])
        
        return {
            "BTC": btc_gbp,
            "ETH": eth_gbp
        }
    except Exception as e:
        print(f"⚠️  Couldn't fetch prices: {e}")
        return {}

def show_wallet_status(config):
    """Show Bankr wallet status"""
    print("\n💳 BANKR WALLET STATUS")
    print("=" * 60)
    
    wallet = config['platforms']['bankr']['base_address']
    api_key = config['platforms']['bankr']['api_key']
    backup = config['platforms']['bankr']['backup_address']
    
    print(f"Main Address:   {wallet}")
    print(f"Backup Address: {backup}")
    print(f"API Key:        {api_key[:10]}...{api_key[-10:]}")
    
    # Try to get balance
    print("\n📊 Fetching balances...")
    balance = get_wallet_balance(wallet, api_key)
    
    if balance:
        print(f"✅ Wallet connected!")
        print(f"💰 ETH Balance: {balance.get('eth', 0):.4f} ETH")
        print(f"🪙 Token Count: {len(balance.get('tokens', []))}")
    else:
        print("⚠️  Couldn't fetch live balance (API may need setup)")
        print("   This is normal - Bankr API may require additional auth")
    
    # Show token prices
    print("\n📈 Current Prices (from Coinbase):")
    prices = get_token_prices()
    if prices:
        print(f"   BTC: {format_money(prices.get('BTC', 0))}")
        print(f"   ETH: {format_money(prices.get('ETH', 0))}")
    
    print("\n📝 Notes:")
    print("   - Bankr wallet is your main on-chain wallet")
    print("   - Used for $PNY and other Base tokens")
    print("   - For trades, use Bankr app or connect to DEX")
    print()

def show_full_portfolio(config):
    """Show full portfolio across all wallets"""
    print("\n💼 FULL PORTFOLIO OVERVIEW")
    print("=" * 60)
    
    wallets = config.get('all_wallets', {}).get('ethereum', {})
    
    print("\n🪙 Ethereum Wallets:")
    for name, address in wallets.items():
        print(f"   {name:20s}: {address}")
    
    print("\n₿ Bitcoin:")
    btc = config.get('all_wallets', {}).get('bitcoin', {})
    print(f"   Address: {btc.get('address', 'N/A')}")
    
    print("\n✕ XRP:")
    xrp = config.get('all_wallets', {}).get('xrp', {})
    print(f"   Address: {xrp.get('address', 'N/A')}")
    print(f"   Memo:    {xrp.get('memo', 'N/A')}")
    
    print("\n👤 Monero:")
    xmr = config.get('all_wallets', {}).get('monero', {})
    print(f"   Address: {xmr.get('address', 'N/A')[:30]}...")
    
    print("\n📊 Token Prices:")
    prices = get_token_prices()
    if prices:
        print(f"   BTC: {format_money(prices.get('BTC', 0))}")
        print(f"   ETH: {format_money(prices.get('ETH', 0))}")

def main():
    parser = argparse.ArgumentParser(description="Bankr Wallet Bot")
    parser.add_argument("--check", action="store_true", help="Show wallet status")
    parser.add_argument("--portfolio", action="store_true", help="Full portfolio")
    args = parser.parse_args()
    
    config = load_config()
    logger = setup_logging(config.get("logging", {}))
    
    if args.check:
        show_wallet_status(config)
        return
    
    if args.portfolio:
        show_full_portfolio(config)
        return
    
    # Default: show status
    show_wallet_status(config)
    show_full_portfolio(config)

if __name__ == "__main__":
    main()
