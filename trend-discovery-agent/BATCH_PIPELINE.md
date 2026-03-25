# Hourly Batch Pipeline - AIC-18 Implementation

## Overview

The hourly batch pipeline automatically collects trend data from Google Trends and Twitter/X, scores them using the scoring algorithm, and stores results in a persistent database for dashboard consumption.

**Implementation Date:** March 25, 2026
**Task ID:** AIC-18
**Status:** Complete

## Architecture

### Components

1. **TrendDatabase** (`trend_database.py`)
   - SQLAlchemy-based database manager
   - Models: `TrendResult`, `BatchRunLog`
   - Persistent storage using SQLite (default) or PostgreSQL
   - Includes data cleanup utilities

2. **BatchPipeline** (`batch_pipeline.py`)
   - Orchestrates the complete pipeline workflow
   - Collects trends from Google Trends and Twitter
   - Scores and ranks trends
   - Stores results in database
   - Comprehensive error handling and logging

3. **FastAPI Integration** (updated `main.py`)
   - APScheduler-based job scheduling
   - RESTful API endpoints for batch control
   - Dashboard data endpoint
   - Startup/shutdown handlers

### Data Flow

```
┌─────────────────────────────────────────────────────────┐
│         Hourly Batch Pipeline Execution (Top of Hour)    │
└─────────────┬───────────────────────────────────────────┘
              │
              ├─→ 1. Collect from Google Trends (by region)
              │   - UNITED_STATES, INDIA, JAPAN
              │   - Top 20 trends per region
              │
              ├─→ 2. Collect from Twitter/X (by location)
              │   - Worldwide, US, UK, India, Japan
              │   - Top 20 trends per location
              │
              ├─→ 3. Score All Trends
              │   - Relevance score (40%)
              │   - Velocity score (35%)
              │   - Audience score (25%)
              │   - Overall score calculation
              │
              ├─→ 4. Store in Database
              │   - TrendResult table
              │   - BatchRunLog for tracking
              │
              └─→ 5. Report Results
                  - Log batch statistics
                  - Track success/failure
```

## Database Schema

### TrendResult Table

Stores individual trend scores from each batch run.

```sql
trend_results:
  - id (INTEGER, PRIMARY KEY)
  - trend_name (STRING) - The trend text
  - source (STRING) - 'google_trends', 'twitter', or 'combined'
  - region (STRING) - Geographic region (e.g., 'UNITED_STATES')
  - location (STRING) - Location for Twitter trends
  - relevance_score (FLOAT) - Keyword relevance (0-100)
  - velocity_score (FLOAT) - Trend velocity/acceleration (0-100)
  - audience_score (FLOAT) - Audience size (0-100)
  - overall_score (FLOAT) - Composite score (0-100)
  - rank (INTEGER) - Rank in scoring results
  - scorer_type (STRING) - Which scorer was used
  - component_scores (JSON) - Detailed component breakdown
  - metadata (JSON) - Additional context
  - collected_at (DATETIME) - When data was collected
  - created_at (DATETIME) - Record creation time
  - batch_run_id (STRING) - References batch execution
```

### BatchRunLog Table

Tracks each batch execution for monitoring and debugging.

```sql
batch_run_logs:
  - id (INTEGER, PRIMARY KEY)
  - batch_run_id (STRING) - Unique batch identifier
  - status (STRING) - 'running', 'success', 'error', 'partial'
  - started_at (DATETIME)
  - completed_at (DATETIME)
  - duration_seconds (FLOAT)
  - trends_collected (INTEGER)
  - trends_scored (INTEGER)
  - trends_stored (INTEGER)
  - google_trends_success (INTEGER)
  - twitter_trending_success (INTEGER)
  - error_message (TEXT)
  - error_details (JSON)
  - created_at (DATETIME)
```

## Features

### Automated Hourly Scheduling

The pipeline runs automatically at the top of every hour using APScheduler.

```
Execution Schedule: 00:00, 01:00, 02:00, ... 23:00 (UTC)
```

**Features:**
- Misfire grace time: 10 seconds
- Single instance enforcement: Only one pipeline can run simultaneously
- Automatic restart on app startup

### Error Handling

Multi-layer error handling ensures robustness:

1. **Per-Region Handling**: Individual region/location failures don't crash the entire batch
2. **Context Manager**: Automatic database transaction management
3. **Error Logging**: Detailed error tracking in BatchRunLog
4. **Graceful Degradation**: Partial success scenarios handled properly

### Data Retention

Automatic cleanup of old trend data:

```python
# Keep last 30 days by default
batch_pipeline.cleanup_old_data(days_to_keep=30)
```

## API Endpoints

### Manual Batch Trigger

```bash
POST /batch/run
```

Manually execute the batch pipeline immediately.

**Response:**
```json
{
  "status": "completed",
  "message": "Batch pipeline executed",
  "timestamp": "2026-03-25T13:05:30.123456"
}
```

### Batch Status

```bash
GET /batch/status
```

Get current batch scheduler and execution status.

**Response:**
```json
{
  "scheduler_running": true,
  "next_run": "2026-03-25T14:00:00",
  "last_run": "2026-03-25T13:00:00",
  "last_run_status": "success",
  "trends_stored": 120
}
```

### Dashboard Data

```bash
GET /dashboard?limit=20
```

Get top trends formatted for dashboard consumption.

**Response:**
```json
{
  "timestamp": "2026-03-25T13:05:30.123456",
  "trends_count": 20,
  "last_run": {
    "batch_run_id": "a1b2c3d4",
    "completed_at": "2026-03-25T13:00:30",
    "trends_stored": 120
  },
  "trends": [
    {
      "rank": 1,
      "trend": "Python",
      "overall_score": 92.5,
      "relevance_score": 85.0,
      "velocity_score": 88.0,
      "audience_score": 95.0,
      "source": "google_trends",
      "region": "UNITED_STATES",
      "collected_at": "2026-03-25T13:00:00"
    },
    ...
  ]
}
```

