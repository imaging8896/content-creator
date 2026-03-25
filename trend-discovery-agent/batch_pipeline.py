"""Hourly batch pipeline for collecting and scoring trends."""
import logging
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from contextlib import contextmanager

from google_trends_client import GoogleTrendsClient
from twitter_client import TwitterClient
from cache_manager import CacheManager
from scoring_algorithm import ScoringAlgorithm, create_default_scorer, create_tech_scorer
from trend_database import TrendDatabase, TrendResult, BatchRunLog

logger = logging.getLogger(__name__)


class BatchPipeline:
    """Hourly batch pipeline for trend discovery, scoring, and storage."""

    def __init__(
        self,
        db: TrendDatabase,
        google_trends_client: GoogleTrendsClient,
        twitter_client: TwitterClient,
        default_scorer: ScoringAlgorithm,
        tech_scorer: Optional[ScoringAlgorithm] = None,
    ):
        """Initialize batch pipeline.

        Args:
            db: TrendDatabase instance
            google_trends_client: GoogleTrendsClient instance
            twitter_client: TwitterClient instance
            default_scorer: Default scoring algorithm
            tech_scorer: Optional tech-specific scorer
        """
        self.db = db
        self.google_trends_client = google_trends_client
        self.twitter_client = twitter_client
        self.default_scorer = default_scorer
        self.tech_scorer = tech_scorer or default_scorer

        # Regions to monitor
        self.google_trends_regions = ["UNITED_STATES", "INDIA", "JAPAN"]
        self.twitter_locations = ["worldwide", "us", "uk", "india", "japan"]

    @contextmanager
    def _batch_context(self, batch_run_id: str):
        """Context manager for batch run execution."""
        session = self.db.get_session()
        run_log = BatchRunLog(
            batch_run_id=batch_run_id,
            status="running",
            started_at=datetime.utcnow(),
        )

        try:
            yield session, run_log
            # Success
            run_log.status = "success"
            run_log.completed_at = datetime.utcnow()
            if run_log.started_at:
                run_log.duration_seconds = (
                    run_log.completed_at - run_log.started_at
                ).total_seconds()

        except Exception as e:
            logger.error(f"Batch pipeline error: {str(e)}", exc_info=True)
            run_log.status = "error"
            run_log.error_message = str(e)
            run_log.completed_at = datetime.utcnow()
            if run_log.started_at:
                run_log.duration_seconds = (
                    run_log.completed_at - run_log.started_at
                ).total_seconds()
            raise

        finally:
            # Store run log
            self.db.store_batch_run_log(session, run_log)
            session.commit()
            session.close()

    def run_batch(self) -> bool:
        """Execute hourly batch pipeline.

        Returns:
            True if successful, False otherwise
        """
        batch_run_id = str(uuid.uuid4())[:8]  # Short ID for tracking
        logger.info(f"Starting batch run: {batch_run_id}")

        try:
            with self._batch_context(batch_run_id) as (session, run_log):
                all_scored_trends = []

                # Collect from Google Trends
                logger.info("Collecting trends from Google Trends...")
                google_trends = self._collect_google_trends(batch_run_id, run_log)
                all_scored_trends.extend(google_trends)

                # Collect from Twitter
                logger.info("Collecting trends from Twitter...")
                twitter_trends = self._collect_twitter_trends(batch_run_id, run_log)
                all_scored_trends.extend(twitter_trends)

                # Combine and score all trends
                logger.info(f"Scoring {len(all_scored_trends)} total trends...")
                scored_results = self._score_and_rank_trends(all_scored_trends)

                # Store results
                logger.info(f"Storing {len(scored_results)} trend results...")
                stored_count = self._store_trend_results(
                    session, scored_results, batch_run_id, run_log
                )

                run_log.trends_scored = len(all_scored_trends)
                run_log.trends_stored = stored_count

                logger.info(
                    f"Batch run {batch_run_id} completed: "
                    f"{stored_count} trends stored"
                )
                return True

        except Exception as e:
            logger.error(f"Batch run {batch_run_id} failed: {str(e)}")
            return False

    def _collect_google_trends(self, batch_run_id: str, run_log: BatchRunLog) -> List[Dict[str, Any]]:
        """Collect trends from Google Trends API.

        Args:
            batch_run_id: ID of the batch run
            run_log: Run log to update with statistics

        Returns:
            List of trend dictionaries
        """
        collected_trends = []

        for region in self.google_trends_regions:
            try:
                logger.info(f"Fetching Google Trends for {region}...")
                result = self.google_trends_client.get_trending_searches(region=region)

                if result.get("source") != "error" and result.get("trends"):
                    trends_list = result.get("trends", [])[:20]  # Top 20
                    for idx, trend in enumerate(trends_list, 1):
                        collected_trends.append({
                            "trend": trend,
                            "source": "google_trends",
                            "region": region,
                            "position": idx,
                            "batch_run_id": batch_run_id,
                        })
                    logger.info(f"Collected {len(trends_list)} trends from {region}")
                    run_log.google_trends_success = run_log.google_trends_success or 0
                    run_log.google_trends_success += len(trends_list)
                else:
                    logger.warning(f"Failed to fetch Google Trends for {region}")

            except Exception as e:
                logger.error(f"Error collecting Google Trends for {region}: {str(e)}")
                continue

        run_log.trends_collected = len(collected_trends)
        return collected_trends

    def _collect_twitter_trends(self, batch_run_id: str, run_log: BatchRunLog) -> List[Dict[str, Any]]:
        """Collect trends from Twitter/X API.

        Args:
            batch_run_id: ID of the batch run
            run_log: Run log to update with statistics

        Returns:
            List of trend dictionaries
        """
        collected_trends = []

        for location in self.twitter_locations:
            try:
                logger.info(f"Fetching Twitter trends for {location}...")
                result = self.twitter_client.get_trending_topics(location=location)

                if result.get("source") != "error" and result.get("topics"):
                    topics_list = result.get("topics", [])[:20]  # Top 20
                    for idx, topic in enumerate(topics_list, 1):
                        collected_trends.append({
                            "trend": topic,
                            "source": "twitter",
                            "location": location,
                            "position": idx,
                            "batch_run_id": batch_run_id,
                        })
                    logger.info(f"Collected {len(topics_list)} trends from Twitter ({location})")
                    run_log.twitter_trending_success = run_log.twitter_trending_success or 0
                    run_log.twitter_trending_success += len(topics_list)
                else:
                    logger.warning(f"Failed to fetch Twitter trends for {location}")

            except Exception as e:
                logger.error(f"Error collecting Twitter trends for {location}: {str(e)}")
                continue

        run_log.trends_collected = (run_log.trends_collected or 0) + len(collected_trends)
        return collected_trends

    def _score_and_rank_trends(self, trends: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Score and rank trends using scoring algorithm.

        Args:
            trends: List of collected trend dictionaries

        Returns:
            List of scored trend dictionaries
        """
        if not trends:
            logger.warning("No trends to score")
            return []

        # Determine scorer based on trend characteristics
        scorer = self._select_scorer()

        # Extract trend names and score them
        trend_names = [t["trend"] for t in trends]
        scored_trend_objects = scorer.score_trends(trend_names)

        # Merge scored data back with original trend info
        scored_results = []
        for idx, scored_trend in enumerate(scored_trend_objects):
            # Find corresponding original trend
            original_trend = next(
                (t for t in trends if t["trend"] == scored_trend.trend),
                None,
            )

            if original_trend:
                result = {
                    **original_trend,
                    "relevance_score": scored_trend.relevance_score,
                    "velocity_score": scored_trend.velocity_score,
                    "audience_score": scored_trend.audience_score,
                    "overall_score": scored_trend.overall_score,
                    "rank": scored_trend.rank,
                    "scorer_type": "default",  # Track which scorer was used
                    "component_scores": scored_trend.component_scores,
                }
                scored_results.append(result)

        logger.info(f"Scored {len(scored_results)} trends")
        return scored_results

    def _select_scorer(self) -> ScoringAlgorithm:
        """Select appropriate scorer for trends.

        Returns:
            ScoringAlgorithm instance
        """
        # For now, use default scorer. Could be enhanced to use tech_scorer
        # for tech-specific trends based on keyword detection
        return self.default_scorer

    def _store_trend_results(
        self,
        session,
        scored_results: List[Dict[str, Any]],
        batch_run_id: str,
        run_log: BatchRunLog,
    ) -> int:
        """Store scored trend results in database.

        Args:
            session: Database session
            scored_results: List of scored trend dictionaries
            batch_run_id: ID of the batch run
            run_log: Run log to update with statistics

        Returns:
            Number of trends stored
        """
        stored_count = 0

        try:
            for trend_data in scored_results:
                try:
                    self.db.store_trend_result(session, trend_data, batch_run_id)
                    stored_count += 1
                except Exception as e:
                    logger.error(
                        f"Error storing trend '{trend_data.get('trend')}': {str(e)}"
                    )
                    continue

            session.commit()
            logger.info(f"Successfully stored {stored_count} trends")

        except Exception as e:
            logger.error(f"Error during trend storage: {str(e)}")
            session.rollback()

        return stored_count

    def cleanup_old_data(self, days_to_keep: int = 30) -> int:
        """Clean up old trend results from database.

        Args:
            days_to_keep: Number of days of data to retain

        Returns:
            Number of rows deleted
        """
        session = self.db.get_session()
        try:
            deleted_count = self.db.cleanup_old_results(session, days_to_keep)
            session.commit()
            logger.info(f"Cleaned up {deleted_count} old trend results")
            return deleted_count
        except Exception as e:
            logger.error(f"Error cleaning up old data: {str(e)}")
            session.rollback()
            return 0
        finally:
            session.close()

    def get_dashboard_data(self, limit: int = 20, hours: int = 24) -> Dict[str, Any]:
        """Get formatted data for dashboard consumption.

        Args:
            limit: Number of trends to return
            hours: Time window in hours to consider

        Returns:
            Dictionary with dashboard-ready data
        """
        session = self.db.get_session()
        try:
            top_trends = self.db.get_top_trends_by_score(session, limit, hours)
            latest_run = self.db.get_latest_batch_run(session)

            return {
                "timestamp": datetime.utcnow().isoformat(),
                "trends_count": len(top_trends),
                "last_run": {
                    "batch_run_id": latest_run.batch_run_id if latest_run else None,
                    "completed_at": latest_run.completed_at.isoformat() if latest_run else None,
                    "trends_stored": latest_run.trends_stored if latest_run else 0,
                },
                "trends": [
                    {
                        "rank": idx + 1,
                        "trend": trend.trend_name,
                        "overall_score": round(trend.overall_score, 2),
                        "relevance_score": round(trend.relevance_score, 2),
                        "velocity_score": round(trend.velocity_score, 2),
                        "audience_score": round(trend.audience_score, 2),
                        "source": trend.source,
                        "region": trend.region,
                        "location": trend.location,
                        "collected_at": trend.collected_at.isoformat(),
                    }
                    for idx, trend in enumerate(top_trends)
                ],
            }
        finally:
            session.close()
