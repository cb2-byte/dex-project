import os
import asyncio
from contextlib import asynccontextmanager
from typing import Optional, List
from datetime import datetime, timedelta

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from twscrape import API
from twscrape.logger import set_log_level
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
set_log_level("INFO")

# Global API instance
api: Optional[API] = None
_accounts_loaded = False


class TweetResponse(BaseModel):
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
    hashtags: List[str]
    mentions: List[str]
    is_retweet: bool
    is_reply: bool
    language: Optional[str] = None


class TweetsResponse(BaseModel):
    symbol: str
    count: int
    tweets: List[TweetResponse]
    fetched_at: str


class HealthResponse(BaseModel):
    status: str
    accounts_loaded: bool
    accounts_count: int
    timestamp: str


# Global state
_accounts_file = "/app/accounts.json"
_twitter_accounts = []  # Will be loaded from env


async def load_accounts():
    """Load Twitter accounts from environment variables."""
    global _accounts_loaded
    
    # Load from environment variables
    # Format: TWITTER_ACCOUNTS=username1:password1:email1:email_password1,username2:password2:email2:email_password2
    accounts_env = os.getenv("TWITTER_ACCOUNTS", "")
    
    if not accounts_env:
        logger.warning("No TWITTER_ACCOUNTS environment variable set. Scraping will fail.")
        return
    
    accounts = []
    for acc_str in accounts_env.split(","):
        parts = acc_str.strip().split(":")
        if len(parts) >= 4:
            accounts.append({
                "username": parts[0],
                "password": parts[1],
                "email": parts[2],
                "email_password": parts[3],
            })
        elif len(parts) >= 2:
            accounts.append({
                "username": parts[0],
                "password": parts[1],
                "email": "",
                "email_password": "",
            })
    
    logger.info(f"Loaded {len(accounts)} Twitter accounts from environment")
    
    if not api:
        return
    
    for acc in accounts:
        try:
            await api.pool.add_account(
                acc["username"],
                acc["password"],
                acc["email"],
                acc["email_password"]
            )
            logger.info(f"Added account: {acc['username']}")
        except Exception as e:
            logger.error(f"Failed to add account {acc['username']}: {e}")
    
    await api.pool.login_all()
    _accounts_loaded = True
    logger.info("All accounts logged in")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global api
    api = API()
    await load_accounts()
    yield
    # Cleanup
    await api.pool.close()


app = FastAPI(
    title="twscrape HTTP Wrapper for PennyShield",
    description="HTTP endpoint to fetch tweets for token symbols",
    version="1.0.0",
    lifespan=lifespan,
)


def extract_symbols(text: str) -> list[str]:
    """Extract $TOKEN symbols from tweet text."""
    import re
    return re.findall(r'\$([A-Za-z0-9]{2,10})', text)


def tweet_to_response(tweet) -> TweetResponse:
    """Convert twscrape tweet to response model."""
    return TweetResponse(
        id=str(tweet.id),
        username=tweet.user.username,
        display_name=tweet.user.displayname,
        content=tweet.rawContent,
        created_at=tweet.date.isoformat() if tweet.date else "",
        url=f"https://x.com/{tweet.user.username}/status/{tweet.id}",
        retweet_count=tweet.retweetCount,
        like_count=tweet.likeCount,
        reply_count=tweet.replyCount,
        quote_count=tweet.quoteCount,
        hashtags=[tag for tag in (tweet.hashtags or [])],
        mentions=[mention for mention in (tweet.mentions or [])],
        is_retweet=tweet.retweetedTweet is not None,
        is_reply=tweet.inReplyToTweetId is not None,
        language=tweet.lang,
    )


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy" if _accounts_loaded else "degraded",
        accounts_loaded=_accounts_loaded,
        accounts_count=len(api.pool.accounts) if api and api.pool else 0,
        timestamp=datetime.utcnow().isoformat(),
    )


@app.get("/tweets", response_model=TweetsResponse)
async def get_tweets(
    symbol: str = Query(..., description="Token symbol (e.g., PEPE, BONK, WIF)"),
    limit: int = Query(50, ge=1, le=200, description="Number of tweets to fetch"),
    hours: int = Query(24, ge=1, le=168, description="Look back hours"),
):
    """
    Fetch recent tweets mentioning a token symbol.
    
    Example: /tweets?symbol=PEPE&limit=50&hours=24
    """
    if not _accounts_loaded:
        raise HTTPException(status_code=503, detail="Twitter accounts not loaded yet")
    
    if not api:
        raise HTTPException(status_code=503, detail="API not initialized")
    
    # Normalize symbol
    symbol = symbol.upper().lstrip("$")
    query = f"${symbol}"
    
    # Calculate date range
    since = datetime.utcnow() - timedelta(hours=hours)
    
    tweets_data = []
    try:
        # Search for tweets
        tweets = await api.search(query, limit=limit)
        
        for tweet in tweets:
            # Filter by time
            if tweet.date and tweet.date.replace(tzinfo=None) < since:
                continue
            
            # Check if tweet actually mentions our symbol
            tweet_symbols = extract_symbols(tweet.rawContent)
            if symbol not in [s.upper() for s in tweet_symbols]:
                continue
            
            tweets_data.append(tweet_to_response(tweet))
            
            if len(tweets_data) >= limit:
                break
    
    except Exception as e:
        logger.error(f"Error fetching tweets for ${symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch tweets: {str(e)}")
    
    return TweetsResponse(
        symbol=symbol,
        count=len(tweets_data),
        tweets=tweets_data,
        fetched_at=datetime.utcnow().isoformat(),
    )


@app.get("/tweets/user/{username}", response_model=TweetsResponse)
async def get_user_tweets(
    username: str,
    limit: int = Query(50, ge=1, le=200),
    hours: int = Query(24, ge=1, le=168),
):
    """Fetch recent tweets from a specific user."""
    if not _accounts_loaded:
        raise HTTPException(status_code=503, detail="Twitter accounts not loaded yet")
    
    if not api:
        raise HTTPException(status_code=503, detail="API not initialized")
    
    since = datetime.utcnow() - timedelta(hours=hours)
    tweets_data = []
    
    try:
        tweets = await api.user_tweets(username, limit=limit)
        
        for tweet in tweets:
            if tweet.date and tweet.date.replace(tzinfo=None) < since:
                continue
            tweets_data.append(tweet_to_response(tweet))
            if len(tweets_data) >= limit:
                break
    
    except Exception as e:
        logger.error(f"Error fetching user tweets for {username}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch tweets: {str(e)}")
    
    return TweetsResponse(
        symbol=f"@{username}",
        count=len(tweets_data),
        tweets=tweets_data,
        fetched_at=datetime.utcnow().isoformat(),
    )


@app.post("/accounts/reload")
async def reload_accounts():
    """Reload Twitter accounts from environment."""
    global _accounts_loaded
    _accounts_loaded = False
    await load_accounts()
    return {"status": "reloaded", "accounts_loaded": _accounts_loaded}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)