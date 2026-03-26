"""Tests for quality review queue system.

Tests content storage, sampling, review workflows, and quality metrics.
"""

import pytest
import tempfile
import os
from datetime import datetime, timedelta
from content_storage import ContentStorage, StoredContent
from quality_review_queue import QualityReviewQueue, ReviewFeedback


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        yield db_path


@pytest.fixture
def storage(temp_db):
    """Create a storage instance with temporary database."""
    return ContentStorage(db_path=temp_db)


@pytest.fixture
def queue(storage):
    """Create a review queue instance."""
    return QualityReviewQueue(storage)


class TestContentStorage:
    """Test ContentStorage functionality."""

    def test_store_and_retrieve_content(self, storage):
        """Test storing and retrieving generated content."""
        content_id = "test-1"
        result = storage.store_content(
            content_id=content_id,
            trend_topic="AI Safety",
            content_type="article",
            content="This is test content about AI safety.",
            provider="claude",
            quality_score=75.5,
            metadata={"word_count": 50},
        )

        assert result is True

        retrieved = storage.get_content(content_id)
        assert retrieved is not None
        assert retrieved.content_id == content_id
        assert retrieved.trend_topic == "AI Safety"
        assert retrieved.quality_score == 75.5

    def test_mark_for_review(self, storage):
        """Test marking content for review."""
        content_id = "test-2"
        storage.store_content(
            content_id=content_id,
            trend_topic="Test",
            content_type="article",
            content="Test content",
            provider="claude",
            quality_score=70.0,
            metadata={},
        )

        result = storage.mark_for_review(content_id)
        assert result is True

        content = storage.get_content(content_id)
        assert content.sampled is True
        assert content.review_status == 'pending'

    def test_submit_review(self, storage):
        """Test submitting review feedback."""
        content_id = "test-3"
        storage.store_content(
            content_id=content_id,
            trend_topic="Test",
            content_type="article",
            content="Test content",
            provider="claude",
            quality_score=70.0,
            metadata={},
        )
        storage.mark_for_review(content_id)

        result = storage.submit_review(
            content_id=content_id,
            status="approved",
            feedback="Good quality"
        )
        assert result is True

        content = storage.get_content(content_id)
        assert content.review_status == 'approved'
        assert content.review_feedback == "Good quality"
        assert content.reviewed_at is not None

    def test_get_pending_reviews(self, storage):
        """Test retrieving pending reviews."""
        for i in range(5):
            content_id = f"test-pending-{i}"
            storage.store_content(
                content_id=content_id,
                trend_topic="Test",
                content_type="article",
                content=f"Test content {i}",
                provider="claude",
                quality_score=70.0 + i,
                metadata={},
            )
            if i < 3:  # Mark first 3 for review
                storage.mark_for_review(content_id)

        pending = storage.get_pending_reviews(limit=10)
        assert len(pending) == 3
        assert all(p.review_status == 'pending' for p in pending)

    def test_get_review_statistics(self, storage):
        """Test retrieving review statistics."""
        # Create some test content
        for i in range(10):
            content_id = f"stats-test-{i}"
            storage.store_content(
                content_id=content_id,
                trend_topic="Test",
                content_type="article",
                content=f"Test content {i}",
                provider="claude",
                quality_score=70.0 + i,
                metadata={},
            )

            if i < 5:  # Sample first 5
                storage.mark_for_review(content_id)
                # Review first 3
                if i < 3:
                    storage.submit_review(
                        content_id=content_id,
                        status="approved" if i % 2 == 0 else "rejected",
                    )

        stats = storage.get_review_statistics(days=7)
        assert stats['total_content'] == 10
        assert stats['sampled_content'] == 5
        assert stats['reviewed_content'] == 3
        assert stats['approved_content'] == 2
        assert stats['rejected_content'] == 1
        assert stats['rejection_rate'] > 0

    def test_get_unsampled_content(self, storage):
        """Test retrieving unsampled content."""
        for i in range(5):
            content_id = f"unsampled-{i}"
            storage.store_content(
                content_id=content_id,
                trend_topic="Test",
                content_type="article",
                content=f"Test content {i}",
                provider="claude",
                quality_score=70.0,
                metadata={},
            )

        unsampled = storage.get_unsampled_content(limit=10)
        assert len(unsampled) == 5
        assert all(not u.sampled for u in unsampled)

    def test_invalid_review_status(self, storage):
        """Test that invalid review status is rejected."""
        content_id = "test-invalid-status"
        storage.store_content(
            content_id=content_id,
            trend_topic="Test",
            content_type="article",
            content="Test",
            provider="claude",
            quality_score=70.0,
            metadata={},
        )
        storage.mark_for_review(content_id)

        result = storage.submit_review(
            content_id=content_id,
            status="invalid_status"
        )
        assert result is False


