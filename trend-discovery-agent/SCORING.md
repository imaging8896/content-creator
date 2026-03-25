# Trend Scoring Algorithm

The trend scoring algorithm evaluates trends based on three key metrics:
- **Relevance**: How relevant a trend is to target audience (based on keywords, categories, specificity)
- **Velocity**: Rate of growth/momentum (based on trending position, tweet velocity, search volume changes)
- **Audience**: Audience size and engagement (based on engagement metrics, tweet count, search volume, position)

## Algorithm Details

### Relevance Score (0-100)

Calculated using:
1. **Keyword matching** (0-40 points): Exact or substring match with target keywords
2. **Category matching** (0-25 points): Match with target content categories
3. **Keyword specificity** (0-20 points): Multi-word trends score higher than single words
4. **Generic term penalty** (0-15 points): Bonus for avoiding generic terms like "new", "update", etc.

Example:
- "Python Machine Learning Framework" scores high on relevance for tech audience
- "New Update" scores low (generic terms penalized)

### Velocity Score (0-100)

Calculated using:
1. **Position-based velocity** (0-40 points): Earlier position in trending list = higher growth rate
   - Uses exponential decay: `40 * exp(-position/10)`
2. **Tweet velocity** (0-30 points): Ratio of recent tweets to total tweets
3. **Volume change** (0-20 points): Growth rate of search volume vs previous period
4. **Time-since-emergence** (0-10 points): Newer trends score higher

Example:
- Position 0: 40 points
- Position 10: ~18 points
- Position 20: ~5 points

### Audience Score (0-100)

Calculated using:
1. **Engagement metrics** (0-35 points): Likes, retweets, replies (retweets weighted 2x)
2. **Discussion volume** (0-30 points): Total tweet count (log scale)
3. **Search volume** (0-20 points): Google search volume (log scale)
4. **Position-based audience** (0-15 points): Top positions imply larger reach

Example:
- 1,000 tweets with 0.05 engagement rate: ~20 points
- 100,000 tweets with 0.08 engagement rate: ~35 points

### Overall Score

Weighted combination of component scores:
```
overall = (relevance × w_rel) + (velocity × w_vel) + (audience × w_aud)
```

Default weights:
- **Relevance**: 0.40 (40%)
- **Velocity**: 0.35 (35%)
- **Audience**: 0.25 (25%)

## API Endpoints

### List Available Scorers

**GET /score/scorers**

Returns available scorer types and their descriptions.

```bash
curl http://localhost:8000/score/scorers
```

Response:
```json
{
  "tech": "Optimized for technology and programming trends",
  "entertainment": "Optimized for entertainment, celebrity, and media trends",
  "business": "Optimized for business, finance, and startup trends",
  "default": "General-purpose scorer with no specific optimizations"
}
```

### Score a Single Trend

**POST /score/trend**

Score one trend with optional metadata.

```bash
curl -X POST "http://localhost:8000/score/trend?trend=Python%20AI&scorer_type=tech&position=0"
```

Query parameters:
- `trend` (required): Trend string to score
- `scorer_type` (optional): Type of scorer - "tech", "entertainment", "business", "default" (default: "default")
- `position` (optional): Position in trending list (0 = top) (default: 0)
- `metadata` (optional): JSON string with metrics (e.g., `{"tweet_count": 1000, "engagement_rate": 0.05}`)

Response:
```json
{
  "trend": "Python AI",
  "relevance_score": 75.0,
  "velocity_score": 70.0,
  "audience_score": 56.8,
  "overall_score": 68.5,
  "rank": 0,
  "component_scores": {
    "relevance": 75.0,
    "velocity": 70.0,
    "audience": 56.8
  }
}
```

### Score Multiple Trends

**POST /score/trends**

Score multiple trends at once.

```bash
curl -X POST "http://localhost:8000/score/trends" \
  -d "trends=Python&trends=JavaScript&trends=Web3&scorer_type=tech"
```

Query parameters:
- `trends` (required, multiple): List of trend strings to score
- `scorer_type` (optional): Scorer type
- `metadata` (optional): JSON object mapping trends to metadata

Example with metadata:
```bash
curl -X POST "http://localhost:8000/score/trends" \
  -d "trends=Python&trends=JavaScript&scorer_type=tech" \
  -d "metadata={\"Python\": {\"tweet_count\": 50000}, \"JavaScript\": {\"tweet_count\": 45000}}"
```

