"""
Live Execution Adapter
======================
Connects paper_engine strategies to real Solana DEX endpoints (Jupiter, Raydium, Orca).
Provides a unified interface for executing trades on Solana mainnet.
"""

from __future__ import annotations
import asyncio
import time
import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Literal
from enum import Enum
from decimal import Decimal
from abc import ABC, abstractmethod

import aiohttp
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.transaction import VersionedTransaction
from solders.message import MessageV0
from solders.hash import Hash

from paper_engine.config import PaperConfig
from paper_engine.market_data import PriceQuote
from paper_engine.execution import PaperExecutionEngine, NetReturnResult
from paper_engine.boundaries import get_boundary, assert_paper_mode


class DEXProvider(Enum):
    """Supported DEX providers."""
    JUPITER = "jupiter"
    RAYDIUM = "raydium"
    ORCA = "orca"
    PHOENIX = "phoenix"


class OrderType(Enum):
    """Order types."""
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"


class OrderSide(Enum):
    """Order sides."""
    BUY = "buy"
    SELL = "sell"


class OrderStatus(Enum):
    """Order status."""
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass
class LiveOrder:
    """Live order representation."""
    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    amount: Decimal  # Base token amount
    price: Optional[Decimal] = None  # For limit orders
    stop_price: Optional[Decimal] = None  # For stop orders
    status: OrderStatus = OrderStatus.PENDING
    filled_amount: Decimal = Decimal("0")
    avg_fill_price: Optional[Decimal] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    signature: Optional[str] = None
    error: Optional[str] = None
    retry_count: int = 0
    metadata: Dict = field(default_factory=dict)


@dataclass
class SwapQuote:
    """DEX swap quote."""
    input_mint: str
    output_mint: str
    input_amount: Decimal
    output_amount: Decimal
    price_impact: float
    fee: Decimal
    route: List[Dict]
    dex: DEXProvider
    expires_at: float


class DEXClient(ABC):
    """Abstract DEX client interface."""

    @abstractmethod
    async def get_quote(
        self,
        input_mint: str,
        output_mint: str,
        amount: Decimal,
        slippage_bps: int = 50,
    ) -> SwapQuote:
        """Get swap quote."""

    @abstractmethod
    async def build_swap_transaction(
        self,
        quote: SwapQuote,
        user_pubkey: Pubkey,
        slippage_bps: int = 50,
    ) -> VersionedTransaction:
        """Build swap transaction."""

    @abstractmethod
    async def submit_transaction(
        self,
        transaction: VersionedTransaction,
    ) -> str:
        """Submit transaction and return signature."""

    @abstractmethod
    async def get_transaction_status(
        self,
        signature: str,
    ) -> Dict[str, Any]:
        """Get transaction status."""


