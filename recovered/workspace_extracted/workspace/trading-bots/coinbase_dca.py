#!/usr/bin/env python3
"""
Coinbase DCA + Dip Buying Bot - LIVE DATA VERSION

Fetches REAL prices from Coinbase API and shows what trades WOULD happen.
Uses your real API keys but in dry-run mode = no actual trading.

Usage:
    python3 coinbase_dca.py --live-test    # See real prices, no trades
    python3 coinbase_dca.py --check        # Just show status
"""
import argparse
import sys
import os
import requests
import base64
import json
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from trading_utils import (
    load_config, load_state, save_state, setup_logging,
    format_money, format_percent, log_trade,
    load_positions, save_positions, add_position,
    check_stop_losses, check_daily_loss_limit, get_total_invested
)

def get_coinbase_headers(config):
    """Create authenticated headers for Coinbase API"""
    import hmac
    import hashlib
    
    timestamp = str(int(datetime.now().timestamp()))
    message = timestamp + 'GET' + '/api/v3/brokerage/accounts'
    
    # Decode the EC key (simplified for demo - real implementation would use proper signing)
    signature = base64.b64encode(
        hmac.new(
            config['api_secret'].encode(),
            message.encode(),
            hashlib.sha256
        ).digest()
    ).decode()
    
    return {
        'CB-ACCESS-KEY': config['api_key'].split('/')[-1],  # Just the key ID
        'CB-ACCESS-SIGN': signature,
        'CB-ACCESS-TIMESTAMP': timestamp,
        'Content-Type': 'application/json'
    }

def get_btc_price_live():
    """Get LIVE BTC price from Coinbase public API (no auth needed)"""
    try:
        response = requests.get(
            "https://api.coinbase.com/v2/exchange-rates?currency=BTC",
            timeout=15
        )
        data = response.json()
        btc_gbp = float(data['data']['rates']['GBP'])
        return btc_gbp
    except Exception as e:
        print(f"⚠️  Couldn't get live price: {e}")
        return None

def get_btc_price_history(days=30):
    """Get historical BTC prices from Coinbase"""
    try:
        # Coinbase candles endpoint (public)
        end = datetime.utcnow()
        start = end - timedelta(days=days)
        
        url = "https://api.exchange.coinbase.com/products/BTC-GBP/candles"
        params = {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "granularity": 86400  # 1 day candles
        }
        
        response = requests.get(url, params=params, timeout=15)
        candles = response.json()
        
        # Extract close prices
        prices = [candle[4] for candle in candles]  # Close is index 4
        return prices[::-1]  # Reverse to chronological order
        
    except Exception as e:
        print(f"⚠️  Couldn't get history: {e}")
        return []

def check_for_dip(prices, threshold=3):
    """Check if current price is down X% from recent high"""
    if not prices or len(prices) < 2:
        return False, 0
    
    current = prices[-1]
    recent_high = max(prices[-7:]) if len(prices) >= 7 else max(prices)
    
    if recent_high <= 0:
        return False, 0
    
    drop_pct = ((recent_high - current) / recent_high) * 100
    return drop_pct >= threshold, drop_pct