Response:
```json
{
  "scorer_type": "tech",
  "trends_count": 3,
  "scored_trends": [
    {
      "trend": "Python",
      "relevance_score": 27.0,
      "velocity_score": 70.0,
      "audience_score": 57.8,
      "overall_score": 50.8,
      "rank": 1,
      "component_scores": {
        "relevance": 27.0,
        "velocity": 70.0,
        "audience": 57.8
      }
    },
    {
      "trend": "JavaScript",
      "relevance_score": 27.0,
      "velocity_score": 66.2,
      "audience_score": 56.7,
      "overall_score": 49.6,
      "rank": 2,
      "component_scores": {
        "relevance": 27.0,
        "velocity": 66.2,
        "audience": 56.7
      }
    },
    {
      "trend": "Web3",
      "relevance_score": 27.0,
      "velocity_score": 59.6,
      "audience_score": 55.5,
      "overall_score": 47.2,
      "rank": 3,
      "component_scores": {
        "relevance": 27.0,
        "velocity": 59.6,
        "audience": 55.5
      }
    }
  ],
  "timestamp": "2026-03-25T12:45:30.123456"
}
```

## Pre-configured Scorers

### Tech Scorer
Optimized for technology trends.
- Target keywords: ai, python, javascript, web3, crypto, machine learning, etc.
- Weights: 40% relevance, 35% velocity, 25% audience

### Entertainment Scorer
Optimized for entertainment trends.
- Target keywords: movie, tv, celebrity, music, award, etc.
- Weights: 35% relevance, 40% velocity, 25% audience (higher velocity weight for trending content)

### Business Scorer
Optimized for business trends.
- Target keywords: startup, investment, ipo, funding, acquisition, etc.
- Weights: 45% relevance, 30% velocity, 25% audience (higher relevance weight)

### Default Scorer
General-purpose with no specific keywords.
- Target keywords: None
- Weights: 40% relevance, 35% velocity, 25% audience

## Creating Custom Scorers

You can create custom scorers programmatically:

```python
from scoring_algorithm import ScoringAlgorithm

# Create custom scorer for news/content
news_scorer = ScoringAlgorithm(
    relevance_weight=0.4,
    velocity_weight=0.35,
    audience_weight=0.25,
    target_keywords=[
        "breaking", "exclusive", "first", "developing",
        "investigation", "report", "analysis", "interview"
    ],
    target_categories=["news", "journalism", "media"]
)

# Score trends
trends = ["Breaking News Investigation", "Celebrity Interview"]
scores = news_scorer.score_trends(trends)
```

## Integration with Phase 1 Pipeline

The scoring algorithm integrates with:
1. **Google Trends API** (`GET /trends/trending`) - Gets base trends
2. **Twitter API** (`GET /twitter/trending`) - Gets Twitter trends and metrics
3. **Scoring Engine** (`POST /score/trends`) - Scores combined trends
4. **Pipeline** (AIC-18) - Batch processes trends hourly
5. **Dashboard** (AIC-19) - Displays top scored trends

Example pipeline flow:
```python
# 1. Fetch trends from multiple sources
google_trends = get_google_trends(region="UNITED_STATES")
twitter_trends = get_twitter_trends(location="worldwide")
combined = google_trends + twitter_trends

# 2. Enrich with metadata from APIs
for trend in combined:
    twitter_metrics = get_tweet_metrics(trend)
    google_volume = get_search_volume(trend)
    metadata[trend] = {
        "tweet_count": twitter_metrics.count,
        "engagement_rate": twitter_metrics.engagement,
        "search_volume": google_volume
    }

# 3. Score and rank
scorer = create_tech_scorer()  # Or any other scorer
scored = scorer.score_trends(combined, metadata=metadata)

# 4. Store top results for dashboard
store_top_trends(scored[:20])
```

## Customization

The algorithm can be customized at multiple levels:

### 1. Component Weights
Adjust the weight of each component:
```python
scorer = ScoringAlgorithm(
    relevance_weight=0.5,    # Higher relevance weight
    velocity_weight=0.25,    # Lower velocity weight
    audience_weight=0.25
)
```

### 2. Target Keywords
Customize keywords for your domain:
```python
scorer = ScoringAlgorithm(
    target_keywords=["crypto", "blockchain", "defi", "nft", "web3"]
)
```

### 3. Thresholds
Modify scoring within the algorithm (requires code changes):
- Position decay rate for velocity
- Log scale multipliers for volume calculations
- Engagement metric weighting

## Performance Considerations

- **Scoring single trend**: O(1) - negligible time
- **Scoring N trends**: O(N) - linear with number of trends
- **Memory**: ~1KB per scored trend (includes all metadata)
- **Typical latency**: <100ms for 100 trends on modern CPU

## Future Enhancements

Planned improvements for Phase 2:
1. **Historical velocity**: Compare current velocity to past trends
2. **Seasonal adjustment**: Account for seasonal trends
3. **Sentiment analysis**: Integrate sentiment scores
4. **Cross-platform aggregation**: Weight different sources differently
5. **ML-based relevance**: Train model on user engagement
6. **Real-time feedback**: Learn from content performance
