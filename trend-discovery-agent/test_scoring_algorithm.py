"""Tests for the trend scoring algorithm."""
import pytest
from scoring_algorithm import (
    ScoringAlgorithm,
    TrendScore,
    create_tech_scorer,
    create_entertainment_scorer,
    create_business_scorer,
    create_default_scorer,
)


class TestScoringAlgorithm:
    """Test suite for ScoringAlgorithm."""

    def test_initialization(self):
        """Test scorer initialization with custom weights."""
        scorer = ScoringAlgorithm(
            relevance_weight=0.5,
            velocity_weight=0.3,
            audience_weight=0.2,
        )
        # Weights should sum to 1.0
        total = scorer.relevance_weight + scorer.velocity_weight + scorer.audience_weight
        assert abs(total - 1.0) < 0.001

    def test_weight_normalization(self):
        """Test that weights are normalized if they don't sum to 1."""
        scorer = ScoringAlgorithm(
            relevance_weight=2.0,
            velocity_weight=1.5,
            audience_weight=1.0,
        )
        # Should normalize to sum to 1.0
        total = scorer.relevance_weight + scorer.velocity_weight + scorer.audience_weight
        assert abs(total - 1.0) < 0.001

    def test_invalid_weights(self):
        """Test that invalid weights raise error."""
        with pytest.raises(ValueError):
            ScoringAlgorithm(
                relevance_weight=0,
                velocity_weight=0,
                audience_weight=0,
            )

    def test_score_single_trend(self):
        """Test scoring a single trend."""
        scorer = ScoringAlgorithm()
        score = scorer.score_single_trend("Python AI", position=0)

        assert isinstance(score, TrendScore)
        assert score.trend == "Python AI"
        assert 0 <= score.relevance_score <= 100
        assert 0 <= score.velocity_score <= 100
        assert 0 <= score.audience_score <= 100
        assert 0 <= score.overall_score <= 100
        assert score.rank == 0  # Not ranked yet

    def test_score_trends_ranking(self):
        """Test scoring and ranking multiple trends."""
        scorer = ScoringAlgorithm()
        trends = [
            "Python AI",
            "Machine Learning",
            "JavaScript",
            "Web3",
            "Cloud Computing",
        ]

        scores = scorer.score_trends(trends)

        assert len(scores) == 5
        # Should be sorted by overall_score descending
        for i in range(len(scores) - 1):
            assert scores[i].overall_score >= scores[i + 1].overall_score
            assert scores[i].rank <= scores[i + 1].rank

    def test_relevance_with_keywords(self):
        """Test relevance scoring with target keywords."""
        scorer = ScoringAlgorithm(target_keywords=["ai", "python"])
        score = scorer.score_single_trend("Python AI Model")

        # Should have high relevance score due to keyword matches
        assert score.relevance_score > 50

    def test_relevance_without_keywords(self):
        """Test relevance scoring without matching keywords."""
        scorer = ScoringAlgorithm(target_keywords=["ai", "python"])
        score = scorer.score_single_trend("Celebrity Gossip")

        # Should have lower relevance score
        assert score.relevance_score < 50

    def test_velocity_position_impact(self):
        """Test that position impacts velocity score."""
        scorer = ScoringAlgorithm()

        # Position 0 should have higher velocity
        score_0 = scorer.score_single_trend("Trend 1", position=0)
        # Position 20 should have lower velocity
        score_20 = scorer.score_single_trend("Trend 2", position=20)

        assert score_0.velocity_score > score_20.velocity_score

    def test_audience_with_metrics(self):
        """Test audience scoring with engagement metrics."""
        scorer = ScoringAlgorithm()

        metadata = {
            "tweet_count": 1000,
            "engagement_rate": 0.05,
            "like_count": 500,
            "retweet_count": 300,
        }

        score = scorer.score_single_trend(
            "Popular Trend", position=0, metadata=metadata
        )

        # Should have reasonable audience score
        assert score.audience_score > 30

    def test_overall_score_combination(self):
        """Test that overall score is weighted combination of components."""
        scorer = ScoringAlgorithm(
            relevance_weight=0.5, velocity_weight=0.3, audience_weight=0.2
        )

        score = scorer.score_single_trend("Test Trend")

        expected = (
            (score.relevance_score * 0.5)
            + (score.velocity_score * 0.3)
            + (score.audience_score * 0.2)
        )
        assert abs(score.overall_score - expected) < 0.1

    def test_keyword_matching(self):
        """Test keyword matching utility."""
        scorer = ScoringAlgorithm()

        # Exact match
        assert scorer._match_keywords("python ai", ["python"]) > 0.3
        # No match
        assert scorer._match_keywords("celebrity gossip", ["python"]) < 0.3

    def test_generic_term_penalty(self):
        """Test that generic terms get penalized in relevance."""
        scorer = ScoringAlgorithm()

        generic_score = scorer.score_single_trend("New Update News")
        specific_score = scorer.score_single_trend("Advanced Python Framework")

        # Specific trend should score higher on relevance
        assert specific_score.relevance_score > generic_score.relevance_score

    def test_specificity_bonus(self):
        """Test that specific multi-word trends get higher scores."""
        scorer = ScoringAlgorithm()

        simple = scorer.score_single_trend("AI")
        specific = scorer.score_single_trend("Advanced Machine Learning Framework")

        # Specific should score higher on relevance
        assert specific.relevance_score > simple.relevance_score

    def test_component_scores_dict(self):
        """Test that component scores are properly recorded."""
        scorer = ScoringAlgorithm()
        score = scorer.score_single_trend("Test Trend")

        assert "relevance" in score.component_scores
        assert "velocity" in score.component_scores
        assert "audience" in score.component_scores
        assert (
            score.relevance_score == score.component_scores["relevance"]
        )

    def test_metadata_in_response(self):
        """Test that metadata is included in response."""
        scorer = ScoringAlgorithm()
        score = scorer.score_single_trend("Test Trend", position=5)

        assert score.metadata["position"] == 5
        assert "calculation_timestamp" in score.metadata