def show_live_status(config):
    """Show live BTC price and analysis"""
    print("\n🪙 LIVE COINBASE STATUS")
    print("=" * 60)
    
    # Get live price
    current_price = get_btc_price_live()
    if not current_price:
        print("❌ Can't fetch live data")
        return
    
    print(f"📈 BTC/GBP: {format_money(current_price)}")
    print(f"🕐 Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Get 30-day history
    print("\n📊 Fetching 30-day history...")
    prices = get_btc_price_history(30)
    
    if prices:
        print(f"📈 30-day high: {format_money(max(prices))}")
        print(f"📉 30-day low:  {format_money(min(prices))}")
        print(f"📊 Current vs high: {((current_price - max(prices)) / max(prices) * 100):+.1f}%")
        
        # Check for dip
        dip_config = config.get('strategies', {}).get('buy_dips', {})
        is_dip, drop_pct = check_for_dip(prices, dip_config.get('dip_threshold_percent', 3))
        
        print(f"\n🎯 Dip Analysis:")
        print(f"   Threshold: {dip_config.get('dip_threshold_percent', 3)}%")
        print(f"   Current drop: {drop_pct:.1f}%")
        
        if is_dip:
            print(f"   🚨 DIP DETECTED! BTC down {drop_pct:.1f}%")
            buy_amount = config['strategies']['buy_dips']['max_buy_amount']
            btc_qty = buy_amount / current_price
            print(f"   💰 Would buy: {format_money(buy_amount)} → {btc_qty:.6f} BTC")
        else:
            print(f"   ✅ No dip detected (market stable/pumping)")
    
    # Show DCA info
    dca = config.get('strategies', {}).get('dca', {})
    print(f"\n📅 DCA Schedule:")
    print(f"   Amount: {format_money(dca.get('amount_gbp', 10))} every {dca.get('frequency_days', 7)} days")
    print(f"   Next buy: {format_money(dca.get('amount_gbp', 10))} → {(dca.get('amount_gbp', 10) / current_price):.6f} BTC")
    
    print("\n" + "=" * 60)

def simulate_run(config, full_config, logger):
    """Simulate what the bot would do with LIVE data"""
    print("\n🚀 SIMULATING BOT RUN WITH LIVE DATA")
    print("=" * 60)
    
    current_price = get_btc_price_live()
    if not current_price:
        return
    
    prices = get_btc_price_history(7)
    
    # Load positions and check safety
    positions = load_positions()
    safety = config.get("safety", {})
    
    # SAFETY CHECK 1: Stop Loss
    stop_loss_pct = safety.get("stop_loss_percent", 20)
    stop_losses = check_stop_losses(positions, {"BTC-GBP": current_price}, stop_loss_pct, logger)
    
    if stop_losses:
        print(f"\n🚨 STOP LOSS CHECK:")
        for sl in stop_losses:
            print(f"   {sl['asset']}: down {sl['loss_percent']:.1f}%")
            print(f"   Would sell: {sl['amount_btc']:.6f} BTC for {format_money(sl['value_gbp'])}")
            log_trade(logger, "STOP_LOSS_WOULD_SELL",
                      f"{sl['asset']}: {sl['amount_btc']:.6f} BTC (down {sl['loss_percent']:.1f}%)", 
                      dry_run=True)
        print("   ⚠️  Trading paused - positions need attention!")
        print("=" * 60)
        return  # Don't buy if we need to sell!
    else:
        print(f"\n✅ Stop loss check: No positions down {stop_loss_pct}% or more")
    
    # SAFETY CHECK 2: Daily Loss Limit
    max_daily_loss = safety.get("max_daily_loss", 20)
    can_trade, daily_loss = check_daily_loss_limit(positions, {"BTC-GBP": current_price}, 
                                                     max_daily_loss, logger)
    if not can_trade:
        print(f"\n⛔ Daily loss limit reached: {format_money(daily_loss)}")
        print("   Trading paused for today.")
        print("=" * 60)
        return
    else:
        print(f"✅ Daily loss: {format_money(daily_loss)} (limit: {format_money(max_daily_loss)})")
    
    # SAFETY CHECK 3: Total Invested
    total_invested = get_total_invested(positions)
    max_invested = safety.get("max_total_invested", 100)
    if total_invested >= max_invested:
        print(f"\n⛔ Max invested limit reached: {format_money(total_invested)}")
        print("=" * 60)
        return
    else:
        remaining = max_invested - total_invested
        print(f"✅ Invested: {format_money(total_invested)} / {format_money(max_invested)} ({format_money(remaining)} left)")
    
    print("\n" + "-" * 60)
    
    # Check DCA
    dca = config.get('strategies', {}).get('dca', {})
    if dca.get('enabled'):
        btc_qty = dca['amount_gbp'] / current_price
        print(f"\n📅 DCA Strategy:")
        print(f"   BUY: {format_money(dca['amount_gbp'])} → {btc_qty:.6f} BTC @ {format_money(current_price)}")
        log_trade(logger, "DCA_WOULD_BUY", 
                  f"{format_money(dca['amount_gbp'])} → {btc_qty:.6f} BTC", dry_run=True)
        
        # Simulate recording position
        if not full_config.get("dry_run", True):
            add_position(positions, "BTC-GBP", btc_qty, current_price, dca['amount_gbp'])
    
    # Check Dip
    dip = config.get('strategies', {}).get('buy_dips', {})
    if dip.get('enabled') and prices:
        is_dip, drop_pct = check_for_dip(prices, dip['dip_threshold_percent'])
        
        print(f"\n🎯 Dip Strategy:")
        if is_dip:
            btc_qty = dip['max_buy_amount'] / current_price
            print(f"   🚨 TRIGGERED: BTC down {drop_pct:.1f}%")
            print(f"   BUY: {format_money(dip['max_buy_amount'])} → {btc_qty:.6f} BTC")
            log_trade(logger, "DIP_WOULD_BUY",
                      f"{format_money(dip['max_buy_amount'])} → {btc_qty:.6f} BTC (down {drop_pct:.1f}%)", 
                      dry_run=True)
            
            # Simulate recording position
            if not full_config.get("dry_run", True):
                add_position(positions, "BTC-GBP", btc_qty, current_price, dip['max_buy_amount'])
        else:
            print(f"   ⏸️  No dip (drop: {drop_pct:.1f}% < {dip['dip_threshold_percent']}% threshold)")
    
    print("\n" + "=" * 60)
    print("📝 This was a SIMULATION using LIVE prices")
    print("   No actual trades were made")
    print("   Set dry_run: false in config to trade for real")

def main():
    parser = argparse.ArgumentParser(description="Coinbase Bot - Live Data Mode")
    parser.add_argument("--live-test", action="store_true", help="Run simulation with live prices")
    parser.add_argument("--check", action="store_true", help="Check live status only")
    args = parser.parse_args()
    
    full_config = load_config()
    config = full_config.get("platforms", {}).get("coinbase", {})
    logger = setup_logging(full_config.get("logging", {}))
    
    if args.check:
        show_live_status(config)
        return
    
    if args.live_test:
        simulate_run(config, full_config, logger)
        return
    
    # Default: show live status
    show_live_status(config)

if __name__ == "__main__":
    main()
