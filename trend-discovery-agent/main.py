"""FastAPI application for trend discovery agent."""
import logging
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from google_trends_client import GoogleTrendsClient
from twitter_client import TwitterClient
from cache_manager import CacheManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize app
app = FastAPI(
    title="Trend Discovery Agent",
    description="API for discovering trends from Google Trends with caching",
    version="0.1.0"
)

# Initialize clients
cache_manager = CacheManager(db_path="cache/trends.db", ttl_hours=1)
trends_client = GoogleTrendsClient(cache_manager=cache_manager)

# Separate cache for Twitter to avoid key conflicts
twitter_cache = CacheManager(db_path="cache/twitter.db", ttl_hours=1)
twitter_client = TwitterClient(cache_manager=twitter_cache)


# Pydantic models
class TrendsResponse(BaseModel):
    """Response model for trends."""
    source: str  # 'api', 'cache', 'cache_fallback', 'error'
    region: str
    trends: List[str]
    timestamp: str
    note: Optional[str] = None
    error: Optional[str] = None


class MultiRegionTrendsResponse(BaseModel):
    """Response model for multi-region trends."""
    regions: dict  # Mapping of region to TrendsResponse


class CacheStatsResponse(BaseModel):
    """Response model for cache statistics."""
    total_entries: int
    valid_entries: int
    expired_entries: int
    cache_location: str


class TweetMetrics(BaseModel):
    """Tweet metrics."""
    like_count: Optional[int] = None
    retweet_count: Optional[int] = None
    reply_count: Optional[int] = None


class Tweet(BaseModel):
    """Tweet object."""
    id: str
    text: str
    created_at: str
    metrics: Optional[dict] = None


class TwitterSearchResponse(BaseModel):
    """Response model for Twitter search."""
    source: str  # 'api', 'cache', 'cache_fallback', 'error'
    query: str
    tweets: List[Tweet]
    timestamp: str
    note: Optional[str] = None
    error: Optional[str] = None


class TwitterTrendingResponse(BaseModel):
    """Response model for trending topics."""
    source: str
    location: str
    topics: List[str]
    timestamp: str
    note: Optional[str] = None


class TwitterTimelineResponse(BaseModel):
    """Response model for user timeline."""
    source: str
    username: str
    tweets: List[Tweet]
    timestamp: str
    note: Optional[str] = None
    error: Optional[str] = None


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "trend-discovery-agent"}


# Trending searches endpoints
@app.get("/trends/trending", response_model=TrendsResponse)
async def get_trending_searches(region: str = Query("UNITED_STATES", description="Region code")):
    """Get trending searches for a region.

    Args:
        region: Region code (e.g., 'UNITED_STATES', 'INDIA', 'JAPAN')

    Returns:
        Trending searches with caching information
    """
    try:
        result = trends_client.get_trending_searches(region=region)
        return TrendsResponse(**result)
    except Exception as e:
        logger.error(f"Error fetching trends: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/trends/trending-multi", response_model=MultiRegionTrendsResponse)
async def get_trending_searches_multi(
    regions: Optional[str] = Query(None, description="Comma-separated region codes")
):
    """Get trending searches for multiple regions.

    Args:
        regions: Comma-separated region codes

    Returns:
        Trending searches for multiple regions
    """
    try:
        regions_list = None
        if regions:
            regions_list = [r.strip() for r in regions.split(",")]

        result = trends_client.get_trending_searches_multi_region(regions=regions_list)
        return MultiRegionTrendsResponse(regions=result)
    except Exception as e:
        logger.error(f"Error fetching multi-region trends: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/trends/interest")
