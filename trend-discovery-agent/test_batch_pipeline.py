"""Tests for batch pipeline module."""
import pytest
import sqlite3
import os
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch

from trend_database import TrendDatabase, TrendResult, BatchRunLog
from batch_pipeline import BatchPipeline


@pytest.fixture
def test_db():
    """Create a test database."""
    db = TrendDatabase(db_path="sqlite:///:memory:")
    yield db


@pytest.fixture
def mock_clients():
    """Create mock API clients."""
    google_client = Mock()
    twitter_client = Mock()
    default_scorer = Mock()

    return {
        "google": google_client,
        "twitter": twitter_client,
        "scorer": default_scorer,
    }


@pytest.fixture
def batch_pipeline_instance(test_db, mock_clients):
    """Create a batch pipeline instance with mocks."""
    pipeline = BatchPipeline(
        db=test_db,
        google_trends_client=mock_clients["google"],
        twitter_client=mock_clients["twitter"],
        default_scorer=mock_clients["scorer"],
    )
    return pipeline


class TestTrendDatabase:
    """Tests for TrendDatabase class."""

    def test_database_initialization(self, test_db):
        """Test database initialization."""
        assert test_db.db_path == "sqlite:///:memory:"
        session = test_db.get_session()
        assert session is not None
        session.close()

    def test_store_trend_result(self, test_db):
        """Test storing a trend result."""
        session = test_db.get_session()
        trend_data = {
            "trend": "Python",
            "source": "google_trends",
            "region": "UNITED_STATES",
            "relevance_score": 85.5,
            "velocity_score": 72.0,
            "audience_score": 90.0,
            "overall_score": 82.5,
            "rank": 1,
        }

        trend = test_db.store_trend_result(session, trend_data, "batch123")
        session.commit()

        assert trend.trend_name == "Python"
        assert trend.overall_score == 82.5
        assert trend.batch_run_id == "batch123"

        session.close()

    def test_get_latest_trends(self, test_db):
        """Test retrieving latest trends."""
        session = test_db.get_session()

        # Add multiple trends
        for i in range(5):
            trend_data = {
                "trend": f"Trend{i}",
                "source": "google_trends",
                "overall_score": 80 - i * 5,
                "relevance_score": 75.0,
                "velocity_score": 70.0,
                "audience_score": 80.0,
                "rank": i + 1,
            }
            test_db.store_trend_result(session, trend_data, "batch123")

        session.commit()

        # Test retrieving
        trends = test_db.get_latest_trends(session, limit=3)
        assert len(trends) == 3
        assert trends[0].trend_name == "Trend4"  # Most recent

        session.close()

    def test_get_top_trends_by_score(self, test_db):
        """Test retrieving top trends by score."""
        session = test_db.get_session()

        # Add trends with different scores
        scores = [95, 75, 85, 65, 90]
        for i, score in enumerate(scores):
            trend_data = {
                "trend": f"Trend{i}",
                "source": "google_trends",
                "overall_score": score,
                "relevance_score": 75.0,
                "velocity_score": 70.0,
                "audience_score": 80.0,
                "rank": i + 1,
            }
            test_db.store_trend_result(session, trend_data, "batch123")

        session.commit()

        # Test retrieving top trends by score
        trends = test_db.get_top_trends_by_score(session, limit=3)
        assert len(trends) == 3
        assert trends[0].overall_score == 95
        assert trends[1].overall_score == 90
        assert trends[2].overall_score == 85

        session.close()

    def test_batch_run_log(self, test_db):
        """Test storing batch run logs."""
        session = test_db.get_session()

        run_log = BatchRunLog(
            batch_run_id="batch123",
            status="success",
            trends_collected=100,
            trends_scored=100,
            trends_stored=95,
        )

        test_db.store_batch_run_log(session, run_log)
        session.commit()

        retrieved = test_db.get_batch_run_log(session, "batch123")
        assert retrieved.batch_run_id == "batch123"
        assert retrieved.status == "success"
        assert retrieved.trends_stored == 95

        session.close()

    def test_cleanup_old_results(self, test_db):
        """Test cleaning up old results."""
        session = test_db.get_session()

        # Add a trend
        trend_data = {
            "trend": "OldTrend",
            "source": "google_trends",
            "overall_score": 80.0,
            "relevance_score": 75.0,
            "velocity_score": 70.0,
            "audience_score": 80.0,
            "rank": 1,
            "collected_at": datetime(2020, 1, 1),  # Very old date
        }

        test_db.store_trend_result(session, trend_data, "batch123")
        session.commit()

        # Cleanup old data (keep last 30 days)
        deleted = test_db.cleanup_old_results(session, days_to_keep=30)
        assert deleted >= 1

        session.close()


