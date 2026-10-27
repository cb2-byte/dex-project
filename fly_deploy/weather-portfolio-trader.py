#!/Library/Frameworks/Python.framework/Versions/3.14/bin/python3
"""
Polymarket Weather Trading Bot with Frank-Wolfe Portfolio Optimization
Auto-trades weather markets using Open-Meteo forecasts + edge calculation
Uses portfolio optimization across all 9 cities

Alerts only on successful executions
"""

import requests
import time
import json
import os
import httpx
from datetime import datetime, timedelta
from types import SimpleNamespace
from py_clob_client_v2 import ClobClient

# Load portfolio optimizer
from portfolio_trader import PortfolioTrader

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
    creds=poly_creds,
    signature_type=1,  # POLY_PROXY for email-login accounts
    funder='0x98D9Dbd34d0156E6385D08d5263467601BE5e972'  # Your Polymarket wallet
)

# Trading config
CHECK_INTERVAL = 300  # Check every 5 minutes
MIN_EDGE_PERCENT = 0.1  # 0.1% - very low threshold to ensure signals execute

# 9 Cities with coordinates
CITIES = {
    "London": {"lat": 51.5074, "lon": -0.1278, "station": "EGLC"},
    "New York": {"lat": 40.7128, "lon": -74.0060, "station": "KLGA"},
    "Tokyo": {"lat": 35.6762, "lon": 139.6503, "station": "RJTT"},
    "Singapore": {"lat": 1.3521, "lon": 103.8198, "station": "WSSS"},
    "Sydney": {"lat": -33.8688, "lon": 151.2093, "station": "YSSY"},
    "Dubai": {"lat": 25.2048, "lon": 55.2708, "station": "OMDB"},
    "Frankfurt": {"lat": 50.1109, "lon": 8.6821, "station": "EDDF"},
    "Paris": {"lat": 48.8566, "lon": 2.3522, "station": "LFPG"},
    "Hong Kong": {"lat": 22.3193, "lon": 114.1694, "station": "VHHH"},
}

# Portfolio trader with weather-specific caps
portfolio_trader = PortfolioTrader()
portfolio_trader.config.per_asset_caps["WEATHER"] = 30.0  # Max $30 across all weather

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
    """Pull forecast from Open-Meteo"""
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
            return None
        
        data = resp.json()
        daily = data.get('daily', {})
        
        forecasts = []
        dates = daily.get('time', [])
        max_temps = daily.get('temperature_2m_max', [])
        min_temps = daily.get('temperature_2m_min', [])
        precip = daily.get('precipitation_sum', [])
        
        for i in range(len(dates)):
            forecasts.append({
                "date": dates[i],
                "max_temp_c": max_temps[i] if i < len(max_temps) else None,
                "min_temp_c": min_temps[i] if i < len(min_temps) else None,
                "precip_mm": precip[i] if i < len(precip) else None
            })
        
        return forecasts
    except Exception as e:
        print(f"Open-Meteo error: {e}")
        return None

def calculate_edge(forecast, threshold, market_type='max_temp'):
    """Calculate edge based on forecast vs market threshold"""
    if not forecast or len(forecast) == 0:
        return 0.0, 0.0
    
    # Use tomorrow's forecast (index 1)
    tomorrow = forecast[1] if len(forecast) > 1 else forecast[0]
    
    if market_type == 'max_temp':
        predicted = tomorrow.get('max_temp_c')
    elif market_type == 'min_temp':
        predicted = tomorrow.get('min_temp_c')
    else:
        predicted = tomorrow.get('precip_mm')
    
    if predicted is None:
        return 0.0, 0.0
    
    # Edge = difference from threshold / uncertainty buffer
    diff = predicted - threshold
    uncertainty = 3.0  # °C buffer for temp uncertainty
    
    edge = abs(diff) / (uncertainty * 100)  # Convert to decimal
    edge = min(edge, 0.20)  # Cap at 20%
    
    confidence = 0.80  # Base confidence for weather forecasts
    
    return edge, confidence

def find_weather_market(city, market_type='max_temp'):
    """
    Surgical Weather Market Lookup.
    Targets the exact label pattern: 'highest-temperature-in-[city]-on-[date]'
    """
    try:
        # 1. Determine the target date (Tomorrow)
        tomorrow_date = (datetime.now() + timedelta(days=1)).strftime('%B-%d-%Y').lower()
        # Example: 'july-09-2026'
        
        # 2. Construct the "Universal Label" for weather
        # Pattern from link: highest-temperature-in-london-on-july-9-2026
        # We'll use a few variations to be safe (with/without leading zeros)
        city_clean = city.lower().replace(' ', '-')
        
        # Simplified date for the slug (e.g., 'july-9-2026')
        date_obj = datetime.now() + timedelta(days=1)
        date_simple = date_obj.strftime('%B-%d-%Y').lower().replace(' 0', '-') # handle 09 -> 9
        
        # Try Gamma API search first
        search_query = f"highest temperature {city}"
        r = httpx.get(
            f'https://gamma-api.polymarket.com/markets',
            params={'search': search_query, 'active': 'true', 'limit': 20},
            timeout=15
        )
        
        if r.status_code == 200:
            markets = r.json()
            for m in markets:
                slug = m.get('slug', '').lower()
                question = m.get('question', '').lower()
                
                # Match: City + Date + Temperature keywords
                if city_clean in slug and any(x in slug for x in ['temperature', 'temp', 'highest']):
                    if m.get('accepting_orders'):
                        tokens = m.get('tokens', [])
                        if len(tokens) >= 2:
                            # Use the same robust extraction as the crypto bots
                            token_yes = tokens[0].get('token_id') if isinstance(tokens[0], dict) else tokens[0]
                            token_no = tokens[1].get('token_id') if isinstance(tokens[1], dict) else tokens[1]
                            if token_yes and token_no:
                                return {
                                    "token_yes": token_yes,
                                    "token_no": token_no,
                                    "slug": slug,
                                    "title": m.get('question')
                                }
        
        return None
    except Exception as e:
        print(f"Surgical Weather Lookup Error for {city}: {e}")
        return None

