#!/usr/bin/env python3
"""Standalone test for Twitter client without pytest."""
import os
import sys
import tempfile
from datetime import datetime
from cache_manager import CacheManager
from twitter_client import TwitterClient


def test_cache_manager():
    """Test cache manager functionality."""
    print("\n=== Testing CacheManager ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = os.path.join(tmpdir, "test.db")
        cache = CacheManager(db_path=cache_path, ttl_hours=1)

        # Test set and get
        test_data = {"key": "value", "number": 42}
        cache.set("test_key", test_data)
        retrieved = cache.get("test_key")
        assert retrieved == test_data, f"Expected {test_data}, got {retrieved}"
        print("✓ Cache set/get works")

        # Test expiration
        import time
        cache.set("short_ttl", {"data": "test"}, ttl_seconds=0)
        time.sleep(0.5)  # Increased sleep time to ensure expiration
        expired = cache.get("short_ttl")
        assert expired is None, f"Should return None for expired entry, got {expired}"
        print("✓ Cache expiration works")

        # Test allow_expired
        expired_fallback = cache.get("short_ttl", allow_expired=True)
        assert expired_fallback is not None, "Should return expired data when allow_expired=True"
        print("✓ Cache fallback works")

        # Test stats
        stats = cache.get_cache_stats()
        assert stats["total_entries"] > 0, "Should have entries"
        assert "cache_location" in stats, "Stats should include cache location"
        print("✓ Cache stats work")


def test_twitter_client_initialization():
    """Test Twitter client initialization."""
    print("\n=== Testing TwitterClient Initialization ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = os.path.join(tmpdir, "twitter.db")
        cache = CacheManager(db_path=cache_path, ttl_hours=1)

        # Test with token
        client = TwitterClient(bearer_token="test_token", cache_manager=cache)
        assert client.bearer_token == "test_token", "Token not set correctly"
        print("✓ Client initializes with token")

        # Test without token
        client_no_token = TwitterClient(cache_manager=cache)
        assert client_no_token.bearer_token is None, "Token should be None"
        print("✓ Client initializes without token")


def test_trending_topics():
    """Test trending topics functionality."""
    print("\n=== Testing Trending Topics ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = os.path.join(tmpdir, "twitter.db")
        cache = CacheManager(db_path=cache_path, ttl_hours=1)
        client = TwitterClient(cache_manager=cache)

        # Test worldwide
        result = client.get_trending_topics("worldwide")
        assert result["source"] == "static", "Should return static source"
        assert result["location"] == "worldwide", "Should return correct location"
        assert len(result["topics"]) > 0, "Should have topics"
        assert "AI" in result["topics"], "Should include AI in worldwide topics"
        print("✓ Worldwide trending topics work")

        # Test cached result
        result2 = client.get_trending_topics("worldwide")
        assert result2["source"] == "cache", "Second call should return cache"
        assert result2["topics"] == result["topics"], "Topics should match"
        print("✓ Trending topics caching works")

        # Test different locations
        for location in ["us", "uk", "india", "japan"]:
            result = client.get_trending_topics(location)
            assert result["location"] == location, f"Should return {location}"
            assert len(result["topics"]) > 0, f"Should have topics for {location}"
        print("✓ Multi-location trending topics work")

        # Test unknown location defaults to worldwide
        result = client.get_trending_topics("unknown_xyz")
        assert "AI" in result["topics"], "Unknown location should default to worldwide"
        print("✓ Unknown location defaults correctly")


def test_search_tweets_structure():
    """Test search tweets response structure."""
    print("\n=== Testing Search Tweets Structure ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = os.path.join(tmpdir, "twitter.db")
        cache = CacheManager(db_path=cache_path, ttl_hours=1)
        client = TwitterClient(bearer_token="test_token", cache_manager=cache)

        # Without token/API, should return error
        result = client.search_tweets("python")
        assert "source" in result, "Should have source"
        assert "query" in result, "Should have query"
        assert "tweets" in result, "Should have tweets list"
        assert "timestamp" in result, "Should have timestamp"
        # Without proper setup, will error
        print("✓ Search tweets returns correct structure")


def test_timeline_structure():
    """Test timeline response structure."""
    print("\n=== Testing Timeline Structure ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = os.path.join(tmpdir, "twitter.db")
        cache = CacheManager(db_path=cache_path, ttl_hours=1)
        client = TwitterClient(bearer_token="test_token", cache_manager=cache)

        result = client.get_user_timeline("testuser")
        assert "source" in result, "Should have source"
        assert "username" in result, "Should have username"
        assert "tweets" in result, "Should have tweets list"
        assert "timestamp" in result, "Should have timestamp"
        print("✓ Timeline returns correct structure")


def test_cache_clear():
    """Test cache clearing functionality."""
    print("\n=== Testing Cache Clear ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = os.path.join(tmpdir, "twitter.db")
        cache = CacheManager(db_path=cache_path, ttl_hours=1)
        client = TwitterClient(cache_manager=cache)

        # Add some data
        client.get_trending_topics("worldwide")
        client.get_trending_topics("us")
        stats = client.get_cache_info()
        initial_count = stats["total_entries"]
        assert initial_count > 0, "Should have cache entries"
        print(f"✓ Cache populated with {initial_count} entries")

        # Clear specific key
        client.clear_cache("twitter:trending:worldwide")
        stats = client.get_cache_info()
        assert stats["total_entries"] < initial_count, "Should have fewer entries"
        print("✓ Selective cache clear works")

        # Clear all
        client.clear_cache()
        stats = client.get_cache_info()
        assert stats["total_entries"] == 0, "Should be empty"
        print("✓ Clear all cache works")


def test_max_retries_constant():
    """Test that max retries constant is set correctly."""
    print("\n=== Testing Retry Constants ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = os.path.join(tmpdir, "twitter.db")
        cache = CacheManager(db_path=cache_path, ttl_hours=1)
        client = TwitterClient(cache_manager=cache)

        assert client.MAX_RETRIES > 0, "MAX_RETRIES should be positive"
        assert client.INITIAL_RETRY_DELAY > 0, "INITIAL_RETRY_DELAY should be positive"
        assert client.RATE_LIMIT_RETRY_DELAY > 0, "RATE_LIMIT_RETRY_DELAY should be positive"
        print(f"✓ Retry constants set: MAX_RETRIES={client.MAX_RETRIES}, "
              f"INITIAL_RETRY_DELAY={client.INITIAL_RETRY_DELAY}s, "
              f"RATE_LIMIT_RETRY_DELAY={client.RATE_LIMIT_RETRY_DELAY}s")


def main():
    """Run all tests."""
    print("Starting Twitter Client Standalone Tests...")
    print("=" * 60)

    tests = [
        test_cache_manager,
        test_twitter_client_initialization,
        test_trending_topics,
        test_search_tweets_structure,
        test_timeline_structure,
        test_cache_clear,
        test_max_retries_constant,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"✗ {test.__name__} failed: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {test.__name__} errored: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
