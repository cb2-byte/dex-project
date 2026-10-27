"""
Etherscan API client for Ethereum and Base chain monitoring.
"""
import aiohttp
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Transaction:
    """Standardized transaction data."""
    hash: str
    from_address: str
    to_address: str
    value: float  # in native currency (ETH)
    value_usd: Optional[float] = None
    token_symbol: Optional[str] = None
    token_value: Optional[float] = None
    timestamp: datetime = None
    block_number: int = 0
    chain: str = "ethereum"


class EtherscanClient:
    """Client for Etherscan API (Ethereum and Base)."""
    
    BASE_URLS = {
        "ethereum": "https://api.etherscan.io/api",
        "base": "https://api.basescan.org/api",
    }
    
    def __init__(self, api_key: str, chain: str = "ethereum"):
        self.api_key = api_key
        self.chain = chain
        self.base_url = self.BASE_URLS.get(chain, self.BASE_URLS["ethereum"])
        self.session = None
    
    async def __aenter__(self):
        import aiohttp
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def _request(self, params: Dict) -> Dict:
        """Make API request."""
        import aiohttp
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        params["apikey"] = self.api_key
        async with self.session.get(self.base_url, params=params) as resp:
            data = await resp.json()
            if data.get("status") == "0" and data.get("message") != "No transactions found":
                raise Exception(f"Etherscan API error: {data.get('result')}")
            return data
    
    async def get_normal_transactions(self, address: str, start_block: int = 0, 
                                      end_block: int = 99999999, page: int = 1, 
                                      offset: int = 50, sort: str = "desc") -> List:
        """Get normal transactions for an address."""
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
        
        params = {
            "module": "account",
            "action": "txlist",
            "address": address,
            "startblock": start_block,
            "endblock": end_block,
            "page": page,
            "offset": offset,
            "sort": sort,
        }
        data = await self._request(params)
        
        transactions = []
        for tx in data.get("result", []):
            value_eth = int(tx["value"]) / 1e18
            transactions.append(Transaction(
                hash=tx["hash"],
                from_address=tx["from"].lower(),
                to_address=tx["to"].lower() if tx["to"] else "",
                value=value_eth,
                timestamp=datetime.fromtimestamp(int(tx["timeStamp"])),
                block_number=int(tx["blockNumber"]),
                chain=self.chain
            ))
        return transactions
    
    async def _request(self, params: Dict) -> Dict:
        """Make API request."""
        import aiohttp
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        params["apikey"] = self.api_key
        async with self.session.get(self.base_url, params=params) as resp:
            data = await resp.json()
            if data.get("status") == "0" and data.get("message") != "No transactions found":
                raise Exception(f"Etherscan API error: {data.get('result')}")
            return data
    
    async def get_normal_transactions(self, address: str, start_block: int = 0, 
                                      end_block: int = 99999999, page: int = 1, 
                                      offset: int = 50, sort: str = "desc") -> List:
        """Get normal transactions for an address."""
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
        
        params = {
            "module": "account",
            "action": "txlist",
            "address": address,
            "startblock": start_block,
            "endblock": end_block,
            "page": page,
            "offset": offset,
            "sort": sort,
        }
        data = await self._request(params)
        
        transactions = []
        for tx in data.get("result", []):
            value_eth = int(tx["value"]) / 1e18
            transactions.append(Transaction(
                hash=tx["hash"],
                from_address=tx["from"].lower(),
                to_address=tx["to"].lower() if tx["to"] else "",
                value=value_eth,
                timestamp=datetime.fromtimestamp(int(tx["timeStamp"])),
                block_number=int(tx["blockNumber"]),
                chain=self.chain
            ))
        return transactions
    
    async def get_token_transfers(self, address: str, page: int = 1, 
                                  offset: int = 50, sort: str = "desc") -> List:
        """Get ERC-20 token transfers for an address."""
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
        
        params = {
            "module": "account",
            "action": "tokentx",
            "address": address,
            "page": page,
            "offset": offset,
            "sort": "desc",
        }
        data = await self._request(params)
        
        transactions = []
        for tx in data.get("result", []):
            value = int(tx["value"]) / (10 ** int(tx.get("tokenDecimal", 18)))
            transactions.append(Transaction(
                hash=tx["hash"],
                from_address=tx["from"].lower(),
                to_address=tx["to"].lower() if tx["to"] else "",
                value=0.0,
                value_usd=None,
                token_symbol=tx.get("tokenSymbol", ""),
                token_value=value,
                timestamp=datetime.fromtimestamp(int(tx["timeStamp"])),
                block_number=int(tx["blockNumber"]),
                chain=self.chain
            ))
        return transactions
    
    async def get_eth_balance(self, address: str) -> float:
        params = {
            "module": "account",
            "action": "balance",
            "address": address,
            "tag": "latest",
        }
        data = await self._request(params)
        return int(data.get("result", "0")) / 1e18
    
    async def get_latest_block(self) -> int:
        params = {
            "module": "proxy",
            "action": "eth_blockNumber",
        }
        data = await self._request(params)
        return int(data.get("result", "0x0"), 16)
    
    def get_chain_name(self) -> str:
        return "Base" if self.chain == "base" else "Ethereum"
    
    async def check_address_activity(self, address: str, threshold_eth: float, 
                                     threshold_usd: float, eth_price_usd: float) -> List[Dict]:
        """Check for large transactions in recent history."""
        txs = await self.get_normal_transactions(address, offset=50)
        
        alerts = []
        for tx in txs:
            tx_usd = tx.value * eth_price_usd
            if tx.value >= threshold_eth or tx_usd >= threshold_usd:
                alerts.append({
                    "type": "large_transfer",
                    "chain": self.chain,
                    "hash": tx.hash,
                    "from": tx.from_address,
                    "to": tx.to_address,
                    "value_eth": tx.value,
                    "value_usd": tx_usd,
                    "timestamp": tx.timestamp.isoformat() if tx.timestamp else None,
                    "block": tx.block_number,
                    "chain_name": self.get_chain_name(),
                })
        
        return alerts
    
    async def _request(self, params: Dict) -> Dict:
        import aiohttp
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        params["apikey"] = self.api_key
        async with self.session.get(self.base_url, params=params) as resp:
            data = await resp.json()
            if data.get("status") == "0" and data.get("message") != "No transactions found":
                raise Exception(f"Etherscan API error: {data.get('result')}")
            return data