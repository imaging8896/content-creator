"""FastAPI application for trend discovery agent."""
import logging
import os
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from google_trends_client import GoogleTrendsClient
from twitter_client import TwitterClient
from cache_manager import CacheManager
from news_api_client import NewsAPIClient
from rate_limiter import RateLimiter
from scoring_algorithm import (
    ScoringAlgorithm,
    TrendScore,
    create_tech_scorer,
    create_entertainment_scorer,
    create_business_scorer,
    create_default_scorer,
)
from trend_database import TrendDatabase
from batch_pipeline import BatchPipeline

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

# Mount static files for dashboard
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Initialize clients
cache_manager = CacheManager(db_path="cache/trends.db", ttl_hours=1)
trends_client = GoogleTrendsClient(cache_manager=cache_manager)

# Separate cache for Twitter to avoid key conflicts
twitter_cache = CacheManager(db_path="cache/twitter.db", ttl_hours=1)
twitter_client = TwitterClient(cache_manager=twitter_cache)

# Initialize rate limiter and NewsAPI client
rate_limiter = RateLimiter()
news_cache = CacheManager(db_path="cache/newsapi.db", ttl_hours=3)
news_client = NewsAPIClient(cache_manager=news_cache, rate_limiter=rate_limiter)

# Initialize scoring algorithms
tech_scorer = create_tech_scorer()
entertainment_scorer = create_entertainment_scorer()
business_scorer = create_business_scorer()
default_scorer = create_default_scorer()

# Map of scorer types
SCORERS = {
    "tech": tech_scorer,
    "entertainment": entertainment_scorer,
    "business": business_scorer,
    "default": default_scorer,
}

# Initialize database
trend_db = TrendDatabase(db_path="sqlite:///data/trends.db")

# Initialize batch pipeline
batch_pipeline = BatchPipeline(
    db=trend_db,
    google_trends_client=trends_client,
    twitter_client=twitter_client,
    default_scorer=default_scorer,
    tech_scorer=tech_scorer,
)

# Initialize scheduler for batch jobs
scheduler = BackgroundScheduler()
scheduler_started = False


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


class ScoredTrendResponse(BaseModel):
    """Response model for a single scored trend."""
    trend: str
    relevance_score: float
    velocity_score: float
    audience_score: float
    overall_score: float
    rank: int
    component_scores: Dict[str, float]


class TrendsScoresResponse(BaseModel):
    """Response model for multiple scored trends."""
    scorer_type: str
    trends_count: int
    scored_trends: List[ScoredTrendResponse]
    timestamp: str


# NewsAPI models
class NewsArticle(BaseModel):
    """News article object."""
    title: str
    description: Optional[str] = None
    url: str
    urlToImage: Optional[str] = None
    publishedAt: str
    source: Optional[Dict[str, str]] = None
    content: Optional[str] = None
    author: Optional[str] = None


class NewsSearchResponse(BaseModel):
    """Response model for news search."""
    source: str  # 'api', 'cache', 'cache_fallback', 'error'
    query: str
    articles: List[NewsArticle]
    total_results: int
    timestamp: str
    note: Optional[str] = None
    error: Optional[str] = None


class TopHeadlinesResponse(BaseModel):
    """Response model for top headlines."""
    source: str
    country: str
    articles: List[NewsArticle]
    timestamp: str
    note: Optional[str] = None
    error: Optional[str] = None


class TrendWithNewsResponse(BaseModel):
    """Response model for trend with related news articles."""
    trend: str
    overall_score: float
    articles_count: int
    articles: List[NewsArticle]
    timestamp: str


class RateLimitStatusResponse(BaseModel):
    """Response model for rate limit status."""
    available_requests: int
    capacity: int
    refill_rate: str
    daily_limit: int
    note: str


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


