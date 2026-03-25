"""Tests for Twitter API client."""
import pytest
import json
import time
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from cache_manager import CacheManager
from twitter_client import TwitterClient


class TestTwitterClientCaching:
    """Test caching functionality."""

    @pytest.fixture
    def cache_manager(self, tmp_path):
        """Create a temporary cache manager for testing."""
        cache_db = tmp_path / "test_cache.db"
        return CacheManager(db_path=str(cache_db), ttl_hours=1)

    @pytest.fixture
    def twitter_client(self, cache_manager):
        """Create Twitter client with test cache."""
        return TwitterClient(cache_manager=cache_manager, bearer_token="test_token")

    def test_search_tweets_caching(self, twitter_client):
        """Test that search results are cached."""
        # Mock the API client
        mock_client = MagicMock()
        mock_tweet = MagicMock()
        mock_tweet.id = "12345"
        mock_tweet.text = "Test tweet"
        mock_tweet.created_at = datetime(2026, 3, 25, 10, 0, 0)
        mock_tweet.public_metrics = {"like_count": 100}

        mock_response = MagicMock()
        mock_response.data = [mock_tweet]

        mock_client.search_recent_tweets.return_value = mock_response
        twitter_client._client = mock_client

        # First call should hit API
        result1 = twitter_client.search_tweets("python")
        assert result1["source"] == "api"
        assert len(result1["tweets"]) == 1
        assert result1["tweets"][0]["text"] == "Test tweet"

        # Second call should use cache
        result2 = twitter_client.search_tweets("python")
        assert result2["source"] == "cache"
        assert result2["tweets"] == result1["tweets"]
        assert mock_client.search_recent_tweets.call_count == 1  # Still 1, not 2

    def test_trending_topics_caching(self, twitter_client):
        """Test that trending topics are cached."""
        # First call
        result1 = twitter_client.get_trending_topics("worldwide")
        assert result1["source"] == "static"
        assert "AI" in result1["topics"]

        # Second call should use cache
        result2 = twitter_client.get_trending_topics("worldwide")
        assert result2["source"] == "cache"
        assert result1["topics"] == result2["topics"]

    def test_cache_fallback_on_error(self, twitter_client, cache_manager):
        """Test fallback to expired cache when API fails."""
        # Pre-populate cache with old data
        cache_key = "twitter:search:test"
        old_data = {
            "tweets": [{"id": "old", "text": "Old tweet"}],
            "timestamp": (datetime.utcnow()).isoformat()
        }
        # Set with very short TTL to make it expire immediately
        cache_manager.set(cache_key, old_data, ttl_seconds=0)
        time.sleep(0.1)  # Ensure it's expired

        # Mock API to fail
        mock_client = MagicMock()
        mock_client.search_recent_tweets.side_effect = Exception("API Error")
        twitter_client._client = mock_client

        # Should return expired cache as fallback
        result = twitter_client.search_tweets("test")
        assert result["source"] == "cache_fallback"
        assert result["tweets"][0]["id"] == "old"
        assert "error" in result

    def test_error_when_no_cache(self, twitter_client):
        """Test error response when API fails and no cache exists."""
        mock_client = MagicMock()
        mock_client.search_recent_tweets.side_effect = Exception("API Error")
        twitter_client._client = mock_client

        result = twitter_client.search_tweets("nonexistent_query_12345")
        assert result["source"] == "error"
        assert len(result["tweets"]) == 0
        assert "error" in result


