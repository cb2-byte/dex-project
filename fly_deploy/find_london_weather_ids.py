import httpx
import json

GAMMA_API = 'https://gamma-api.polymarket.com'
HEADERS = {'User-Agent': 'Mozilla/5.0'}

def find_markets():
    search_terms = ['London temperature', 'highest temperature', 'June 1']
    all_results = []
    
    for term in search_terms:
        print(f"Searching for: {term}...")
        r = httpx.get(
            f'{GAMMA_API}/markets',
            params={'search': term, 'active': 'true', 'limit': 100},
            headers=HEADERS
        )
        markets = r.json()
        if isinstance(markets, list):
            all_results.extend(markets)
    
    # Remove duplicates by ID
    seen = set()
    unique_markets = []
    for m in all_results:
        mid = m.get('id')
        if mid and mid not in seen:
            seen.add(mid)
            unique_markets.append(m)
    
    final_results = []
    for m in unique_markets:
        question = m.get('question', '')
        if 'London' in question and 'June 1' in question:
            final_results.append({
                'question': question,
                'id': m.get('id'),
                'slug': m.get('slug'),
                'clobTokenIds': m.get('clobTokenIds'),
                'outcomePrices': m.get('outcomePrices')
            })
    
    print(json.dumps(final_results, indent=2))

if __name__ == '__main__':
    find_markets()
