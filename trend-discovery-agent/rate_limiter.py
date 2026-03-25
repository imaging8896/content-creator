"""Rate limiter with token bucket algorithm for API rate limiting."""
import time
import threading
from typing import Optional, Dict


class TokenBucket:
    """Token bucket rate limiter."""

    def __init__(self, capacity: int, refill_rate: float):
        """Initialize token bucket.

        Args:
            capacity: Maximum number of tokens (burst capacity)
            refill_rate: Tokens per second refill rate
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_refill_time = time.time()
        self.lock = threading.Lock()

    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill_time
        tokens_to_add = elapsed * self.refill_rate

        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill_time = now

    def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens.

        Args:
            tokens: Number of tokens to consume

        Returns:
            True if tokens were available, False otherwise
        """
        with self.lock:
            self._refill()
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

    def wait_and_consume(self, tokens: int = 1) -> None:
        """Wait and consume tokens (blocking).

        Args:
            tokens: Number of tokens to consume
        """
        while not self.consume(tokens):
            time.sleep(0.1)

    def get_available_tokens(self) -> float:
        """Get current available tokens.

        Returns:
            Number of available tokens
        """
        with self.lock:
            self._refill()
            return self.tokens


class RateLimiter:
    """Rate limiter for multiple endpoints with configurable limits."""

    # Default rate limits (requests per day)
    DEFAULT_LIMITS = {
        "newsapi": 100,  # NewsAPI free tier
        "google_trends": 1000,  # High limit, rarely hit
        "twitter": 450,  # Twitter free tier (v1.1)
    }

    # Convert daily limits to per-second rates
    SECONDS_PER_DAY = 86400

    def __init__(self, custom_limits: Optional[Dict[str, int]] = None):
        """Initialize rate limiter.

        Args:
            custom_limits: Custom rate limits (requests per day) by endpoint
        """
        limits = self.DEFAULT_LIMITS.copy()
        if custom_limits:
            limits.update(custom_limits)

        self.buckets: Dict[str, TokenBucket] = {}

        for endpoint, daily_limit in limits.items():
            # Convert daily limit to per-second rate
            per_second = daily_limit / self.SECONDS_PER_DAY
            # Bucket capacity = daily limit (burst capacity)
            self.buckets[endpoint] = TokenBucket(capacity=daily_limit, refill_rate=per_second)

    def is_allowed(self, endpoint: str, tokens: int = 1) -> bool:
        """Check if request is allowed for endpoint.

        Args:
            endpoint: API endpoint identifier
            tokens: Number of tokens to consume

        Returns:
            True if request is allowed
        """
        if endpoint not in self.buckets:
            # Unknown endpoint - allow by default
            return True

        return self.buckets[endpoint].consume(tokens)

    def wait_if_needed(self, endpoint: str, tokens: int = 1) -> float:
        """Wait if necessary to comply with rate limit.

        Args:
            endpoint: API endpoint identifier
            tokens: Number of tokens to consume

        Returns:
            Wait time in seconds (0 if no wait needed)
        """
        if endpoint not in self.buckets:
            return 0.0

        bucket = self.buckets[endpoint]
        start_time = time.time()
        bucket.wait_and_consume(tokens)
        return time.time() - start_time

    def get_status(self, endpoint: str) -> Dict[str, float]:
        """Get rate limit status for endpoint.

        Args:
            endpoint: API endpoint identifier

        Returns:
            Dictionary with status information
        """
        if endpoint not in self.buckets:
            return {"available": float('inf'), "capacity": float('inf')}

        bucket = self.buckets[endpoint]
        with bucket.lock:
            bucket._refill()
            return {
                "available": bucket.tokens,
                "capacity": bucket.capacity,
                "refill_rate": bucket.refill_rate
            }

    def reset(self, endpoint: Optional[str] = None) -> None:
        """Reset rate limiter for endpoint(s).

        Args:
            endpoint: Specific endpoint to reset, or None to reset all
        """
        if endpoint:
            if endpoint in self.buckets:
                self.buckets[endpoint].tokens = self.buckets[endpoint].capacity
                self.buckets[endpoint].last_refill_time = time.time()
        else:
            for bucket in self.buckets.values():
                bucket.tokens = bucket.capacity
                bucket.last_refill_time = time.time()
