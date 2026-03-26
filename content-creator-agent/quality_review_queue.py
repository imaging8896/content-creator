"""Quality review queue for managing human content reviews.

Implements 10% random sampling of generated content for human review
and tracks rejection rates for quality feedback.
"""

import random
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from content_storage import ContentStorage, StoredContent

logger = logging.getLogger(__name__)


@dataclass
class QualityReviewItem:
    """Item in the quality review queue."""
    id: str
    trend_topic: str
    content_type: str
    content: str
    provider: str
    quality_score: float
    created_at: str
    metadata: Dict[str, Any]


@dataclass
class ReviewFeedback:
    """Feedback from a human review."""
    content_id: str
    status: str  # 'approved' or 'rejected'
    feedback: Optional[str] = None
    reviewer_id: Optional[str] = None


class QualityReviewQueue:
    """Manages quality review queue with 10% sampling strategy."""

    SAMPLING_RATE = 0.10  # 10% of content sampled
    HIGH_QUALITY_THRESHOLD = 70  # Score >= 70 is high quality
    TARGET_REJECTION_RATE = 0.05  # Target < 5% rejection

    def __init__(self, storage: ContentStorage):
        """Initialize review queue with storage backend.

        Args:
            storage: ContentStorage instance for persistence
        """
        self.storage = storage

    def process_generated_content(self, content_id: str) -> bool:
        """Process newly generated content and potentially add to review queue.

        Implements 10% random sampling strategy.

        Args:
            content_id: ID of generated content

        Returns:
            True if content was sampled for review, False otherwise
        """
        # Random 10% sampling
        if random.random() < self.SAMPLING_RATE:
            success = self.storage.mark_for_review(content_id)
            if success:
                logger.info(f"Content {content_id} sampled for human review")
            return success
        return False

    def batch_process_unsampled_content(self, limit: int = 100) -> int:
        """Process batch of unsampled content and sample 10% of them.

        Useful for backfilling sampling on existing content.

        Args:
            limit: Maximum number of unsampled items to process

        Returns:
            Count of items added to review queue
        """
        unsampled = self.storage.get_unsampled_content(limit)
        sampled_count = 0

        for content in unsampled:
            if random.random() < self.SAMPLING_RATE:
                if self.storage.mark_for_review(content.id):
                    sampled_count += 1

        logger.info(
            f"Batch processed {len(unsampled)} unsampled items, "
            f"added {sampled_count} to review queue"
        )
        return sampled_count

    def get_review_queue(self, limit: int = 10) -> List[QualityReviewItem]:
        """Get pending items from the review queue.

        Args:
            limit: Maximum number of items to return

        Returns:
            List of QualityReviewItem pending review
        """
        pending = self.storage.get_pending_reviews(limit)
        return [
            QualityReviewItem(
                id=item.id,
                trend_topic=item.trend_topic,
                content_type=item.content_type,
                content=item.content,
                provider=item.provider,
                quality_score=item.quality_score,
                created_at=item.created_at,
                metadata=item.metadata,
            )
            for item in pending
        ]

    def submit_review(self, feedback: ReviewFeedback) -> bool:
        """Submit review feedback for content.

        Args:
            feedback: ReviewFeedback with review result and optional feedback

        Returns:
            True if review was recorded successfully
        """
        if feedback.status not in ['approved', 'rejected']:
            logger.error(f"Invalid review status: {feedback.status}")
            return False

        success = self.storage.submit_review(
            feedback.content_id,
            feedback.status,
            feedback.feedback
        )

        if success:
            if feedback.status == 'rejected':
                logger.warning(
                    f"Content {feedback.content_id} rejected: {feedback.feedback}"
                )
            else:
                logger.info(f"Content {feedback.content_id} approved")
        return success

    def get_quality_metrics(self, days: int = 7) -> Dict[str, Any]:
        """Get quality metrics for the review process.

        Args:
            days: Number of days to look back

        Returns:
            Dictionary with quality metrics
        """
        stats = self.storage.get_review_statistics(days)

        # Add analysis
        metrics = {
            **stats,
            'meets_target_rejection_rate': (
                stats.get('rejection_rate', 100) <= self.TARGET_REJECTION_RATE * 100
            ),
            'meets_target_quality_score': (
                stats.get('average_quality_score', 0) >= self.HIGH_QUALITY_THRESHOLD
            ),
            'health_status': self._calculate_health_status(stats),
        }

        return metrics

    def get_content_by_quality_range(
        self,
        min_score: float = 0,
        max_score: float = 100,
        content_type: Optional[str] = None,
        days: int = 7,
    ) -> List[StoredContent]:
        """Get content within a quality score range.

        Useful for analyzing content at different quality levels.

        Args:
            min_score: Minimum quality score (0-100)
            max_score: Maximum quality score (0-100)
            content_type: Optional content type filter
            days: Number of days to look back

        Returns:
            List of StoredContent matching criteria
        """
        try:
            from datetime import timedelta
            cutoff_date = (
                datetime.utcnow() - timedelta(days=days)
            ).isoformat()

            query = '''
                SELECT * FROM generated_content
                WHERE created_at >= ?
                AND quality_score >= ?
                AND quality_score <= ?
            '''
            params = [cutoff_date, min_score, max_score]

            if content_type:
                query += ' AND content_type = ?'
                params.append(content_type)

            query += ' ORDER BY quality_score DESC'

            import sqlite3
            with sqlite3.connect(self.storage.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(query, params)
                rows = cursor.fetchall()
                return [
                    self.storage._row_to_stored_content(row)
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"Error retrieving content by quality range: {e}")
            return []

    def _calculate_health_status(self, stats: Dict[str, Any]) -> str:
        """Calculate overall health status of quality process."""
        rejection_rate = stats.get('rejection_rate', 100)
        avg_quality = stats.get('average_quality_score', 0)

        if rejection_rate <= 3 and avg_quality >= 75:
            return 'excellent'
        elif rejection_rate <= 5 and avg_quality >= 70:
            return 'good'
        elif rejection_rate <= 10 and avg_quality >= 60:
            return 'fair'
        else:
            return 'poor'

    def get_recommendations(self) -> Dict[str, Any]:
        """Get recommendations for improving quality based on metrics.

        Returns:
            Dictionary with recommendations and action items
        """
        metrics = self.get_quality_metrics(days=7)
        recommendations = {
            'actions': [],
            'focus_areas': [],
            'positive_notes': [],
        }

        rejection_rate = metrics.get('rejection_rate', 0)
        avg_quality = metrics.get('average_quality_score', 0)

        # Rejection rate recommendations
        if rejection_rate > self.TARGET_REJECTION_RATE * 100:
            recommendations['actions'].append(
                f"Rejection rate is {rejection_rate:.1f}%, exceeds target of "
                f"{self.TARGET_REJECTION_RATE * 100:.1f}%"
            )
            recommendations['focus_areas'].append('content_generation')
        else:
            recommendations['positive_notes'].append(
                f"Rejection rate ({rejection_rate:.1f}%) is within target"
            )

        # Quality score recommendations
        if avg_quality < self.HIGH_QUALITY_THRESHOLD:
            recommendations['actions'].append(
                f"Average quality score ({avg_quality:.1f}) below threshold of "
                f"{self.HIGH_QUALITY_THRESHOLD}"
            )
            recommendations['focus_areas'].append('content_quality')
        else:
            recommendations['positive_notes'].append(
                f"Average quality score ({avg_quality:.1f}) meets expectations"
            )

        # Sampling rate check
        sampling_rate = metrics.get('sampling_rate', 0)
        if sampling_rate < self.SAMPLING_RATE * 100 * 0.8:  # 20% tolerance
            recommendations['actions'].append(
                f"Sampling rate ({sampling_rate:.1f}%) is below expected "
                f"{self.SAMPLING_RATE * 100:.1f}%"
            )
            recommendations['focus_areas'].append('sampling_coverage')

        return recommendations
