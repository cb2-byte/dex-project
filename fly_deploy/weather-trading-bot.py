#!/usr/bin/env python3
"""
Polymarket Weather Trading Bot
Auto-trades weather markets using Open-Meteo forecasts + edge calculation
"""

import requests
import time
import json
import os
from datetime import datetime, timedelta
from types import SimpleNamespace
from py_clob_client_v2 import ClobClient

# Load Polymarket API credentials
POLY_KEYS_FILE = os.path.join(os.path.dirname(__file__), '.polymarket-keys.json')
with open(POLY_KEYS_FILE) as f:
    poly_keys = json.load(f)

# Polymarket CLOB Client
poly_creds = SimpleNamespace(
    api_key=poly_keys['apiKey'],
    api_secret=poly_keys['secret'],
    api_passphrase=poly_keys['passphrase']
)

poly_client = ClobClient(
    host='https://clob.polymarket.com',
    chain_id=137,
    key='0xd2aad0f4a95a4e2b8d5090613fb95c278fcddb506616096d49df5d4c39859a3b',
    creds=poly_creds
)

# Load Polymarket API credentials (same as crypto bots)
POLY_KEYS_FILE = os.path.join(os.path.dirname(__file__), '.polymarket-keys.json')
with open(POLY_KEYS_FILE) as f:
    poly_keys = json.load(f)

# Trading config
CHECK_INTERVAL = 300  # Check every 5 minutes
MIN_EDGE_PERCENT = 5.0  # Minimum edge to trade
MAX_POSITION_USDC = 50  # Max per trade
MAX_DAILY_EXPOSURE = 100  # Max per day
KELLY_FRACTION = 0.25  # Quarter Kelly
TRADING_MODE = 'LIVE'  # 'PAPER' or 'LIVE'

# 8 WU-based cities (HK added later)
CITIES = {
    "London": {"lat": 51.5074, "lon": -0.1278, "station": "EGLC", "wu_path": "gb/london/EGLC"},
    "New York": {"lat": 40.7128, "lon": -74.0060, "station": "KLGA", "wu_path": "us/ny/new-york/KLGA"},
    "Tokyo": {"lat": 35.6762, "lon": 139.6503, "station": "RJTT", "wu_path": "jp/tokyo/RJTT"},
    "Singapore": {"lat": 1.3521, "lon": 103.8198, "station": "WSSS", "wu_path": "sg/singapore/WSSS"},
    "Sydney": {"lat": -33.8688, "lon": 151.2093, "station": "YSSY", "wu_path": "au/nsw/sydney/YSSY"},
    "Dubai": {"lat": 25.2048, "lon": 55.2708, "station": "OMDB", "wu_path": "ae/dubai/OMDB"},
    "Frankfurt": {"lat": 50.1109, "lon": 8.6821, "station": "EDDF", "wu_path": "de/frankfurt/EDDF"},
    "Paris": {"lat": 48.8566, "lon": 2.3522, "station": "LFPG", "wu_path": "fr/paris/LFPG"},
}

# Track daily exposure
daily_exposure = {
    "date": datetime.now().strftime('%Y-%m-%d'),
    "total_usdc": 0,
    "trades": []
}

def send_telegram_alert(message):
    """Send Telegram alert"""
    try:
        token = '8527377021:AAFfUppTGj8EU8v4GBtMztAoOVbYVKNcQ4s'
        chat_id = '868123037'
        url = f'https://api.telegram.org/bot{token}/sendMessage'
        requests.post(url, json={'chat_id': chat_id, 'text': message})
    except Exception as e:
        print(f"Telegram error: {e}")

def get_openmeteo_forecast(lat, lon, days=7):
    """
    Pull forecast data from Open-Meteo (free, no API key)
    Returns daily max temps for next N days
    """
    try:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
            "timezone": "auto",
            "forecast_days": days
        }
        
        resp = requests.get(url, params=params, timeout=15)
        if resp.status_code != 200:
            print(f"Open-Meteo error: {resp.status_code}")
            return None
        
        data = resp.json()
        daily = data.get('daily', {})
        
        # Parse into structured format
        forecasts = []
        dates = daily.get('time', [])
        max_temps = daily.get('temperature_2m_max', [])
        min_temps = daily.get('temperature_2m_min', [])
        precip = daily.get('precipitation_sum', [])
        
        for i, date in enumerate(dates):
            forecasts.append({
                'date': date,
                'max_temp': max_temps[i] if i < len(max_temps) else None,
                'min_temp': min_temps[i] if i < len(min_temps) else None,
                'precip': precip[i] if i < len(precip) else None
            })
        
        return forecasts
        
    except Exception as e:
        print(f"Open-Meteo fetch error: {e}")
        return None