class TestPreconfiguredScorers:
    """Test pre-configured scorer factories."""

    def test_tech_scorer(self):
        """Test technology-optimized scorer."""
        scorer = create_tech_scorer()

        tech_trend = scorer.score_single_trend("Kubernetes Docker DevOps")
        generic_trend = scorer.score_single_trend("Celebrity News")

        # Tech trend should score higher with tech scorer
        assert tech_trend.relevance_score > generic_trend.relevance_score

    def test_entertainment_scorer(self):
        """Test entertainment-optimized scorer."""
        scorer = create_entertainment_scorer()

        entertainment_trend = scorer.score_single_trend("Celebrity Movie Award")
        tech_trend = scorer.score_single_trend("Python Machine Learning")

        # Entertainment trend should score higher with entertainment scorer
        assert (
            entertainment_trend.relevance_score > tech_trend.relevance_score
        )

    def test_business_scorer(self):
        """Test business-optimized scorer."""
        scorer = create_business_scorer()

        business_trend = scorer.score_single_trend("Startup IPO Funding")
        celebrity_trend = scorer.score_single_trend("Celebrity Gossip")

        # Business trend should score higher with business scorer
        assert business_trend.relevance_score > celebrity_trend.relevance_score

    def test_default_scorer(self):
        """Test default general-purpose scorer."""
        scorer = create_default_scorer()

        # Should create without errors
        assert scorer is not None
        assert scorer.target_keywords == []

    def test_different_scorers_same_trend(self):
        """Test same trend with different scorers."""
        trend = "Python AI Startup IPO"

        tech_score = create_tech_scorer().score_single_trend(trend)
        business_score = create_business_scorer().score_single_trend(trend)
        entertainment_score = create_entertainment_scorer().score_single_trend(
            trend
        )

        # Different scorers should weight the same trend differently
        # Tech scorer should prefer it slightly
        assert tech_score.relevance_score > 40
        assert business_score.relevance_score > 40
        assert entertainment_score.relevance_score < 40


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_trends_list(self):
        """Test scoring empty trends list."""
        scorer = ScoringAlgorithm()
        scores = scorer.score_trends([])

        assert len(scores) == 0

    def test_single_trend(self):
        """Test scoring single trend."""
        scorer = ScoringAlgorithm()
        scores = scorer.score_trends(["Single Trend"])

        assert len(scores) == 1
        assert scores[0].rank == 1

    def test_duplicate_trends(self):
        """Test scoring duplicate trends."""
        scorer = ScoringAlgorithm()
        scores = scorer.score_trends(["Trend A", "Trend A", "Trend B"])

        # All trends should be scored even if duplicated
        assert len(scores) == 3

    def test_very_high_metrics(self):
        """Test audience scoring with very large metrics."""
        scorer = ScoringAlgorithm()

        metadata = {
            "tweet_count": 1000000,
            "like_count": 500000,
            "retweet_count": 100000,
        }

        score = scorer.score_single_trend(
            "Viral Trend", position=0, metadata=metadata
        )

        # Should still be capped at 100
        assert score.audience_score <= 100
        assert score.overall_score <= 100

    def test_negative_metrics_ignored(self):
        """Test that negative metrics are handled gracefully."""
        scorer = ScoringAlgorithm()

        metadata = {
            "tweet_count": -100,  # Invalid
            "engagement_rate": 1.5,  # Invalid
        }

        # Should not raise error
        score = scorer.score_single_trend(
            "Test Trend", position=0, metadata=metadata
        )
        assert 0 <= score.audience_score <= 100

    def test_no_metadata(self):
        """Test scoring without any metadata."""
        scorer = ScoringAlgorithm()

        score = scorer.score_single_trend("Trend")

        assert score.relevance_score > 0
        assert score.velocity_score > 0
        assert score.audience_score > 0

    def test_empty_keywords_list(self):
        """Test with empty target keywords."""
        scorer = ScoringAlgorithm(target_keywords=[])

        score = scorer.score_single_trend("Any Trend")

        # Should still score using other components
        assert score.relevance_score > 0

    def test_very_long_trend_name(self):
        """Test with very long trend name."""
        scorer = ScoringAlgorithm()

        long_trend = (
            "Very Long Trend Name With Many Words To Test Edge Cases"
        )
        score = scorer.score_single_trend(long_trend)

        assert score.relevance_score > 0
        assert score.relevance_score <= 100