### Data Cleanup

```bash
DELETE /batch/cleanup?days_to_keep=30
```

Remove trend results older than specified days.

**Response:**
```json
{
  "deleted_count": 1250,
  "days_retained": 30,
  "timestamp": "2026-03-25T13:05:30.123456"
}
```

## Configuration

### Database Configuration

**SQLite (Development)**
```python
trend_db = TrendDatabase(db_path="sqlite:///data/trends.db")
```

**PostgreSQL (Production)**
```python
trend_db = TrendDatabase(
    db_path="postgresql://user:password@localhost:5432/trends"
)
```

### Scheduler Configuration

Edit `main.py` to customize:

```python
# Change from hourly (minute=0) to custom schedule
scheduler.add_job(
    batch_pipeline.run_batch,
    trigger=CronTrigger(hour="*", minute=0),  # Run at top of every hour
    ...
)
```

**Common Cron Patterns:**
- `minute=0` - Every hour
- `minute=0, hour="*/4"` - Every 4 hours
- `minute=0, hour=9` - Daily at 9 AM

### Regions and Locations Monitored

**Google Trends Regions:**
- `UNITED_STATES`
- `INDIA`
- `JAPAN`

**Twitter Locations:**
- `worldwide`
- `us`
- `uk`
- `india`
- `japan`

To add more regions/locations, edit `batch_pipeline.py`:

```python
self.google_trends_regions = ["UNITED_STATES", "INDIA", "JAPAN", "BRAZIL"]
self.twitter_locations = ["worldwide", "us", "uk", "india", "japan", "brazil"]
```

## Monitoring

### Batch Run Logs

Query batch execution history:

```python
session = trend_db.get_session()
latest_run = trend_db.get_latest_batch_run(session)
print(f"Status: {latest_run.status}")
print(f"Trends stored: {latest_run.trends_stored}")
print(f"Duration: {latest_run.duration_seconds}s")
```

### Trend Analytics

Get top trends from the last 24 hours:

```python
session = trend_db.get_session()
top_trends = trend_db.get_top_trends_by_score(
    session,
    limit=20,
    since_hours=24
)
```

## Testing

Run the test suite:

```bash
# Install test dependencies
pip install pytest pytest-asyncio

# Run batch pipeline tests
pytest test_batch_pipeline.py -v

# Run all tests
pytest -v
```

**Test Coverage:**
- Database operations (CRUD)
- Trend collection from both sources
- Scoring and ranking
- Error handling
- Integration tests with mocked APIs

## Performance Characteristics

### Typical Execution Time

```
Collection Phase:    ~2-3 seconds per API (with caching)
Scoring Phase:       ~1-2 seconds for 100+ trends
Storage Phase:       ~1 second
Total per run:       ~5-10 seconds
```

### Data Volume

```
Per batch run:
  - Google Trends: ~60 trends (3 regions × 20 trends)
  - Twitter/X:     ~100 trends (5 locations × 20 trends)
  - Total:         ~160 trends per hour

Daily:            ~3,840 trends
Monthly:          ~115,200 trends
```

### Database Growth

```
With 30-day retention:
  - TrendResult: ~3,840 rows per day
  - BatchRunLog: 24 rows per day (one per hour)
  - Total size: ~500MB-1GB per month (SQLite)
```

## Troubleshooting

### Batch not running on schedule

1. Check scheduler status: `GET /batch/status`
2. Verify app is running: `GET /health`
3. Check logs for startup errors
4. Manual trigger to test: `POST /batch/run`

### High execution time

- Check API rate limits (Google Trends, Twitter)
- Verify database performance
- Monitor cache hit rates
- Consider batch parallelization (future enhancement)

### Database disk space

- Run cleanup job: `DELETE /batch/cleanup`
- Adjust retention: `days_to_keep` parameter
- Consider archival to cold storage for historical data

### Missing trends

- Verify API credentials (Twitter)
- Check regional availability
- Review error logs in BatchRunLog
- Test manual collection: `GET /trends/trending`

## Future Enhancements

1. **Parallel Collection**: Collect from multiple regions simultaneously
2. **Intelligent Deduplication**: Detect same trends across sources
3. **Trend Velocity Tracking**: Calculate real velocity from historical data
4. **Machine Learning Scoring**: Train models on engagement metrics
5. **Webhook Notifications**: Alert on significant trend events
6. **PostgreSQL Migration**: Move from SQLite for production scale
7. **Redis Caching**: Cache popular trend queries
8. **Trend Prediction**: Forecast future trend movements

## Integration with Phase 1 Goals

**Success Metrics (by April 6, 2026):**

- ✅ 20+ trends identified/day
- ✅ Hourly batch pipeline implemented
- ✅ Reliable trend discovery and storage
- ✅ Scoring algorithm integrated
- ⏳ Dashboard live (AIC-12)
- ⏳ Content Creation Agent integration (Phase 2)

## References

- Task: [AIC-18](/AIC/issues/AIC-18) - Build hourly batch pipeline
- Parent Task: [AIC-11](/AIC/issues/AIC-11) - Build Trend Discovery Agent (Phase 1)
- Grand-parent Task: [AIC-5](/AIC/issues/AIC-5) - Execute Automated Content Empire Strategy
- Project: [自動化內容與流量帝國](/AIC/projects/content-creator)
- Goal: [月淨利>0](/AIC/goals/monthly-profit)
