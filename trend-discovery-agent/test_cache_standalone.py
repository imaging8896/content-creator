"""Standalone test for cache manager - no external dependencies."""
import tempfile
import time
import os
import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from cache_manager import CacheManager


def test_cache_basic():
    """Test basic cache operations."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
        db_path = f.name

    try:
        cm = CacheManager(db_path=db_path, ttl_hours=1)

        # Test set and get
        test_data = {"trends": ["python", "javascript"], "count": 2}
        cm.set("test_key", test_data)
        retrieved = cm.get("test_key")
        assert retrieved == test_data, "Basic set/get failed"
        print("✓ Basic set/get works")

        # Test non-existent key
        assert cm.get("non_existent") is None, "Non-existent key should return None"
        print("✓ Non-existent key returns None")

        # Test is_expired
        assert not cm.is_expired("test_key"), "Fresh key should not be expired"
        assert cm.is_expired("non_existent"), "Non-existent key should be marked expired"
        print("✓ is_expired works correctly")

        # Test clear specific key
        cm.clear("test_key")
        assert cm.get("test_key") is None, "Cleared key should be None"
        print("✓ Clear specific key works")

        # Test cache stats
        cm.set("stat_test1", {"data": "test1"})
        cm.set("stat_test2", {"data": "test2"})
        stats = cm.get_cache_stats()
        assert stats["total_entries"] == 2, f"Expected 2 entries, got {stats['total_entries']}"
        assert stats["valid_entries"] == 2, f"Expected 2 valid entries, got {stats['valid_entries']}"
        print("✓ Cache stats work correctly")

        # Test clear all
        cm.clear()
        assert cm.get_cache_stats()["total_entries"] == 0, "Clear all should remove all entries"
        print("✓ Clear all works")

        print("\n✅ All cache manager tests passed!")

    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


def test_cache_ttl():
    """Test TTL functionality."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
        db_path = f.name

    try:
        cm = CacheManager(db_path=db_path, ttl_hours=1)

        # Test TTL expiration
        test_data = {"trends": ["test"]}
        cm.set("expire_test", test_data, ttl_seconds=1)

        assert cm.get("expire_test") == test_data, "Fresh cache should be accessible"
        print("✓ Fresh cache is accessible")

        # Wait for expiration
        time.sleep(1.1)

        assert cm.get("expire_test") is None, "Expired cache should not be accessible"
        print("✓ Expired cache is not accessible")

        # Test allow_expired flag
        expired = cm.get("expire_test", allow_expired=True)
        assert expired == test_data, "Expired cache should be accessible with allow_expired=True"
        print("✓ Expired cache accessible with allow_expired=True")

        print("\n✅ All TTL tests passed!")

    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


if __name__ == "__main__":
    print("Running standalone cache manager tests...\n")
    test_cache_basic()
    print()
    test_cache_ttl()
