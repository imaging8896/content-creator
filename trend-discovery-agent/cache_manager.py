"""Cache manager for trend data with TTL support."""
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional
import sqlite3


class CacheManager:
    """Manages caching of trend data with TTL support."""

    def __init__(self, db_path: str = "cache.db", ttl_hours: int = 1):
        """Initialize cache manager.

        Args:
            db_path: Path to SQLite database file
            ttl_hours: Time-to-live for cached entries in hours
        """
        self.db_path = db_path
        self.ttl_seconds = ttl_hours * 3600
        self._init_db()

    def _init_db(self):
        """Initialize SQLite database."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    ttl_seconds INTEGER NOT NULL
                )
            """)
            conn.commit()

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """Store value in cache.

        Args:
            key: Cache key
            value: Value to cache (will be JSON serialized)
            ttl_seconds: Override TTL for this entry
        """
        ttl = ttl_seconds if ttl_seconds is not None else self.ttl_seconds
        timestamp = time.time()
        value_json = json.dumps(value)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO cache (key, value, timestamp, ttl_seconds)
                VALUES (?, ?, ?, ?)
            """, (key, value_json, timestamp, ttl))
            conn.commit()

    def get(self, key: str, allow_expired: bool = False) -> Optional[Any]:
        """Retrieve value from cache.

        Args:
            key: Cache key
            allow_expired: If True, return expired entries as fallback

        Returns:
            Cached value or None if not found or expired
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT value, timestamp, ttl_seconds FROM cache WHERE key = ?",
                (key,)
            )
            row = cursor.fetchone()

        if not row:
            return None

        value_json, timestamp, ttl_seconds = row
        age_seconds = time.time() - timestamp

        # Check if expired
        if age_seconds > ttl_seconds:
            if not allow_expired:
                return None
            # Log that we're using expired data
            print(f"WARNING: Using expired cache for key '{key}' (age: {age_seconds:.0f}s, TTL: {ttl_seconds}s)")

        return json.loads(value_json)

    def is_expired(self, key: str) -> bool:
        """Check if cache entry exists and is not expired.

        Args:
            key: Cache key

        Returns:
            True if key doesn't exist or is expired
        """
        return self.get(key) is None

    def clear(self, key: Optional[str] = None) -> None:
        """Clear cache entries.

        Args:
            key: Specific key to clear, or None to clear all
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            if key:
                cursor.execute("DELETE FROM cache WHERE key = ?", (key,))
            else:
                cursor.execute("DELETE FROM cache")
            conn.commit()

    def cleanup_expired(self) -> int:
        """Remove expired entries from cache.

        Returns:
            Number of entries removed
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            current_time = time.time()
            cursor.execute("""
                DELETE FROM cache
                WHERE (? - timestamp) > ttl_seconds
            """, (current_time,))
            rows_deleted = cursor.rowcount
            conn.commit()
        return rows_deleted

    def get_cache_stats(self) -> dict:
        """Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM cache")
            total_entries = cursor.fetchone()[0]

            current_time = time.time()
            cursor.execute("""
                SELECT COUNT(*) FROM cache
                WHERE (? - timestamp) <= ttl_seconds
            """, (current_time,))
            valid_entries = cursor.fetchone()[0]

        return {
            "total_entries": total_entries,
            "valid_entries": valid_entries,
            "expired_entries": total_entries - valid_entries,
            "cache_location": self.db_path
        }