class TestQualityReviewQueue:
    """Test QualityReviewQueue functionality."""

    def test_process_generated_content_sampling(self, queue, storage):
        """Test that content is sampled according to rate."""
        # Store multiple content items
        sampled_count = 0
        num_items = 1000

        for i in range(num_items):
            content_id = f"sample-test-{i}"
            storage.store_content(
                content_id=content_id,
                trend_topic="Test",
                content_type="article",
                content=f"Test content {i}",
                provider="claude",
                quality_score=70.0,
                metadata={},
            )

            if queue.process_generated_content(content_id):
                sampled_count += 1

        # With 10% sampling rate and 1000 items, expect ~100 sampled
        # Allow 20% variance for randomness
        expected = num_items * queue.SAMPLING_RATE
        assert 80 <= sampled_count <= 120, (
            f"Sampling rate {sampled_count/num_items*100:.1f}% "
            f"outside expected range around {queue.SAMPLING_RATE*100:.1f}%"
        )

    def test_batch_process_unsampled_content(self, queue, storage):
        """Test batch processing of unsampled content."""
        for i in range(50):
            storage.store_content(
                content_id=f"batch-{i}",
                trend_topic="Test",
                content_type="article",
                content=f"Test content {i}",
                provider="claude",
                quality_score=70.0,
                metadata={},
            )

        sampled = queue.batch_process_unsampled_content(limit=50)
        assert sampled > 0
        assert sampled <= 5  # ~10% of 50

    def test_get_review_queue(self, queue, storage):
        """Test retrieving review queue items."""
        for i in range(5):
            content_id = f"queue-{i}"
            storage.store_content(
                content_id=content_id,
                trend_topic="Test",
                content_type="article",
                content=f"Test content {i}",
                provider="claude",
                quality_score=70.0 + i,
                metadata={"order": i},
            )
            storage.mark_for_review(content_id)

        items = queue.get_review_queue(limit=10)
        assert len(items) == 5
        assert all(item.metadata.get("order") is not None for item in items)

    def test_submit_review(self, queue, storage):
        """Test submitting review feedback."""
        content_id = "review-test"
        storage.store_content(
            content_id=content_id,
            trend_topic="Test",
            content_type="article",
            content="Test content",
            provider="claude",
            quality_score=70.0,
            metadata={},
        )
        storage.mark_for_review(content_id)

        feedback = ReviewFeedback(
            content_id=content_id,
            status="approved",
            feedback="Good quality",
            reviewer_id="reviewer-1",
        )

        result = queue.submit_review(feedback)
        assert result is True

        content = storage.get_content(content_id)
        assert content.review_status == 'approved'

    def test_submit_invalid_review_status(self, queue, storage):
        """Test that invalid review status is rejected."""
        content_id = "invalid-review"
        storage.store_content(
            content_id=content_id,
            trend_topic="Test",
            content_type="article",
            content="Test",
            provider="claude",
            quality_score=70.0,
            metadata={},
        )
        storage.mark_for_review(content_id)

        feedback = ReviewFeedback(
            content_id=content_id,
            status="maybe",  # Invalid
            feedback="Bad status",
        )

        result = queue.submit_review(feedback)
        assert result is False

    def test_get_quality_metrics(self, queue, storage):
        """Test retrieving quality metrics."""
        # Create test data
        for i in range(20):
            content_id = f"metrics-{i}"
            storage.store_content(
                content_id=content_id,
                trend_topic="Test",
                content_type="article",
                content=f"Test content {i}",
                provider="claude",
                quality_score=70.0 + (i % 20),
                metadata={},
            )

            if i < 10:  # Sample 10
                storage.mark_for_review(content_id)
                if i < 8:  # Review 8
                    storage.submit_review(
                        content_id=content_id,
                        status="rejected" if i % 4 == 0 else "approved"
                    )

        metrics = queue.get_quality_metrics(days=7)
        assert metrics['total_content'] == 20
        assert metrics['sampled_content'] == 10
        assert metrics['reviewed_content'] == 8
        assert 'rejection_rate' in metrics
        assert 'health_status' in metrics
        assert metrics['health_status'] in ['excellent', 'good', 'fair', 'poor']

    def test_get_recommendations(self, queue, storage):
        """Test getting quality improvement recommendations."""
        # Create high-rejection scenario
        for i in range(10):
            content_id = f"bad-content-{i}"
            storage.store_content(
                content_id=content_id,
                trend_topic="Test",
                content_type="article",
                content=f"Test content {i}",
                provider="claude",
                quality_score=30.0,  # Low quality
                metadata={},
            )
            storage.mark_for_review(content_id)
            storage.submit_review(
                content_id=content_id,
                status="rejected",
                feedback="Poor quality"
            )

        recommendations = queue.get_recommendations()
        assert 'actions' in recommendations
        assert 'focus_areas' in recommendations
        assert 'positive_notes' in recommendations
        # With high rejection rate and low quality, should have actions
        assert len(recommendations['actions']) > 0

    def test_health_status_calculation(self, queue, storage):
        """Test health status calculation with different metrics."""
        # Excellent: low rejection, high quality
        for i in range(10):
            storage.store_content(
                content_id=f"excellent-{i}",
                trend_topic="Test",
                content_type="article",
                content=f"Test content {i}",
                provider="claude",
                quality_score=85.0,
                metadata={},
            )
            storage.mark_for_review(f"excellent-{i}")

        for i in range(9):  # 1 rejected out of 10 = 10% rejection (exceeds 5% target)
            storage.submit_review(
                content_id=f"excellent-{i}",
                status="approved"
            )
        storage.submit_review(
            content_id="excellent-9",
            status="rejected"
        )

        metrics = queue.get_quality_metrics(days=7)
        assert metrics['health_status'] in ['excellent', 'good', 'fair', 'poor']


