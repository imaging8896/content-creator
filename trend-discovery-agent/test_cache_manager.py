"""Tests for cache manager."""
import pytest
import tempfile
import time
import os
from pathlib import Path
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


def test_cache_manager_init(temp_db):
    """Test cache manager initialization."""
    cm = CacheManager(db_path=temp_db)
    assert cm.db_path == temp_db
    assert cm.ttl_seconds == 3600  # 1 hour default


def test_cache_set_and_get(temp_db):
    """Test setting and getting cache values."""
    cm = CacheManager(db_path=temp_db)

    # Set a value
    test_data = {"trends": ["python", "javascript"], "count": 2}
    cm.set("test_key", test_data)

    # Retrieve it
    retrieved = cm.get("test_key")
    assert retrieved == test_data


def test_cache_ttl_expiration(temp_db):
    """Test cache TTL expiration."""
    cm = CacheManager(db_path=temp_db, ttl_hours=0)  # 0 hours = immediate expiration

    # Set a value
    test_data = {"trends": ["test"]}
    cm.set("test_key", test_data, ttl_seconds=1)

    # Should be available immediately
    assert cm.get("test_key") == test_data

    # Wait for expiration
    time.sleep(1.1)

    # Should be expired
    assert cm.get("test_key") is None


def test_cache_allow_expired(temp_db):
    """Test retrieving expired cache with allow_expired flag."""
    cm = CacheManager(db_path=temp_db)

    # Set a value with short TTL
    test_data = {"trends": ["test"]}
    cm.set("test_key", test_data, ttl_seconds=1)

    # Wait for expiration
    time.sleep(1.1)

    # Should be None by default
    assert cm.get("test_key") is None

    # Should be retrievable with allow_expired=True
    expired = cm.get("test_key", allow_expired=True)
    assert expired == test_data


def test_cache_is_expired(temp_db):
    """Test is_expired method."""
    cm = CacheManager(db_path=temp_db)

    # Non-existent key should be expired
    assert cm.is_expired("non_existent")

    # Fresh key should not be expired
    cm.set("fresh", {"data": "test"})
    assert not cm.is_expired("fresh")

    # Expired key should be marked as expired
    cm.set("old", {"data": "test"}, ttl_seconds=1)
    time.sleep(1.1)
    assert cm.is_expired("old")


def test_cache_clear_specific_key(temp_db):
    """Test clearing specific cache key."""
    cm = CacheManager(db_path=temp_db)

    # Set multiple values
    cm.set("key1", {"data": "test1"})
    cm.set("key2", {"data": "test2"})

    # Clear one key
    cm.clear("key1")

    # Check that key1 is gone but key2 remains
    assert cm.get("key1") is None
    assert cm.get("key2") == {"data": "test2"}


def test_cache_clear_all(temp_db):
    """Test clearing all cache."""
    cm = CacheManager(db_path=temp_db)

    # Set multiple values
    cm.set("key1", {"data": "test1"})
    cm.set("key2", {"data": "test2"})

    # Clear all
    cm.clear()

    # Check that both are gone
    assert cm.get("key1") is None
    assert cm.get("key2") is None


def test_cache_cleanup_expired(temp_db):
    """Test cleanup_expired method."""
    cm = CacheManager(db_path=temp_db)

    # Set some fresh and some expired entries
    cm.set("fresh", {"data": "test"}, ttl_seconds=3600)
    cm.set("expired1", {"data": "test"}, ttl_seconds=1)
    cm.set("expired2", {"data": "test"}, ttl_seconds=1)

    # Wait for expiration
    time.sleep(1.1)

    # Cleanup
    removed = cm.cleanup_expired()

    # Should remove 2 entries
    assert removed == 2

    # Fresh should still exist
    assert cm.get("fresh") == {"data": "test"}
    # Expired should be gone
    assert cm.get("expired1") is None
    assert cm.get("expired2") is None


def test_cache_stats(temp_db):
    """Test cache statistics."""
    cm = CacheManager(db_path=temp_db)

    # Set entries
    cm.set("key1", {"data": "test1"})
    cm.set("key2", {"data": "test2"}, ttl_seconds=1)

    # Get stats
    stats = cm.get_cache_stats()

    assert stats["total_entries"] == 2
    assert stats["valid_entries"] == 2
    assert stats["expired_entries"] == 0

    # Wait for expiration
    time.sleep(1.1)

    # Get stats again
    stats = cm.get_cache_stats()
    assert stats["total_entries"] == 2
    assert stats["valid_entries"] == 1
    assert stats["expired_entries"] == 1


def test_cache_complex_data_types(temp_db):
    """Test caching complex data types."""
    cm = CacheManager(db_path=temp_db)

    # Test various data types
    test_cases = [
        ("list", ["a", "b", "c"]),
        ("dict", {"nested": {"data": "value"}}),
        ("mixed", {"list": [1, 2, 3], "dict": {"key": "value"}}),
        ("numbers", {"int": 42, "float": 3.14}),
        ("strings", {"empty": "", "special": "test\nwith\nnewlines"}),
    ]

    for key, data in test_cases:
        cm.set(key, data)
        retrieved = cm.get(key)
        assert retrieved == data, f"Failed for {key}"