class JupiterClient(DEXClient):
    """Jupiter Aggregator API client."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://quote-api.jup.ag/v6",
        session: Optional[aiohttp.ClientSession] = None,
    ):
        self.base_url = base_url
        self.api_key = api_key
        self._session = session
        self._owns_session = session is None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "pennyshield/1.0",
                }
            )
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def get_quote(
        self,
        input_mint: str,
        output_mint: str,
        amount: Decimal,
        slippage_bps: int = 50,
    ) -> SwapQuote:
        session = await self._get_session()
        params = {
            "inputMint": input_mint,
            "outputMint": output_mint,
            "amount": str(int(amount * Decimal(10**9))),  # Convert to lamports
            "slippageBps": slippage_bps,
            "onlyDirectRoutes": "false",
            "asLegacyTransaction": "false",
        }

        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        async with session.get(
            f"{self.base_url}/quote",
            params=params,
            headers=headers,
        ) as resp:
            if resp.status != 200:
                raise Exception(f"Jupiter quote failed: {resp.status} - {await resp.text()}")
            data = await resp.json()

        return SwapQuote(
            input_mint=input_mint,
            output_mint=output_mint,
            input_amount=amount,
            output_amount=Decimal(str(data["outAmount"])) / Decimal(10**9),
            price_impact=float(data.get("priceImpactPct", 0)),
            fee=Decimal(str(data.get("swapFee", 0))) / Decimal(10**9),
            route=data.get("routePlan", []),
            dex=DEXProvider.JUPITER,
            expires_at=time.time() + 30,
        )

    async def build_swap_transaction(
        self,
        quote: SwapQuote,
        user_pubkey: Pubkey,
        slippage_bps: int = 50,
    ) -> VersionedTransaction:
        session = await self._get_session()

        # Get the quote again to get the swap transaction
        params = {
            "inputMint": quote.input_mint,
            "outputMint": quote.output_mint,
            "amount": str(int(quote.input_amount * Decimal(10**9))),
            "slippageBps": slippage_bps,
            "userPublicKey": str(user_pubkey),
            "wrapAndUnwrapSol": "true",
            "dynamicComputeUnitLimit": "true",
            "prioritizationFeeLamports": "auto",
        }

        async with session.post(
            f"{self.base_url}/swap",
            json=params,
        ) as resp:
            if resp.status != 200:
                raise Exception(f"Jupiter swap build failed: {resp.status} - {await resp.text()}")
            data = await resp.json()

        # Deserialize the transaction
        tx_bytes = bytes.fromhex(data["swapTransaction"])
        return VersionedTransaction.from_bytes(tx_bytes)

    async def submit_transaction(
        self,
        transaction: VersionedTransaction,
    ) -> str:
        # Jupiter doesn't submit directly; uses RPC
        # This is a placeholder - actual submission happens via RPC
        raise NotImplementedError("Use RPC client to submit Jupiter transactions")

    async def get_transaction_status(
        self,
        signature: str,
    ) -> Dict[str, Any]:
        # Placeholder
        return {"status": "unknown", "signature": signature}


class RaydiumClient(DEXClient):
    """Raydium CLMM/AMM client (placeholder)."""

    def __init__(self, rpc_url: str):
        self.rpc_url = rpc_url

    async def get_quote(self, input_mint: str, output_mint: str, amount: Decimal, slippage_bps: int = 50) -> SwapQuote:
        # Placeholder - implement Raydium CLMM/AMM quote
        raise NotImplementedError("Raydium client not yet implemented")

    async def build_swap_transaction(self, quote: SwapQuote, user_pubkey: Pubkey, slippage_bps: int = 50) -> VersionedTransaction:
        raise NotImplementedError

    async def submit_transaction(self, transaction: VersionedTransaction) -> str:
        raise NotImplementedError

    async def get_transaction_status(self, signature: str) -> Dict[str, Any]:
        raise NotImplementedError


class DEXRegistry:
    """Registry of DEX clients."""

    def __init__(self):
        self._clients: Dict[DEXProvider, DEXClient] = {}

    def register(self, provider: DEXProvider, client: DEXClient):
        self._clients[provider] = client

    def get(self, provider: DEXProvider) -> Optional[DEXClient]:
        return self._clients.get(provider)

    def get_best_quote(
        self,
        input_mint: str,
        output_mint: str,
        amount: Decimal,
        slippage_bps: int = 50,
    ) -> Optional[SwapQuote]:
        """Get best quote across all DEXs."""
        best_quote = None
        best_output = Decimal("0")

        for provider, client in self._clients.items():
            try:
                quote = await client.get_quote(
                    input_mint, output_mint, amount, slippage_bps
                )
                if quote.output_amount > best_output:
                    best_output = quote.output_amount
                    best_quote = quote
            except Exception:
                continue

        return best_quote


class LiveExecutionAdapter:
    """
    Live execution adapter connecting paper_engine strategies to real DEX execution.
    """

    def __init__(
        self,
        config: PaperConfig,
        rpc_url: str,
        jupiter_api_key: Optional[str] = None,
        wallet_manager: Optional["WalletManager"] = None,
    ):
        self.config = config
        self.rpc_url = rpc_url
        self.wallet_manager = wallet_manager

        # Initialize DEX clients
        self.dex_registry = DEXRegistry()
        self.dex_registry.register(
            DEXProvider.JUPITER,
            JupiterClient(api_key=jupiter_api_key),
        )
        self.dex_registry.register(
            DEXProvider.RAYDIUM,
            RaydiumClient(rpc_url),
        )

        # Execution engine
        self.execution_engine = PaperExecutionEngine(config)

        # Active orders
        self.active_orders: Dict[str, LiveOrder] = {}

        # RPC session
        self._rpc_session: Optional[aiohttp.ClientSession] = None

    async def _get_rpc_session(self) -> aiohttp.ClientSession:
        if self._rpc_session is None or self._rpc_session.closed:
            self._rpc_session = aiohttp.ClientSession()
        return self._rpc_session

    async def close(self):
        await self.dex_registry._clients[DEXProvider.JUPITER].close()
        if self._rpc_session and not self._rpc_session.closed:
            await self._rpc_session.close()

    def _get_paper_config(self) -> PaperConfig:
        """Get paper config for execution engine."""
        return self.config

    async def execute_signal(
        self,
        strategy: str,
        symbol: str,
        side: Literal["buy", "sell"],
        quote: PriceQuote,
        size_usd: float,
        net_return: NetReturnResult,
    ) -> Optional[LiveOrder]:
        """
        Execute a trading signal from a strategy.
        Converts paper signal to live order and submits to DEX.
        """
        # Get wallet
        if not self.wallet_manager:
            raise Exception("Wallet manager not configured")

        keypair = self.wallet_manager.get_keypair()
        if not keypair:
            raise Exception("No keypair available")

        # Determine tokens
        # symbol format: "BASE/QUOTE" e.g., "SOL/USDC"
        base, quote_token = symbol.split("/")
        # For simplicity, assume we have mint addresses mapped
        # In production, use a token registry

        # Get DEX quote (use Jupiter for now)
        jupiter = self.dex_registry.get(DEXProvider.JUPITER)
        if not jupiter:
            raise Exception("Jupiter client not available")

        # Get swap quote
        # This is simplified - in production, use proper token mint mapping
        base_mint = self._get_mint(base)
        quote_mint = self._get_mint(quote_token)

        side = "sell" if side == "buy" else "buy"  # Reverse for quote
        amount = Decimal(str(size_usd))

        quote_obj = await jupiter.get_quote(
            input_mint=base_mint if side == "sell" else quote_mint,
            output_mint=quote_mint if side == "sell" else base_mint,
            amount=amount,
            slippage_bps=int(net_return.cost_breakdown.slippage_bps),
        )

        # Build transaction
        keypair = self.wallet_manager.get_keypair()
        tx = await jupiter.build_swap_transaction(quote, keypair.pubkey())

        # Sign and submit
        signed_tx = self.wallet_manager.sign_transaction(tx)
        signature = await self._submit_transaction(signed_tx)

        # Create order record
        order = LiveOrder(
            order_id=signature[:16],
            symbol=symbol,
            side=OrderSide(side),
            order_type=OrderType.MARKET,
            amount=amount,
            status=OrderStatus.SUBMITTED,
            signature=signature,
        )

        self.active_orders[order.order_id] = order
        return order

    def _get_mint(self, symbol: str) -> str:
        """Get token mint address from symbol."""
        # Token mint registry - in production, fetch from registry
        mints = {
            "SOL": "So11111111111111111111111111111111111111112",
            "USDC": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
            "USDT": "Es9vMFrzaCERmJN9h4hZD5H7GLnLhFQM9rTvsjNkQUd",
            "WETH": "7vfCXTuxx5gkV5b6n3L3h6P4K1QwJwFZGHGVWqFUo1sR",
            "BONK": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xNQn6FzgJR7wYb1",
            "WIF": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopZLHYxdXNy5z1A",
        }
        return mints.get(symbol, symbol)

    async def _submit_transaction(self, transaction: VersionedTransaction) -> str:
        """Submit transaction via RPC."""
        session = await self._get_rpc_session()
        tx_bytes = bytes(transaction)

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "sendTransaction",
            "params": [
                transaction.serialize().hex(),
                {"encoding": "base64", "skipPreflight": False, "maxRetries": 3},
            ],
        }

        async with self._rpc_session.post(self.rpc_url, json=payload) as resp:
            if resp.status != 200:
                raise Exception(f"RPC submit failed: {resp.status}")
            result = await resp.json()
            if "error" in result:
                raise Exception(f"RPC error: {result['error']}")
            return result["result"]

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an active order."""
        order = self.active_orders.get(order_id)
        if not order:
            return False

        # For market orders, can't cancel once submitted
        if order.order_type == OrderType.MARKET and order.status == OrderStatus.SUBMITTED:
            return False

        # For limit orders, would need to cancel via DEX
        order.status = OrderStatus.CANCELLED
        order.updated_at = time.time()
        return True

    async def get_order_status(self, order_id: str) -> Optional[LiveOrder]:
        """Get order status."""
        return self.active_orders.get(order_id)

    async def monitor_orders(self):
        """Monitor active orders and update status."""
        for order_id, order in list(self.active_orders.items()):
            if order.status in (OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED):
                continue

            if order.signature:
                status = await self._check_transaction_status(order.signature)
                if status.get("confirmed"):
                    order.status = OrderStatus.FILLED
                    order.filled_amount = order.amount
                    order.avg_fill_price = status.get("price")
                    order.updated_at = time.time()
                elif status.get("failed"):
                    order.status = OrderStatus.REJECTED
                    order.error = status.get("error")
                    order.updated_at = time.time()

    async def _check_transaction_status(self, signature: str) -> Dict[str, Any]:
        """Check transaction status via RPC."""
        session = await self._get_rpc_session()
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getSignatureStatuses",
            "params": [[signature], {"searchTransactionHistory": True}],
        }
        async with self._rpc_session.post(self.rpc_url, json=payload) as resp:
            result = await resp.json()
            if "result" in result and result["result"]["value"]:
                status = result["result"]["value"][0]
                return {
                    "confirmed": status.get("confirmationStatus") in ("confirmed", "finalized"),
                    "failed": status.get("err") is not None,
                    "error": status.get("err"),
                }
        return {"confirmed": False, "failed": False}


