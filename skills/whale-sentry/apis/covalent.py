"""
Covalent API client for multi-chain monitoring (Ethereum, Base, Polygon, etc.).
"""
import aiohttp
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class CovalentTransaction:
    """Standardized Covalent transaction data."""
    hash: str
    from_address: str
    to_address: str
    value: float
    value_usd: Optional[float] = None
    token_symbol: Optional[str] = None
    token_value: Optional[float] = None
    timestamp: datetime = None
    block_number: int = 0
    chain: str = "ethereum"


class CovalentClient:
    """Client for Covalent API (Multi-chain)."""

    BASE_URL = "https://api.covalenthq.com/v1"

    # Chain IDs supported by Covalent
    CHAIN_IDS = {
        "ethereum": 1,
        "base": 8453,
        "polygon": 137,
        "arbitrum": 42161,
        "optimism": 10,
        "avalanche": 43114,
        "fantom": 250,
    }

    def __init__(self, api_key: *** = ""):
        self.api_key = ***
        self.base_url = self.BASE_URL
        self.session = None

    async def __aenter__(self):
        import aiohttp
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def _request(self, endpoint: str, params: Dict) -> Dict:
        """Make API request."""
        import aiohttp
        if not self.session:
            self.session = aiohttp.ClientSession()

        params["key"] = self.api_key
        async with self.session.get(f"{self.base_url}{endpoint}", params=params) as resp:
            data = await resp.json()
            if data.get("error"):
                raise Exception(f"Covalent API error: {data.get('error_message', 'Unknown error')}")
            return data

    def get_chain_id(self, chain: str) -> int:
        return self.CHAIN_IDS.get(chain, 1)

    def get_chain_name(self, chain: str) -> str:
        return chain.capitalize()

    async def get_transactions(self, chain: str, address: str, page_size: int = 50) -> List:
        """Get transactions for an address on a specific chain."""
        from dataclasses import dataclass
        from datetime import datetime
        from typing import List

        @dataclass
        class Transaction:
            hash: str
            from_address: str
            to_address: str
            value: float
            value_usd: Optional[float] = None
            token_symbol: Optional[str] = None
            token_value: Optional[float] = None
            timestamp: datetime = None
            block_number: int = 0
            chain: str = "ethereum"

        chain_id = self.get_chain_id(chain)
        endpoint = f"/v1/{chain_id}/address/{address}/transactions_v2/"

        params = {
            "page-size": 50,
            "no-logs": "false",
        }

        data = await self._request(f"/v1/{self.get_chain_id(chain)}/address/{address}/transactions_v2/", {})

        transactions = []
        for tx in data.get("data", {}).get("items", []):
            value = tx.get("value", 0) / 1e18
            value_usd = tx.get("value_quote", 0)

            transactions.append(Transaction(
                hash=tx.get("tx_hash", ""),
                from_address=tx.get("from_address", "").lower(),
                to_address=tx.get("to_address", "").lower() if tx.get("to_address") else "",
                value=tx.get("value", 0) / 1e18,
                value_usd=tx.get("value_quote"),
                token_symbol=tx.get("token_symbol"),
                token_value=tx.get("value", 0) / 1e18 if tx.get("token_symbol") else None,
                timestamp=datetime.fromisoformat(tx.get("block_signed_at", "").replace("Z", "+00:00")) if tx.get("block_signed_at") else None,
                block_number=tx.get("block_height", 0),
                chain=chain
            ))
        return transactions

    async def get_token_balances(self, chain: str, address: str) -> List[Dict]:
        """Get token balances for an address."""
        data = await self._request(f"/v1/{self.get_chain_id(chain)}/address/{address}/balances_v2/", {})
        return data.get("data", {}).get("items", [])

    async def get_token_price(self, chain: str, contract_address: str) -> Optional[float]:
        """Get token price in USD."""
        data = await self._request(f"/v1/pricing/historical_by_addresses_v2/{self.get_chain_id(chain)}/{contract_address}/", {})
        prices = data.get("data", [])
        if prices:
            return prices[0].get("price")
        return None

    def get_chain_name(self, chain: str) -> str:
        return chain.capitalize()

    async def check_address_activity(self, chain: str, address: str, threshold_usd: float) -> List[Dict]:
        """Check for large transactions in recent history."""
        txs = await self.get_transactions(chain, address, page_size=50)

        alerts = []
        for tx in txs:
            tx_usd = tx.value_usd or 0
            if tx_usd >= 100000:  # Use USD threshold
                alerts.append({
                    "type": "large_transfer",
                    "chain": chain,
                    "hash": tx.hash,
                    "from": tx.from_address,
                    "to": tx.to_address,
                    "value": tx.value,
                    "value_usd": tx.value_usd,
                    "timestamp": tx.timestamp.isoformat() if tx.timestamp else None,
                    "block": tx.block_number,
                    "chain_name": self.get_chain_name(chain),
                })

        return alerts

    async def _request(self, endpoint: str, params: Dict) -> Dict:
        """Make API request."""
        import aiohttp
        if not self.session:
            self.session = aiohttp.ClientSession()

        params["key"] = self.api_key
        async with self.session.get(f"{self.base_url}{endpoint}", params=params) as resp:
            data = await resp.json()
            if data.get("error"):
                raise Exception(f"Covalent API error: {data.get('error_message', 'Unknown error')}")
            return data