# NewsAPI research endpoints
@app.get("/research/search", response_model=NewsSearchResponse)
async def search_news(
    keyword: str = Query(..., description="Search keyword or query"),
    sort_by: str = Query("publishedAt", description="Sort by: 'relevancy', 'publishedAt', 'popularity'"),
    limit: int = Query(10, ge=1, le=100, description="Number of articles to return")
):
    """Search for news articles about a keyword.

    Args:
        keyword: Search keyword or query
        sort_by: Sort order for results
        limit: Number of articles to return

    Returns:
        News articles matching the keyword with caching information
    """
    try:
        result = news_client.search_news(query=keyword, sort_by=sort_by, page_size=limit)
        articles = [NewsArticle(**article) if isinstance(article, dict) else article
                   for article in result.get("articles", [])]
        return NewsSearchResponse(
            source=result.get("source"),
            query=keyword,
            articles=articles,
            total_results=result.get("total_results", 0),
            timestamp=result.get("timestamp"),
            note=result.get("note"),
            error=result.get("error")
        )
    except Exception as e:
        logger.error(f"Error searching news: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/research/trending", response_model=TopHeadlinesResponse)
async def get_trending_news(
    country: str = Query("us", description="Country code (e.g., 'us', 'in', 'gb')"),
    category: Optional[str] = Query(None, description="Category: business, entertainment, general, health, science, sports, technology"),
    limit: int = Query(10, ge=1, le=100, description="Number of articles to return")
):
    """Get trending news and top headlines.

    Args:
        country: Country code for headlines
        category: News category to filter by
        limit: Number of articles to return

    Returns:
        Top headlines for the country with caching information
    """
    try:
        result = news_client.get_top_headlines(country=country, category=category, page_size=limit)
        articles = [NewsArticle(**article) if isinstance(article, dict) else article
                   for article in result.get("articles", [])]
        return TopHeadlinesResponse(
            source=result.get("source"),
            country=country,
            articles=articles,
            timestamp=result.get("timestamp"),
            note=result.get("note"),
            error=result.get("error")
        )
    except Exception as e:
        logger.error(f"Error fetching trending news: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/research/trend-news", response_model=NewsSearchResponse)
async def get_trend_news(
    trend: str = Query(..., description="Trend to find news articles about"),
    limit: int = Query(10, ge=1, le=100, description="Number of articles to return")
):
    """Get news articles related to a specific trend.

    Searches for recent articles about the given trend to provide fact-checking
    and research context for trending topics.

    Args:
        trend: Trend name to search for
        limit: Number of articles to return

    Returns:
        News articles about the trend
    """
    try:
        result = news_client.search_news(query=trend, sort_by="publishedAt", page_size=limit)
        articles = [NewsArticle(**article) if isinstance(article, dict) else article
                   for article in result.get("articles", [])]
        return NewsSearchResponse(
            source=result.get("source"),
            query=trend,
            articles=articles,
            total_results=result.get("total_results", 0),
            timestamp=result.get("timestamp"),
            note=result.get("note"),
            error=result.get("error")
        )
    except Exception as e:
        logger.error(f"Error fetching trend news: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/research/rate-limit", response_model=RateLimitStatusResponse)
async def get_rate_limit_status():
    """Get current rate limit status for NewsAPI.

    Returns:
        Rate limit information including available requests and daily limit
    """
    try:
        status = news_client.get_rate_limit_status()
        return RateLimitStatusResponse(**status)
    except Exception as e:
        logger.error(f"Error getting rate limit status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/research/cache/stats", response_model=CacheStatsResponse)
async def get_news_cache_stats():
    """Get NewsAPI cache statistics."""
    return CacheStatsResponse(**news_cache.get_cache_stats())


@app.delete("/research/cache/clear")
async def clear_news_cache(key: Optional[str] = Query(None, description="Specific key to clear")):
    """Clear NewsAPI cache.

    Args:
        key: Optional specific key to clear. If not provided, clears all.

    Returns:
        Status message
    """
    news_cache.clear(key=key)
    return {
        "message": f"News cache cleared: {key or 'all'}",
        "timestamp": __import__('datetime').datetime.utcnow().isoformat()
    }