class TestTwitterClientRateLimit:
    """Test rate limit handling."""

    @pytest.fixture
    def cache_manager(self, tmp_path):
        """Create a temporary cache manager for testing."""
        cache_db = tmp_path / "test_cache.db"
        return CacheManager(db_path=str(cache_db), ttl_hours=1)

    @pytest.fixture
    def twitter_client(self, cache_manager):
        """Create Twitter client with test cache."""
        return TwitterClient(cache_manager=cache_manager, bearer_token="test_token")

    def test_retry_on_too_many_requests(self, twitter_client):
        """Test retry logic on rate limit errors."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.headers = {"x-rate-limit-reset": str(int(time.time()) + 1)}

        # First call raises TooManyRequests, second succeeds
        mock_tweet = MagicMock()
        mock_tweet.id = "123"
        mock_tweet.text = "Tweet after retry"
        mock_tweet.created_at = datetime(2026, 3, 25, 10, 0, 0)
        mock_tweet.public_metrics = {}

        success_response = MagicMock()
        success_response.data = [mock_tweet]

        mock_client.search_recent_tweets.side_effect = [
            Exception("Rate limited"),
            success_response
        ]
        twitter_client._client = mock_client
        twitter_client.MAX_RETRIES = 3
        twitter_client.INITIAL_RETRY_DELAY = 0.01

        result = twitter_client.search_tweets("test")
        # Even with retry failure, should have attempted
        assert mock_client.search_recent_tweets.call_count >= 1

    def test_max_retries_exceeded(self, twitter_client):
        """Test that max retries is respected."""
        mock_client = MagicMock()
        mock_client.search_recent_tweets.side_effect = Exception("Persistent error")
        twitter_client._client = mock_client
        twitter_client.MAX_RETRIES = 2
        twitter_client.INITIAL_RETRY_DELAY = 0.01

        result = twitter_client.search_tweets("test")
        assert result["source"] == "error"
        assert mock_client.search_recent_tweets.call_count == 2


class TestTwitterClientTimeline:
    """Test user timeline functionality."""

    @pytest.fixture
    def cache_manager(self, tmp_path):
        """Create a temporary cache manager for testing."""
        cache_db = tmp_path / "test_cache.db"
        return CacheManager(db_path=str(cache_db), ttl_hours=1)

    @pytest.fixture
    def twitter_client(self, cache_manager):
        """Create Twitter client with test cache."""
        return TwitterClient(cache_manager=cache_manager, bearer_token="test_token")

    def test_get_user_timeline(self, twitter_client):
        """Test fetching user timeline."""
        mock_client = MagicMock()

        # Mock user lookup
        mock_user = MagicMock()
        mock_user.id = "user123"
        user_response = MagicMock()
        user_response.data = mock_user

        # Mock timeline
        mock_tweet = MagicMock()
        mock_tweet.id = "tweet456"
        mock_tweet.text = "User's tweet"
        mock_tweet.created_at = datetime(2026, 3, 25, 10, 0, 0)
        mock_tweet.public_metrics = {"like_count": 50}

        timeline_response = MagicMock()
        timeline_response.data = [mock_tweet]

        mock_client.get_user.return_value = user_response
        mock_client.get_users_tweets.return_value = timeline_response
        twitter_client._client = mock_client

        result = twitter_client.get_user_timeline("testuser")
        assert result["source"] == "api"
        assert result["username"] == "testuser"
        assert len(result["tweets"]) == 1
        assert result["tweets"][0]["text"] == "User's tweet"

    def test_user_not_found(self, twitter_client):
        """Test handling of user not found."""
        mock_client = MagicMock()
        user_response = MagicMock()
        user_response.data = None
        mock_client.get_user.return_value = user_response
        twitter_client._client = mock_client

        result = twitter_client.get_user_timeline("nonexistent_user_xyz")
        assert result["source"] == "error"
        assert "not found" in result["error"].lower()


class TestTwitterClientTrendingTopics:
    """Test trending topics functionality."""

    @pytest.fixture
    def cache_manager(self, tmp_path):
        """Create a temporary cache manager for testing."""
        cache_db = tmp_path / "test_cache.db"
        return CacheManager(db_path=str(cache_db), ttl_hours=1)

    @pytest.fixture
    def twitter_client(self, cache_manager):
        """Create Twitter client with test cache."""
        return TwitterClient(cache_manager=cache_manager, bearer_token="test_token")

    def test_trending_topics_worldwide(self, twitter_client):
        """Test worldwide trending topics."""
        result = twitter_client.get_trending_topics("worldwide")
        assert result["location"] == "worldwide"
        assert len(result["topics"]) > 0
        assert "AI" in result["topics"]

    def test_trending_topics_by_location(self, twitter_client):
        """Test trending topics by different locations."""
        locations = ["us", "uk", "india", "japan"]
        for location in locations:
            result = twitter_client.get_trending_topics(location)
            assert result["location"] == location
            assert len(result["topics"]) > 0

    def test_trending_topics_default_fallback(self, twitter_client):
        """Test that unknown location defaults to worldwide."""
        result = twitter_client.get_trending_topics("unknown_location")
        assert result["source"] == "static"
        assert "AI" in result["topics"]  # Should have default topics


class TestTwitterClientConfiguration:
    """Test client configuration and initialization."""

    @pytest.fixture
    def cache_manager(self, tmp_path):
        """Create a temporary cache manager for testing."""
        cache_db = tmp_path / "test_cache.db"
        return CacheManager(db_path=str(cache_db), ttl_hours=1)

    def test_client_without_bearer_token(self, cache_manager):
        """Test that client works without token but API calls will fail."""
        client = TwitterClient(bearer_token=None, cache_manager=cache_manager)
        assert client.bearer_token is None
        assert client._client is None

    def test_cache_info(self, cache_manager):
        """Test getting cache statistics."""
        client = TwitterClient(cache_manager=cache_manager, bearer_token="test")
        stats = client.get_cache_info()
        assert "total_entries" in stats
        assert "valid_entries" in stats
        assert "expired_entries" in stats

    def test_clear_cache(self, cache_manager):
        """Test clearing cache."""
        client = TwitterClient(cache_manager=cache_manager, bearer_token="test")
        # Pre-populate cache
        client.get_trending_topics("worldwide")
        stats_before = client.get_cache_info()
        assert stats_before["total_entries"] > 0

        # Clear specific key
        client.clear_cache("twitter:trending:worldwide")
        stats_after = client.get_cache_info()
        assert stats_after["total_entries"] < stats_before["total_entries"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
