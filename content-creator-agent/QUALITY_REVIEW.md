# Quality Review Queue System

## Overview

The Quality Review Queue System implements a 10% human sampling pipeline for generated content quality assurance. It tracks rejection rates, provides quality metrics, and feeds insights back into content improvement processes.

**Key Metrics Target (Phase 2 Deadline: 2026-04-20):**
- **Sampling Rate**: 10% of all generated content
- **Target Rejection Rate**: <5%
- **Target Average Quality Score**: >70/100

## Architecture

### Components

1. **ContentStorage** (`content_storage.py`)
   - SQLite-based persistence layer
   - Manages generated content records
   - Tracks review status and feedback
   - Computes quality statistics

2. **QualityReviewQueue** (`quality_review_queue.py`)
   - Implements 10% random sampling strategy
   - Orchestrates review workflow
   - Generates quality recommendations
   - Calculates health metrics

3. **API Integration** (`main.py`)
   - Extends FastAPI with quality review endpoints
   - Automatically stores generated content
   - Exposes review queue and metrics

## Database Schema

### `generated_content` table

```sql
CREATE TABLE generated_content (
    id TEXT PRIMARY KEY,
    trend_topic TEXT NOT NULL,
    content_type TEXT NOT NULL,
    content TEXT NOT NULL,
    provider TEXT NOT NULL,
    quality_score REAL NOT NULL,
    created_at TEXT NOT NULL,
    metadata TEXT NOT NULL,
    sampled BOOLEAN DEFAULT 0,
    review_status TEXT,
    review_feedback TEXT,
    reviewed_at TEXT,
    updated_at TEXT NOT NULL
)
```

**Fields:**
- `id`: Unique content identifier (UUID)
- `trend_topic`: Topic the content addresses
- `content_type`: Type of content (article, video_script, etc.)
- `content`: Full content text
- `provider`: LLM provider used (claude, gpt)
- `quality_score`: Automated quality score (0-100)
- `sampled`: Whether content is in review queue
- `review_status`: 'pending', 'approved', or 'rejected'
- `review_feedback`: Reviewer's comments
- `reviewed_at`: Timestamp of review

## API Endpoints

### Content Generation (Modified)

```bash
POST /generate
Content-Type: application/json

{
  "trend_topic": "AI in healthcare",
  "content_type": "article",
  "provider": "claude",
  "metadata": {"word_count": 2000}
}
```

**Changes:**
- Automatically stores generated content
- Samples 10% of content for human review
- Returns quality score with response

**Response:**
```json
{
  "success": true,
  "content": "...",
  "content_type": "article",
  "model": "claude-3.5-sonnet",
  "metadata": {...},
  "errors": [],
  "quality_score": {
    "overall_score": 75.5,
    "readability_score": 80.0,
    "length_score": 85.0,
    "structure_score": 70.0,
    "metadata": {...}
  }
}
```

### Get Review Queue

```bash
GET /review-queue?limit=10
```

Retrieves pending content items waiting for human review.

**Response:**
```json
[
  {
    "id": "uuid-123",
    "trend_topic": "AI Safety",
    "content_type": "article",
    "content": "...",
    "provider": "claude",
    "quality_score": 75.5,
    "created_at": "2026-03-26T10:00:00",
    "metadata": {...}
  },
  ...
]
```

**Parameters:**
- `limit` (optional, default=10, max=100): Number of items to return

### Submit Review

```bash
POST /submit-review
Content-Type: application/json

{
  "content_id": "uuid-123",
  "status": "approved",
  "feedback": "Good quality, well-structured",
  "reviewer_id": "reviewer-1"
}
```

Submits human review feedback for content.

**Parameters:**
- `content_id` (required): ID of content being reviewed
- `status` (required): 'approved' or 'rejected'
- `feedback` (optional): Reviewer comments
- `reviewer_id` (optional): ID of reviewer

**Response:**
```json
{
  "success": true,
  "content_id": "uuid-123",
  "status": "approved",
  "message": "Content approved successfully"
}
```

### Get Quality Metrics

```bash
GET /quality-metrics?days=7
```

Retrieves quality statistics and performance metrics.

**Parameters:**
- `days` (optional, default=7, max=90): Period to analyze

**Response:**
```json
{
  "period_days": 7,
  "total_content": 150,
  "sampled_content": 15,
  "sampling_rate": 10.0,
  "reviewed_content": 12,
  "approved_content": 11,
  "rejected_content": 1,
  "rejection_rate": 8.33,
  "average_quality_score": 72.5,
  "high_quality_count": 85,
  "meets_target_rejection_rate": true,
  "meets_target_quality_score": true,
  "health_status": "good"
}
```

