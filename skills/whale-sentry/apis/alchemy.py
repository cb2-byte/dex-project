"""
Alchemy API client for Ethereum and Base chain monitoring (enhanced features).
"""
import aiohttp
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class AlchemyTransaction:
    """Standardized Alchemy transaction data."""
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


class AlchemyClient:
    """Client for Alchemy API (Ethereum and Base) - enhanced features."""

    BASE_URLS = {
        "ethereum": "https://eth-mainnet.g.alchemy.com/v2",
        "base": "https://base-mainnet.g.alchemy.com/v2",
    }

    def __init__(self, api_key: *** = "", chain: str = "ethereum"):
        self.api_key = ***
        self.chain = chain
        self.base_url = f"{self.BASE_URLS.get(chain, self.BASE_URLS['ethereum'])}/{api_key}"
        self.session = None

    async def __aenter__(self):
        import aiohttp
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def _request(self, method: str, params: List) -> Dict:
        """Make JSON-RPC request."""
        import aiohttp
        if not self.session:
            self.session = aiohttp.ClientSession()

        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": 1,
        }
        async with self.session.post(self.base_url, json=payload) as resp:
            data = await resp.json()
            if data.get("error"):
                raise Exception(f"Alchemy API error: {data.get('error', {}).get('message', 'Unknown error')}")
            return data

    async def get_asset_transfers(self, address: str, from_block: str = "0x0",
                                  to_block: str = "latest",
                                  category: List[str] = None) -> List:
        """Get asset transfers for an address (enhanced with metadata)."""
        from dataclasses import dataclass
        from datetime import datetime
        from typing import List, Optional

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

        if category is None:
            category = ["erc20", "erc721", "erc1155", "external", "internal"]

        params = [
            {
                "fromAddress": address,
                "category": category,
                "fromBlock": from_block,
                "toBlock": to_block,
                "withMetadata": True,
                "excludeZeroValue": True,
            }
        ]

        data = await self._request("alchemy_getAssetTransfers", params)

        transactions = []
        for tx in data.get("result", {}).get("transfers", []):
            value = 0.0
            value_usd = None
            token_symbol = None

            if tx.get("value"):
                value = float(tx["value"])
            if tx.get("valueUsd") is not None:
                value_usd = float(tx["value"])
            if tx.get("tokenSymbol"):
                token_symbol = tx["tokenSymbol"]

            transactions.append(Transaction(
                hash=tx.get("hash", ""),
                from_address=tx.get("from", "").lower(),
                to_address=tx.get("to", "").lower() if tx.get("to") else "",
                value=tx.get("value", 0.0),
                value_usd=tx.get("value", 0.0),
                token_symbol=tx.get("tokenSymbol"),
                token_value=tx.get("value", 0.0) if tx.get("tokenSymbol") else None,
                timestamp=datetime.fromisoformat(tx.get("blockTimestamp", "").replace("Z", "+00:00")) if tx.get("blockTimestamp") else None,
                block_number=int(tx.get("blockNum", "0x0"), 16),
                chain="ethereum"
            ))
        return transactions

    async def get_token_balances(self, address: str) -> List[Dict]:
        """Get token balances for an address."""
        data = await self._request("alchemy_getTokenBalances", ["latest", "erc20"])
        return data.get("result", {}).get("tokenBalances", [])

    async def get_token_metadata(self, contract_address: str) -> Dict:
        """Get token metadata."""
        data = await self._request("alchemy_getTokenMetadata", ["latest", "erc20"])
        return data.get("result", {})

    async def get_nfts(self, address: str) -> List[Dict]:
        """Get NFTs owned by an address."""
        data = await self._request("alchemy_getNfts", [{"owner": address}])
        return data.get("result", {}).get("ownedNfts", [])

    async def get_gas_price(self) -> int:
        """Get current gas price in wei."""
        data = await self._request("eth_gasPrice", [])
        return int(data.get("result", "0x0"), 16)

    async def get_latest_block(self) -> int:
        """Get latest block number."""
        data = await self._request("eth_blockNumber", [])
        return int(data.get("result", "0x0"), 16)

    def get_chain_name(self) -> str:
        return "Ethereum"

    async def check_address_activity(self, address: str, threshold_usd: float, eth_price_usd: float) -> List[Dict]:
        """Check for large transactions in recent history."""
        txs = await self.get_asset_transfers(address)

        alerts = []
        for tx in txs:
            tx_usd = tx.value_usd or 0
            if tx_usd >= 100000:  # Use USD threshold
                alerts.append({
                    "type": "large_transfer",
                    "chain": "ethereum",
                    "hash": tx.hash,
                    "from": tx.from_address,
                    "to": tx.to_address,
                    "value": tx.value,
                    "value_usd": tx.value_usd,
                    "timestamp": tx.timestamp.isoformat() if tx.timestamp else None,
                    "block": tx.block_number,
                    "chain_name": "Ethereum",
                })

        return alerts

    async def _request(self, method: str, params: List) -> Dict:
        """Make JSON-RPC request."""
        import aiohttp
        if not self.session:
            self.session = aiohttp.ClientSession()

        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": 1,
        }
        async with self.session.post(self.base_url, json=payload) as resp:
            data = await resp.json()
            if data.get("error"):
                raise Exception(f"Alchemy API error: {data.get('error', {}).get('message', 'Unknown error')}")
            return data