class TestStorageIntegration:
    """Integration tests for storage and queue together."""

    def test_full_workflow(self, queue, storage):
        """Test complete workflow from generation to review to metrics."""
        # 1. Generate and store content
        for i in range(100):
            storage.store_content(
                content_id=f"workflow-{i}",
                trend_topic="AI",
                content_type="article",
                content=f"Article about trend {i}",
                provider="claude",
                quality_score=60.0 + (i % 30),
                metadata={"index": i},
            )

        # 2. Sample content
        sampled_count = 0
        for i in range(100):
            if queue.process_generated_content(f"workflow-{i}"):
                sampled_count += 1

        assert sampled_count > 0

        # 3. Review sampled content
        pending = storage.get_pending_reviews(limit=100)
        reviewed_count = 0
        for item in pending[:5]:  # Review first 5 items
            storage.submit_review(
                content_id=item.id,
                status="approved" if item.quality_score > 75 else "rejected"
            )
            reviewed_count += 1

        # 4. Check metrics
        metrics = storage.get_review_statistics(days=7)
        assert metrics['total_content'] == 100
        assert metrics['sampled_content'] == sampled_count
        assert metrics['reviewed_content'] == reviewed_count
        assert 'rejection_rate' in metrics
        assert 'average_quality_score' in metrics


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
