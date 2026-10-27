import json
import os
from types import SimpleNamespace
from py_clob_client_v2 import ClobClient, OrderArgsV2
import httpx

# Load keys
KEYS_FILE = os.path.join(os.path.dirname(__file__), '.polymarket-keys.json')
with open(KEYS_FILE) as f:
    keys = json.load(f)

creds = SimpleNamespace(api_key=keys['apiKey'], api_secret=keys['secret'], api_passphrase=keys['passphrase'])

# Using the verified credentials from the BTC trader
client = ClobClient(
    host='https://clob.polymarket.com',
    chain_id=137,
    key='0xd2aad0f4a95a4e2b8d5090613fb95c278fcddb506616096d49df5d4c39859a3b',
    creds=creds,
    signature_type=1,
    funder='0x98D9Dbd34d0156E6385D08d5263467601BE5e972'
)

def get_token_id_by_slug(slug, outcome='YES'):
    try:
        r = httpx.get(f'https://gamma-api.polymarket.com/events?slug={slug}', timeout=10)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list) and len(data) > 0:
                event = data[0]
                markets = event.get('markets', [])
                if markets:
                    m = markets[0]
                    clob_ids = m.get('clobTokenIds', [])
                    if len(clob_ids) >= 2:
                        return clob_ids[0] if outcome == 'YES' else clob_ids[1]
    except Exception as e:
        print(f"Error finding token for {slug}: {e}")
    return None

def place_bet(slug, amount, price, outcome='YES'):
    token_id = get_token_id_by_slug(slug, outcome)
    if not token_id:
        print(f"Could not find token for {slug} ({outcome})")
        return None

    print(f"Placing bet on {slug} {outcome} (Token: {token_id}) for ${amount} at {price}...")
    try:
        order_args = OrderArgsV2(
            token_id=token_id,
            price=price,
            size=amount,
            side='BUY'
        )
        result = client.create_and_post_order(order_args, {})
        print(f"Success! Order ID: {result}")
        return result
    except Exception as e:
        print(f"Failed to place bet on {slug}: {e}")
        return None

if __name__ == "__main__":
    # England: Bet on NO (they won't win)
    # Current NO price is ~0.90
    place_bet("will-england-win-the-2026-fifa-world-cup-937", 2.0, 0.91, outcome='NO')
    
    # Algeria: Bet on YES (the chaos play)
    # Current YES price is ~0.07
    place_bet("will-algeria-reach-the-quarterfinals-at-the-2026-fifa-world-cup-20260602145134505", 2.0, 0.08, outcome='YES')
