"""
Trust Tier History Management

Tracks changes in trust tiers over time for traceability and evolution.
"""

import sqlite3
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from agentos.core.time.clock import utc_now, utc_now_ms, parse_db_time
from .models import TrustTier, TierChangeRecord


class TierHistory:
    """
    Manages trust tier change history.

    Responsibilities:
    - Record tier changes
    - Query historical changes
    - Provide tier evolution statistics
    """

    def __init__(self, db_path: str):
        """
        Initialize tier history manager.

        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path

    def record_change(
        self,
        extension_id: str,
        action_id: str,
        old_tier: Optional[TrustTier],
        new_tier: TrustTier,
        risk_score: float,
        reason: str
    ) -> str:
        """
        Record a tier change event.

        Args:
            extension_id: Extension identifier
            action_id: Action identifier
            old_tier: Previous tier (None if first time)
            new_tier: New tier value
            risk_score: Risk score that triggered the change
            reason: Human-readable reason

        Returns:
            Record ID
        """
        record_id = str(uuid.uuid4())
        created_at = utc_now_ms()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO trust_tier_history (
                    record_id, extension_id, action_id,
                    old_tier, new_tier, risk_score,
                    reason, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record_id,
                extension_id,
                action_id,
                old_tier.value if old_tier else None,
                new_tier.value,
                risk_score,
                reason,
                created_at
            ))

            # Update current tier cache
            conn.execute("""
                INSERT OR REPLACE INTO trust_tier_current (
                    extension_id, action_id, tier, risk_score, updated_at
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                extension_id,
                action_id,
                new_tier.value,
                risk_score,
                created_at
            ))

            conn.commit()

        return record_id

    def get_history(
        self,
        extension_id: str,
        action_id: str = "*",
        limit: int = 30
    ) -> List[Dict]:
        """
        Get tier change history for an extension.

        Args:
            extension_id: Extension identifier
            action_id: Action identifier (default: "*" for all)
            limit: Maximum number of records to return

        Returns:
            List of tier change records
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            if action_id == "*":
                cursor = conn.execute("""
                    SELECT * FROM trust_tier_history
                    WHERE extension_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (extension_id, limit))
            else:
                cursor = conn.execute("""
                    SELECT * FROM trust_tier_history
                    WHERE extension_id = ? AND action_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (extension_id, action_id, limit))

            records = []
            for row in cursor:
                records.append({
                    "record_id": row["record_id"],
                    "extension_id": row["extension_id"],
                    "action_id": row["action_id"],
                    "old_tier": row["old_tier"],
                    "new_tier": row["new_tier"],
                    "risk_score": row["risk_score"],
                    "reason": row["reason"],
                    "created_at": row["created_at"]
                })

            return records

    def get_current_tier(
        self,
        extension_id: str,
        action_id: str = "*"
    ) -> Optional[TrustTier]:
        """
        Get current cached tier for an extension.

        Args:
            extension_id: Extension identifier
            action_id: Action identifier

        Returns:
            Current tier or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT tier FROM trust_tier_current
                WHERE extension_id = ? AND action_id = ?
            """, (extension_id, action_id))

            row = cursor.fetchone()
            if row:
                return TrustTier(row[0])

        return None

    def get_transition_stats(self) -> Dict:
        """
        Get tier transition statistics.

        Returns:
            Dictionary with transition counts
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT
                    old_tier,
                    new_tier,
                    COUNT(*) as count
                FROM trust_tier_history
                WHERE old_tier IS NOT NULL
                GROUP BY old_tier, new_tier
            """)

            transitions = {}
            for row in cursor:
                old_tier, new_tier, count = row
                transition_key = f"{old_tier} → {new_tier}"
                transitions[transition_key] = count

            return {
                "transitions": transitions,
                "total_changes": sum(transitions.values())
            }

    def get_tier_distribution(self) -> Dict:
        """
        Get current tier distribution across all extensions.

        Returns:
            Dictionary with tier counts
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT tier, COUNT(*) as count
                FROM trust_tier_current
                GROUP BY tier
            """)

            distribution = {}
            for row in cursor:
                tier, count = row
                distribution[tier] = count

            return distribution
