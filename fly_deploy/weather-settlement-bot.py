#!/usr/bin/env python3
"""
Polymarket Weather Settlement Bot
Auto-settles weather markets using official resolution sources
"""

import requests
import time
import json
import os
from datetime import datetime, timedelta
from types import SimpleNamespace
from bs4 import BeautifulSoup

# Load API keys
KEYS_FILE = os.path.join(os.path.dirname(__file__), '.weather-keys.json')
with open(KEYS_FILE) as f:
    weather_keys = json.load(f)

WU_API_KEY = weather_keys.get('api_key', '')
STATION_ID = weather_keys.get('station_id', '')

# Trading config
CHECK_INTERVAL = 300  # Check every 5 minutes

# Resolution source mapping for each city
RESOLUTION_SOURCES = {
    "London": {
        "source": "wunderground",
        "station": "EGLC",  # London City Airport
        "wunderground_path": "gb/london/EGLC",
        "units": "C"
    },
    "New York": {
        "source": "wunderground",
        "station": "KLGA",  # LaGuardia
        "wunderground_path": "us/ny/new-york/KLGA",
        "units": "C"
    },
    "Tokyo": {
        "source": "wunderground",
        "station": "RJTT",  # Haneda
        "wunderground_path": "jp/tokyo/RJTT",
        "units": "C"
    },
    "Singapore": {
        "source": "wunderground",
        "station": "WSSS",  # Changi
        "wunderground_path": "sg/singapore/WSSS",
        "units": "C"
    },
    "Sydney": {
        "source": "wunderground",
        "station": "YSSY",  # Kingsford Smith
        "wunderground_path": "au/nsw/sydney/YSSY",
        "units": "C"
    },
    "Dubai": {
        "source": "wunderground",
        "station": "OMDB",  # DXB
        "wunderground_path": "ae/dubai/OMDB",
        "units": "C"
    },
    "Frankfurt": {
        "source": "wunderground",
        "station": "EDDF",  # FRA
        "wunderground_path": "de/frankfurt/EDDF",
        "units": "C"
    },
    "Paris": {
        "source": "wunderground",
        "station": "LFPG",  # Charles de Gaulle
        "wunderground_path": "fr/paris/LFPG",
        "units": "C"
    },
    "Hong Kong": {
        "source": "hko",  # Hong Kong Observatory
        "station": "HKO",
        "url": "https://www.weather.gov.hk/en/cis/climat.htm",
        "units": "C"
    }
}

def send_telegram_alert(message):
    try:
        token = '8527377021:AAFfUppTGj8EU8v4GBtMztAoOVbYVKNcQ4s'
        chat_id = '868123037'
        url = f'https://api.telegram.org/bot{token}/sendMessage'
        requests.post(url, json={'chat_id': chat_id, 'text': message})
    except Exception as e:
        print(f"Telegram error: {e}")

def get_wunderground_high_temp(station_path, date_str):
    """
    Scrape daily high temp from Wunderground history page
    date_str: YYYY-MM-DD format
    """
    try:
        url = f"https://www.wunderground.com/history/daily/{station_path}/date/{date_str}"
        headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}
        resp = requests.get(url, headers=headers, timeout=15)
        
        if resp.status_code != 200:
            print(f"WU API error: {resp.status_code}")
            return None
        
        # Parse HTML for high temperature
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Look for the high temperature value
        # Wunderground uses specific classes for temp data
        temp_element = soup.find('div', {'class': 'ng-star-inserted'})
        if temp_element:
            # Extract temperature value
            temp_text = temp_element.get_text(strip=True)
            # Parse out the number
            import re
            match = re.search(r'(\d+)', temp_text)
            if match:
                return int(match.group(1))
        
        # Fallback: try API
        if WU_API_KEY:
            api_url = f"https://api.wundergroundapi.com/v1/history/{date_str}/station/{station_path.split('/')[-1]}"
            api_resp = requests.get(api_url, params={'apiKey': WU_API_KEY}, timeout=10)
            if api_resp.status_code == 200:
                data = api_resp.json()
                # Extract max temp from response
                return data.get('max_temp')
        
        return None
        
    except Exception as e:
        print(f"WU scrape error: {e}")
        return None