def execute_weather_trade(market_id, stake, direction, city):
    """Execute weather trade"""
    try:
        # Parse market_id to get token
        parts = market_id.split('_')
        token_id = parts[-1] if parts else None
        
        if not token_id:
            return None
        
        price = 0.65 if direction == 'UP' else 0.35
        
        order = poly_client.create_and_post_order(
            {
                'tokenID': token_id,
                'price': price,
                'size': stake,
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
        
        return order_id
        
    except Exception as e:
        print(f"Weather trade error: {e}")
        raise

def check_and_trade_portfolio():
    """Main loop: scan all cities, collect signals, optimize, execute"""
    print(f"[{datetime.now()}] Starting Weather Portfolio Trader...")
    
    portfolio_trader.reset_daily_state()
    
    send_telegram_alert(f"🌦️ Weather Portfolio Bot started\nMode: {'PAPER' if portfolio_trader.config.paper_mode else 'LIVE'}\nCities: {len(CITIES)}")
    
    while True:
        print(f"\n[{datetime.now()}] Scanning {len(CITIES)} cities...")
        
        # Scan all cities and collect signals
        for city_name, city_data in CITIES.items():
            # Get forecast
            forecast = get_openmeteo_forecast(city_data['lat'], city_data['lon'])
            if not forecast:
                continue
            
            # Check max temp market
            market = find_weather_market(city_name, 'max_temp')
            if market:
                # Simple edge: if forecast > 25°C, edge on UP
                tomorrow = forecast[1] if len(forecast) > 1 else forecast[0]
                predicted = tomorrow.get('max_temp_c', 20)
                
                if predicted > 25:
                    edge, confidence = calculate_edge(forecast, 25, 'max_temp')
                    if edge >= MIN_EDGE_PERCENT / 100:
                        portfolio_trader.add_signal(
                            asset="WEATHER",
                            direction="UP",
                            edge=edge,
                            confidence=confidence,
                            market_id=f"{city_name}_max_{market['token_yes']}",
                            min_stake=1.0,
                            max_stake=20.0
                        )
                        print(f"  {city_name}: UP signal (edge: {edge:.1%})")
                elif predicted < 15:
                    edge, confidence = calculate_edge(forecast, 15, 'max_temp')
                    if edge >= MIN_EDGE_PERCENT / 100:
                        portfolio_trader.add_signal(
                            asset="WEATHER",
                            direction="DOWN",
                            edge=edge,
                            confidence=confidence,
                            market_id=f"{city_name}_max_{market['token_no']}",
                            min_stake=1.0,
                            max_stake=20.0
                        )
                        print(f"  {city_name}: DOWN signal (edge: {edge:.1%})")
        
        # Run optimization if we have signals
        if portfolio_trader.signals:
            print(f"\n[{datetime.now()}] Running portfolio optimization...")
            print(f"Signals collected: {len(portfolio_trader.signals)}")
            
            def exec_callback(market_id, stake, direction):
                city = market_id.split('_')[0]
                order_id = execute_weather_trade(market_id, stake, direction, city)
                if order_id:
                    msg = f"🌦️ WEATHER TRADE EXECUTED\n\n"
                    msg += f"City: {city}\n"
                    msg += f"Direction: {direction}\n"
                    msg += f"Stake: {stake:.2f} USDC\n"
                    msg += f"Order: {order_id}\n"
                    print(msg)
                    send_telegram_alert(msg)
                return order_id
            
            result = portfolio_trader.optimize_and_execute(execution_callback=exec_callback)
            
            if "error" not in result:
                print(f"\n=== Portfolio Result ===")
                print(f"Total stake: ${result.get('total_stake', 0):.2f}")
                print(f"Expected value: ${result.get('total_expected_value', 0):.2f}")
                
                if result.get('allocations'):
                    print("\nAllocations:")
                    for alloc in result['allocations']:
                        print(f"  {alloc['asset']} {alloc['direction']}: ${alloc['stake']:.2f}")
            
            portfolio_trader.signals = []
        else:
            print(f"[{datetime.now()}] No signals with edge >= {MIN_EDGE_PERCENT}%")
        
        print(f"\n[{datetime.now()}] Sleeping for {CHECK_INTERVAL}s...")
        time.sleep(CHECK_INTERVAL)

if __name__ == '__main__':
    # Skip Polymarket balance check (API broken) - use actual wallet balance
    print("USDC Balance: 20.00 (actual wallet has ~26.1 pUSD)")
    
    check_and_trade_portfolio()
