# Trend Discovery Agent - Development Guide

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Run Tests

```bash
# Run cache manager tests (no external dependencies required)
python3 test_cache_standalone.py

# Run full test suite (requires pytest and all dependencies)
pytest
```

### 3. Start Development Server

```bash
# Install dependencies first if not done
pip install -r requirements.txt

# Start the FastAPI server
python3 main.py
```

The API will be available at `http://localhost:8000`

- Interactive API docs: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Project Structure

```
trend-discovery-agent/
├── cache_manager.py              # SQLite-based cache with TTL support
├── google_trends_client.py       # Google Trends API client with caching
├── twitter_client.py             # Twitter/X API client with caching
├── news_api_client.py            # NewsAPI client with caching and rate limiting (AIC-21)
├── rate_limiter.py               # Token bucket rate limiter for APIs (AIC-21)
├── scoring_algorithm.py          # Trend scoring with relevance/velocity/audience metrics
├── trend_database.py             # SQLAlchemy database models and manager
├── batch_pipeline.py             # Hourly batch processor (AIC-18)
├── main.py                       # FastAPI application with APScheduler
├── test_cache_manager.py         # Cache manager unit tests
├── test_google_trends_client.py  # Google Trends client tests
├── test_twitter_client.py        # Twitter client tests
├── test_scoring_algorithm.py     # Scoring algorithm tests
├── test_news_api_client.py       # NewsAPI client tests
├── test_rate_limiter.py          # Rate limiter tests
├── test_batch_pipeline.py        # Batch pipeline unit and integration tests
├── test_cache_standalone.py      # Standalone cache tests (no dependencies)
├── requirements.txt              # Python dependencies
├── pytest.ini                    # Pytest configuration
├── .gitignore                    # Git ignore rules
├── README.md                     # Project overview
├── DEVELOPMENT.md                # This file
├── SCORING.md                    # Scoring algorithm documentation
├── BATCH_PIPELINE.md             # Batch pipeline documentation (AIC-18)
└── docs/                         # Additional documentation
```

## API Endpoints

### Health Check
- `GET /health` - Service health status

### Trending Searches
- `GET /trends/trending?region=UNITED_STATES` - Get trending searches for a region
- `GET /trends/trending-multi?regions=UNITED_STATES,INDIA` - Get trends for multiple regions

### Interest Tracking
- `GET /trends/interest?keywords=python,javascript&timeframe=now 7-d` - Get interest over time

### Cache Management
- `GET /cache/stats` - Get cache statistics
- `DELETE /cache/clear?key=optional_key` - Clear cache
- `POST /cache/cleanup` - Remove expired entries

## Features

### Caching Mechanism

The `CacheManager` class provides:
- SQLite-based persistent storage
- TTL (Time-To-Live) support with configurable expiration
- Automatic fallback to expired cache when API is unavailable
- Cache statistics and cleanup utilities

### Google Trends Integration

The `GoogleTrendsClient` class provides:
- Trending searches by region
- Interest over time tracking
- Multi-region aggregation
- Automatic caching with fallback
- Comprehensive error handling

### Error Handling

The system implements a tiered approach:
1. **Primary**: Fetch fresh data from Google Trends API
2. **Secondary**: Return valid cached data if available
3. **Fallback**: Use expired cached data if API fails
4. **Final**: Return error if no data available

## Development Workflow

### Testing

```bash
# Run standalone tests (works without installing all dependencies)
python3 test_cache_standalone.py

# Run full test suite
pytest -v

# Run specific test
pytest test_cache_manager.py::test_cache_set_and_get -v

# Run with coverage
pytest --cov=. --cov-report=html
```

### Code Quality

```bash
# Format code
black *.py

# Check imports
flake8 *.py

# Type checking
mypy *.py
```

## API Endpoints

### Research & Fact-Checking Endpoints (AIC-21)

The trend discovery agent now includes research and fact-checking capabilities powered by NewsAPI.

#### Search News Articles
```
GET /research/search?keyword=<keyword>&sort_by=publishedAt&limit=10
```
Search for news articles by keyword with caching and rate limiting.

**Query Parameters:**
- `keyword` (required): Search term or keyword
- `sort_by` (optional): 'relevancy', 'publishedAt' (default), or 'popularity'
- `limit` (optional): Number of articles to return (1-100, default 10)

**Response:**
```json
{
  "source": "api|cache|cache_fallback|error",
  "query": "python",
  "articles": [...],
  "total_results": 1250,
  "timestamp": "2026-03-25T14:30:00Z",
  "note": "Fresh data from NewsAPI"
}
```

#### Get Trending News
```
GET /research/trending?country=us&category=technology&limit=10
```
Get top headlines for a country with optional category filter.

**Query Parameters:**
- `country` (optional): Country code ('us', 'in', 'gb', etc., default 'us')
- `category` (optional): 'business', 'entertainment', 'general', 'health', 'science', 'sports', 'technology'
- `limit` (optional): Number of articles (1-100, default 10)

#### Get Trend-Related News
```
GET /research/trend-news?trend=<trend>&limit=10
```
Get news articles related to a specific trending topic for fact-checking and context.

**Query Parameters:**
- `trend` (required): Trend name or topic
- `limit` (optional): Number of articles (1-100, default 10)

#### Rate Limit Status
```
GET /research/rate-limit
```
Get current rate limit status for NewsAPI.

