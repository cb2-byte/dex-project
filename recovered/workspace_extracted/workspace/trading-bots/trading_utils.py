"""
Trading utilities - helper functions for both bots
"""
import json
import os
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Setup paths
WORKSPACE = Path.home() / "workspace" / "trading-bots"
LOG_FILE = WORKSPACE / "trading_bot.log"

def setup_logging(config):
    """Setup logging to file and console"""
    level = getattr(logging, config.get("level", "INFO"))
    
    handlers = [logging.FileHandler(LOG_FILE)]
    if config.get("console", True):
        handlers.append(logging.StreamHandler())
    
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=handlers
    )
    return logging.getLogger()

def load_config():
    """Load config from JSON - handles both old and new structures"""
    config_path = WORKSPACE / "config.json"
    with open(config_path) as f:
        config = json.load(f)
    
    # Handle new structure with platforms
    if 'platforms' in config:
        return config
    
    # Handle old flat structure (backward compat)
    return {
        'platforms': {
            'coinbase': config.get('coinbase', {}),
            'polymarket': config.get('polymarket', {}),
            'bankr': config.get('bankr', {}),
            'polytrade': config.get('polytrade', {})
        },
        'telegram': config.get('telegram', {}),
        'logging': config.get('logging', {}),
        'dry_run': config.get('dry_run', True)
    }

def save_state(data, filename):
    """Save bot state to file"""
    state_path = WORKSPACE / filename
    with open(state_path, 'w') as f:
        json.dump(data, f, indent=2, default=str)

def load_state(filename, default=None):
    """Load bot state from file"""
    state_path = WORKSPACE / filename
    if state_path.exists():
        with open(state_path) as f:
            return json.load(f)
    return default or {}

def format_money(amount, currency="£"):
    """Format money nicely"""
    return f"{currency}{amount:,.2f}"

def format_percent(value):
    """Format percentage nicely"""
    return f"{value:+.2f}%"

def log_trade(logger, action, details, dry_run=False):
    """Log a trade action"""
    mode = "[DRY RUN] " if dry_run else ""
    logger.info(f"{mode}{action}: {details}")

def check_safety_limits(config, current_invested, logger):
    """Check if we're within safety limits"""
    max_invested = config.get("max_total_invested", 100)
    
    if current_invested >= max_invested:
        logger.warning(f"Safety limit reached: {format_money(current_invested)} invested")
        return False
    
    return True

def send_telegram_alert(token, chat_id, message):
    """Send Telegram alert (if configured)"""
    if not token or not chat_id:
        return False
    
    try:
        import requests
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
        response = requests.post(url, json=data, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"Failed to send Telegram alert: {e}")
        return False

def should_run_daily_task(task_name, frequency_days=1):
    """Check if a daily task should run"""
    state = load_state("task_state.json")
    last_run = state.get(task_name)
    
    if last_run:
        last_run = datetime.fromisoformat(last_run)
        if datetime.now() - last_run < timedelta(days=frequency_days):
            return False
    
    # Update last run
    state[task_name] = datetime.now().isoformat()
    save_state(state, "task_state.json")
    return True

def calculate_portfolio_value(holdings, current_prices):
    """Calculate total portfolio value"""
    total = 0
    for asset, amount in holdings.items():
        price = current_prices.get(asset, 0)
        total += amount * price
    return total


def load_positions():
    """Load tracked positions (what we bought and at what price)"""
    return load_state("positions.json", {"holdings": {}, "buy_history": []})


def save_positions(positions):
    """Save positions to file"""
    save_state(positions, "positions.json")


def add_position(positions, asset, amount, price_gbp, amount_gbp):
    """Record a new buy position"""
    if asset not in positions["holdings"]:
        positions["holdings"][asset] = {
            "total_btc": 0,
            "total_spent": 0,
            "avg_buy_price": 0,
            "buys": []
        }
    
    holding = positions["holdings"][asset]
    holding["total_btc"] += amount
    holding["total_spent"] += amount_gbp
    holding["avg_buy_price"] = holding["total_spent"] / holding["total_btc"] if holding["total_btc"] > 0 else 0
    
    # Record individual buy
    holding["buys"].append({
        "date": datetime.now().isoformat(),
        "amount_btc": amount,
        "price_gbp": price_gbp,
        "spent_gbp": amount_gbp
    })
    
    # Add to history
    positions["buy_history"].append({
        "date": datetime.now().isoformat(),
        "asset": asset,
        "amount_btc": amount,
        "price_gbp": price_gbp,
        "spent_gbp": amount_gbp
    })
    
    save_positions(positions)


def check_stop_losses(positions, current_prices, stop_loss_percent, logger):
    """Check if any positions should be sold (stop loss triggered)"""
    assets_to_sell = []
    
    for asset, holding in positions["holdings"].items():
        if holding["total_btc"] <= 0:
            continue
            
        current_price = current_prices.get(asset)
        if not current_price:
            continue
        
        avg_buy = holding["avg_buy_price"]
        if avg_buy <= 0:
            continue
        
        # Calculate loss percentage
        loss_pct = ((avg_buy - current_price) / avg_buy) * 100
        
        if loss_pct >= stop_loss_percent:
            assets_to_sell.append({
                "asset": asset,
                "avg_buy_price": avg_buy,
                "current_price": current_price,
                "loss_percent": loss_pct,
                "amount_btc": holding["total_btc"],
                "value_gbp": holding["total_btc"] * current_price
            })
            logger.warning(f"🚨 STOP LOSS TRIGGERED for {asset}: down {loss_pct:.1f}%")
    
    return assets_to_sell


def check_daily_loss_limit(positions, current_prices, max_daily_loss, logger):
    """Check if we've hit daily loss limit"""
    today = datetime.now().strftime("%Y-%m-%d")
    daily_state = load_state("daily_loss.json", {})
    
    # Reset if new day
    if daily_state.get("date") != today:
        daily_state = {"date": today, "loss_gbp": 0, "trades": []}
    
    # Calculate current unrealized loss for today
    todays_buys = [b for b in positions.get("buy_history", []) 
                   if b["date"].startswith(today)]
    
    daily_loss = 0
    for buy in todays_buys:
        asset = buy["asset"]
        current_price = current_prices.get(asset, buy["price_gbp"])
        current_value = buy["amount_btc"] * current_price
        loss = buy["spent_gbp"] - current_value
        if loss > 0:
            daily_loss += loss
    
    daily_state["loss_gbp"] = daily_loss
    save_state(daily_state, "daily_loss.json")
    
    if daily_loss >= max_daily_loss:
        logger.warning(f"⚠️ Daily loss limit hit: {format_money(daily_loss)} (limit: {format_money(max_daily_loss)})")
        return False, daily_loss
    
    return True, daily_loss


def get_total_invested(positions):
    """Get total amount invested"""
    total = 0
    for holding in positions["holdings"].values():
        total += holding.get("total_spent", 0)
    return total