**Metrics:**
- `sampling_rate`: Actual percentage of content sampled (target: 10%)
- `rejection_rate`: Percentage of reviewed content rejected (target: <5%)
- `average_quality_score`: Mean quality score (target: >70)
- `health_status`: Overall system health (excellent, good, fair, poor)

### Get Quality Recommendations

```bash
GET /quality-recommendations
```

Retrieves data-driven recommendations for improving content quality.

**Response:**
```json
{
  "actions": [
    "Rejection rate is 8.33%, exceeds target of 5.0%"
  ],
  "focus_areas": [
    "content_generation"
  ],
  "positive_notes": [
    "Average quality score (72.5) meets expectations"
  ]
}
```

### Batch Sample Unreviewed Content

```bash
POST /batch-sample-unreviewed?limit=100
```

Backfill sampling coverage on existing content. Useful for legacy content or recovery scenarios.

**Parameters:**
- `limit` (optional, default=100, max=1000): Max items to process

**Response:**
```json
{
  "success": true,
  "sampled_count": 8,
  "message": "8 items added to review queue"
}
```

## Usage Examples

### Example 1: Complete Review Workflow

```python
import requests

API_BASE = "http://localhost:8001"

# 1. Generate content (automatically sampled if in 10%)
response = requests.post(f"{API_BASE}/generate", json={
    "trend_topic": "Quantum Computing",
    "content_type": "article",
    "provider": "claude"
})
result = response.json()
print(f"Generated: {result['content_type']}, Score: {result['quality_score']['overall_score']}")

# 2. Check review queue
queue = requests.get(f"{API_BASE}/review-queue", params={"limit": 5}).json()
print(f"Items pending review: {len(queue)}")

# 3. Review an item
if queue:
    item = queue[0]
    review = requests.post(f"{API_BASE}/submit-review", json={
        "content_id": item["id"],
        "status": "approved" if item["quality_score"] > 70 else "rejected",
        "feedback": "Well-written and informative",
        "reviewer_id": "reviewer-1"
    })
    print(f"Review submitted: {review.json()['status']}")

# 4. Check metrics
metrics = requests.get(f"{API_BASE}/quality-metrics", params={"days": 7}).json()
print(f"Rejection rate: {metrics['rejection_rate']:.1f}%")
print(f"Health status: {metrics['health_status']}")

# 5. Get recommendations
recommendations = requests.get(f"{API_BASE}/quality-recommendations").json()
if recommendations['actions']:
    print("Recommended actions:")
    for action in recommendations['actions']:
        print(f"  - {action}")
```

### Example 2: Batch Processing and Analytics

```python
import requests
from datetime import datetime

API_BASE = "http://localhost:8001"

# Backfill sampling on existing content
backfill = requests.post(
    f"{API_BASE}/batch-sample-unreviewed",
    params={"limit": 500}
).json()
print(f"Added {backfill['sampled_count']} items to review queue")

# Analyze quality trends
for days in [7, 14, 30]:
    metrics = requests.get(
        f"{API_BASE}/quality-metrics",
        params={"days": days}
    ).json()

    print(f"\n{days}-day period:")
    print(f"  Generated: {metrics['total_content']}")
    print(f"  Sampled: {metrics['sampled_content']} ({metrics['sampling_rate']:.1f}%)")
    print(f"  Rejection rate: {metrics['rejection_rate']:.2f}%")
    print(f"  Avg quality: {metrics['average_quality_score']:.1f}/100")
```

## Quality Score Components

The automated quality score combines four dimensions:

### 1. Readability Score (30% weight)
- Based on Flesch-Kincaid grade level
- Optimal: Grade 6-8 (accessible to general audience)
- Penalties for overly complex or overly simple text

### 2. Length Score (30% weight)
- Content-type specific min/max word counts
- 100% if within range, penalties for too short/long
- Example ranges:
  - Article: 800-3000 words
  - Video script: 400-2500 words
  - Caption: 20-500 words

### 3. Structure Score (40% weight)
- Presence of required sections and key phrases
- Paragraph diversity and sentence variety
- Expected section count per content type

### 4. Overall Score (Weighted Average)
- Range: 0-100
- Threshold for high quality: ≥70
- Used to guide rejection decisions

## Sampling Strategy

### 10% Random Sampling