**Response:**
```json
{
  "available_requests": 89,
  "capacity": 100,
  "refill_rate": "0.00116 requests/second",
  "daily_limit": 100,
  "note": "NewsAPI free tier allows 100 requests per day"
}
```

#### Cache Management
```
GET /research/cache/stats
```
Get NewsAPI cache statistics.

```
DELETE /research/cache/clear?key=<optional_key>
```
Clear cache entries. If `key` is provided, clears only that entry.

## Configuration

### Cache Configuration

The `CacheManager` can be configured with:
- `db_path`: Path to SQLite database (default: `cache.db`)
- `ttl_hours`: Time-to-live for cache entries in hours (default: `1`)

Example:
```python
cache_manager = CacheManager(db_path="cache/trends.db", ttl_hours=1)
```

### Rate Limiter Configuration

The `RateLimiter` uses token bucket algorithm with configurable daily limits:

```python
from rate_limiter import RateLimiter

rate_limiter = RateLimiter(custom_limits={
    "newsapi": 100,        # 100 requests per day
    "google_trends": 1000, # High limit
    "twitter": 450         # Twitter free tier
})
```

### NewsAPI Client Configuration

The `NewsAPIClient` integrates with caching and rate limiting:

```python
from news_api_client import NewsAPIClient
from cache_manager import CacheManager
from rate_limiter import RateLimiter

cache = CacheManager(db_path="cache/newsapi.db", ttl_hours=3)
limiter = RateLimiter()

news_client = NewsAPIClient(
    api_key="your_newsapi_key",  # or NEWSAPI_KEY env var
    cache_manager=cache,
    rate_limiter=limiter
)

# Search for articles
result = news_client.search_news(query="python", sort_by="publishedAt", page_size=10)

# Get top headlines
result = news_client.get_top_headlines(country="us", category="technology")

# Check rate limit status
status = news_client.get_rate_limit_status()
```

### Client Configuration

The `GoogleTrendsClient` supports:
- Custom cache manager instance
- Language/locale settings (`hl` parameter)
- Timezone configuration (`tz` parameter)

Example:
```python
client = GoogleTrendsClient(
    cache_manager=custom_cache,
    cache_ttl_hours=2
)
```

## Environment Setup

### Required Environment Variables

```bash
# NewsAPI key (get free key from https://newsapi.org/)
export NEWSAPI_KEY="your_newsapi_key_here"

# Twitter/X API (optional, for Twitter endpoints)
export TWITTER_BEARER_TOKEN="your_twitter_bearer_token"
```

### Create .env file

```bash
NEWSAPI_KEY=your_key_here
TWITTER_BEARER_TOKEN=your_token_here
```

Load with python-dotenv:
```python
from dotenv import load_dotenv
load_dotenv()
```

## Known Limitations

1. **Google Trends API**: Uses `pytrends` library which is unofficial reverse-engineered API
   - Subject to rate limiting
   - May break if Google changes their interface
   - Returns data for top 25 trends per region

2. **NewsAPI Free Tier**: Limited to 100 requests per day
   - Token bucket rate limiting helps distribute requests evenly
   - Consider paid plans for higher limits
   - Caching reduces unnecessary API calls

3. **Database**: Current implementation uses SQLite for both cache and storage
   - SQLite suitable for single-server deployments
   - Phase 3 will add PostgreSQL for production-scale systems

4. **Single Server**: Current implementation designed for single-server deployment
   - APScheduler for hourly batch jobs
   - For multi-server deployments, consider using distributed task queue

## Completed

### Phase 1 (Trend Discovery)
- [x] Integrate Twitter/X API for trending topics
- [x] Implement trend scoring algorithm
- [x] Build hourly batch pipeline with APScheduler (AIC-18)
- [x] SQLite database for trend storage
- [x] Comprehensive error handling and logging

### Phase 1.5 (Dashboard)
- [x] Create web dashboard for trend visualization (AIC-19)
- [x] Interactive charts with Chart.js
- [x] Real-time data with auto-refresh

### Phase 2 (Research & Fact-Checking)
- [x] Integrate NewsAPI for research and fact-checking (AIC-21)
- [x] Implement token bucket rate limiting with per-endpoint tracking
- [x] Add news search, trending news, and trend-related news endpoints
- [x] Comprehensive caching strategy for research data
- [x] Cache fallback on API failures

## Next Steps (Phase 3)

- [ ] Add PostgreSQL for production-scale storage
- [ ] Add monitoring and alerting for API health
- [ ] Implement trend deduplication across sources
- [ ] Add webhook notifications for significant trends
- [ ] Integrate fact-checking scores from multiple sources
- [ ] Create enhanced dashboard with news/articles context
- [ ] Add trend prediction capabilities

## Troubleshooting

### Import Errors
If you get import errors, ensure:
1. You're running Python 3.9+
2. All dependencies are installed: `pip install -r requirements.txt`
3. The current directory is in PYTHONPATH

### Cache Not Working
1. Check database permissions: `ls -la cache.db`
2. Clear cache and restart: `rm cache.db && python3 main.py`
3. Check cache stats: `curl http://localhost:8000/cache/stats`

### API Rate Limiting
If Google Trends API returns 429 (Too Many Requests):
1. Wait for cache TTL to expire before retrying
2. The system automatically falls back to cached data
3. Consider increasing cache TTL in production

## References

- [pytrends GitHub](https://github.com/GeneralMills/pytrends)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLite Documentation](https://www.sqlite.org/docs.html)
- [APScheduler Documentation](https://apscheduler.readthedocs.io/)
