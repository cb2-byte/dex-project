"""
Solana FM API client for Solana chain monitoring (alternative to Solscan).
"""
import aiohttp
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class SolanaFMTransaction:
    """Standardized Solana FM transaction data."""
    signature: str
    from_address: str
    to_address: str
    value: float  # in SOL
    value_usd: Optional[float] = None
    token_symbol: Optional[str] = None
    token_value: Optional[float] = None
    timestamp: datetime = None
    slot: int = 0
    chain: str = "solana"


class SolanaFMClient:
    """Client for Solana FM API (Solana)."""

    BASE_URL = "https://api.solana.fm"

    def __init__(self, api_key: str = ""):
        self.api_key = api_key
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

        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        async with self.session.get(f"{self.base_url}{endpoint}", params=params, headers=headers) as resp:
            data = await resp.json()
            if not data.get("success", True):
                raise Exception(f"Solana FM API error: {data.get('message', 'Unknown error')}")
            return data

    async def get_account_transactions(self, address: str, limit: int = 50) -> List:
        """Get transactions for a Solana address."""
        from dataclasses import dataclass
        from datetime import datetime
        from typing import List

        @dataclass
        class Transaction:
            signature: str
            from_address: str
            to_address: str
            value: float
            value_usd: Optional[float] = None
            token_symbol: Optional[str] = None
            token_value: Optional[float] = None
            timestamp: datetime = None
            slot: int = 0
            chain: str = "solana"

        params = {
            "account": address,
            "limit": limit,
        }
        data = await self._request(f"/v0/accounts/{address}/transactions".format(address=address), params)

        transactions = []
        for tx in data.get("result", {}).get("transactions", []):
            if tx.get("nativeTransfer"):
                value_sol = tx["nativeTransfer"]["amount"] / 1e9
                transactions.append(Transaction(
                    signature=tx.get("signature", ""),
                    from_address=tx["nativeTransfer"]["fromAddress"],
                    to_address=tx["nativeTransfer"]["toAddress"],
                    value=value_sol,
                    timestamp=datetime.fromtimestamp(tx.get("blockTime", 0)) if tx.get("blockTime") else None,
                    slot=tx.get("slot", 0),
                    chain="solana"
                ))
        return transactions

    async def get_token_transfers(self, address: str, limit: int = 50) -> List:
        """Get SPL token transfers for an address."""
        from dataclasses import dataclass
        from datetime import datetime
        from typing import List, Optional

        @dataclass
        class Transaction:
            signature: str
            from_address: str
            to_address: str
            value: float
            value_usd: Optional[float] = None
            token_symbol: Optional[str] = None
            token_value: Optional[float] = None
            timestamp: datetime = None
            slot: int = 0
            chain: str = "solana"

        params = {
            "account": address,
            "limit": limit,
        }
        data = await self._request(f"/v0/accounts/{address}/token-transfers".format(address=address), {})

        transactions = []
        for tx in data.get("result", {}).get("transfers", []):
            decimals = tx.get("token", {}).get("decimals", 9)
            value = tx.get("amount", 0) / (10 ** decimals)
            transactions.append(Transaction(
                signature=tx.get("signature", ""),
                from_address=tx.get("fromAddress", ""),
                to_address=tx.get("toAddress", ""),
                value=0.0,
                value_usd=None,
                token_symbol=tx.get("token", {}).get("symbol", ""),
                token_value=value,
                timestamp=datetime.fromtimestamp(tx.get("blockTime", 0)) if tx.get("blockTime") else None,
                slot=tx.get("slot", 0),
                chain="solana"
            ))
        return transactions

    async def get_sol_balance(self, address: str) -> float:
        """Get SOL balance for an address."""
        data = await self._request(f"/v0/accounts/{address}/tokens", {})
        for token in data.get("result", {}).get("tokens", []):
            if token.get("mint") == "So11111111111111111111111111111111111111112":
                return token.get("amount", 0) / 1e9
        return 0.0

    def get_chain_name(self) -> str:
        return "Solana"

    async def check_address_activity(self, address: str, threshold_sol: float,
                                     threshold_usd: float, sol_price_usd: float) -> List[Dict]:
        """Check for large transactions in recent history."""
        txs = await self.get_account_transactions(address, limit=50)

        alerts = []
        for tx in txs:
            tx_usd = tx.value * sol_price_usd
            if tx.value >= threshold_sol or tx_usd >= threshold_usd:
                alerts.append({
                    "type": "large_transfer",
                    "chain": "solana",
                    "hash": tx.signature,
                    "from": tx.from_address,
                    "to": tx.to_address,
                    "value_sol": tx.value,
                    "value_usd": tx_usd,
                    "timestamp": tx.timestamp.isoformat() if tx.timestamp else None,
                    "slot": tx.slot,
                    "chain_name": self.get_chain_name(),
                })

        return alerts

    async def _request(self, endpoint: str, params: Dict) -> Dict:
        """Make API request."""
        import aiohttp
        if not self.session:
            self.session = aiohttp.ClientSession()

        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        async with self.session.get(f"{self.base_url}{endpoint}", params=params, headers=headers) as resp:
            data = await resp.json()
            if not data.get("success", True):
                raise Exception(f"Solana FM API error: {data.get('message', 'Unknown error')}")
            return data