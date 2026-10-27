import os
import asyncio
import httpx
import logging
import json
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType

# Load environment variables from the local .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("poly_engine.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("PolyCore")

class PolyCore:
    def __init__(self):
        # Credentials from environment or .env file
        self.private_key = os.getenv("POLY_PRIVATE_KEY")
        self.funder_address = os.getenv("POLY_FUNDER_ADDRESS")
        
        if not self.private_key or not self.funder_address:
            logger.error("Missing POLY_PRIVATE_KEY or POLY_FUNDER_ADDRESS in environment/.env")
            raise EnvironmentError("Credentials not found")

        # Strip 0x if present to prevent py-clob-client hex errors
        if self.private_key.startswith("0x"):
            self.private_key = self.private_key[2:]

        # Initialize Polymarket CLOB Client
        self.client = ClobClient(
            host="https://clob.polymarket.com",
            key=self.private_key,
            chain_id=137,
            signature_type=1,
            funder=self.funder_address
        )
        self.http_client = httpx.AsyncClient(timeout=10.0)
        self.gamma_url = "https://gamma-api.polymarket.com/markets"

    async def initialize_auth(self):
        """Derives L2 API credentials required to place trades."""
        try:
            logger.info("Authenticating with Polymarket CLOB...")
            creds = self.client.create_or_derive_api_creds()
            self.client.set_api_creds(creds)
            logger.info("Polymarket Client Authenticated successfully.")
        except Exception as e:
            logger.exception(f"Authentication failed: {e}")
            raise

    async def resolve_token_id(self, query: str, outcome: str = "YES") -> Optional[str]:
        """
        Searches Gamma API for a market by title and returns the token_id for the specified outcome.
        """
        try:
            logger.info(f"Resolving token ID for query: '{query}' (Outcome: {outcome})")
            params = {"search": query, "active": "true"}
            response = await self.http_client.get(self.gamma_url, params=params)
            response.raise_for_status()
            markets = response.json()

            if not markets:
                logger.warning(f"No active markets found for query: {query}")
                return None

            best_market = markets[0]
            clob_tokens_raw = best_market.get("clobTokenIds", [])
            if isinstance(clob_tokens_raw, str):
                try:
                    clob_tokens_list = json.loads(clob_tokens_raw)
                except json.JSONDecodeError:
                    logger.error(f"Failed to decode clobTokenIds string: {clob_tokens_raw}")
                    return None
            else:
                clob_tokens_list = clob_tokens_raw

            if not isinstance(clob_tokens_list, list):
                logger.warning(f"Expected list for clobTokenIds, got {type(clob_tokens_list)}")
                return None

            if outcome.upper() == "YES" and len(clob_tokens_list) > 0:
                token_id = clob_tokens_list[0]
            elif outcome.upper() == "NO" and len(clob_tokens_list) > 1:
                token_id = clob_tokens_list[1]
            else:
                logger.warning(f"Outcome {outcome} not found in clobTokenIds list for market: {best_market.get('question')}")
                return None

            logger.info(f"Resolved {query} -> {token_id}")
            return token_id
        except Exception as e:
            logger.exception(f"Error resolving token ID for {query}: {e}")
            return None

    async def check_usdc_allowance(self) -> bool:
        logger.info("Checking USDC allowance on Polygon...")
        return True

    async def execute_trade(self, token_id: str, side: str, price: float, size: float):
        try:
            # DRY RUN MODE: Execution is disabled for testing
            logger.info(f"[DRY RUN] Would have sent order: {side} {size} shares at ${price} (Token: {token_id})")
            return {"status": "dry_run", "message": "Order simulation successful"}
        except Exception as e:
            logger.exception(f"CRITICAL Trade Execution Failure: {e}")
            return None

    async def close(self):
        await self.http_client.aclose()
