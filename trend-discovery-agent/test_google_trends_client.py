"""Tests for Google Trends client."""
import pytest
import tempfile
import os
from unittest.mock import patch, MagicMock
from google_trends_client import GoogleTrendsClient
from cache_manager import CacheManager


@pytest.fixture
def temp_db():
    """Create temporary database."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
        db_path = f.name
    yield db_path
    # Cleanup
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture
def cache_manager(temp_db):
    """Create cache manager with temp database."""
    return CacheManager(db_path=temp_db, ttl_hours=1)


@pytest.fixture
def trends_client(cache_manager):
    """Create Google Trends client."""
    return GoogleTrendsClient(cache_manager=cache_manager)


def test_client_initialization(trends_client):
    """Test client initialization."""
    assert trends_client.cache_manager is not None
    assert trends_client.hl == "en-US"
    assert trends_client.tz == 360


def test_client_with_custom_cache(cache_manager, temp_db):
    """Test client with custom cache manager."""
    client = GoogleTrendsClient(cache_manager=cache_manager)
    assert client.cache_manager == cache_manager


def test_client_with_default_cache(temp_db):
    """Test client creates default cache manager."""
    client = GoogleTrendsClient()
    assert client.cache_manager is not None


def test_get_trending_searches_from_cache(trends_client):
    """Test getting trends from cache."""
    # Pre-populate cache
    test_trends = {
        "trends": ["AI", "Python", "JavaScript"],
        "timestamp": "2026-03-25T12:00:00"
    }
    trends_client.cache_manager.set(
        "google_trends:trending:UNITED_STATES",
        test_trends
    )

    # Fetch trends (should come from cache)
    result = trends_client.get_trending_searches(region="UNITED_STATES")

    assert result["source"] == "cache"
    assert result["region"] == "UNITED_STATES"
    assert result["trends"] == ["AI", "Python", "JavaScript"]


@patch('google_trends_client.TrendReq')
def test_get_trending_searches_api_success(mock_trend_req, trends_client):
    """Test successful API call."""
    # Mock pytrends response
    mock_pytrends = MagicMock()
    mock_trend_req.return_value = mock_pytrends

    # Mock the dataframe response
    import pandas as pd
    mock_df = pd.DataFrame({0: ["AI", "Python", "JavaScript"]})
    mock_pytrends.trending_searches.return_value = mock_df

    # Mock the trending_searches method
    trends_client._pytrends = mock_pytrends

    # Fetch trends
    result = trends_client.get_trending_searches(region="UNITED_STATES")

    assert result["source"] == "api"
    assert result["region"] == "UNITED_STATES"
    assert len(result["trends"]) == 3
    assert "timestamp" in result


@patch('google_trends_client.TrendReq')
def test_get_trending_searches_api_failure_with_fallback(mock_trend_req, trends_client):
    """Test API failure falling back to expired cache."""
    # Pre-populate cache with old data
    old_trends = {
        "trends": ["OldTrend1", "OldTrend2"],
        "timestamp": "2026-03-24T12:00:00"
    }
    trends_client.cache_manager.set(
        "google_trends:trending:UNITED_STATES",
        old_trends,
        ttl_seconds=1  # Expire immediately
    )

    # Wait for cache to expire
    import time
    time.sleep(1.1)

    # Mock API failure
    mock_pytrends = MagicMock()
    mock_trend_req.return_value = mock_pytrends
    mock_pytrends.trending_searches.side_effect = Exception("API Error")
    trends_client._pytrends = mock_pytrends

    # Fetch trends (should fall back to expired cache)
    result = trends_client.get_trending_searches(region="UNITED_STATES")

    assert result["source"] == "cache_fallback"
    assert result["region"] == "UNITED_STATES"
    assert result["trends"] == ["OldTrend1", "OldTrend2"]
    assert "error" in result


@patch('google_trends_client.TrendReq')
def test_get_trending_searches_api_failure_no_fallback(mock_trend_req, trends_client):
    """Test API failure with no cached data."""
    # Mock API failure
    mock_pytrends = MagicMock()
    mock_trend_req.return_value = mock_pytrends
    mock_pytrends.trending_searches.side_effect = Exception("API Error")
    trends_client._pytrends = mock_pytrends

    # Fetch trends (no cache available)
    result = trends_client.get_trending_searches(region="UNITED_STATES")

    assert result["source"] == "error"
    assert result["region"] == "UNITED_STATES"
    assert result["trends"] == []
    assert "error" in result


def test_get_trending_searches_multi_region(trends_client):
    """Test fetching trends for multiple regions."""
    # Pre-populate cache for two regions
    trends_client.cache_manager.set(
        "google_trends:trending:UNITED_STATES",
        {"trends": ["US_trend"], "timestamp": "2026-03-25T12:00:00"}
    )
    trends_client.cache_manager.set(
        "google_trends:trending:INDIA",
        {"trends": ["INDIA_trend"], "timestamp": "2026-03-25T12:00:00"}
    )

    # Fetch trends for multiple regions
    result = trends_client.get_trending_searches_multi_region(regions=["UNITED_STATES", "INDIA"])

    assert "UNITED_STATES" in result
    assert "INDIA" in result
    assert result["UNITED_STATES"]["trends"] == ["US_trend"]
    assert result["INDIA"]["trends"] == ["INDIA_trend"]


def test_get_cache_info(trends_client):
    """Test getting cache information."""
    # Add some data to cache
    trends_client.cache_manager.set(
        "google_trends:trending:UNITED_STATES",
        {"trends": ["test"], "timestamp": "2026-03-25T12:00:00"}
    )

    # Get cache info
    info = trends_client.get_cache_info()

    assert "total_entries" in info
    assert "valid_entries" in info
    assert "expired_entries" in info
    assert info["total_entries"] >= 1


def test_clear_cache(trends_client):
    """Test clearing cache."""
    # Add data to cache
    trends_client.cache_manager.set(
        "google_trends:trending:UNITED_STATES",
        {"trends": ["test"], "timestamp": "2026-03-25T12:00:00"}
    )

    # Clear specific key
    trends_client.clear_cache("google_trends:trending:UNITED_STATES")

    # Verify it's gone
    result = trends_client.cache_manager.get("google_trends:trending:UNITED_STATES")
    assert result is None


@patch('google_trends_client.TrendReq')
def test_get_interest_over_time_from_cache(mock_trend_req, trends_client):
    """Test getting interest over time from cache."""
    # Pre-populate cache
    test_data = {
        "data": {"python": [50, 60, 70], "javascript": [80, 85, 90]},
        "timestamp": "2026-03-25T12:00:00"
    }
    trends_client.cache_manager.set(
        "google_trends:interest_over_time:javascript:python",
        test_data
    )

    # Fetch data (should come from cache)
    result = trends_client.get_interest_over_time(keywords=["python", "javascript"])

    assert result["source"] == "cache"
    assert "data" in result
    assert "timestamp" in result


def test_pytrends_lazy_loading(trends_client):
    """Test that pytrends is lazily loaded."""
    assert trends_client._pytrends is None

    # After calling _get_pytrends, it should be loaded
    pytrends = trends_client._get_pytrends()
    assert pytrends is not None
    assert trends_client._pytrends is not None

    # Second call should return the same instance
    pytrends2 = trends_client._get_pytrends()
    assert pytrends is pytrends2