class TestBatchPipeline:
    """Tests for BatchPipeline class."""

    def test_pipeline_initialization(self, batch_pipeline_instance):
        """Test batch pipeline initialization."""
        assert batch_pipeline_instance.google_trends_client is not None
        assert batch_pipeline_instance.twitter_client is not None
        assert batch_pipeline_instance.db is not None
        assert len(batch_pipeline_instance.google_trends_regions) == 3

    def test_collect_google_trends(self, batch_pipeline_instance):
        """Test collecting trends from Google Trends."""
        # Mock the client response
        batch_pipeline_instance.google_trends_client.get_trending_searches.return_value = {
            "source": "api",
            "trends": ["Python", "JavaScript", "React"],
        }

        run_log = BatchRunLog(batch_run_id="test123", status="running")
        trends = batch_pipeline_instance._collect_google_trends("test123", run_log)

        assert len(trends) > 0
        assert trends[0]["source"] == "google_trends"
        assert run_log.trends_collected > 0

    def test_collect_twitter_trends(self, batch_pipeline_instance):
        """Test collecting trends from Twitter."""
        # Mock the client response
        batch_pipeline_instance.twitter_client.get_trending_topics.return_value = {
            "source": "api",
            "topics": ["#Python", "#JavaScript", "#React"],
        }

        run_log = BatchRunLog(batch_run_id="test123", status="running")
        trends = batch_pipeline_instance._collect_twitter_trends("test123", run_log)

        assert len(trends) > 0
        assert trends[0]["source"] == "twitter"

    def test_score_and_rank_trends(self, batch_pipeline_instance):
        """Test scoring and ranking trends."""
        # Mock scorer response
        mock_scored = Mock()
        mock_scored.trend = "Python"
        mock_scored.relevance_score = 85.0
        mock_scored.velocity_score = 72.0
        mock_scored.audience_score = 90.0
        mock_scored.overall_score = 82.5
        mock_scored.rank = 1
        mock_scored.component_scores = {"keyword": 0.5, "position": 0.3}

        batch_pipeline_instance.default_scorer.score_trends.return_value = [mock_scored]

        trends = [
            {"trend": "Python", "source": "google_trends"},
        ]

        scored = batch_pipeline_instance._score_and_rank_trends(trends)

        assert len(scored) > 0
        assert scored[0]["overall_score"] == 82.5

    def test_get_dashboard_data(self, batch_pipeline_instance):
        """Test getting dashboard data."""
        session = batch_pipeline_instance.db.get_session()

        # Add some trends
        trend_data = {
            "trend": "Python",
            "source": "google_trends",
            "overall_score": 85.0,
            "relevance_score": 75.0,
            "velocity_score": 70.0,
            "audience_score": 80.0,
            "rank": 1,
        }
        batch_pipeline_instance.db.store_trend_result(session, trend_data, "batch123")
        session.commit()
        session.close()

        # Get dashboard data
        data = batch_pipeline_instance.get_dashboard_data(limit=10)

        assert "timestamp" in data
        assert "trends" in data
        assert "last_run" in data

    def test_pipeline_error_handling(self, batch_pipeline_instance):
        """Test error handling in pipeline."""
        # Mock client to raise exception
        batch_pipeline_instance.google_trends_client.get_trending_searches.side_effect = Exception(
            "API Error"
        )

        run_log = BatchRunLog(batch_run_id="test123", status="running")
        trends = batch_pipeline_instance._collect_google_trends("test123", run_log)

        # Should return empty list on error
        assert trends == []


class TestBatchPipelineIntegration:
    """Integration tests for batch pipeline."""

    def test_full_batch_run(self, batch_pipeline_instance):
        """Test a complete batch pipeline run."""
        # Mock API responses
        batch_pipeline_instance.google_trends_client.get_trending_searches.return_value = {
            "source": "api",
            "trends": ["Python", "JavaScript"],
        }

        batch_pipeline_instance.twitter_client.get_trending_topics.return_value = {
            "source": "api",
            "topics": ["#Python"],
        }

        # Mock scorer
        mock_scored = Mock()
        mock_scored.trend = "Python"
        mock_scored.relevance_score = 85.0
        mock_scored.velocity_score = 72.0
        mock_scored.audience_score = 90.0
        mock_scored.overall_score = 82.5
        mock_scored.rank = 1
        mock_scored.component_scores = {}

        batch_pipeline_instance.default_scorer.score_trends.return_value = [
            mock_scored,
            mock_scored,
            mock_scored,
        ]

        # Run the batch
        success = batch_pipeline_instance.run_batch()

        assert success is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