def get_hko_high_temp(date_str):
    """
    Get daily high temp from Hong Kong Observatory
    """
    try:
        # HKO provides daily climate extracts
        url = "https://www.weather.gov.hk/en/cis/climat.htm"
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, headers=headers, timeout=15)
        
        if resp.status_code != 200:
            return None
        
        # Parse for the specific date's max temp
        soup = BeautifulSoup(resp.text, 'html.parser')
        # HKO tables contain daily max temps
        # This is simplified - actual implementation would parse the specific date
        temp_element = soup.find('td', string=lambda t: t and date_str in t)
        if temp_element:
            # Extract temp from table row
            return int(temp_element.get_text(strip=True))
        
        return None
        
    except Exception as e:
        print(f"HKO error: {e}")
        return None

def get_daily_high_temp(city, date_str):
    """
    Get daily high temperature for a city on a specific date
    Uses the official resolution source for each city
    """
    source_info = RESOLUTION_SOURCES.get(city)
    if not source_info:
        print(f"Unknown city: {city}")
        return None
    
    source = source_info['source']
    
    if source == 'wunderground':
        return get_wunderground_high_temp(source_info['wunderground_path'], date_str)
    elif source == 'hko':
        return get_hko_high_temp(date_str)
    else:
        print(f"Unknown source: {source}")
        return None

def check_settlement_opportunities():
    """
    Check for weather markets ready to settle
    """
    print(f"[{datetime.now()}] Checking weather settlement opportunities...")
    
    # Get yesterday's date (markets settle after day is complete)
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    settled_markets = []
    
    for city, source_info in RESOLUTION_SOURCES.items():
        try:
            high_temp = get_daily_high_temp(city, yesterday)
            
            if high_temp is not None:
                msg = f"🌤️ {city} Settlement Data\n"
                msg += f"Date: {yesterday}\n"
                msg += f"High Temp: {high_temp}°{source_info['units']}\n"
                msg += f"Source: {source_info['source'].upper()}"
                
                print(msg)
                settled_markets.append({
                    'city': city,
                    'date': yesterday,
                    'high_temp': high_temp,
                    'source': source_info['source']
                })
                
        except Exception as e:
            print(f"Error checking {city}: {e}")
    
    # Send summary alert
    if settled_markets:
        summary = f"🌤️ Weather Settlement Summary\n"
        summary += f"Date: {yesterday}\n\n"
        for m in settled_markets:
            summary += f"📍 {m['city']}: {m['high_temp']}°C ({m['source'].upper()})\n"
        
        print(summary)
        send_telegram_alert(summary)
    
    return settled_markets

def log_settlement_data(settlements):
    """
    Log settlement data to file for transparency
    """
    log_file = os.path.join(os.path.dirname(__file__), 'logs', 'weather-settlements.json')
    
    # Create logs directory if needed
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    # Load existing logs
    existing = []
    if os.path.exists(log_file):
        try:
            with open(log_file) as f:
                existing = json.load(f)
        except:
            existing = []
    
    # Add new settlements
    for s in settlements:
        s['logged_at'] = datetime.now().isoformat()
        existing.append(s)
    
    # Save
    with open(log_file, 'w') as f:
        json.dump(existing, f, indent=2)
    
    print(f"Logged {len(settlements)} settlements to {log_file}")

def run_bot():
    """
    Main bot loop
    """
    print(f"[{datetime.now()}] Starting Weather Settlement Bot...")
    send_telegram_alert("🌤️ Weather Settlement Bot started\nMonitoring Polymarket weather markets")
    
    # Initial check
    check_settlement_opportunities()
    
    # Run continuously
    while True:
        time.sleep(CHECK_INTERVAL)
        
        # Check if it's after midnight (new day settled)
        now = datetime.now()
        if now.hour == 1 and now.minute < 10:  # Check around 1 AM
            check_settlement_opportunities()

if __name__ == '__main__':
    run_bot()
