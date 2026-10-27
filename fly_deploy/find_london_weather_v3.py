import httpx
import json

GAMMA_API = 'https://gamma-api.polymarket.com'
HEADERS = {'User-Agent': 'Mozilla/5.0'}

def find_london_weather():
    # Try searching for just 'temperature' to get a broader list
    search_term = 'temperature'
    print(f"Searching for: {search_term}...")
    
    # We'll fetch multiple pages or a large limit if possible
    r = httpx.get(
        f'{GAMMA_API}/markets',
        params={'search': search_term, 'active': 'true', 'limit': 100},
        headers=HEADERS
    )
    markets = r.json()
    
    if not isinstance(markets, list):
        print("Error: API did not return a list")
        return

    london_june_1 = []
    for m in markets:
        q = m.get('question', '')
        if 'London' in q and 'June 1' in q:
            london_june_1.append({
                'question': q,
                'id': m.get('id'),
                'slug': m.get('slug'),
                'clobTokenIds': m.get('clobTokenIds'),
                'outcomePrices': m.get('outcomePrices')
            })
    
    if london_june_1:
        print(json.dumps(london_june_1, indent=2))
    else:
        print("No matching London June 1 markets found in top 100 results for 'temperature'.")

if __name__ == '__main__':
    find_london_weather()
