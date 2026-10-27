import os
import requests
from dotenv import load_dotenv

def get_balance():
    load_dotenv()
    wallet = os.getenv('POLY_FUNDER_ADDRESS')
    if not wallet:
        print("Error: POLY_FUNDER_ADDRESS not found in .env")
        return

    # High-fidelity browser headers to bypass Cloudflare
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://polygonscan.com/",
        "Origin": "https://polygonscan.com"
    }
    
    # USDC Contract on Polygon
    contract = "0x2791Bca1a2330218B6f3807C73561111E99C499d"
    url = f"https://api.polygonscan.com/api?module=account&action=tokbalance&contractaddress={contract}&address={wallet}&tag=latest"

    try:
        print(f"Sovereign Truth-Check: Querying chain for {wallet}...")
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        if data.get('status') == '1':
            raw_balance = int(data['result'])
            balance = raw_balance / 1e6
            print(f"\n✅ CHAIN CONFIRMED BALANCE: {balance:.2f} USDC")
        else:
            print(f"\n❌ API Error: {data.get('message', 'Unknown error')}")
            print(f"Raw Response: {data}")
            
    except Exception as e:
        print(f"\n❌ Critical Connection Failure: {e}")

if __name__ == "__main__":
    get_balance()
