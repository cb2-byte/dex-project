"""
PennyShield Social Data Client
==============================
Connects to the twscrape HTTP wrapper and feeds tweets into PennyShield's
SocialDataCollector for real-time sentiment analysis.
"""

import os
import asyncio
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class TweetData(BaseModel):
    """Normalized tweet data for PennyShield."""
    id: str
    username: str
    display_name: str
    content: str
    created_at: str
    url: str
    retweet_count: int
    like_count: int
    reply_count: int
    quote_count: int
    hashtags: List[str] = field(default_factory=list)
    mentions: List[str] = field(default_factory=list)
    is_retweet: bool = False
    is_reply: bool = False
    language: Optional[str] = None


@dataclass
class SocialMention:
    """Social mention formatted for PennyShield's SocialDataCollector."""
    platform: str
    author: str
    content: str
    timestamp: float
    url: str
    engagement: int
    symbols: List[str]
    sentiment_score: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class TwscrapeClient:
    """Client for the twscrape HTTP wrapper."""
    
    def __init__(
        self,
        base_url: str = "http://localhost:8080",
        timeout: float = 30.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self):
        self._client = httpx.AsyncClient(timeout=self.timeout)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()
    
    async def health_check(self) -> Dict[str, Any]:
        """Check if the twscrape service is healthy."""
        if not self._client:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        try:
            resp = await self._client.get(f"{self.base_url}/health")
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {"status": "unhealthy", "error": str(e)}
    
    async def get_tweets_for_symbol(
        self,
        symbol: str,
        limit: int = 50,
        hours: int = 24,
    ) -> List[TweetData]:
        """Fetch tweets mentioning a token symbol."""
        if not self._client:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        
        try:
            resp = await self._client.get(
                f"{self.base_url}/tweets",
                params={"symbol": symbol, "limit": limit, "hours": hours},
            )
            resp.raise_for_status()
            data = resp.json()
            
            tweets = []
            for tweet_data in data.get("tweets", []):
                tweets.append(TweetData(**tweet_data))
            return tweets
        except Exception as e:
            logger.error(f"Failed to fetch tweets for ${symbol}: {e}")
            return []
    
    async def get_user_tweets(
        self,
        username: str,
        limit: int = 50,
        hours: int = 24,
    ) -> List[TweetData]:
        """Fetch tweets from a specific user."""
        if not self._client:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        
        try:
            resp = await self._client.get(
                f"{self.base_url}/tweets/user/{username}",
                params={"limit": limit, "hours": hours},
            )
            resp.raise_for_status()
            data = resp.json()
            
            tweets = []
            for tweet_data in data.get("tweets", []):
                tweets.append(TweetData(**tweet_data))
            return tweets
        except Exception as e:
            logger.error(f"Failed to fetch user tweets for @{username}: {e}")
            return []


