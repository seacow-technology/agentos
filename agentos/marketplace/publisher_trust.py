"""
Publisher Trust Manager (Phase F3)

This module manages publisher trust scores based on their historical
capability performance. Publisher trust is one of three sources for
trust inheritance (max 30% contribution).

Core Principle:
    Publisher trust is EARNED through consistent capability performance,
    not assigned based on identity or reputation claims.

Trust Calculation Method:
    1. Aggregate all capabilities from this publisher
    2. Calculate average trust scores from local system
    3. Apply time decay (recent performance matters more)
    4. Normalize to 0-100 scale
    5. Cap at maximum contribution (30%)

Red Lines:
    ❌ Cannot inherit trust across publishers
    ❌ New publishers start at 0% trust
    ❌ Publisher trust does not bypass local Phase E
    ❌ Cannot manually override publisher trust

Architecture:
    PublisherTrustManager
      ├─ calculate_publisher_trust() - Calculate trust for publisher
      ├─ update_publisher_trust() - Refresh publisher trust score
      ├─ get_publisher_capabilities() - Get all publisher capabilities
      └─ get_publisher_stats() - Get publisher statistics

Database Schema:
    marketplace_publisher_trust:
      - publisher_id: Publisher identifier
      - trust_score: Calculated trust (0-100)
      - capability_count: Number of capabilities
      - average_risk_score: Average risk across capabilities
      - last_calculated_at: Last calculation timestamp

Created: 2026-02-02
Author: Phase F3 Agent
Reference: Phase F Task Cards (plan1.md)
"""

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class PublisherStats:
    """
    Publisher statistics and trust information.

    Attributes:
        publisher_id: Publisher identifier
        trust_score: Calculated trust score (0-100)
        capability_count: Number of capabilities
        average_risk_score: Average risk across capabilities
        successful_executions: Total successful executions
        failed_executions: Total failed executions
        last_calculated_at: Last calculation timestamp
    """
    publisher_id: str
    trust_score: float
    capability_count: int
    average_risk_score: float
    successful_executions: int
    failed_executions: int
    last_calculated_at: datetime

    @property
    def success_rate(self) -> float:
        """Calculate execution success rate"""
        total = self.successful_executions + self.failed_executions
        if total == 0:
            return 0.0
        return (self.successful_executions / total) * 100

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "publisher_id": self.publisher_id,
            "trust_score": round(self.trust_score, 2),
            "capability_count": self.capability_count,
            "average_risk_score": round(self.average_risk_score, 2),
            "successful_executions": self.successful_executions,
            "failed_executions": self.failed_executions,
            "success_rate": round(self.success_rate, 2),
            "last_calculated_at": int(self.last_calculated_at.timestamp() * 1000)
        }


