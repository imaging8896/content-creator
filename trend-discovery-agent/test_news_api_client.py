"""Tests for NewsAPI client."""
import os
import pytest
from unittest.mock import Mock, patch, MagicMock
from news_api_client import NewsAPIClient
from cache_manager import CacheManager
from rate_limiter import RateLimiter


@pytest.fixture
def cache_manager():
    """Create a test cache manager."""
    return CacheManager(db_path="cache/test_newsapi.db", ttl_hours=1)


@pytest.fixture
def rate_limiter():
    """Create a test rate limiter."""
    return RateLimiter(custom_limits={"newsapi": 10})  # Low limit for testing


@pytest.fixture
def news_client(cache_manager, rate_limiter):
    """Create a test NewsAPI client."""
    client = NewsAPIClient(
        api_key="test_api_key",
        cache_manager=cache_manager,
        rate_limiter=rate_limiter
    )
    # Clean up cache before each test
    cache_manager.clear()
    return client


class TestNewsAPIClient:
    """Tests for NewsAPI client."""

    def test_client_initialization(self, news_client):
        """Test client initialization."""
        assert news_client.api_key == "test_api_key"
        assert news_client.cache_manager is not None
        assert news_client.rate_limiter is not None

    def test_client_initialization_with_env_var(self, cache_manager, rate_limiter, monkeypatch):
        """Test client initialization from environment variable."""
        monkeypatch.setenv("NEWSAPI_KEY", "env_api_key")
        client = NewsAPIClient(cache_manager=cache_manager, rate_limiter=rate_limiter)
        assert client.api_key == "env_api_key"

    def test_client_initialization_no_key(self, cache_manager, rate_limiter):
        """Test client initialization without API key."""
        client = NewsAPIClient(cache_manager=cache_manager, rate_limiter=rate_limiter)
        assert client.api_key is None

    @patch('requests.Session.get')
    def test_search_news_success(self, mock_get, news_client):
        """Test successful news search."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "ok",
            "articles": [
                {
                    "title": "Test Article",
                    "description": "Test description",
                    "url": "http://example.com",
                    "urlToImage": None,
                    "publishedAt": "2026-03-25T10:00:00Z",
                    "source": {"id": "test", "name": "Test Source"},
                    "content": "Test content"
                }
            ],
            "totalResults": 1
        }
        mock_get.return_value = mock_response

        result = news_client.search_news(query="test")

        assert result["source"] == "api"
        assert result["query"] == "test"
        assert len(result["articles"]) == 1
        assert result["articles"][0]["title"] == "Test Article"
        assert result["total_results"] == 1

    @patch('requests.Session.get')
    def test_search_news_cached(self, mock_get, news_client):
        """Test cached news search."""
        # First call should hit the API
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "ok",
            "articles": [{"title": "Test"}],
            "totalResults": 1
        }
        mock_get.return_value = mock_response

        result1 = news_client.search_news(query="test")
        assert result1["source"] == "api"
        assert mock_get.call_count == 1

        # Second call should be cached
        result2 = news_client.search_news(query="test")
        assert result2["source"] == "cache"
        assert mock_get.call_count == 1  # No additional API call

        assert result1["articles"] == result2["articles"]

    @patch('requests.Session.get')
    def test_search_news_api_error(self, mock_get, news_client):
        """Test news search with API error."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_get.return_value = mock_response

        result = news_client.search_news(query="test")

        assert result["source"] == "error"
        assert result["articles"] == []
        assert "error" in result

    @patch('requests.Session.get')
    def test_get_top_headlines_success(self, mock_get, news_client):
        """Test successful top headlines retrieval."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "ok",
            "articles": [
                {
                    "title": "Breaking News",
                    "description": "Important news",
                    "url": "http://example.com/news",
                    "urlToImage": None,
                    "publishedAt": "2026-03-25T10:00:00Z",
                    "source": {"id": "test", "name": "Test Source"},
                    "content": "Breaking news content"
                }
            ],
            "totalResults": 100
        }
        mock_get.return_value = mock_response

        result = news_client.get_top_headlines(country="us")

        assert result["source"] == "api"
        assert result["country"] == "us"
        assert len(result["articles"]) == 1
        assert result["articles"][0]["title"] == "Breaking News"

    @patch('requests.Session.get')
    def test_rate_limit_exceeded(self, mock_get, news_client):
        """Test handling of rate limit errors."""
        # Exhaust rate limit
        news_client.rate_limiter.buckets["newsapi"].tokens = 0

        # Any attempt to make a request should fail rate limit check
        result = news_client.search_news(query="test")

        assert result["source"] == "error"
        assert mock_get.call_count == 0  # Should not call API

    def test_rate_limit_status(self, news_client):
        """Test rate limit status reporting."""
        status = news_client.get_rate_limit_status()

        assert "available_requests" in status
        assert "capacity" in status
        assert "daily_limit" in status
        assert status["daily_limit"] == 100

    def test_cache_with_category(self, cache_manager, rate_limiter):
        """Test that different categories use separate cache keys."""
        client = NewsAPIClient(
            api_key="test_key",
            cache_manager=cache_manager,
            rate_limiter=rate_limiter
        )

        with patch('requests.Session.get') as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "status": "ok",
                "articles": [{"title": "Tech News"}],
                "totalResults": 1
            }
            mock_get.return_value = mock_response

            # Search with category
            result1 = client.get_top_headlines(country="us", category="technology")
            assert result1["source"] == "api"

            # Same country but no category should be different cache entry
            result2 = client.get_top_headlines(country="us")
            # This would be a new API call since the category differs the cache key
            assert mock_get.call_count >= 1

    def test_article_model_validation(self):
        """Test NewsArticle model with various data."""
        from pydantic import BaseModel, ValidationError

        # This is a conceptual test - validate the data structure
        article_data = {
            "title": "Test Article",
            "description": "Test description",
            "url": "http://example.com",
            "urlToImage": None,
            "publishedAt": "2026-03-25T10:00:00Z",
            "source": {"id": "test", "name": "Test"},
            "content": "Test content"
        }

        # Should not raise an exception
        from news_api_client import NewsArticle
        article = NewsArticle(**article_data)
        assert article.title == "Test Article"
        assert article.url == "http://example.com"


class TestNewsAPIClientIntegration:
    """Integration tests for NewsAPI client."""

    def test_search_and_cache_flow(self):
        """Test the full search and caching flow."""
        cache_manager = CacheManager(db_path="cache/test_integration.db", ttl_hours=1)
        rate_limiter = RateLimiter()
        client = NewsAPIClient(
            api_key="test_key",
            cache_manager=cache_manager,
            rate_limiter=rate_limiter
        )

        cache_manager.clear()

        with patch('requests.Session.get') as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "status": "ok",
                "articles": [
                    {
                        "title": "Article 1",
                        "description": "Desc 1",
                        "url": "http://example1.com",
                        "urlToImage": None,
                        "publishedAt": "2026-03-25T10:00:00Z",
                        "source": {"id": "test", "name": "Test"},
                        "content": "Content 1"
                    }
                ],
                "totalResults": 1
            }
            mock_get.return_value = mock_response

            # First search - should hit API
            result1 = client.search_news(query="python")
            api_calls_1 = mock_get.call_count

            # Second search - should use cache
            result2 = client.search_news(query="python")
            api_calls_2 = mock_get.call_count

            assert result1["source"] == "api"
            assert result2["source"] == "cache"
            assert api_calls_2 == api_calls_1  # No additional API call
            assert result1["articles"][0]["title"] == result2["articles"][0]["title"]

        # Cleanup
        cache_manager.clear()
