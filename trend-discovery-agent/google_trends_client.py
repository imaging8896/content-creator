"""Google Trends API client with caching and fallback support."""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from pytrends.request import TrendReq
from cache_manager import CacheManager

logger = logging.getLogger(__name__)


class GoogleTrendsClient:
    """Client for Google Trends API with caching and fallback."""

    # Cache keys
    CACHE_KEY_TRENDING = "google_trends:trending:{region}"
    CACHE_KEY_METADATA = "google_trends:metadata"

    def __init__(self, cache_manager: Optional[CacheManager] = None, cache_ttl_hours: int = 1):
        """Initialize Google Trends client.

        Args:
            cache_manager: CacheManager instance. Creates one if not provided.
            cache_ttl_hours: TTL for cache entries in hours
        """
        self.cache_manager = cache_manager or CacheManager(ttl_hours=cache_ttl_hours)
        self.hl = "en-US"
        self.tz = 360
        self._pytrends = None

    def _get_pytrends(self) -> TrendReq:
        """Lazy load pytrends with retry logic.

        Returns:
            TrendReq instance
        """
        if self._pytrends is None:
            self._pytrends = TrendReq(hl=self.hl, tz=self.tz)
        return self._pytrends

    def get_trending_searches(self, region: str = "UNITED_STATES") -> Dict[str, Any]:
        """Get trending searches with caching.

        Args:
            region: Region code (e.g., 'UNITED_STATES', 'INDIA', 'JP')

        Returns:
            Dictionary with trends and metadata
        """
        cache_key = self.CACHE_KEY_TRENDING.format(region=region)

        # Try to get from cache first
        cached = self.cache_manager.get(cache_key)
        if cached is not None:
            logger.info(f"Returning cached trends for {region}")
            return {
                "source": "cache",
                "region": region,
                "trends": cached["trends"],
                "timestamp": cached["timestamp"],
                "note": "Data from cache"
            }

        # Try to fetch fresh data
        try:
            logger.info(f"Fetching fresh trends for {region} from Google Trends API")
            pytrends = self._get_pytrends()
            pytrends.build(hl=self.hl, tz=self.tz)

            # Get trending searches by region
            df_trends = pytrends.trending_searches(pn=region)
            trends_list = df_trends[0].tolist() if not df_trends.empty else []

            # Cache the results
            cache_data = {
                "trends": trends_list,
                "timestamp": datetime.utcnow().isoformat()
            }
            self.cache_manager.set(cache_key, cache_data)

            logger.info(f"Successfully fetched {len(trends_list)} trends for {region}")
            return {
                "source": "api",
                "region": region,
                "trends": trends_list,
                "timestamp": cache_data["timestamp"],
                "note": "Fresh data from Google Trends API"
            }

        except Exception as e:
            logger.warning(f"Failed to fetch fresh trends for {region}: {e}")
            # Try to get expired cache as fallback
            expired = self.cache_manager.get(cache_key, allow_expired=True)
            if expired is not None:
                logger.info(f"Returning expired cache fallback for {region}")
                return {
                    "source": "cache_fallback",
                    "region": region,
                    "trends": expired["trends"],
                    "timestamp": expired["timestamp"],
                    "note": "Data from expired cache (API unavailable)",
                    "error": str(e)
                }

            # No data available
            logger.error(f"No data available for {region} (API failed and no cache)")
            return {
                "source": "error",
                "region": region,
                "trends": [],
                "timestamp": datetime.utcnow().isoformat(),
                "note": "Unable to fetch trends",
                "error": str(e)
            }

    def get_trending_searches_multi_region(
        self,
        regions: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Get trending searches for multiple regions.

        Args:
            regions: List of region codes. Defaults to major regions.

        Returns:
            Dictionary mapping regions to trends
        """
        if regions is None:
            regions = ["UNITED_STATES", "INDIA", "UNITED_KINGDOM", "JAPAN", "GERMANY"]

        results = {}
        for region in regions:
            try:
                results[region] = self.get_trending_searches(region)
            except Exception as e:
                logger.error(f"Error fetching trends for {region}: {e}")
                results[region] = {
                    "source": "error",
                    "region": region,
                    "trends": [],
                    "error": str(e)
                }

        return results

    def get_interest_over_time(
        self,
        keywords: List[str],
        timeframe: str = "now 1-d"
    ) -> Dict[str, Any]:
        """Get interest over time for keywords.

        Args:
            keywords: List of keywords to track
            timeframe: Timeframe for data (e.g., 'now 1-d', 'now 7-d')

        Returns:
            Dictionary with interest over time data
        """
        cache_key = f"google_trends:interest_over_time:{':'.join(sorted(keywords))}"

        # Try cache first
        cached = self.cache_manager.get(cache_key)
        if cached is not None:
            logger.info(f"Returning cached interest data for {keywords}")
            return {
                "source": "cache",
                "keywords": keywords,
                "data": cached["data"],
                "timestamp": cached["timestamp"]
            }

        try:
            logger.info(f"Fetching interest over time for {keywords}")
            pytrends = self._get_pytrends()
            pytrends.build(hl=self.hl, tz=self.tz)
            pytrends.interest_over_time(kw_list=keywords, sleep=0.2)

            df = pytrends.interest_over_time()
            data = df.to_dict(orient="list") if not df.empty else {}

            cache_data = {
                "data": data,
                "timestamp": datetime.utcnow().isoformat()
            }
            self.cache_manager.set(cache_key, cache_data)

            return {
                "source": "api",
                "keywords": keywords,
                "data": data,
                "timestamp": cache_data["timestamp"]
            }

        except Exception as e:
            logger.warning(f"Failed to fetch interest data for {keywords}: {e}")
            # Try expired cache fallback
            expired = self.cache_manager.get(cache_key, allow_expired=True)
            if expired is not None:
                return {
                    "source": "cache_fallback",
                    "keywords": keywords,
                    "data": expired["data"],
                    "timestamp": expired["timestamp"],
                    "error": str(e)
                }

            return {
                "source": "error",
                "keywords": keywords,
                "data": {},
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
        logger.info(f"Cache cleared: {key or 'all'}")
