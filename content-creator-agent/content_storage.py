"""Database storage for generated content and quality reviews.

Manages persistence of generated content, tracks reviews, and computes quality metrics.
"""

import sqlite3
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class StoredContent:
    """Stored content record."""
    id: str
    trend_topic: str
    content_type: str
    content: str
    provider: str
    quality_score: float
    created_at: str
    metadata: Dict[str, Any]
    sampled: bool = False
    review_status: Optional[str] = None  # 'pending', 'approved', 'rejected'
    review_feedback: Optional[str] = None
    reviewed_at: Optional[str] = None


class ContentStorage:
    """SQLite-based storage for generated content and reviews."""

    DB_PATH = "/home/ec2-user/content-creator/content_storage.db"

    def __init__(self, db_path: str = DB_PATH):
        """Initialize storage and create schema if needed."""
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Create content table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS generated_content (
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
            ''')

            # Create index on created_at for efficient querying
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_created_at
                ON generated_content(created_at)
            ''')

            # Create index on review_status for queue queries
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_review_status
                ON generated_content(review_status)
            ''')

            # Create index on sampled for sampling queries
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_sampled
                ON generated_content(sampled)
            ''')

            # Create review statistics table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS review_statistics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    total_content INTEGER,
                    sampled_content INTEGER,
                    reviewed_content INTEGER,
                    approved_content INTEGER,
                    rejected_content INTEGER,
                    rejection_rate REAL,
                    average_quality_score REAL
                )
            ''')

            conn.commit()
            logger.info(f"Database initialized at {self.db_path}")

    def store_content(
        self,
        content_id: str,
        trend_topic: str,
        content_type: str,
        content: str,
        provider: str,
        quality_score: float,
        metadata: Dict[str, Any],
    ) -> bool:
        """Store generated content.

        Args:
            content_id: Unique identifier for the content
            trend_topic: The topic the content is about
            content_type: Type of content (article, video_script, etc.)
            content: The actual content text
            provider: LLM provider used (claude, gpt)
            quality_score: Automated quality score (0-100)
            metadata: Additional metadata as dict

        Returns:
            True if successful, False otherwise
        """
        try:
            now = datetime.utcnow().isoformat()
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO generated_content
                    (id, trend_topic, content_type, content, provider,
                     quality_score, created_at, metadata, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    content_id,
                    trend_topic,
                    content_type,
                    content,
                    provider,
                    quality_score,
                    now,
                    json.dumps(metadata),
                    now
                ))
                conn.commit()
            logger.info(f"Stored content {content_id}")
            return True
        except Exception as e:
            logger.error(f"Error storing content: {e}")
            return False

    def get_content(self, content_id: str) -> Optional[StoredContent]:
        """Retrieve content by ID."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT * FROM generated_content WHERE id = ?',
                    (content_id,)
                )
                row = cursor.fetchone()
                if row:
                    return self._row_to_stored_content(row)
        except Exception as e:
            logger.error(f"Error retrieving content: {e}")
        return None

    def mark_for_review(self, content_id: str) -> bool:
        """Mark content as sampled for human review."""
        try:
            now = datetime.utcnow().isoformat()
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE generated_content
                    SET sampled = 1, review_status = 'pending', updated_at = ?
                    WHERE id = ?
                ''', (now, content_id))
                conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error marking for review: {e}")
            return False

    def submit_review(
        self,
        content_id: str,
        status: str,  # 'approved' or 'rejected'
        feedback: Optional[str] = None
    ) -> bool:
        """Submit a human review for content.

        Args:
            content_id: ID of content being reviewed
            status: 'approved' or 'rejected'
            feedback: Optional feedback from reviewer

        Returns:
            True if successful, False otherwise
        """
        if status not in ['approved', 'rejected']:
            logger.error(f"Invalid review status: {status}")
            return False

        try:
            now = datetime.utcnow().isoformat()
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE generated_content
                    SET review_status = ?, review_feedback = ?,
                        reviewed_at = ?, updated_at = ?
                    WHERE id = ?
                ''', (status, feedback, now, now, content_id))
                conn.commit()
            logger.info(f"Review submitted for {content_id}: {status}")
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error submitting review: {e}")
            return False

    def get_pending_reviews(self, limit: int = 10) -> List[StoredContent]:
        """Get content pending human review."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM generated_content
                    WHERE review_status = 'pending'
                    ORDER BY created_at DESC
                    LIMIT ?
                ''', (limit,))
                rows = cursor.fetchall()
                return [self._row_to_stored_content(row) for row in rows]
        except Exception as e:
            logger.error(f"Error retrieving pending reviews: {e}")
            return []

    def get_review_statistics(self, days: int = 7) -> Dict[str, Any]:
        """Get review statistics for the past N days."""
        try:
            cutoff_date = (datetime.utcnow() - timedelta(days=days)).isoformat()

            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # Total content
                cursor.execute('''
                    SELECT COUNT(*) as count FROM generated_content
                    WHERE created_at >= ?
                ''', (cutoff_date,))
                total_content = cursor.fetchone()['count']

                # Sampled content
                cursor.execute('''
                    SELECT COUNT(*) as count FROM generated_content
                    WHERE created_at >= ? AND sampled = 1
                ''', (cutoff_date,))
                sampled_content = cursor.fetchone()['count']

                # Reviewed content
                cursor.execute('''
                    SELECT COUNT(*) as count FROM generated_content
                    WHERE created_at >= ? AND review_status IS NOT NULL
                ''', (cutoff_date,))
                reviewed_content = cursor.fetchone()['count']

                # Approved content
                cursor.execute('''
                    SELECT COUNT(*) as count FROM generated_content
                    WHERE created_at >= ? AND review_status = 'approved'
                ''', (cutoff_date,))
                approved_content = cursor.fetchone()['count']

                # Rejected content
                cursor.execute('''
                    SELECT COUNT(*) as count FROM generated_content
                    WHERE created_at >= ? AND review_status = 'rejected'
                ''', (cutoff_date,))
                rejected_content = cursor.fetchone()['count']

                # Average quality score
                cursor.execute('''
                    SELECT AVG(quality_score) as avg_score FROM generated_content
                    WHERE created_at >= ?
                ''', (cutoff_date,))
                avg_score_result = cursor.fetchone()
                average_quality_score = avg_score_result['avg_score'] or 0

                # Calculate rejection rate
                rejection_rate = (
                    (rejected_content / reviewed_content * 100)
                    if reviewed_content > 0 else 0
                )

                return {
                    'period_days': days,
                    'total_content': total_content,
                    'sampled_content': sampled_content,
                    'sampling_rate': (
                        sampled_content / total_content * 100
                        if total_content > 0 else 0
                    ),
                    'reviewed_content': reviewed_content,
                    'approved_content': approved_content,
                    'rejected_content': rejected_content,
                    'rejection_rate': round(rejection_rate, 2),
                    'average_quality_score': round(average_quality_score, 1),
                    'high_quality_count': self._count_high_quality(cutoff_date),
                }
        except Exception as e:
            logger.error(f"Error retrieving statistics: {e}")
            return {}

    def _count_high_quality(self, cutoff_date: str) -> int:
        """Count content with quality score >= 70."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT COUNT(*) as count FROM generated_content
                    WHERE created_at >= ? AND quality_score >= 70
                ''', (cutoff_date,))
                return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"Error counting high quality content: {e}")
            return 0

    def get_unsampled_content(self, limit: int = 100) -> List[StoredContent]:
        """Get content that hasn't been sampled yet."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM generated_content
                    WHERE sampled = 0
                    ORDER BY created_at ASC
                    LIMIT ?
                ''', (limit,))
                rows = cursor.fetchall()
                return [self._row_to_stored_content(row) for row in rows]
        except Exception as e:
            logger.error(f"Error retrieving unsampled content: {e}")
            return []

    def cleanup_old_records(self, days: int = 90) -> int:
        """Delete records older than N days. Returns count of deleted records."""
        try:
            cutoff_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'DELETE FROM generated_content WHERE created_at < ?',
                    (cutoff_date,)
                )
                conn.commit()
                deleted = cursor.rowcount
                logger.info(f"Cleaned up {deleted} old records")
                return deleted
        except Exception as e:
            logger.error(f"Error cleaning up records: {e}")
            return 0

    @staticmethod
    def _row_to_stored_content(row: sqlite3.Row) -> StoredContent:
        """Convert database row to StoredContent object."""
        return StoredContent(
            id=row['id'],
            trend_topic=row['trend_topic'],
            content_type=row['content_type'],
            content=row['content'],
            provider=row['provider'],
            quality_score=row['quality_score'],
            created_at=row['created_at'],
            metadata=json.loads(row['metadata']),
            sampled=bool(row['sampled']),
            review_status=row['review_status'],
            review_feedback=row['review_feedback'],
            reviewed_at=row['reviewed_at'],
        )