class PublisherTrustManager:
    """
    Publisher Trust Manager.

    Manages publisher trust scores based on historical capability performance.
    Trust scores are calculated from actual execution data, not assigned manually.

    Usage:
        manager = PublisherTrustManager(db_path="agentos.db")

        # Calculate trust for a publisher
        trust_score = manager.calculate_publisher_trust("official")

        # Get detailed statistics
        stats = manager.get_publisher_stats("official")
        print(f"Trust: {stats.trust_score}%")
        print(f"Capabilities: {stats.capability_count}")
        print(f"Success Rate: {stats.success_rate}%")

        # Update all publisher trust scores
        manager.update_all_publisher_trust()
    """

    # Trust calculation parameters
    MIN_CAPABILITY_COUNT = 3      # Minimum capabilities for trust calculation
    TIME_DECAY_DAYS = 90         # Weight recent performance more
    HIGH_RISK_PENALTY = 0.5      # Penalty multiplier for high-risk capabilities

    def __init__(self, db_path: str):
        """
        Initialize Publisher Trust Manager.

        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
        logger.info(f"Publisher Trust Manager initialized: {db_path}")

    def calculate_publisher_trust(
        self,
        publisher_id: str,
        use_cache: bool = True
    ) -> float:
        """
        Calculate trust score for a publisher.

        Aggregates trust data from all capabilities published by this publisher
        in the local system. Returns 0 for unknown publishers.

        Args:
            publisher_id: Publisher identifier
            use_cache: If True, use cached value if available and recent

        Returns:
            Trust score (0-100)
        """
        # Check cache first
        if use_cache:
            cached = self._get_cached_trust(publisher_id)
            if cached is not None:
                return cached

        logger.info(f"Calculating trust for publisher: {publisher_id}")

        # Get publisher capabilities
        capabilities = self._get_publisher_capabilities(publisher_id)

        if not capabilities:
            logger.info(f"No capabilities found for publisher: {publisher_id}")
            return 0.0

        if len(capabilities) < self.MIN_CAPABILITY_COUNT:
            logger.info(
                f"Insufficient capabilities for publisher '{publisher_id}': "
                f"{len(capabilities)} < {self.MIN_CAPABILITY_COUNT}"
            )
            return 0.0

        # Calculate aggregate trust
        total_trust = 0.0
        total_weight = 0.0

        for cap in capabilities:
            # Calculate time decay weight (recent performance matters more)
            age_days = (datetime.now() - cap["last_execution"]).days
            time_weight = max(0.1, 1.0 - (age_days / self.TIME_DECAY_DAYS))

            # Apply risk penalty (high-risk capabilities reduce trust)
            risk_penalty = 1.0
            if cap["risk_score"] > 70:
                risk_penalty = self.HIGH_RISK_PENALTY

            # Calculate weighted trust
            weight = time_weight * risk_penalty
            trust_contribution = (100 - cap["risk_score"]) * weight

            total_trust += trust_contribution
            total_weight += weight

        # Normalize to 0-100 scale
        if total_weight > 0:
            trust_score = total_trust / total_weight
        else:
            trust_score = 0.0

        logger.info(
            f"Publisher '{publisher_id}' trust: {trust_score:.2f}% "
            f"({len(capabilities)} capabilities)"
        )

        return trust_score

    def update_publisher_trust(self, publisher_id: str) -> PublisherStats:
        """
        Update publisher trust score in database.

        Recalculates trust and stores result in marketplace_publisher_trust table.

        Args:
            publisher_id: Publisher identifier

        Returns:
            PublisherStats with updated information
        """
        logger.info(f"Updating publisher trust: {publisher_id}")

        # Calculate trust
        trust_score = self.calculate_publisher_trust(
            publisher_id,
            use_cache=False
        )

        # Get additional stats
        capabilities = self._get_publisher_capabilities(publisher_id)
        capability_count = len(capabilities)

        if capability_count > 0:
            avg_risk = sum(c["risk_score"] for c in capabilities) / capability_count
            total_success = sum(c["successful_executions"] for c in capabilities)
            total_failed = sum(c["failed_executions"] for c in capabilities)
        else:
            avg_risk = 0.0
            total_success = 0
            total_failed = 0

        # Store in database
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            now_ms = int(datetime.now().timestamp() * 1000)

            cursor.execute("""
                INSERT OR REPLACE INTO marketplace_publisher_trust (
                    publisher_id,
                    trust_score,
                    capability_count,
                    average_risk_score,
                    successful_executions,
                    failed_executions,
                    last_calculated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                publisher_id,
                trust_score,
                capability_count,
                avg_risk,
                total_success,
                total_failed,
                now_ms
            ))
            conn.commit()

        logger.info(f"Publisher trust updated: {publisher_id} -> {trust_score:.2f}%")

        return PublisherStats(
            publisher_id=publisher_id,
            trust_score=trust_score,
            capability_count=capability_count,
            average_risk_score=avg_risk,
            successful_executions=total_success,
            failed_executions=total_failed,
            last_calculated_at=datetime.now()
        )

    def get_publisher_stats(self, publisher_id: str) -> Optional[PublisherStats]:
        """
        Get publisher statistics from database.

        Args:
            publisher_id: Publisher identifier

        Returns:
            PublisherStats if found, None otherwise
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    publisher_id,
                    trust_score,
                    capability_count,
                    average_risk_score,
                    successful_executions,
                    failed_executions,
                    last_calculated_at
                FROM marketplace_publisher_trust
                WHERE publisher_id = ?
            """, (publisher_id,))

            row = cursor.fetchone()
            if not row:
                return None

            return PublisherStats(
                publisher_id=row[0],
                trust_score=row[1],
                capability_count=row[2],
                average_risk_score=row[3],
                successful_executions=row[4],
                failed_executions=row[5],
                last_calculated_at=datetime.fromtimestamp(row[6] / 1000)
            )

    def update_all_publisher_trust(self) -> List[PublisherStats]:
        """
        Update trust scores for all publishers.

        Scans all capabilities, identifies unique publishers, and updates
        trust scores for each.

        Returns:
            List of PublisherStats for all publishers
        """
        logger.info("Updating trust for all publishers")

        # Get all unique publishers
        publishers = self._get_all_publishers()

        results = []
        for publisher_id in publishers:
            try:
                stats = self.update_publisher_trust(publisher_id)
                results.append(stats)
            except Exception as e:
                logger.error(
                    f"Failed to update trust for publisher '{publisher_id}': {e}",
                    exc_info=True
                )

        logger.info(f"Updated trust for {len(results)} publishers")
        return results

    def _get_cached_trust(self, publisher_id: str) -> Optional[float]:
        """
        Get cached trust score if available and recent.

        Args:
            publisher_id: Publisher identifier

        Returns:
            Cached trust score or None
        """
        stats = self.get_publisher_stats(publisher_id)
        if not stats:
            return None

        # Check if cache is recent (within 24 hours)
        age = datetime.now() - stats.last_calculated_at
        if age > timedelta(hours=24):
            return None

        return stats.trust_score

    def _get_publisher_capabilities(self, publisher_id: str) -> List[Dict]:
        """
        Get all capabilities from a publisher.

        Args:
            publisher_id: Publisher identifier

        Returns:
            List of capability dictionaries
        """
        # TODO: Query actual database for capabilities
        # For now, return mock data
        return []

    def _get_all_publishers(self) -> List[str]:
        """
        Get all unique publisher IDs.

        Returns:
            List of publisher identifiers
        """
        # TODO: Query actual database
        # For now, return mock data
        return ["official", "smithery.ai", "anthropic", "community"]