# Scoring endpoints
@app.post("/score/trends", response_model=TrendsScoresResponse)
async def score_trends(
    trends: List[str] = Query(..., description="List of trend strings to score"),
    scorer_type: str = Query("default", description="Scorer type: 'tech', 'entertainment', 'business', 'default'"),
    metadata: Optional[str] = Query(None, description="Optional JSON metadata for trends"),
):
    """Score a list of trends using specified scorer.

    Args:
        trends: List of trend strings to score
        scorer_type: Type of scorer to use
        metadata: Optional JSON metadata containing metrics per trend

    Returns:
        Scored trends with ranks
    """
    try:
        import json
        from datetime import datetime

        # Get the appropriate scorer
        scorer = SCORERS.get(scorer_type, default_scorer)

        # Parse metadata if provided
        trend_metadata = {}
        if metadata:
            try:
                trend_metadata = json.loads(metadata)
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON metadata: {metadata}")

        # Score the trends
        scored_trends = scorer.score_trends(trends, metadata=trend_metadata)

        # Convert to response format
        response_trends = [
            ScoredTrendResponse(
                trend=st.trend,
                relevance_score=round(st.relevance_score, 2),
                velocity_score=round(st.velocity_score, 2),
                audience_score=round(st.audience_score, 2),
                overall_score=round(st.overall_score, 2),
                rank=st.rank,
                component_scores={
                    k: round(v, 2) for k, v in st.component_scores.items()
                },
            )
            for st in scored_trends
        ]

        return TrendsScoresResponse(
            scorer_type=scorer_type,
            trends_count=len(trends),
            scored_trends=response_trends,
            timestamp=datetime.utcnow().isoformat(),
        )

    except Exception as e:
        logger.error(f"Error scoring trends: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/score/scorers", response_model=Dict[str, str])
async def list_scorers():
    """List available scorers and their descriptions.

    Returns:
        Dictionary of scorer types and descriptions
    """
    return {
        "tech": "Optimized for technology and programming trends",
        "entertainment": "Optimized for entertainment, celebrity, and media trends",
        "business": "Optimized for business, finance, and startup trends",
        "default": "General-purpose scorer with no specific optimizations",
    }


