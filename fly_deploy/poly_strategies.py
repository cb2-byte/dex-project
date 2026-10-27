import asyncio
import json
import logging
import websockets
import httpx
from typing import Dict, Any, Optional
from poly_core import PolyCore
from poly_brain import PolyBrain

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("poly_strategies.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("PolyStrategies")

class CryptoSensor:
    """
    The Machine Gun: High-frequency sensory organ for 5-min crypto markets.
    Uses WebSockets for real-time orderbook updates and a deterministic math filter.
    """
    def __init__(self, query: str, core: PolyCore, brain: PolyBrain):
        self.query = query
        self.core = core
        self.brain = brain
        self.uri = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
        self.token_id = None
        self.running = True

    async def start(self):
        # 1. Resolve the token ID using the core's resolver
        self.token_id = await self.core.resolve_token_id(self.query)
        if not self.token_id:
            logger.error(f"Could not resolve token ID for {self.query}. Crypto sensor shutting down.")
            return

        logger.info(f"Starting Crypto Sensor for {self.query} (ID: {self.token_id})")
        await self.stream_market_data()

    async def stream_market_data(self):
        self.orderbook_queue = asyncio.Queue()
        
        # Start the consumer worker in the background
        worker_task = asyncio.create_task(self.process_queue_worker())
        
        while self.running:
            try:
                async with websockets.connect(self.uri) as ws:
                    subscribe_msg = {
                        "type": "subscribe",
                        "market_ids": [self.token_id]
                    }
                    await ws.send(json.dumps(subscribe_msg))
                    logger.info(f"[SENSOR] WebSocket Connected & Subscribed to {self.token_id}")

                    async for message in ws:
                        data = json.loads(message)
                        if data.get("type") == "book":
                            # Lightning fast push into memory; loop returns instantly
                            await self.orderbook_queue.put(data)

            except Exception as e:
                logger.warning(f"[SENSOR] Crypto WebSocket dropped: {e}. Reconnecting in 5s...")
                await asyncio.sleep(5)
        
        await worker_task # Clean up worker on shutdown

    async def process_queue_worker(self):
        """
        Background consumer that pulls from the queue and processes updates.
        Ensures the WebSocket receiver never blocks.
        """
        while self.running:
            try:
                book_data = await self.orderbook_queue.get()
                await self.process_orderbook_update(book_data)
                self.orderbook_queue.task_done()
            except Exception as e:
                logger.error(f"Queue Worker Error: {e}")
                await asyncio.sleep(1)

class WeatherSensor:
    """
    The Sniper: Low-frequency sensory organ for weather markets.
    Uses polling with a deep LLM analysis filter.
    """
    def __init__(self, query: str, lat: float, lon: float, threshold: float, core: PolyCore, brain: PolyBrain):
        self.query = query
        self.lat = lat
        self.lon = lon
        self.threshold = threshold
        self.core = core
        self.brain = brain
        self.running = True

    async def start(self):
        self.token_id = await self.core.resolve_token_id(self.query)
        if not self.token_id:
            logger.error(f"Could not resolve token ID for {self.query}. Weather sensor shutting down.")
            return

        logger.info(f"Starting Weather Sensor for {self.query} (ID: {self.token_id})")
        await self.poll_weather_data()

    async def poll_weather_data(self):
        async with httpx.AsyncClient(timeout=15.0) as client:
            while self.running:
                try:
                    # 1. Fetch real-time forecast data
                    url = f"https://api.open-meteo.com/v1/forecast?latitude={self.lat}&longitude={self.lon}&hourly=temperature_2m&temperature_unit=fahrenheit"
                    response = await client.get(url)
                    response.raise_for_status()
                    weather_data = response.json()

                    # 2. Prepare market context
                    # In reality, we'd fetch the current price from the core client
                    market_context = {
                        "description": self.query,
                        "current_price": 0.45, # Placeholder for real-time price fetch
                        "token_id": self.token_id
                    }

                    # 3. DEEP ANALYSIS: Pass to the Brain (Inline Filter)
                    decision = await self.brain.evaluate_weather_edge(market_context, weather_data)
                    
                    if decision.get("execute"):
                        logger.info(f"[SIGNAL] Brain approved weather trade: {decision.get('reasoning')}")
                        # Execute with the identified edge
                        await self.core.execute_trade(
                            token_id=self.token_id,
                            side="BUY",
                            price=0.60, # Target price derived from confidence
                            size=10.0
                        )
                    else:
                        logger.info(f"[NO SIGNAL] Brain rejected trade: {decision.get('reasoning')}")

                except Exception as e:
                    logger.error(f"Weather Polling Error: {e}")

                # Weather moves slowly; check every 10 minutes
                await asyncio.sleep(600)

async def main():
    # Initialize the foundation
    core = PolyCore()
    brain = PolyBrain()
    
    try:
        await core.initialize_auth()
        await brain.warmup()
    except Exception as e:
        logger.critical(f"Critical failure during initialization: {e}")
        return

    # Define the strategies
    # Example: NYC Heatwave and BTC 5-Min
    weather_bot = WeatherSensor("NYC Temperature", 40.7128, -74.0060, 90.0, core, brain)
    crypto_bot = CryptoSensor("BTC 5-Min", core, brain)

    logger.info("Launching Polymarket 2.0 Dual-Track System...")
    await asyncio.gather(
        weather_bot.start(),
        crypto_bot.start()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