class SocialDataCollector:
    """
    Enhanced social data collector that uses twscrape for real-time X data.
    Extends PennyShield's built-in social intel module.
    """
    
    def __init__(
        self,
        twscrape_url: str = "http://localhost:8080",
        symbols_to_monitor: List[str] = None,
        poll_interval_seconds: int = 300,
    ):
        self.twscrape_url = twscrape_url
        self.symbols_to_monitor = [s.upper().lstrip("$") for s in (symbols_to_monitor or [])]
        self.poll_interval = poll_interval_seconds
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._seen_tweet_ids: set = set()
        self._mentions_buffer: List[SocialMention] = []
        self._max_buffer = 10000
    
    async def start(self):
        """Start the background polling task."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info(f"SocialDataCollector started monitoring: {self.symbols_to_monitor}")
    
    async def stop(self):
        """Stop the background polling task."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("SocialDataCollector stopped")
    
    async def _poll_loop(self):
        """Background loop that polls for new tweets."""
        while self._running:
            try:
                await self._poll_once()
            except Exception as e:
                logger.error(f"Poll loop error: {e}")
            await asyncio.sleep(self.poll_interval)
    
    async def _poll_once(self):
        """Single polling iteration for all monitored symbols."""
        async with TwscrapeClient(self.twscrape_url) as client:
            # Check health first
            health = await client.health_check()
            if health.get("status") != "healthy":
                logger.warning(f"twscrape unhealthy: {health}")
                return
            
            for symbol in self.symbols_to_monitor:
                try:
                    tweets = await client.get_tweets_for_symbol(symbol, limit=100, hours=24)
                    
                    for tweet in tweets:
                        if tweet.id in self._seen_tweet_ids:
                            continue
                        self._seen_tweet_ids.add(tweet.id)
                        
                        # Extract symbols from tweet content
                        import re
                        mentioned = re.findall(r'\$([A-Za-z0-9]{2,10})', tweet.content)
                        mentioned = [s.upper() for s in mentioned]
                        
                        # Create social mention
                        mention = SocialMention(
                            platform="x",
                            author=tweet.username,
                            content=tweet.content,
                            timestamp=datetime.fromisoformat(tweet.created_at.replace("Z", "+00:00")).timestamp() if tweet.created_at else datetime.utcnow().timestamp(),
                            url=tweet.url,
                            engagement=tweet.like_count + tweet.retweet_count + tweet.reply_count,
                            symbols=mentioned,
                            metadata={
                                "tweet_id": tweet.id,
                                "username": tweet.username,
                                "display_name": tweet.display_name,
                                "retweet_count": tweet.retweet_count,
                                "like_count": tweet.like_count,
                                "reply_count": tweet.reply_count,
                                "hashtags": tweet.hashtags,
                                "mentions": tweet.mentions,
                                "language": tweet.language,
                            }
                        )
                        
                        self._mentions_buffer.append(mention)
                        if len(self._mentions_buffer) > self._max_buffer:
                            self._mentions_buffer = self._mentions_buffer[-self._max_buffer:]
                
                except Exception as e:
                    logger.error(f"Error polling ${symbol}: {e}")
    
    def get_recent_mentions(
        self,
        symbol: str = None,
        since: float = None,
        limit: int = 100,
    ) -> List[SocialMention]:
        """Get recent social mentions, optionally filtered."""
        mentions = self._mentions_buffer
        
        if symbol:
            symbol = symbol.upper().lstrip("$")
            mentions = [m for m in mentions if symbol in m.symbols]
        
        if since:
            mentions = [m for m in mentions if m.timestamp >= since]
        
        # Sort by timestamp descending
        mentions = sorted(mentions, key=lambda m: m.timestamp, reverse=True)
        return mentions[:limit]
    
    def get_sentiment_summary(self, symbol: str, hours: int = 24) -> Dict[str, Any]:
        """Get a simple sentiment summary for a symbol."""
        since = datetime.utcnow().timestamp() - (hours * 3600)
        mentions = self.get_recent_mentions(symbol=symbol, since=since)
        
        if not mentions:
            return {
                "symbol": symbol,
                "mentions_count": 0,
                "sentiment": "neutral",
                "engagement_total": 0,
            }
        
        # Simple sentiment based on engagement and content
        positive_keywords = ["moon", "bullish", "buy", "long", "gem", "alpha", "pump", "strong", "bull", "green", "up", "gain", "profit"]
        negative_keywords = ["dump", "bearish", "sell", "short", "rug", "scam", "crash", "red", "down", "loss", "bleed", "tank"]
        
        pos_count = 0
        neg_count = 0
        total_engagement = 0
        
        for m in mentions:
            total_engagement += m.engagement
            content_lower = m.content.lower()
            if any(kw in content_lower for kw in positive_keywords):
                pos_count += 1
            if any(kw in content_lower for kw in negative_keywords):
                neg_count += 1
        
        total = len(mentions)
        if pos_count > neg_count:
            sentiment = "bullish"
        elif neg_count > pos_count:
            sentiment = "bearish"
        else:
            sentiment = "neutral"
        
        return {
            "symbol": symbol.upper(),
            "mentions_count": total,
            "sentiment": sentiment,
            "positive_signals": pos_count,
            "negative_signals": neg_count,
            "engagement_total": total_engagement,
            "avg_engagement": total_engagement / total if total > 0 else 0,
        }