async def get_interest_over_time(
    keywords: str = Query(..., description="Comma-separated keywords"),
    timeframe: str = Query("now 1-d", description="Timeframe for data")
):
    """Get interest over time for keywords.

    Args:
        keywords: Comma-separated keywords
        timeframe: Timeframe (e.g., 'now 1-d', 'now 7-d', 'today 3-m')

    Returns:
        Interest over time data
    """
    try:
        keyword_list = [k.strip() for k in keywords.split(",")]
        result = trends_client.get_interest_over_time(keywords=keyword_list, timeframe=timeframe)
        return JSONResponse(result)
    except Exception as e:
        logger.error(f"Error fetching interest data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Cache management endpoints
@app.get("/cache/stats", response_model=CacheStatsResponse)
async def get_cache_stats():
    """Get cache statistics."""
    return CacheStatsResponse(**cache_manager.get_cache_stats())


@app.delete("/cache/clear")
async def clear_cache(key: Optional[str] = Query(None, description="Specific key to clear")):
    """Clear cache.

    Args:
        key: Optional specific key to clear. If not provided, clears all.

    Returns:
        Status message
    """
    cache_manager.clear(key=key)
    return {
        "message": f"Cache cleared: {key or 'all'}",
        "timestamp": __import__('datetime').datetime.utcnow().isoformat()
    }


@app.post("/cache/cleanup")
async def cleanup_expired():
    """Clean up expired cache entries.

    Returns:
        Number of entries removed
    """
    removed = cache_manager.cleanup_expired()
    return {
        "message": f"Removed {removed} expired entries",
        "removed_count": removed,
        "timestamp": __import__('datetime').datetime.utcnow().isoformat()
    }


# Twitter/X API endpoints
@app.get("/twitter/search", response_model=TwitterSearchResponse)
async def search_twitter(
    query: str = Query(..., description="Search query"),
    max_results: int = Query(10, ge=1, le=100, description="Maximum tweets to return")
):
    """Search tweets with caching and rate limit handling.

    Args:
        query: Search query string
        max_results: Maximum tweets to return (1-100)

    Returns:
        Search results with caching information
    """
    try:
        result = twitter_client.search_tweets(query=query, max_results=max_results)
        # Build response ensuring it matches model
        tweets = [Tweet(**tweet) if isinstance(tweet, dict) else tweet for tweet in result.get("tweets", [])]
        return TwitterSearchResponse(
            source=result.get("source"),
            query=result.get("query"),
            tweets=tweets,
            timestamp=result.get("timestamp"),
            note=result.get("note"),
            error=result.get("error")
        )
    except Exception as e:
        logger.error(f"Error searching Twitter: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/twitter/trending", response_model=TwitterTrendingResponse)
async def get_trending(location: str = Query("worldwide", description="Location code")):
    """Get trending topics by location.

    Args:
        location: Location code (e.g., 'worldwide', 'us', 'uk', 'india', 'japan')

    Returns:
        Trending topics with caching information
    """
    try:
        result = twitter_client.get_trending_topics(location=location)
        return TwitterTrendingResponse(
            source=result.get("source"),
            location=result.get("location"),
            topics=result.get("topics", []),
            timestamp=result.get("timestamp"),
            note=result.get("note")
        )
    except Exception as e:
        logger.error(f"Error fetching trending topics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/twitter/timeline", response_model=TwitterTimelineResponse)
async def get_timeline(
    username: str = Query(..., description="Twitter username"),
    max_results: int = Query(10, ge=1, le=100, description="Maximum tweets to return")
):
    """Get user timeline with caching.

    Args:
        username: Twitter username (without @)
        max_results: Maximum tweets to return (1-100)

    Returns:
        User's tweets with caching information
    """
    try:
        result = twitter_client.get_user_timeline(username=username, max_results=max_results)
        tweets = [Tweet(**tweet) if isinstance(tweet, dict) else tweet for tweet in result.get("tweets", [])]
        return TwitterTimelineResponse(
            source=result.get("source"),
            username=result.get("username"),
            tweets=tweets,
            timestamp=result.get("timestamp"),
            note=result.get("note"),
            error=result.get("error")
        )
    except Exception as e:
        logger.error(f"Error fetching timeline: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/twitter/cache/stats", response_model=CacheStatsResponse)
async def get_twitter_cache_stats():
    """Get Twitter cache statistics."""
    return CacheStatsResponse(**twitter_cache.get_cache_stats())


@app.delete("/twitter/cache/clear")
async def clear_twitter_cache(key: Optional[str] = Query(None, description="Specific key to clear")):
    """Clear Twitter cache.

    Args:
        key: Optional specific key to clear. If not provided, clears all.

    Returns:
        Status message
    """
    twitter_cache.clear(key=key)
    return {
        "message": f"Twitter cache cleared: {key or 'all'}",
        "timestamp": __import__('datetime').datetime.utcnow().isoformat()
    }


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Trend Discovery Agent",
        "version": "0.2.0",
        "docs": "/docs",
        "endpoints": {
            "health": "/health",
            "google_trends": {
                "trending_searches": "/trends/trending?region=UNITED_STATES",
                "trending_searches_multi": "/trends/trending-multi?regions=UNITED_STATES,INDIA",
                "interest_over_time": "/trends/interest?keywords=python,javascript&timeframe=now 7-d",
                "cache_stats": "/cache/stats",
                "cache_clear": "/cache/clear",
                "cache_cleanup": "/cache/cleanup"
            },
            "twitter": {
                "search": "/twitter/search?query=python&max_results=10",
                "trending": "/twitter/trending?location=worldwide",
                "timeline": "/twitter/timeline?username=elonmusk&max_results=10",
                "cache_stats": "/twitter/cache/stats",
                "cache_clear": "/twitter/cache/clear"
            }
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