def calculate_probability_distribution(forecast_high, forecast_std=2.5, buckets=None):
    """
    Calculate probability distribution across temperature buckets
    Uses normal distribution approximation
    
    forecast_high: predicted daily high (°C)
    forecast_std: standard deviation based on forecast lead time
    buckets: list of (low, high) tuples defining temperature ranges
    """
    if buckets is None:
        # Default buckets (adjust based on city/season)
        buckets = [
            (15, 16), (16, 17), (17, 18), (18, 19), (19, 20),
            (20, 21), (21, 22), (22, 23), (23, 24), (24, 25),
            (25, 26), (26, 27), (27, 28), (28, 29), (29, 30)
        ]
    
    import math
    
    def normal_cdf(x, mu, sigma):
        return 0.5 * (1 + math.erf((x - mu) / (sigma * math.sqrt(2))))
    
    probabilities = {}
    for low, high in buckets:
        bucket_key = f"{low}-{high}"
        # Probability mass in this bucket
        prob = normal_cdf(high + 0.5, forecast_high, forecast_std) - normal_cdf(low - 0.5, forecast_high, forecast_std)
        probabilities[bucket_key] = round(prob, 3)
    
    return probabilities

def get_market_prices(city, date_str):
    """
    Get current Polymarket prices for weather market buckets
    This is a placeholder — would integrate with Polymarket API
    For now, returns mock data for testing
    """
    # TODO: Replace with actual Polymarket API call
    # For paper trading, we'll simulate market prices
    
    # Mock prices (in real version, fetch from Polymarket)
    mock_prices = {
        "18-19": 0.25,
        "19-20": 0.30,
        "20-21": 0.35,
        "21-22": 0.20,
        "22-23": 0.15,
        "23-24": 0.10,
    }
    
    return mock_prices

def calculate_edge(model_prob, market_price):
    """
    Calculate edge percentage
    Edge = (model_probability - market_price) * 100
    """
    return round((model_prob - market_price) * 100, 2)

def kelly_sizing(model_prob, market_price, bankroll=1000):
    """
    Calculate position size using Kelly Criterion
    f = (q - p) / (1 - p)
    Then apply Kelly fraction (quarter Kelly = 0.25)
    """
    q = model_prob
    p = market_price
    
    if p >= 1.0 or p <= 0:
        return 0
    
    full_kelly = (q - p) / (1 - p)
    fractional_kelly = full_kelly * KELLY_FRACTION
    
    # Convert to USDC amount
    position_size = bankroll * fractional_kelly
    
    # Apply caps
    position_size = min(position_size, MAX_POSITION_USDC)
    position_size = max(position_size, 5)  # Min $5 trade
    
    return round(position_size, 2)

def check_trading_opportunities():
    """
    Main trading logic — check all cities for opportunities
    """
    global daily_exposure
    
    # Reset daily exposure if new day
    today = datetime.now().strftime('%Y-%m-%d')
    if daily_exposure['date'] != today:
        daily_exposure = {'date': today, 'total_usdc': 0, 'trades': []}
    
    print(f"[{datetime.now()}] Checking weather trading opportunities...")
    
    opportunities = []
    
    for city, config in CITIES.items():
        try:
            # Get forecast
            forecast = get_openmeteo_forecast(config['lat'], config['lon'], days=3)
            if not forecast or len(forecast) < 2:
                print(f"  {city}: No forecast data")
                continue
            
            # Get tomorrow's forecast high (index 1)
            tomorrow = forecast[1]
            forecast_high = tomorrow.get('max_temp')
            
            if forecast_high is None:
                print(f"  {city}: No temp data")
                continue
            
            # Calculate probability distribution
            # Adjust std based on forecast lead time (48hr = ~3°C error)
            probs = calculate_probability_distribution(forecast_high, forecast_std=3.0)
            
            # Get market prices
            market_prices = get_market_prices(city, tomorrow['date'])
            
            # Find edges
            for bucket, model_prob in probs.items():
                if bucket not in market_prices:
                    continue
                
                market_price = market_prices[bucket]
                edge = calculate_edge(model_prob, market_price)
                
                if edge >= MIN_EDGE_PERCENT:
                    # Calculate position size
                    position = kelly_sizing(model_prob, market_price, bankroll=500)
                    
                    # Check daily exposure
                    if daily_exposure['total_usdc'] + position > MAX_DAILY_EXPOSURE:
                        print(f"  {city}: Daily exposure limit reached")
                        continue
                    
                    opportunities.append({
                        'city': city,
                        'date': tomorrow['date'],
                        'bucket': bucket,
                        'forecast_high': forecast_high,
                        'model_prob': model_prob,
                        'market_price': market_price,
                        'edge': edge,
                        'position_usdc': position,
                        'station': config['station']
                    })
                    
        except Exception as e:
            print(f"  {city}: Error - {e}")
    
    # Report opportunities
    if opportunities:
        print(f"\nFound {len(opportunities)} trading opportunities:\n")
        for opp in opportunities:
            print(f"  📍 {opp['city']}")
            print(f"     Date: {opp['date']}")
            print(f"     Bucket: {opp['bucket']}°C")
            print(f"     Forecast High: {opp['forecast_high']}°C")
            print(f"     Model Prob: {opp['model_prob']:.1%}")
            print(f"     Market Price: {opp['market_price']:.2f}")
            print(f"     Edge: {opp['edge']:.1f}%")
            print(f"     Position: ${opp['position_usdc']:.2f}")
            print()
        
        # Send Telegram alert
        alert = f"🌤️ Weather Trading Opportunities\n"
        alert += f"Found {len(opportunities)} trades:\n\n"
        for opp in opportunities[:3]:  # Top 3 only
            alert += f"📍 {opp['city']}: {opp['bucket']}°C @ {opp['market_price']:.2f}\n"
            alert += f"   Edge: {opp['edge']:.1f}% | Position: ${opp['position_usdc']:.2f}\n"
        
        send_telegram_alert(alert)
        
        # Execute trades (LIVE mode) or log (PAPER mode)
        if TRADING_MODE == 'LIVE':
            execute_trades(opportunities)
        else:
            log_opportunities(opportunities)
        
    else:
        print("No trading opportunities found (edge < 5%)")
    
    return opportunities

