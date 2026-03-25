"""Database models for storing trend data using SQLAlchemy."""
import logging
from datetime import datetime
from typing import Optional, List
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, JSON, Text, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

logger = logging.getLogger(__name__)

Base = declarative_base()


class TrendResult(Base):
    """Model for storing scored trend results."""
    __tablename__ = "trend_results"

    id = Column(Integer, primary_key=True)
    trend_name = Column(String(500), nullable=False, index=True)
    source = Column(String(50), nullable=False)  # 'google_trends', 'twitter', 'combined'
    region = Column(String(100), nullable=True, index=True)  # e.g., 'UNITED_STATES', 'worldwide'
    location = Column(String(100), nullable=True, index=True)  # For Twitter location

    # Score components
    relevance_score = Column(Float, nullable=False)
    velocity_score = Column(Float, nullable=False)
    audience_score = Column(Float, nullable=False)
    overall_score = Column(Float, nullable=False, index=True)
    rank = Column(Integer, nullable=False)

    # Additional metadata
    scorer_type = Column(String(50), nullable=True)  # 'tech', 'entertainment', 'business', 'default'
    component_scores = Column(JSON, nullable=True)  # Detailed component breakdown
    metadata = Column(JSON, nullable=True)  # Additional context (tweet counts, etc.)

    # Timing and tracking
    collected_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    batch_run_id = Column(String(100), nullable=True, index=True)  # Track which batch run this came from

    __table_args__ = (
        Index('idx_trend_collected', 'trend_name', 'collected_at'),
        Index('idx_source_region_collected', 'source', 'region', 'collected_at'),
    )

    def __repr__(self):
        return (f"TrendResult(id={self.id}, trend={self.trend_name}, "
                f"overall_score={self.overall_score}, rank={self.rank})")


class BatchRunLog(Base):
    """Model for tracking batch run execution."""
    __tablename__ = "batch_run_logs"

    id = Column(Integer, primary_key=True)
    batch_run_id = Column(String(100), nullable=False, unique=True, index=True)
    status = Column(String(50), nullable=False)  # 'running', 'success', 'error', 'partial'

    # Execution details
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, nullable=True)

    # Results summary
    trends_collected = Column(Integer, nullable=False, default=0)
    trends_scored = Column(Integer, nullable=False, default=0)
    trends_stored = Column(Integer, nullable=False, default=0)

    # Sources processed
    google_trends_success = Column(Integer, nullable=True)
    twitter_trending_success = Column(Integer, nullable=True)

    # Error tracking
    error_message = Column(Text, nullable=True)
    error_details = Column(JSON, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return (f"BatchRunLog(id={self.id}, batch_run_id={self.batch_run_id}, "
                f"status={self.status}, trends_stored={self.trends_stored})")


class TrendDatabase:
    """Database manager for trend results."""

    def __init__(self, db_path: str = "sqlite:///data/trends.db"):
        """Initialize database connection.

        Args:
            db_path: SQLAlchemy database URL (default: SQLite at data/trends.db)
        """
        self.db_path = db_path
        self.engine = create_engine(
            db_path,
            echo=False,
            connect_args={"check_same_thread": False} if "sqlite" in db_path else {}
        )
        self.SessionLocal = sessionmaker(bind=self.engine)

        # Create tables
        Base.metadata.create_all(self.engine)
        logger.info(f"TrendDatabase initialized at {db_path}")

    def get_session(self) -> Session:
        """Get a new database session.

        Returns:
            SQLAlchemy session
        """
        return self.SessionLocal()

    def store_trend_result(self, session: Session, trend_data: dict, batch_run_id: str) -> TrendResult:
        """Store a single trend result.

        Args:
            session: Database session
            trend_data: Dictionary containing trend information
            batch_run_id: ID of the batch run that produced this result

        Returns:
            Stored TrendResult object
        """
        trend = TrendResult(
            trend_name=trend_data.get("trend"),
            source=trend_data.get("source", "unknown"),
            region=trend_data.get("region"),
            location=trend_data.get("location"),
            relevance_score=trend_data.get("relevance_score", 0),
            velocity_score=trend_data.get("velocity_score", 0),
            audience_score=trend_data.get("audience_score", 0),
            overall_score=trend_data.get("overall_score", 0),
            rank=trend_data.get("rank", 0),
            scorer_type=trend_data.get("scorer_type"),
            component_scores=trend_data.get("component_scores"),
            metadata=trend_data.get("metadata"),
            collected_at=trend_data.get("collected_at", datetime.utcnow()),
            batch_run_id=batch_run_id,
        )
        session.add(trend)
        return trend

    def store_batch_run_log(self, session: Session, run_log: BatchRunLog) -> BatchRunLog:
        """Store a batch run log entry.

        Args:
            session: Database session
            run_log: BatchRunLog object

        Returns:
            Stored BatchRunLog object
        """
        session.add(run_log)
        return run_log

    def get_latest_trends(self, session: Session, limit: int = 20,
                         source: Optional[str] = None,
                         region: Optional[str] = None) -> List[TrendResult]:
        """Get latest trending results.

        Args:
            session: Database session
            limit: Number of results to return
            source: Filter by source (optional)
            region: Filter by region (optional)

        Returns:
            List of TrendResult objects
        """
        query = session.query(TrendResult).order_by(TrendResult.collected_at.desc())

        if source:
            query = query.filter(TrendResult.source == source)
        if region:
            query = query.filter(TrendResult.region == region)

        return query.limit(limit).all()

    def get_top_trends_by_score(self, session: Session, limit: int = 20,
                               since_hours: int = 24) -> List[TrendResult]:
        """Get top trends by overall score from recent runs.

        Args:
            session: Database session
            limit: Number of results to return
            since_hours: Only include trends from last N hours

        Returns:
            List of TrendResult objects sorted by overall_score
        """
        from datetime import timedelta
        cutoff_time = datetime.utcnow() - timedelta(hours=since_hours)

        return (session.query(TrendResult)
                .filter(TrendResult.collected_at >= cutoff_time)
                .order_by(TrendResult.overall_score.desc())
                .limit(limit)
                .all())

    def get_batch_run_log(self, session: Session, batch_run_id: str) -> Optional[BatchRunLog]:
        """Get a batch run log by ID.

        Args:
            session: Database session
            batch_run_id: ID of the batch run

        Returns:
            BatchRunLog object or None if not found
        """
        return session.query(BatchRunLog).filter(
            BatchRunLog.batch_run_id == batch_run_id
        ).first()

    def get_latest_batch_run(self, session: Session) -> Optional[BatchRunLog]:
        """Get the most recent batch run log.

        Args:
            session: Database session

        Returns:
            Latest BatchRunLog object or None
        """
        return session.query(BatchRunLog).order_by(
            BatchRunLog.started_at.desc()
        ).first()

    def cleanup_old_results(self, session: Session, days_to_keep: int = 30) -> int:
        """Delete trend results older than specified days.

        Args:
            session: Database session
            days_to_keep: Number of days of data to retain

        Returns:
            Number of rows deleted
        """
        from datetime import timedelta
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)

        deleted = session.query(TrendResult).filter(
            TrendResult.collected_at < cutoff_date
        ).delete()

        logger.info(f"Deleted {deleted} trend results older than {days_to_keep} days")
        return deleted
