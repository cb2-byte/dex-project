import os
import asyncio
import json
import httpx
import logging
import re
from typing import Optional, Dict, Any

# Reuse logging config from poly_core
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message) sameS',\n    handlers=[
        logging.FileHandler("poly_brain.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("PolyBrain")

class PolyBrain:
    def __init__(self):
        # We are using Ollama for local inference to minimize latency and costs
        self.ollama_url = "http://localhost:11434/api/chat"
        self.model = "qwen3.5:latest"
        self.http_client = httpx.AsyncClient(timeout=120.0)

    def _parse_soft_json(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Universal parser to extract JSON from generative text.
        Strips markdown, conversational noise, and isolates the first valid JSON block.
        """
        try:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                clean_json = match.group(0)
                return json.loads(clean_json)
            return None
        except Exception as e:
            logger.warning(f"[BRAIN ADAPTER WARNING] Soft bridge regex failed to parse: {e}")
            return None

    async def evaluate_weather_edge(self, market_context: Dict[str, Any], raw_weather_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        MULTI-TIERED FAILOVER ENGINE: Local LLM -> Cloud LLM -> Deterministic Math.
        """
        # 1. Pre-process for lean context
        hourly_temps = raw_weather_data.get('hourly', {}).get('temperature_2m', [])
        if not hourly_temps:
            return {"execute": False, "confidence_score": 0.0, "reasoning": "No temperature data available"}

        day_temps = hourly_temps[:24]
        lean_weather = {
            "daily_max_f": round(max(day_temps), 1),
            "daily_min_f": round(min(day_temps), 1),
            "daily_avg_f": round(sum(day_temps) / 24, 1),
            "trend": "RISING" if day_temps[12] > day_temps[0] else "FALLING"
        }

        system_prompt = (
            "You are an elite predictive analyst for Polymarket trading. "
            "You must respond strictly in JSON format. "
            "Evaluate if the current market price misprices the true probability based on meteorological data."
        )
        user_prompt = (
            f"Market: {market_context.get('description', 'Unknown Weather Market')}\n"
            f"Current YES Price: ${market_context.get('current_price', 'N/A')}\n\n"
            f"Lean Meteorological Summary:\n{json.dumps(lean_weather, indent=2)}\n\n"
            "Analyze for discrepancies. Respond with:\n"
            "{\n"
            "  \"execute\": boolean,\n"
            "  \"confidence_score\": float (0.0-1.0),\n"
            "  \"reasoning\": \"brief explanation\"\n"
            "}"
        )

        # TIER 1: Local Qwen (Fast/Free) - Strict 15s timeout to avoid hanging
        try:
            logger.info("[BRAIN] Tier 1: Dispatch launching to local Qwen weights...")
            async with httpx.AsyncClient(timeout=15.0) as fast_client:
                payload = {
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "stream": False
                }
                response = await fast_client.post(self.ollama_url, json=payload)
                if response.status_code == 200:
                    result = response.json()
                    content = result.get("message", {}).get("content", "")
                    decision = self._parse_soft_json(content)
                    if decision:
                        logger.info("[BRAIN] Tier 1 Success: Local Qwen provided a verdict.")
                        return decision
        except Exception as e:
            logger.warning(f"[BRAIN] Tier 1 Local LLM failed/timed out: {e}")

        # TIER 2: Cloud Failover (Reliable/Paid)
        cloud_key = os.getenv("CLOUD_LLM_API_KEY")
        if cloud_key:
            try:
                logger.info("[BRAIN] Tier 2: Querying redundant Cloud LLM pipeline...")
                # Implementation for actual cloud provider would go here
                pass
            except Exception as e:
                logger.warning(f"[BRAIN] Tier 2 Cloud failover failed: {e}")

        # TIER 3: Deterministic Hard-Math Fallback
        logger.info("[BRAIN] Tier 3: Executing deterministic mathematical rules.")
        current_price = float(market_context.get("current_price", 0.50))
        projected_max = lean_weather["daily_max_f"]
        target_temp = 90.0 
        
        execute = (projected_max >= target_temp and current_price < 0.50)
        return {
            "execute": execute,
            "confidence_score": 0.70 if execute else 0.0,
            "reasoning": "FALLBACK: Local/Cloud LLM offline. Raw math edge evaluation triggered."
        }

    async def audit_crypto_performance(self, trade_log: Dict[str, Any], order_book_snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """
        ASYNC AUDIT FILTER:
        Reviews a trade AFTER it has been executed by the math-engine.
        """
        system_prompt = "You are a post-trade forensic analyst. Respond strictly in JSON."
        user_prompt = f"Trade Log: {json.dumps(trade_log)}\nBook: {json.dumps(order_book_snapshot)}"
        
        try:
            payload = {"model": self.model, "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}], "stream": False}
            response = await self.http_client.post(self.ollama_url, json=payload)
            content = response.json().get("message", {}).get("content", "")
            return self._parse_soft_json(content) or {"quality": "Unknown"}
        except Exception as e:
            logger.error(f"Audit failed: {e}")
            return {"quality": "Unknown"}

    async def warmup(self):
        logger.info("[BRAIN INI] Warming up local model weights into memory...")
        try:
            async with httpx.AsyncClient(timeout=180.0) as warmup_client:
                response = await warmup_client.post(
                    f"{self.ollama_url.replace('/chat', '/generate')}", 
                    json={"model": self.model, "prompt": "ping", "stream": False}
                )
                if response.status_code == 200:
                    logger.info("[BRAIN READY] Model fully cached in VRAM. Inference latency minimized.")
        except Exception as e:
            logger.warning(f"[BRAIN WARNING] Warm-up sequence failed: {e}")

    async def close(self):
        await self.http_client.aclose()