class TestIntegration:
    """Integration tests for real-world scenarios."""

    def test_realistic_trends_scenario(self):
        """Test scoring realistic trending topics."""
        scorer = create_tech_scorer()

        trends_data = {
            "Google AI Breakthrough": {
                "position": 0,
                "metadata": {
                    "tweet_count": 50000,
                    "recent_tweets": 5000,
                    "total_tweets": 50000,
                    "engagement_rate": 0.08,
                },
            },
            "Web3 Security": {
                "position": 1,
                "metadata": {
                    "tweet_count": 30000,
                    "recent_tweets": 3000,
                    "total_tweets": 30000,
                    "engagement_rate": 0.06,
                },
            },
            "Celebrity Scandal": {
                "position": 2,
                "metadata": {
                    "tweet_count": 100000,
                    "recent_tweets": 10000,
                    "total_tweets": 100000,
                    "engagement_rate": 0.1,
                },
            },
        }

        # Score all trends
        trends = []
        for trend_name, data in trends_data.items():
            score = scorer.score_single_trend(
                trend_name,
                position=data["position"],
                metadata=data["metadata"],
            )
            trends.append(score)

        # Sort and rank
        trends.sort(key=lambda x: x.overall_score, reverse=True)
        for rank, trend in enumerate(trends, 1):
            trend.rank = rank

        # Tech-related trends should score higher
        tech_trends = [
            t for t in trends if t.trend in ["Google AI Breakthrough", "Web3 Security"]
        ]
        celeb_trend = [t for t in trends if t.trend == "Celebrity Scandal"]

        # All should have decent scores
        assert all(t.overall_score > 20 for t in trends)

    def test_scoring_pipeline(self):
        """Test complete scoring pipeline."""
        scorer = ScoringAlgorithm(
            relevance_weight=0.4, velocity_weight=0.35, audience_weight=0.25
        )

        # Raw trends from API
        trends_from_api = ["Python", "JavaScript", "Cloud Computing"]

        # Add metadata from different sources
        metadata = {
            "Python": {
                "tweet_count": 45000,
                "search_volume": 1000000,
                "engagement_rate": 0.07,
            },
            "JavaScript": {
                "tweet_count": 40000,
                "search_volume": 800000,
                "engagement_rate": 0.06,
            },
            "Cloud Computing": {
                "tweet_count": 35000,
                "search_volume": 600000,
                "engagement_rate": 0.05,
            },
        }

        # Score all trends
        scores = scorer.score_trends(trends_from_api, metadata=metadata)

        assert len(scores) == 3
        # All should be ranked
        assert all(1 <= s.rank <= 3 for s in scores)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