def execute_trades(opportunities):
    """Execute trades on Polymarket via Zipline API"""
    executed = []
    
    for opp in opportunities:
        try:
            # Zipline API Handshake
            payload = {
                "city": opp['city'],
                "bucket": opp['bucket'],
                "model_prob": opp['model_prob'],
                "market_price": opp['market_price'],
                "edge": opp['edge'],
                "position_usdc": opp['position_usdc'],
                "token_id": "TBD_LOOKUP", 
                "slug": opp['city'].lower().replace(" ", "-"),
                "reasoning": f"Signal detected for {opp['city']} bucket {opp['bucket']} with edge {opp['edge']}%"
            }
            
            resp = requests.post("http://localhost:8000/verify", json=payload, timeout=5)
            
            if resp.status_code == 200:
                res_data = resp.json()
                msg = f"✅ ZIPLINE APPROVED: {opp['city']} {opp['bucket']}°C\n"
                msg += f"Position: ${opp['position_usdc']:.2f} | Edge: {opp['edge']:.1f}%\n"
                msg += f"Artifact: {res_data.get('artifact')}"
            else:
                msg = f"❌ ZIPLINE REJECTED: {opp['city']} {opp['bucket']}°C\n"
                msg += f"Reason: {resp.text}"

            print(msg)
            send_telegram_alert(msg)
            if resp.status_code == 200:
                executed.append(opp)
            
        except Exception as e:
            print(f"Zipline communication error: {e}")
    
    return executed


def log_opportunities(opportunities):
    """Log opportunities to file"""
    log_file = os.path.join(os.path.dirname(__file__), 'logs', 'weather-trades.json')
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    # Load existing
    existing = []
    if os.path.exists(log_file):
        try:
            with open(log_file) as f:
                existing = json.load(f)
        except:
            existing = []
    
    # Add new (as paper trades for now)
    for opp in opportunities:
        opp['logged_at'] = datetime.now().isoformat()
        opp['status'] = 'paper_trade'  # Will change to 'live' when API integration added
        existing.append(opp)
        
        # Update daily exposure
        daily_exposure['total_usdc'] += opp['position_usdc']
        daily_exposure['trades'].append(opp)
    
    # Save
    with open(log_file, 'w') as f:
        json.dump(existing, f, indent=2)
    
    # Save daily exposure
    exposure_file = os.path.join(os.path.dirname(__file__), 'logs', 'weather-daily-exposure.json')
    with open(exposure_file, 'w') as f:
        json.dump(daily_exposure, f, indent=2)
    
    print(f"Logged {len(opportunities)} paper trades")

def run_bot():
    """Main bot loop"""
    print(f"[{datetime.now()}] Starting Weather Trading Bot...")
    print(f"Mode: PAPER TRADING (no real money yet)")
    print(f"Cities: {len(CITIES)}")
    print(f"Min Edge: {MIN_EDGE_PERCENT}%")
    print(f"Max Position: ${MAX_POSITION_USDC}")
    print(f"Max Daily: ${MAX_DAILY_EXPOSURE}")
    
    send_telegram_alert("🌤️ Weather Trading Bot started\nMode: PAPER TRADING\n8 cities monitoring")
    
    # Initial check
    check_trading_opportunities()
    
    # Run continuously
    while True:
        time.sleep(CHECK_INTERVAL)
        
        # Check during active market hours (skip overnight)
        now = datetime.now()
        if 8 <= now.hour <= 22:  # 8 AM - 10 PM
            check_trading_opportunities()

if __name__ == '__main__':
    run_bot()