@app.post("/score/trend", response_model=ScoredTrendResponse)
async def score_single_trend(
    trend: str = Query(..., description="Trend string to score"),
    scorer_type: str = Query("default", description="Scorer type"),
    position: int = Query(0, description="Position in trending list"),
    metadata: Optional[str] = Query(None, description="Optional JSON metadata"),
):
    """Score a single trend.

    Args:
        trend: Trend string to score
        scorer_type: Type of scorer to use
        position: Position in trending list (impacts velocity score)
        metadata: Optional JSON metadata with metrics

    Returns:
        Scored trend with component scores
    """
    try:
        import json
        from datetime import datetime

        # Get the appropriate scorer
        scorer = SCORERS.get(scorer_type, default_scorer)

        # Parse metadata if provided
        trend_metadata = {}
        if metadata:
            try:
                trend_metadata = json.loads(metadata)
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON metadata: {metadata}")

        # Score the single trend
        scored = scorer.score_single_trend(
            trend, position=position, metadata=trend_metadata
        )

        return ScoredTrendResponse(
            trend=scored.trend,
            relevance_score=round(scored.relevance_score, 2),
            velocity_score=round(scored.velocity_score, 2),
            audience_score=round(scored.audience_score, 2),
            overall_score=round(scored.overall_score, 2),
            rank=scored.rank,
            component_scores={
                k: round(v, 2) for k, v in scored.component_scores.items()
            },
        )

    except Exception as e:
        logger.error(f"Error scoring trend: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Batch pipeline endpoints and scheduling
class BatchStatusResponse(BaseModel):
    """Response model for batch status."""
    scheduler_running: bool
    next_run: Optional[str] = None
    last_run: Optional[str] = None
    last_run_status: Optional[str] = None
    trends_stored: Optional[int] = None


class DashboardDataResponse(BaseModel):
    """Response model for dashboard data."""
    timestamp: str
    trends_count: int
    last_run: Dict[str, Any]
    trends: List[Dict[str, Any]]


def _schedule_batch_job():
    """Initialize and schedule the batch job."""
    global scheduler_started
    if not scheduler_started and not scheduler.running:
        try:
            # Schedule batch pipeline to run every hour at minute 0
            scheduler.add_job(
                batch_pipeline.run_batch,
                trigger=CronTrigger(minute=0),  # Run at the top of every hour
                id="hourly_batch_pipeline",
                name="Hourly Trend Discovery Batch Pipeline",
                misfire_grace_time=10,
                max_instances=1,  # Ensure only one instance runs at a time
            )
            scheduler.start()
            scheduler_started = True
            logger.info("Batch scheduler started - running at top of every hour")
        except Exception as e:
            logger.error(f"Failed to start batch scheduler: {e}")


@app.on_event("startup")
async def startup_event():
    """Initialize scheduler on app startup."""
    logger.info("Trend Discovery Agent starting up...")
    _schedule_batch_job()


@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown scheduler on app shutdown."""
    global scheduler_started
    logger.info("Trend Discovery Agent shutting down...")
    if scheduler.running:
        scheduler.shutdown()
        scheduler_started = False
        logger.info("Batch scheduler stopped")


@app.post("/batch/run", response_model=Dict[str, str])
async def run_batch_now():
    """Manually trigger batch pipeline execution.

    Returns:
        Status message with batch run info
    """
    try:
        logger.info("Manual batch trigger requested")
        success = batch_pipeline.run_batch()
        return {
            "status": "completed" if success else "failed",
            "message": "Batch pipeline executed" if success else "Batch pipeline failed",
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error running batch: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/batch/status", response_model=BatchStatusResponse)
async def get_batch_status():
    """Get batch pipeline status.

    Returns:
        Current batch scheduler status
    """
    try:
        session = trend_db.get_session()
        latest_run = trend_db.get_latest_batch_run(session)
        session.close()

        next_run_time = None
        if scheduler.running:
            jobs = scheduler.get_jobs()
            if jobs:
                next_run_time = jobs[0].next_run_time.isoformat() if jobs[0].next_run_time else None

        return BatchStatusResponse(
            scheduler_running=scheduler.running,
            next_run=next_run_time,
            last_run=latest_run.completed_at.isoformat() if latest_run and latest_run.completed_at else None,
            last_run_status=latest_run.status if latest_run else None,
            trends_stored=latest_run.trends_stored if latest_run else None,
        )
    except Exception as e:
        logger.error(f"Error getting batch status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/dashboard", response_model=DashboardDataResponse)
async def get_dashboard_data(limit: int = Query(20, ge=1, le=100)):
    """Get formatted dashboard data with top trends.

    Args:
        limit: Number of top trends to return (1-100)

    Returns:
        Dashboard data including top trends and metadata
    """
    try:
        data = batch_pipeline.get_dashboard_data(limit=limit, hours=24)
        return DashboardDataResponse(**data)
    except Exception as e:
        logger.error(f"Error getting dashboard data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/batch/cleanup")
async def cleanup_old_data(days_to_keep: int = Query(30, ge=1)):
    """Clean up old trend results from database.

    Args:
        days_to_keep: Number of days of data to retain (minimum 1)

    Returns:
        Number of records deleted
    """
    try:
        deleted = batch_pipeline.cleanup_old_data(days_to_keep)
        return {
            "deleted_count": deleted,
            "days_retained": days_to_keep,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error cleaning up data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Add datetime import for startup/shutdown handlers
from datetime import datetime  # noqa: E402


# Dashboard UI endpoint
@app.get("/dashboard-ui")
async def get_dashboard_ui():
    """Serve the dashboard HTML interface."""
    dashboard_path = os.path.join(os.path.dirname(__file__), "static", "dashboard.html")
    if os.path.exists(dashboard_path):
        return FileResponse(dashboard_path, media_type="text/html")
    else:
        raise HTTPException(status_code=404, detail="Dashboard UI not found")


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Trend Discovery Agent",
        "version": "0.4.0",
        "docs": "/docs",
        "description": "Complete trend discovery, scoring, and batch pipeline system",
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
            },
            "research": {
                "description": "Research and fact-checking APIs powered by NewsAPI",
                "search": "/research/search?keyword=python&limit=10",
                "trending_news": "/research/trending?country=us&limit=10",
                "trend_news": "/research/trend-news?trend=Python&limit=10",
                "rate_limit": "/research/rate-limit",
                "cache_stats": "/research/cache/stats",
                "cache_clear": "/research/cache/clear"
            },
            "scoring": {
                "list_scorers": "/score/scorers",
                "score_single": "/score/trend?trend=Python&scorer_type=tech",
                "score_multiple": "/score/trends?trends=Python&trends=JavaScript&scorer_type=tech"
            },
            "batch_pipeline": {
                "description": "Hourly batch processing for trend discovery and storage",
                "run_now": "POST /batch/run",
                "status": "GET /batch/status",
                "cleanup": "DELETE /batch/cleanup?days_to_keep=30"
            },
            "dashboard": {
                "description": "Dashboard data with top trends",
                "data": "GET /dashboard?limit=20"
            }
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
