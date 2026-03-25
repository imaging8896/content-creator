"""Trend scoring algorithm with relevance, velocity, and audience size metrics."""
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import math
import re

logger = logging.getLogger(__name__)


@dataclass
class TrendScore:
    """Scored trend with component scores and overall rank."""
    trend: str
    relevance_score: float  # 0-100
    velocity_score: float  # 0-100
    audience_score: float  # 0-100
    overall_score: float  # 0-100
    rank: int
    component_scores: Dict[str, float]
    metadata: Dict[str, Any]


class ScoringAlgorithm:
    """Trend scoring algorithm evaluating relevance, velocity, and audience size."""

    def __init__(
        self,
        relevance_weight: float = 0.4,
        velocity_weight: float = 0.35,
        audience_weight: float = 0.25,
        target_keywords: Optional[List[str]] = None,
        target_categories: Optional[List[str]] = None,
    ):
        """Initialize scoring algorithm with configurable weights.

        Args:
            relevance_weight: Weight for relevance score (0-1)
            velocity_weight: Weight for velocity score (0-1)
            audience_weight: Weight for audience size score (0-1)
            target_keywords: Keywords to match for relevance (e.g., ['AI', 'tech'])
            target_categories: Content categories for relevance (e.g., ['technology', 'entertainment'])
        """
        # Validate weights sum to 1.0
        total_weight = relevance_weight + velocity_weight + audience_weight
        if total_weight <= 0:
            raise ValueError("Total weight must be greater than 0")

        # Normalize weights to ensure they sum to 1.0
        self.relevance_weight = relevance_weight / total_weight
        self.velocity_weight = velocity_weight / total_weight
        self.audience_weight = audience_weight / total_weight

        # Target keywords and categories for relevance scoring
        self.target_keywords = [kw.lower() for kw in (target_keywords or [])]
        self.target_categories = [cat.lower() for cat in (target_categories or [])]

        logger.info(
            f"Scoring algorithm initialized with weights: "
            f"relevance={self.relevance_weight:.2f}, "
            f"velocity={self.velocity_weight:.2f}, "
            f"audience={self.audience_weight:.2f}"
        )

    def score_trends(
        self,
        trends: List[str],
        metadata: Optional[Dict[str, Any]] = None,
        historical_data: Optional[Dict[str, Any]] = None,
    ) -> List[TrendScore]:
        """Score a list of trends.

        Args:
            trends: List of trend strings to score
            metadata: Optional metadata for trends (e.g., tweet counts, search volumes)
            historical_data: Optional historical trend data for velocity calculation

        Returns:
            List of scored trends, sorted by overall score (descending)
        """
        scored_trends = []

        for idx, trend in enumerate(trends):
            trend_metadata = metadata.get(trend, {}) if metadata else {}
            score = self.score_single_trend(
                trend,
                position=idx,
                metadata=trend_metadata,
                historical_data=historical_data,
            )
            scored_trends.append(score)

        # Rank by overall score
        scored_trends.sort(key=lambda x: x.overall_score, reverse=True)
        for rank, scored_trend in enumerate(scored_trends, 1):
            scored_trend.rank = rank

        return scored_trends

    def score_single_trend(
        self,
        trend: str,
        position: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
        historical_data: Optional[Dict[str, Any]] = None,
    ) -> TrendScore:
        """Score a single trend.

        Args:
            trend: Trend string to score
            position: Position in trending list (0 = most popular)
            metadata: Optional metadata (e.g., tweet_count, search_volume)
            historical_data: Optional historical data for velocity calculation

        Returns:
            TrendScore object with component and overall scores
        """
        metadata = metadata or {}
        historical_data = historical_data or {}

        # Calculate component scores
        relevance = self._calculate_relevance(trend, metadata)
        velocity = self._calculate_velocity(trend, position, metadata, historical_data)
        audience = self._calculate_audience(trend, position, metadata)

        # Calculate weighted overall score
        overall = (
            (relevance * self.relevance_weight)
            + (velocity * self.velocity_weight)
            + (audience * self.audience_weight)
        )

        component_scores = {
            "relevance": relevance,
            "velocity": velocity,
            "audience": audience,
        }

        return TrendScore(
            trend=trend,
            relevance_score=relevance,
            velocity_score=velocity,
            audience_score=audience,
            overall_score=overall,
            rank=0,  # Set later during sorting
            component_scores=component_scores,
            metadata={
                "position": position,
                "input_metadata": metadata,
                "calculation_timestamp": datetime.utcnow().isoformat(),
            },
        )

    def _calculate_relevance(self, trend: str, metadata: Dict[str, Any]) -> float:
        """Calculate relevance score (0-100).

        Relevance is determined by:
        1. Keyword matching (exact/substring match with target keywords)
        2. Category matching (if categories are available)
        3. Keyword specificity (longer, more specific keywords score higher)
        4. Inverse frequency (niche topics score higher than generic ones)

        Args:
            trend: Trend string
            metadata: Optional metadata (may contain 'category', 'keywords', etc.)

        Returns:
            Relevance score (0-100)
        """
        score = 0.0

        trend_lower = trend.lower()

        # 1. Keyword matching (0-40 points)
        if self.target_keywords:
            keyword_match_score = self._match_keywords(trend_lower, self.target_keywords)
            score += keyword_match_score * 40
        else:
            # If no target keywords defined, give base score
            score += 10

        # 2. Category matching (0-25 points)
        if self.target_categories and "category" in metadata:
            category = metadata["category"].lower()
            if category in self.target_categories:
                score += 25
            elif any(cat in category for cat in self.target_categories):
                score += 15
        else:
            # Default moderate category score
            score += 5

        # 3. Keyword specificity (0-20 points)
        # Longer, more specific keywords (usually 2+ words) score higher
        word_count = len(trend.split())
        if word_count >= 2:
            score += min(20, word_count * 5)
        else:
            score += 5

        # 4. Avoid extremely generic terms (0-15 points penalty)
        generic_terms = {"new", "update", "announcement", "news", "trending", "popular"}
        if not any(term == word.lower() for term in generic_terms for word in trend.split()):
            score += 15

        # Normalize to 0-100
        return min(100, max(0, score))

    def _calculate_velocity(
        self,
        trend: str,
        position: int,
        metadata: Dict[str, Any],
        historical_data: Dict[str, Any],
    ) -> float:
        """Calculate velocity score (0-100).

        Velocity measures the rate of growth/momentum:
        1. Position in trending list (earlier = faster growth)
        2. Tweet velocity (if available: recent tweets vs total tweets)
        3. Search volume change (if historical data available)
        4. Time-since-emergence (newer trends score higher)

        Args:
            trend: Trend string
            position: Position in trending list (0 = most popular/fastest growing)
            metadata: Optional metadata (may contain 'tweet_count', 'recent_tweets', etc.)
            historical_data: Optional historical data for trend emergence time

        Returns:
            Velocity score (0-100)
        """
        score = 0.0

        # 1. Position-based velocity (0-40 points)
        # Top position = fastest growth
        position_score = max(0, 40 * math.exp(-position / 10))
        score += position_score

        # 2. Tweet velocity if available (0-30 points)
        if "recent_tweets" in metadata and "total_tweets" in metadata:
            recent = metadata.get("recent_tweets", 0)
            total = metadata.get("total_tweets", 1)
            if total > 0:
                recent_ratio = recent / total
                tweet_velocity = min(30, recent_ratio * 100)
                score += tweet_velocity
        else:
            score += 15  # Default if no tweet data

        # 3. Search volume change (0-20 points) - if historical data available
        if "previous_volume" in metadata and "current_volume" in metadata:
            prev_vol = metadata.get("previous_volume", 1)
            curr_vol = metadata.get("current_volume", 0)
            if prev_vol > 0:
                growth_rate = (curr_vol - prev_vol) / prev_vol
                volume_velocity = min(20, max(0, growth_rate * 20))
                score += volume_velocity
        else:
            score += 10  # Default if no volume data

        # 4. Time-since-emergence (0-10 points) - newer trends score higher
        # If we have emergence time, calculate recency
        if "emerged_at" in historical_data:
            from datetime import datetime
            try:
                emerged_at = datetime.fromisoformat(historical_data["emerged_at"])
                age_hours = (datetime.utcnow() - emerged_at).total_seconds() / 3600
                # Trends less than 12 hours old get higher scores
                recency_score = max(0, 10 * math.exp(-age_hours / 12))
                score += recency_score
            except Exception as e:
                logger.warning(f"Failed to calculate recency: {e}")
                score += 5
        else:
            score += 5  # Default recency score

        # Normalize to 0-100
        return min(100, max(0, score))

    def _calculate_audience(
        self, trend: str, position: int, metadata: Dict[str, Any]
    ) -> float:
        """Calculate audience size score (0-100).

        Audience size measures reach and interest:
        1. Engagement metrics (retweets, likes, replies if available)
        2. Tweet count (total discussion volume)
        3. Search volume (if available)
        4. Trending position (position implies audience size)

        Args:
            trend: Trend string
            position: Position in trending list
            metadata: Optional metadata (engagement metrics, volumes, etc.)

        Returns:
            Audience size score (0-100)
        """
        score = 0.0

        # 1. Engagement metrics (0-35 points)
        engagement_score = 0
        if "engagement_rate" in metadata:
            # engagement_rate should be 0-1, convert to 0-35
            engagement_score = metadata["engagement_rate"] * 35
        elif "like_count" in metadata and "retweet_count" in metadata:
            likes = metadata.get("like_count", 0)
            retweets = metadata.get("retweet_count", 0)
            # Normalize engagement: log scale for large numbers
            engagement = (likes + retweets * 2) / 100  # Retweets weighted more
            engagement_score = min(35, math.log(engagement + 1) * 10)
        else:
            engagement_score = 10  # Default engagement baseline

        score += engagement_score

        # 2. Tweet count/discussion volume (0-30 points)
        if "tweet_count" in metadata:
            tweet_count = metadata.get("tweet_count", 0)
            # Log scale: 1 = 0, 100 = ~20, 1000 = ~30
            volume_score = min(30, math.log(tweet_count + 1) * 5)
            score += volume_score
        else:
            score += 15  # Default volume baseline

        # 3. Search volume if available (0-20 points)
        if "search_volume" in metadata:
            vol = metadata.get("search_volume", 0)
            # Normalize search volume with log scale
            volume_score = min(20, math.log(vol + 1) * 3)
            score += volume_score
        else:
            score += 10  # Default search baseline

        # 4. Position-based audience (0-15 points)
        # Top positions imply larger audience
        position_audience_score = max(0, 15 * math.exp(-position / 20))
        score += position_audience_score

        # Normalize to 0-100
        return min(100, max(0, score))

    def _match_keywords(self, trend: str, keywords: List[str]) -> float:
        """Calculate keyword match ratio (0-1).

        Args:
            trend: Trend string
            keywords: List of target keywords

        Returns:
            Match score from 0-1 (1 = all keywords matched)
        """
        if not keywords:
            return 0.5  # Default medium match if no keywords

        trend_lower = trend.lower()
        matches = 0
        for keyword in keywords:
            # Check for exact word match (surrounded by word boundaries)
            words = trend_lower.split()
            if keyword in words:
                matches += 1
            elif any(keyword in word for word in words):
                matches += 0.75
            elif keyword in trend_lower:
                matches += 0.5

        return min(1.0, matches / len(keywords))


