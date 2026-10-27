import httpx
import json
import os
from datetime import datetime

GAMMA_API = 'https://gamma-api.polymarket.com'
SNAPSHOT_FILE = 'discovery_snapshot.json'
LOG_FILE = 'discovery_log.json'
HEADERS = {'User-Agent': 'Mozilla/5.0'}

def fetch_active_markets():
    try:
        # Fetch a larger page of active markets to increase discovery chance
        r = httpx.get(f'{GAMMA_API}/markets', params={'active': 'true', 'limit': 1000}, headers=HEADERS, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f'Error fetching markets: {e}')
        return []

def load_snapshot():
    if os.path.exists(SNAPSHOT_FILE):
        with open(SNAPSHOT_FILE, 'r') as f:
            try:
                return set(json.load(f))
            except:
                return set()
    return set()

def save_snapshot(ids):
    with open(SNAPSHOT_FILE, 'w') as f:
        json.dump(list(ids), f)

def log_new_markets(new_markets):
    timestamp = datetime.utcnow().isoformat()
    entries = []
    for m in new_markets:
        entry = {
            'timestamp': timestamp,
            'id': m.get('id'),
            'conditionId': m.get('conditionId'),
            'question': m.get('question'),
            'slug': m.get('slug'),
            'active': m.get('active')
        }
        entries.append(entry)
    
    existing_logs = []
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r') as f:
            try: existing_logs = json.load(f)
            except: pass
            
    existing_logs.extend(entries)
    with open(LOG_FILE, 'w') as f:
        json.dump(existing_logs, f, indent=2)
    return entries

def main():
    current_markets = fetch_active_markets()
    if not current_markets:
        return

    current_ids = {m.get('id') for m in current_markets if m.get('id')}
    previous_ids = load_snapshot()
    
    new_ids = current_ids - previous_ids
    
    if new_ids:
        new_markets = [m for m in current_markets if m.get('id') in new_ids]
        logged = log_new_markets(new_markets)
        
        # Filter for anything that looks like a window/price event for the user
        interesting = [m for m in logged if any(k in (m['question'] or '').lower() or (m['slug'] or '').lower() for k in ['btc', 'eth', 'sol', 'link', 'price', 'updown', 'up or down', '5m', 'arbitrage', 'resolution'])]
        if interesting:
            print(f'SENSING TARGETS! Found {len(interesting)} candidates.')
            print(json.dumps(interesting, indent=2))
    
    save_snapshot(current_ids)

if __name__ == '__main__':
    main()
