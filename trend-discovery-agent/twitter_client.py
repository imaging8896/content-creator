"""Twitter/X API client with rate limit handling, retries, and caching."""
import logging
import os
import time
from typing import List, Dict, Any, Optional
from datetime import datetime
from cache_manager import CacheManager

try:
    import tweepy
    HAS_TWEEPY = True
except ImportError:
    HAS_TWEEPY = False
    # Create placeholder exception classes for when tweepy is not available
    class TooManyRequests(Exception):
        """Placeholder for tweepy.TooManyRequests."""
        pass

logger = logging.getLogger(__name__)


class TwitterClient:
    """Client for Twitter/X API with rate limit handling, retries, and caching."""

    # Cache keys
    CACHE_KEY_TRENDING = "twitter:trending:{location}"
    CACHE_KEY_SEARCH = "twitter:search:{query}"

    # Rate limit constants
    MAX_RETRIES = 3
    INITIAL_RETRY_DELAY = 1  # seconds
    RATE_LIMIT_RETRY_DELAY = 60  # seconds (for 429 errors)

    def __init__(
        self,
        bearer_token: Optional[str] = None,
        cache_manager: Optional[CacheManager] = None,
        cache_ttl_hours: int = 1
    ):
        """Initialize Twitter/X API client.

        Args:
            bearer_token: Twitter/X API Bearer Token. If not provided, reads from TWITTER_BEARER_TOKEN env var.
            cache_manager: CacheManager instance. Creates one if not provided.
            cache_ttl_hours: TTL for cache entries in hours
        """
        self.bearer_token = bearer_token or os.getenv("TWITTER_BEARER_TOKEN")
        if not self.bearer_token:
            logger.warning("Twitter Bearer Token not provided or found in environment")

        self.cache_manager = cache_manager or CacheManager(ttl_hours=cache_ttl_hours)
        self._client = None
        self._rate_limit_reset_time = {}

    def _get_client(self):
        """Get or create Twitter/X API client.

        Returns:
            tweepy.Client instance or None if tweepy not available
        """
        if self._client is None and self.bearer_token and HAS_TWEEPY:
            self._client = tweepy.Client(bearer_token=self.bearer_token, wait_on_rate_limit=False)
        return self._client

    def _handle_rate_limit(self, endpoint: str) -> None:
        """Handle rate limit by waiting if necessary.

        Args:
            endpoint: API endpoint identifier
        """
        if endpoint in self._rate_limit_reset_time:
            reset_time = self._rate_limit_reset_time[endpoint]
            wait_time = reset_time - time.time()
            if wait_time > 0:
                logger.warning(f"Rate limited on {endpoint}. Waiting {wait_time:.1f} seconds...")
                time.sleep(wait_time)

    def _retry_with_backoff(self, func, *args, endpoint: str = "unknown", **kwargs):
        """Execute function with exponential backoff retry logic.

        Args:
            func: Function to execute
            endpoint: API endpoint identifier for rate limit tracking
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Function result or None if all retries fail
        """
        retry_delay = self.INITIAL_RETRY_DELAY

        for attempt in range(self.MAX_RETRIES):
            try:
                self._handle_rate_limit(endpoint)
                return func(*args, **kwargs)

            except Exception as e:
                # Check if it's a rate limit error
                is_rate_limit = False
                if HAS_TWEEPY and isinstance(e, tweepy.TooManyRequests):
                    is_rate_limit = True
                    # Try to extract reset time from response headers
                    if hasattr(e, 'response') and hasattr(e.response, 'headers'):
                        reset_time_str = e.response.headers.get('x-rate-limit-reset')
                        if reset_time_str:
                            self._rate_limit_reset_time[endpoint] = int(reset_time_str)

                if is_rate_limit:
                    logger.warning(f"Rate limit hit on {endpoint}: {e}")
                    if attempt < self.MAX_RETRIES - 1:
                        time.sleep(self.RATE_LIMIT_RETRY_DELAY)
                        continue
                    else:
                        logger.error(f"Rate limit exceeded on {endpoint} after {attempt + 1} attempts")
                        return None
                else:
                    logger.warning(f"Error on {endpoint} (attempt {attempt + 1}/{self.MAX_RETRIES}): {e}")
                    if attempt < self.MAX_RETRIES - 1:
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                    else:
                        logger.error(f"Failed after {self.MAX_RETRIES} retries: {e}")
                        return None

    def search_tweets(
        self,
        query: str,
        max_results: int = 10,
        tweet_fields: List[str] = None,
    ) -> Dict[str, Any]:
        """Search for tweets with caching and retry logic.

        Args:
            query: Search query string
            max_results: Maximum tweets to return
            tweet_fields: Fields to include in response

        Returns:
            Dictionary with tweets and metadata
        """
        cache_key = self.CACHE_KEY_SEARCH.format(query=query)

        # Try cache first
        cached = self.cache_manager.get(cache_key)
        if cached is not None:
            logger.info(f"Returning cached search results for '{query}'")
            return {
                "source": "cache",
                "query": query,
                "tweets": cached["tweets"],
                "timestamp": cached["timestamp"],
                "note": "Data from cache"
            }

        if not self._get_client():
            logger.error("Twitter API client not configured")
            return {
                "source": "error",
                "query": query,
                "tweets": [],
                "timestamp": datetime.utcnow().isoformat(),
                "error": "Twitter API client not configured"
            }

        # Try to fetch fresh data
        try:
            logger.info(f"Searching tweets for '{query}'")
            if tweet_fields is None:
                tweet_fields = ["created_at", "public_metrics", "author_id"]

            def do_search():
                response = self._client.search_recent_tweets(
                    query=query,
                    max_results=max_results,
                    tweet_fields=tweet_fields,
                )
                return response

            result = self._retry_with_backoff(do_search, endpoint="search_recent_tweets")

            if result and result.data:
                tweets_list = [
                    {
                        "id": tweet.id,
                        "text": tweet.text,
                        "created_at": tweet.created_at.isoformat() if hasattr(tweet.created_at, 'isoformat') else str(tweet.created_at),
                        "metrics": tweet.public_metrics if hasattr(tweet, 'public_metrics') else {}
                    }
                    for tweet in result.data
                ]

                # Cache the results
                cache_data = {
                    "tweets": tweets_list,
                    "timestamp": datetime.utcnow().isoformat()
                }
                self.cache_manager.set(cache_key, cache_data)

                logger.info(f"Successfully fetched {len(tweets_list)} tweets for '{query}'")
                return {
                    "source": "api",
                    "query": query,
                    "tweets": tweets_list,
                    "timestamp": cache_data["timestamp"],
                    "note": "Fresh data from Twitter API"
                }
            else:
                logger.warning(f"No tweets found for query: '{query}'")
                return {
                    "source": "api",
                    "query": query,
                    "tweets": [],
                    "timestamp": datetime.utcnow().isoformat(),
                    "note": "No tweets found"
                }

        except Exception as e:
            logger.warning(f"Failed to fetch tweets for '{query}': {e}")
            # Try expired cache as fallback
            expired = self.cache_manager.get(cache_key, allow_expired=True)
            if expired is not None:
                logger.info(f"Returning expired cache fallback for '{query}'")
                return {
                    "source": "cache_fallback",
                    "query": query,
                    "tweets": expired["tweets"],
                    "timestamp": expired["timestamp"],
                    "note": "Data from expired cache (API unavailable)",
                    "error": str(e)
                }

            logger.error(f"No data available for '{query}' (API failed and no cache)")
            return {
                "source": "error",
                "query": query,
                "tweets": [],
                "timestamp": datetime.utcnow().isoformat(),
                "note": "Unable to fetch tweets",
                "error": str(e)
            }

    def get_trending_topics(self, location: str = "worldwide") -> Dict[str, Any]:
        """Get trending topics (simulated with search fallback).

        Note: Twitter v2 API doesn't have direct trending endpoint.
        This uses common trend keywords as a fallback.

        Args:
            location: Location for trends (e.g., 'worldwide', 'us', 'uk')

        Returns:
            Dictionary with trending topics
        """
        cache_key = self.CACHE_KEY_TRENDING.format(location=location)

        # Try cache first
        cached = self.cache_manager.get(cache_key)
        if cached is not None:
            logger.info(f"Returning cached trending topics for {location}")
            return {
                "source": "cache",
                "location": location,
                "topics": cached["topics"],
                "timestamp": cached["timestamp"],
                "note": "Data from cache"
            }

        # Default trending keywords by location
        trending_keywords = {
            "worldwide": ["AI", "technology", "crypto", "news", "trending"],
            "us": ["USA", "tech", "politics", "sports", "entertainment"],
            "uk": ["UK", "business", "tech", "football", "politics"],
            "india": ["India", "tech", "cricket", "Bollywood", "startups"],
            "japan": ["日本", "tech", "anime", "gaming", "news"],
        }

        topics = trending_keywords.get(location.lower(), trending_keywords["worldwide"])

        cache_data = {
            "topics": topics,
            "timestamp": datetime.utcnow().isoformat()
        }
        self.cache_manager.set(cache_key, cache_data)

        return {
            "source": "static",
            "location": location,
            "topics": topics,
            "timestamp": cache_data["timestamp"],
            "note": "Default trending topics (Twitter v2 API doesn't provide direct trending endpoint)"
        }

    def get_user_timeline(
        self,
        username: str,
        max_results: int = 10,
        tweet_fields: List[str] = None,
    ) -> Dict[str, Any]:
        """Get tweets from a user's timeline with caching.

        Args:
            username: Twitter username
            max_results: Maximum tweets to return
            tweet_fields: Fields to include in response

        Returns:
            Dictionary with tweets and metadata
        """
        cache_key = f"twitter:timeline:{username}"

        # Try cache first
        cached = self.cache_manager.get(cache_key)
        if cached is not None:
            logger.info(f"Returning cached timeline for @{username}")
            return {
                "source": "cache",
                "username": username,
                "tweets": cached["tweets"],
                "timestamp": cached["timestamp"],
                "note": "Data from cache"
            }

        if not self._get_client():
            logger.error("Twitter API client not configured")
            return {
                "source": "error",
                "username": username,
                "tweets": [],
                "timestamp": datetime.utcnow().isoformat(),
                "error": "Twitter API client not configured"
            }

        try:
            logger.info(f"Fetching timeline for @{username}")
            if tweet_fields is None:
                tweet_fields = ["created_at", "public_metrics"]

            def get_user():
                return self._client.get_user(username=username)

            def get_timeline(user_id):
                return self._client.get_users_tweets(
                    id=user_id,
                    max_results=max_results,
                    tweet_fields=tweet_fields,
                )

            user_result = self._retry_with_backoff(get_user, endpoint="get_user")
            if not user_result or not user_result.data:
                logger.error(f"User not found: {username}")
                return {
                    "source": "error",
                    "username": username,
                    "tweets": [],
                    "error": f"User not found: {username}"
                }

            user_id = user_result.data.id
            timeline_result = self._retry_with_backoff(
                get_timeline, user_id, endpoint="get_users_tweets"
            )

            if timeline_result and timeline_result.data:
                tweets_list = [
                    {
                        "id": tweet.id,
                        "text": tweet.text,
                        "created_at": tweet.created_at.isoformat() if hasattr(tweet.created_at, 'isoformat') else str(tweet.created_at),
                        "metrics": tweet.public_metrics if hasattr(tweet, 'public_metrics') else {}
                    }
                    for tweet in timeline_result.data
                ]

                cache_data = {
                    "tweets": tweets_list,
                    "timestamp": datetime.utcnow().isoformat()
                }
                self.cache_manager.set(cache_key, cache_data)

                logger.info(f"Successfully fetched {len(tweets_list)} tweets from @{username}")
                return {
                    "source": "api",
                    "username": username,
                    "tweets": tweets_list,
                    "timestamp": cache_data["timestamp"],
                    "note": "Fresh data from Twitter API"
                }

            return {
                "source": "api",
                "username": username,
                "tweets": [],
                "timestamp": datetime.utcnow().isoformat(),
                "note": "No tweets found"
            }

        except Exception as e:
            logger.warning(f"Failed to fetch timeline for @{username}: {e}")
            expired = self.cache_manager.get(cache_key, allow_expired=True)
            if expired is not None:
                return {
                    "source": "cache_fallback",
                    "username": username,
                    "tweets": expired["tweets"],
                    "timestamp": expired["timestamp"],
                    "error": str(e)
                }

            return {
                "source": "error",
                "username": username,
                "tweets": [],
                "error": str(e)
            }

    def get_cache_info(self) -> Dict[str, Any]:
        """Get cache statistics.

        Returns:
            Cache statistics
        """
        return self.cache_manager.get_cache_stats()

    def clear_cache(self, key: Optional[str] = None) -> None:
        """Clear cache.

        Args:
            key: Specific cache key to clear, or None for all
        """
        self.cache_manager.clear(key)
        logger.info(f"Twitter cache cleared: {key or 'all'}")
