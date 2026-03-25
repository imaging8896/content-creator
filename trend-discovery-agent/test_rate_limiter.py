"""Tests for rate limiter."""
import pytest
import time
from rate_limiter import TokenBucket, RateLimiter


class TestTokenBucket:
    """Tests for TokenBucket."""

    def test_initialization(self):
        """Test token bucket initialization."""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        assert bucket.capacity == 10
        assert bucket.refill_rate == 1.0
        assert bucket.tokens == 10

    def test_consume_success(self):
        """Test successful token consumption."""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        assert bucket.consume(5) is True
        assert bucket.tokens == 5

    def test_consume_exact(self):
        """Test consuming exact amount of tokens."""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        assert bucket.consume(10) is True
        assert bucket.tokens == 0

    def test_consume_fails(self):
        """Test consume fails when not enough tokens."""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        bucket.consume(10)
        assert bucket.consume(1) is False
        assert bucket.tokens == 0

    def test_refill(self):
        """Test token refilling over time."""
        bucket = TokenBucket(capacity=10, refill_rate=10.0)  # 10 tokens per second
        bucket.consume(10)
        assert bucket.tokens == 0

        # Wait for refill
        time.sleep(0.1)  # 0.1 seconds = 1 token refill
        bucket._refill()
        assert bucket.tokens >= 0.9  # Allow some rounding

    def test_get_available_tokens(self):
        """Test getting available tokens."""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        available = bucket.get_available_tokens()
        assert available == 10

    def test_multiple_consumes(self):
        """Test multiple consume operations."""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        assert bucket.consume(3) is True
        assert bucket.consume(3) is True
        assert bucket.consume(3) is True
        assert bucket.consume(2) is True
        assert bucket.tokens == -1  # Over consumed (threads not considered in this test)

    def test_capacity_limit(self):
        """Test that tokens don't exceed capacity."""
        bucket = TokenBucket(capacity=10, refill_rate=100.0)
        time.sleep(0.1)
        bucket._refill()
        assert bucket.tokens <= 10  # Should not exceed capacity


class TestRateLimiter:
    """Tests for RateLimiter."""

    def test_initialization_with_defaults(self):
        """Test rate limiter with default limits."""
        limiter = RateLimiter()
        assert "newsapi" in limiter.buckets
        assert "google_trends" in limiter.buckets
        assert "twitter" in limiter.buckets

    def test_initialization_with_custom_limits(self):
        """Test rate limiter with custom limits."""
        custom_limits = {
            "custom_api": 50,
            "newsapi": 200
        }
        limiter = RateLimiter(custom_limits=custom_limits)
        assert "custom_api" in limiter.buckets
        assert "newsapi" in limiter.buckets

    def test_is_allowed_success(self):
        """Test successful rate limit check."""
        limiter = RateLimiter(custom_limits={"test_api": 10})
        assert limiter.is_allowed("test_api", tokens=5) is True

    def test_is_allowed_failure(self):
        """Test rate limit exceeded."""
        limiter = RateLimiter(custom_limits={"test_api": 10})
        # Consume all tokens
        limiter.buckets["test_api"].tokens = 0
        assert limiter.is_allowed("test_api", tokens=1) is False

    def test_is_allowed_unknown_endpoint(self):
        """Test unknown endpoint is allowed by default."""
        limiter = RateLimiter()
        assert limiter.is_allowed("unknown_api") is True

    def test_multiple_requests(self):
        """Test multiple requests against rate limit."""
        limiter = RateLimiter(custom_limits={"test_api": 5})

        # First 5 should succeed
        for i in range(5):
            assert limiter.is_allowed("test_api", tokens=1) is True

        # 6th should fail
        assert limiter.is_allowed("test_api", tokens=1) is False

    def test_get_status(self):
        """Test getting rate limit status."""
        limiter = RateLimiter(custom_limits={"test_api": 100})
        status = limiter.get_status("test_api")

        assert "available" in status
        assert "capacity" in status
        assert "refill_rate" in status
        assert status["capacity"] == 100

    def test_reset_single_endpoint(self):
        """Test resetting a specific endpoint."""
        limiter = RateLimiter(custom_limits={"test_api": 10})
        # Consume all tokens
        limiter.buckets["test_api"].tokens = 0

        # Reset
        limiter.reset("test_api")
        status = limiter.get_status("test_api")
        assert status["available"] == 10

    def test_reset_all(self):
        """Test resetting all endpoints."""
        limiter = RateLimiter(custom_limits={
            "api1": 10,
            "api2": 20
        })

        # Consume tokens
        limiter.buckets["api1"].tokens = 0
        limiter.buckets["api2"].tokens = 0

        # Reset all
        limiter.reset()

        assert limiter.get_status("api1")["available"] == 10
        assert limiter.get_status("api2")["available"] == 20

    def test_newsapi_daily_limit(self):
        """Test NewsAPI daily limit conversion."""
        limiter = RateLimiter()
        status = limiter.get_status("newsapi")

        # 100 requests per day = ~0.00115 requests per second
        expected_per_second = 100 / (24 * 60 * 60)
        assert abs(status["refill_rate"] - expected_per_second) < 0.0001
        assert status["capacity"] == 100

    def test_wait_if_needed(self):
        """Test wait_if_needed method."""
        limiter = RateLimiter(custom_limits={"test_api": 10})
        limiter.buckets["test_api"].tokens = 10

        # Should not wait when tokens available
        wait_time = limiter.wait_if_needed("test_api", tokens=5)
        assert wait_time == 0

    def test_concurrent_rate_limiting(self):
        """Test thread safety of rate limiting."""
        import threading

        limiter = RateLimiter(custom_limits={"test_api": 10})
        results = []

        def make_request():
            result = limiter.is_allowed("test_api", tokens=1)
            results.append(result)

        # Try to make 15 concurrent requests
        threads = []
        for _ in range(15):
            t = threading.Thread(target=make_request)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Exactly 10 should succeed (due to initial capacity of 10)
        assert sum(results) == 10
        assert len([r for r in results if not r]) == 5

    def test_endpoints_independent(self):
        """Test that different endpoints have independent rate limits."""
        limiter = RateLimiter(custom_limits={
            "api1": 10,
            "api2": 5
        })

        # Exhaust api1
        for _ in range(10):
            limiter.is_allowed("api1", tokens=1)

        # api1 should be exhausted
        assert limiter.is_allowed("api1", tokens=1) is False

        # api2 should still have tokens
        assert limiter.is_allowed("api2", tokens=1) is True
        assert limiter.is_allowed("api2", tokens=1) is True
        assert limiter.is_allowed("api2", tokens=1) is True
        assert limiter.is_allowed("api2", tokens=1) is True
        assert limiter.is_allowed("api2", tokens=1) is True
        assert limiter.is_allowed("api2", tokens=1) is False