The system uses uniform random sampling:

```python
if random.random() < 0.10:  # 10% probability
    mark_for_review(content_id)
```

**Properties:**
- Simple and unbiased
- Every piece of content has equal 10% chance
- Over time, converges to exactly 10% sampling rate
- Can be refined based on quality_score (optional future enhancement)

### Sampling Rates by Quality

Possible future enhancement: adjust sampling rate by quality_score

```python
# Example: increased sampling for low-quality content
if score < 50:
    sample_rate = 0.20  # 20% sampling
elif score < 70:
    sample_rate = 0.15  # 15% sampling
else:
    sample_rate = 0.05  # 5% sampling
```

## Health Status Calculation

The system calculates overall health based on two key metrics:

| Health Status | Rejection Rate | Avg Quality Score |
|---|---|---|
| Excellent | ≤3% | ≥75 |
| Good | ≤5% | ≥70 |
| Fair | ≤10% | ≥60 |
| Poor | >10% | <60 |

## Feedback Loop

### Using Rejection Patterns

Rejected content provides valuable signals:

1. **Analyze rejection feedback** → Identify common issues
2. **Group by content type** → Type-specific problems
3. **Group by provider** → Claude vs GPT performance
4. **Update templates** → Improve prompts
5. **Retrain scoring** → Calibrate automated scores
6. **Adjust parameters** → Optimize generation

### Example: Template Improvement

```
Rejected due to: "Missing call-to-action in conclusion"
  → Content type: article
  → Provider: claude
  → Issue: Template missing CTA instruction

Action: Update prompt_templates.py for article type
```

## Data Retention

The system includes cleanup for old records:

```python
# Delete records older than 90 days
storage.cleanup_old_records(days=90)
```

**Recommended schedule:**
- Run weekly via cron job
- Maintain 30-60 days rolling window
- Backup data before cleanup

## Performance Considerations

### Database Optimization

```python
# Indexes created for fast queries
- idx_created_at      # For time-based filtering
- idx_review_status   # For queue queries
- idx_sampled         # For sampling operations
```

### Scaling Recommendations

- **SQLite**: Suitable for <1M records
- **Migration path**: PostgreSQL for large scale
- **Batch inserts**: Use for high-volume generation
- **Archive strategy**: Move old data to data warehouse

## Integration with Content Pipeline

```
Trend Discovery → Content Generation → Quality Review → Distribution
                                            ↓
                                      Human Review (10%)
                                            ↓
                                      Feedback Loop
                                            ↓
                                      Template Updates
```

## Success Metrics (Phase 2)

| Metric | Target | Status |
|---|---|---|
| Content generation | 5+/day | In progress |
| Avg quality score | >70/100 | Depends on content |
| Rejection rate | <5% | Depends on reviews |
| Review queue turnaround | <24h | Operational |
| Data integrity | 100% | SQLite ensures |
| System availability | 99.9% | Lightweight system |

## Troubleshooting

### Low Sampling Rate

**Problem**: Actual sampling < 10%

**Causes:**
- Many items already have review_status set
- Unsampled queue depleted

**Solution:**
```bash
POST /batch-sample-unreviewed?limit=1000
```

### High Rejection Rate

**Problem**: Rejection rate > 5%

**Causes:**
- Template issues
- Provider performance
- Content type mismatch

**Solution:**
1. Get recommendations: `GET /quality-recommendations`
2. Analyze rejected content by type/provider
3. Update templates
4. Monitor improvement

### Database Issues

**Problem**: Database locked or corrupted

**Causes:**
- Concurrent writes
- Unexpected process termination

**Solution:**
- Restart API service
- Verify database integrity: `sqlite3 content_storage.db "PRAGMA integrity_check;"`
- Restore from backup if needed

## Future Enhancements

1. **Quality-based sampling**: Higher sampling for uncertain quality
2. **A/B testing**: Compare providers and templates
3. **Predictive flagging**: ML model to predict rejection
4. **Feedback summarization**: Aggregate feedback by theme
5. **Automated rewriting**: Suggest fixes for rejected content
6. **Multi-language support**: Handle non-English content
7. **Workflow integration**: Connect to external review systems
8. **Real-time dashboards**: Live metrics visualization

## References

- [Quality Scorer Documentation](./quality_scorer.py)
- [Content Generator Documentation](./content_generator.py)
- [Content Storage API](./content_storage.py)
- [Quality Review Queue API](./quality_review_queue.py)
- [Main API Documentation](./main.py)