# =============================================================================
# Integration with PennyShield's existing SocialDataCollector
# =============================================================================

class PennyShieldSocialBridge:
    """
    Bridge between twscrape wrapper and PennyShield's existing SocialDataCollector.
    """
    
    def __init__(
        self,
        twscrape_url: str = "http://localhost:8080",
        pennyshield_evidence_dir: str = "/home/ubuntu/.openclaw/workspace/pennyshield/evidence",
    ):
        self.twscrape_url = twscrape_url
        self.evidence_dir = pennyshield_evidence_dir
        self.collector = SocialDataCollector(twscrape_url=twscrape_url)
    
    async def start_monitoring(self, symbols: List[str]):
        """Start monitoring symbols for social sentiment."""
        self.collector.symbols_to_monitor = [s.upper().lstrip("$") for s in symbols]
        await self.collector.start()
    
    async def stop_monitoring(self):
        await self.collector.stop()
    
    async def get_social_context(
        self,
        token_address: str,
        chain: str,
        token_symbol: str,
    ) -> Dict[str, Any]:
        """
        Get social context for a token, formatted for PennyShield's DetectionContext.
        """
        # Get recent mentions
        mentions = self.collector.get_recent_mentions(
            symbol=token_symbol,
            since=datetime.utcnow().timestamp() - 86400,  # 24h
            limit=200,
        )
        
        if not mentions:
            return {
                "mentions_count": 0,
                "sentiment": "neutral",
                "buzz_score": 0.0,
                "top_tweets": [],
            }
        
        # Calculate buzz score (engagement-weighted)
        total_engagement = sum(m.engagement for m in mentions)
        buzz_score = min(total_engagement / 10000.0, 1.0)  # Normalize
        
        # Simple sentiment
        positive = sum(1 for m in mentions if any(
            kw in m.content.lower() for kw in ["moon", "bullish", "buy", "gem", "alpha", "pump"]
        ))
        negative = sum(1 for m in mentions if any(
            kw in m.content.lower() for kw in ["dump", "rug", "scam", "sell", "bearish"]
        ))
        
        sentiment = "bullish" if positive > negative else ("bearish" if negative > positive else "neutral")
        
        # Top tweets by engagement
        top_tweets = sorted(mentions, key=lambda m: m.engagement, reverse=True)[:5]
        
        return {
            "mentions_count": len(mentions),
            "sentiment": sentiment,
            "buzz_score": buzz_score,
            "positive_signals": positive,
            "negative_signals": negative,
            "total_engagement": total_engagement,
            "top_tweets": [
                {
                    "author": m.author,
                    "content": m.content[:200],
                    "url": m.url,
                    "engagement": m.engagement,
                    "timestamp": m.timestamp,
                }
                for m in top_tweets
            ],
        }
    
    async def enrich_detection_context(
        self,
        context: "DetectionContext",
    ) -> "DetectionContext":
        """
        Enrich a PennyShield DetectionContext with social data.
        """
        social_data = await self.get_social_context(
            token_address=context.token_address,
            chain=context.chain,
            token_symbol=context.token_data.get("symbol", "") if context.token_data else "",
        )
        
        # Merge into context metadata
        context.metadata["social_data"] = social_data
        return context


# =============================================================================
# Quick test / demo
# =============================================================================

async def demo():
    """Demo the twscrape client."""
    print("🐸 twscrape Client Demo")
    print("=" * 50)
    
    async with TwscrapeClient() as client:
        health = await client.health_check()
        print(f"Health: {health}")
        
        if health.get("status") == "healthy":
            tweets = await client.get_tweets_for_symbol("PEPE", limit=5)
            print(f"\nFound {len(tweets)} tweets for $PEPE:")
            for tweet in tweets:
                print(f"  @{tweet.username}: {tweet.content[:80]}... ({tweet.like_count}❤️)")
        else:
            print("Service not healthy - need Twitter accounts configured")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(demo())