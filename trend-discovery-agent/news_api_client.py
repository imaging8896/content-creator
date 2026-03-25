"""NewsAPI client with caching and rate limiting."""
import logging
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
import requests
from cache_manager import CacheManager
from rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class NewsAPIClient:
    """Client for NewsAPI integration with caching and rate limiting."""

    # API endpoint
    BASE_URL = "https://newsapi.org/v2"

    # Cache keys
    CACHE_KEY_SEARCH = "newsapi:search:{query}"
    CACHE_KEY_TOP_HEADLINES = "newsapi:top_headlines:{country}"
    CACHE_KEY_EVERYTHING = "newsapi:everything:{query}"

    # Rate limit constants
    MAX_RETRIES = 3
    INITIAL_RETRY_DELAY = 1  # seconds

    def __init__(
        self,
        api_key: Optional[str] = None,
        cache_manager: Optional[CacheManager] = None,
        rate_limiter: Optional[RateLimiter] = None,
        cache_ttl_hours: int = 1
    ):
        """Initialize NewsAPI client.

        Args:
            api_key: NewsAPI key. If not provided, reads from NEWSAPI_KEY env var.
            cache_manager: CacheManager instance. Creates one if not provided.
            rate_limiter: RateLimiter instance. Creates one if not provided.
            cache_ttl_hours: TTL for cache entries in hours
        """
        self.api_key = api_key or os.getenv("NEWSAPI_KEY")
        if not self.api_key:
            logger.warning("NewsAPI key not provided or found in environment")

        self.cache_manager = cache_manager or CacheManager(
            db_path="cache/newsapi.db", ttl_hours=cache_ttl_hours
        )
        self.rate_limiter = rate_limiter or RateLimiter(custom_limits={"newsapi": 100})
        self.session = requests.Session()

    def _make_request(
        self,
        endpoint: str,
        params: Dict[str, Any],
        retry_count: int = 0
    ) -> Optional[Dict[str, Any]]:
        """Make API request with retry logic and rate limiting.

        Args:
            endpoint: API endpoint (e.g., 'top-headlines', 'everything')
            params: Query parameters
            retry_count: Current retry attempt

        Returns:
            API response or None if failed
        """
        # Check rate limit
        if not self.rate_limiter.is_allowed("newsapi"):
            logger.warning("NewsAPI rate limit reached")
            return None

        try:
            # Add API key to params
            params["apiKey"] = self.api_key
            url = f"{self.BASE_URL}/{endpoint}"

            logger.debug(f"Making request to {endpoint} with params: {params}")
            response = self.session.get(url, params=params, timeout=10)

            # Check for rate limit error
            if response.status_code == 429:
                logger.warning(f"Rate limited by NewsAPI (HTTP 429)")
                if retry_count < self.MAX_RETRIES:
                    wait_time = 2 ** retry_count  # Exponential backoff
                    logger.info(f"Retrying after {wait_time} seconds...")
                    import time
                    time.sleep(wait_time)
                    return self._make_request(endpoint, params, retry_count + 1)
                return None

            # Check for other errors
            if response.status_code != 200:
                logger.error(f"NewsAPI error {response.status_code}: {response.text}")
                return None

            data = response.json()

            # Check for API error response
            if data.get("status") != "ok":
                logger.error(f"NewsAPI returned error: {data.get('message')}")
                return None

            return data

        except requests.RequestException as e:
            logger.error(f"Request error: {e}")
            if retry_count < self.MAX_RETRIES:
                wait_time = 2 ** retry_count
                import time
                time.sleep(wait_time)
                return self._make_request(endpoint, params, retry_count + 1)
            return None
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return None

    def search_news(
        self,
        query: str,
        language: str = "en",
        sort_by: str = "publishedAt",
        page_size: int = 10
    ) -> Dict[str, Any]:
        """Search news articles.

        Args:
            query: Search query
            language: Language code (e.g., 'en')
            sort_by: Sort order ('relevancy', 'publishedAt', 'popularity')
            page_size: Number of articles to return (max 100)

        Returns:
            Dictionary with articles and metadata
        """
        cache_key = self.CACHE_KEY_SEARCH.format(query=query)

        # Try cache first
        cached = self.cache_manager.get(cache_key)
        if cached is not None:
            logger.info(f"Returning cached search results for '{query}'")
            return {
                "source": "cache",
                "query": query,
                "articles": cached["articles"],
                "total_results": len(cached["articles"]),
                "timestamp": cached["timestamp"],
                "note": "Data from cache"
            }

        # Make API request
        params = {
            "q": query,
            "language": language,
            "sortBy": sort_by,
            "pageSize": min(page_size, 100),  # API max is 100
        }

        data = self._make_request("everything", params)

        if data:
            # Cache results
            cache_data = {
                "articles": data.get("articles", []),
                "timestamp": datetime.utcnow().isoformat()
            }
            self.cache_manager.set(cache_key, cache_data)

            logger.info(f"Found {len(data.get('articles', []))} articles for '{query}'")
            return {
                "source": "api",
                "query": query,
                "articles": data.get("articles", []),
                "total_results": data.get("totalResults", 0),
                "timestamp": cache_data["timestamp"],
                "note": "Fresh data from NewsAPI"
            }

        # Fallback to expired cache
        expired = self.cache_manager.get(cache_key, allow_expired=True)
        if expired is not None:
            logger.info(f"Returning expired cache fallback for '{query}'")
            return {
                "source": "cache_fallback",
                "query": query,
                "articles": expired["articles"],
                "total_results": len(expired["articles"]),
                "timestamp": expired["timestamp"],
                "note": "Data from expired cache (API unavailable)"
            }

        logger.error(f"Failed to fetch articles for '{query}'")
        return {
            "source": "error",
            "query": query,
            "articles": [],
            "total_results": 0,
            "timestamp": datetime.utcnow().isoformat(),
            "error": "Failed to fetch articles from NewsAPI"
        }

    def get_top_headlines(
        self,
        country: str = "us",
        category: Optional[str] = None,
        page_size: int = 10
    ) -> Dict[str, Any]:
        """Get top headlines by country.

        Args:
            country: Country code (e.g., 'us', 'in', 'gb')
            category: News category (e.g., 'business', 'technology', 'entertainment')
            page_size: Number of articles to return

        Returns:
            Dictionary with articles and metadata
        """
        cache_key = self.CACHE_KEY_TOP_HEADLINES.format(country=country)

        # Try cache first
        cached = self.cache_manager.get(cache_key)
        if cached is not None:
            logger.info(f"Returning cached top headlines for {country}")
            return {
                "source": "cache",
                "country": country,
                "articles": cached["articles"],
                "timestamp": cached["timestamp"],
                "note": "Data from cache"
            }

        # Make API request
        params = {
            "country": country,
            "pageSize": min(page_size, 100),
        }
        if category:
            params["category"] = category

        data = self._make_request("top-headlines", params)

        if data:
            # Cache results
            cache_data = {
                "articles": data.get("articles", []),
                "timestamp": datetime.utcnow().isoformat()
            }
            self.cache_manager.set(cache_key, cache_data)

            logger.info(f"Found {len(data.get('articles', []))} top headlines for {country}")
            return {
                "source": "api",
                "country": country,
                "articles": data.get("articles", []),
                "timestamp": cache_data["timestamp"],
                "note": "Fresh data from NewsAPI"
            }

        # Fallback to expired cache
        expired = self.cache_manager.get(cache_key, allow_expired=True)
        if expired is not None:
            logger.info(f"Returning expired cache fallback for top headlines")
            return {
                "source": "cache_fallback",
                "country": country,
                "articles": expired["articles"],
                "timestamp": expired["timestamp"],
                "note": "Data from expired cache (API unavailable)"
            }

        logger.error(f"Failed to fetch top headlines for {country}")
        return {
            "source": "error",
            "country": country,
            "articles": [],
            "timestamp": datetime.utcnow().isoformat(),
            "error": "Failed to fetch headlines from NewsAPI"
        }

    def get_rate_limit_status(self) -> Dict[str, Any]:
        """Get current rate limit status.

        Returns:
            Dictionary with rate limit information
        """
        status = self.rate_limiter.get_status("newsapi")
        return {
            "available_requests": int(status["available"]),
            "capacity": int(status["capacity"]),
            "refill_rate": f"{status['refill_rate']:.4f} requests/second",
            "daily_limit": 100,
            "note": "NewsAPI free tier allows 100 requests per day"
        }
