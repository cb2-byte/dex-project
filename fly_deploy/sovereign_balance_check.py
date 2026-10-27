import os
import asyncio
import httpx
import json
from dotenv import load_dotenv
from py_clob_client.client import ClobClient

async def check_truth():
    load_dotenv()
    pk = os.getenv("POLY_PRIVATE_KEY")
    funder = os.getenv("POLY_FUNDER_ADDRESS")
    
    if not pk or not funder:
        print("Error: Credentials missing")
        return

    if pk.startswith("0x"):
        pk = pk[2:]

    try:
        client = ClobClient(
            host="https://clob.polymarket.com",
            key=pk,
            chain_id=137,
            signature_type=1,
            funder=funder
        )
        # Use the actual client method to fetch balance
        balance = client.get_balance()
        print(f"Sovereign Balance Report for {funder}:")
        print(json.dumps(balance, indent=2))
    except Exception as e:
        print(f"Critical Failure during truth-check: {e}")

if __name__ == "__main__":
    asyncio.run(check_truth())
