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
├── scoring_algorithm.py          # Trend scoring with relevance/velocity/audience metrics
├── trend_database.py             # SQLAlchemy database models and manager
├── batch_pipeline.py             # Hourly batch processor (AIC-18)
├── main.py                       # FastAPI application with APScheduler
├── test_cache_manager.py         # Cache manager unit tests
├── test_google_trends_client.py  # Google Trends client tests
├── test_twitter_client.py        # Twitter client tests
├── test_scoring_algorithm.py     # Scoring algorithm tests
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

## Configuration

### Cache Configuration

The `CacheManager` can be configured with:
- `db_path`: Path to SQLite database (default: `cache.db`)
- `ttl_hours`: Time-to-live for cache entries in hours (default: `1`)

Example:
```python
cache_manager = CacheManager(db_path="cache/trends.db", ttl_hours=1)
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

## Known Limitations

1. **Google Trends API**: Uses `pytrends` library which is unofficial reverse-engineered API
   - Subject to rate limiting
   - May break if Google changes their interface
   - Returns data for top 25 trends per region

2. **No Database Persistence**: Current implementation uses SQLite for cache only
   - Historical data not stored long-term
   - Phase 2 will add PostgreSQL integration

3. **Single Server**: Current implementation is single-threaded
   - Phase 2 will add APScheduler for hourly batch jobs

## Completed (Phase 1)

- [x] Integrate Twitter/X API for trending topics
- [x] Implement trend scoring algorithm
- [x] Build hourly batch pipeline with APScheduler (AIC-18)
- [x] SQLite database for trend storage
- [x] Comprehensive error handling and logging

## Next Steps (Phase 2)

- [ ] Create web dashboard for visualization
- [ ] Add PostgreSQL for production-scale storage
- [ ] Add monitoring and alerting
- [ ] Implement trend deduplication across sources
- [ ] Add webhook notifications for significant trends
- [ ] Integrate with Content Creation Agent

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