class WalletManager:
    """Secure wallet and key management."""

    def __init__(
        self,
        keypair: Optional[Keypair] = None,
        key_path: Optional[str] = None,
        password: Optional[str] = None,
    ):
        self._keypair = keypair
        self._key_path = key_path
        self._password = password

    def load_keypair(self, key_path: str, password: Optional[str] = None) -> Keypair:
        """Load keypair from file."""
        with open(key_path, "rb") as f:
            if password:
                # Decrypt if encrypted
                import nacl.secret
                import nacl.utils
                # Simplified - use proper encryption in production
                pass
            secret = f.read()
            return Keypair.from_bytes(secret)

    def get_keypair(self) -> Keypair:
        if not self._keypair:
            if self._key_path:
                self._keypair = self.load_keypair(self._key_path, self._password)
            else:
                raise Exception("No keypair loaded")
        return self._keypair

    def set_keypair(self, keypair: Keypair):
        self._keypair = keypair

    def get_pubkey(self) -> Pubkey:
        return self.get_keypair().pubkey()

    def sign_transaction(self, transaction: VersionedTransaction) -> VersionedTransaction:
        """Sign a versioned transaction."""
        keypair = self.get_keypair()
        # Sign the transaction
        signed = transaction.sign([keypair])
        return signed

    def sign_message(self, message: bytes) -> bytes:
        """Sign arbitrary message."""
        keypair = self.get_keypair()
        return keypair.sign_message(message)


# Import required modules at the end to avoid circular imports
from dataclasses import field
from typing import Optional
from decimal import Decimal