# Pre-configured scorers for common use cases
def create_tech_scorer() -> ScoringAlgorithm:
    """Create a scorer optimized for technology trends."""
    return ScoringAlgorithm(
        relevance_weight=0.4,
        velocity_weight=0.35,
        audience_weight=0.25,
        target_keywords=[
            "ai",
            "python",
            "javascript",
            "web3",
            "crypto",
            "metaverse",
            "nft",
            "machine learning",
            "data",
            "cloud",
            "devops",
            "kubernetes",
            "rust",
            "golang",
            "react",
            "nodejs",
            "database",
            "api",
            "microservices",
            "blockchain",
        ],
        target_categories=["technology", "programming", "science"],
    )


def create_entertainment_scorer() -> ScoringAlgorithm:
    """Create a scorer optimized for entertainment trends."""
    return ScoringAlgorithm(
        relevance_weight=0.35,
        velocity_weight=0.4,
        audience_weight=0.25,
        target_keywords=[
            "movie",
            "tv",
            "celebrity",
            "music",
            "actor",
            "actress",
            "entertainment",
            "show",
            "film",
            "award",
            "video",
        ],
        target_categories=["entertainment", "celebrity", "media"],
    )


def create_business_scorer() -> ScoringAlgorithm:
    """Create a scorer optimized for business/finance trends."""
    return ScoringAlgorithm(
        relevance_weight=0.45,
        velocity_weight=0.3,
        audience_weight=0.25,
        target_keywords=[
            "startup",
            "investment",
            "ipo",
            "funding",
            "acquisition",
            "merger",
            "stock",
            "market",
            "business",
            "entrepreneur",
            "venture",
            "capital",
        ],
        target_categories=["business", "finance", "economy"],
    )


def create_default_scorer() -> ScoringAlgorithm:
    """Create a default general-purpose scorer."""
    return ScoringAlgorithm(
        relevance_weight=0.4,
        velocity_weight=0.35,
        audience_weight=0.25,
    )
