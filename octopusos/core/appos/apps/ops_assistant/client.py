"""
Governance API Client

This client provides access to the governance infrastructure:
- Policy Engine
- Risk Scoring
- Trust Tier
- Audit Trail

Ops Assistant uses this client to:
1. Query governance state
2. Request policy evaluation
3. Display governance decisions

It does NOT:
- Make execution decisions
- Cache authorization
- Bypass policy rules
"""

import logging
import sqlite3
from typing import Dict, List, Optional, Any
from datetime import datetime

from agentos.core.capabilities.execution_policy.engine import PolicyEngine
from agentos.core.capabilities.execution_policy.models import (
    PolicyEvaluationRequest,
    PolicyDecisionResult
)

logger = logging.getLogger(__name__)


class GovernanceAPIClient:
    """
    Governance API Client

    Provides access to governance infrastructure without exposing
    decision-making authority.

    Design Principle:
    - Query: Always allowed
    - Request: Always goes through Policy Engine
    - Execute: Never directly accessible
    """

    def __init__(self, db_path: str):
        """
        Initialize governance API client

        Args:
            db_path: Path to AgentOS database
        """
        self.db_path = db_path
        self.policy_engine = PolicyEngine(db_path)

    # ========================================================================
    # LOW RISK: Query Operations (Always Allowed)
    # ========================================================================

    def get_extension_info(self, extension_id: str) -> Optional[Dict[str, Any]]:
        """
        Get extension information

        Args:
            extension_id: Extension identifier

        Returns:
            Extension info or None if not found
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT *
                FROM extensions
                WHERE extension_id = ?
            """, (extension_id,))

            row = cursor.fetchone()
            conn.close()

            if row:
                return dict(row)
            return None

        except Exception as e:
            logger.error(f"Failed to get extension info: {e}", exc_info=True)
            return None

    def get_recent_executions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent extension executions

        Args:
            limit: Maximum number of results

        Returns:
            List of execution records
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Query from execution_history if exists
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='execution_history'
            """)

            if cursor.fetchone():
                cursor.execute("""
                    SELECT *
                    FROM execution_history
                    ORDER BY executed_at DESC
                    LIMIT ?
                """, (limit,))

                rows = cursor.fetchall()
                conn.close()
                return [dict(row) for row in rows]
            else:
                conn.close()
                return []

        except Exception as e:
            logger.error(f"Failed to get recent executions: {e}", exc_info=True)
            return []

    def get_policy_decisions(
        self,
        extension_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get recent policy decisions

        Args:
            extension_id: Filter by extension (optional)
            limit: Maximum number of results

        Returns:
            List of policy decision records
        """
        return self.policy_engine.get_recent_decisions(extension_id, limit)

    def get_risk_score(self, extension_id: str) -> Optional[Dict[str, Any]]:
        """
        Get risk score for extension

        Args:
            extension_id: Extension identifier

        Returns:
            Risk score information or None
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Check if risk_scores table exists
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='risk_scores'
            """)

            if cursor.fetchone():
                cursor.execute("""
                    SELECT *
                    FROM risk_scores
                    WHERE extension_id = ?
                    ORDER BY calculated_at DESC
                    LIMIT 1
                """, (extension_id,))

                row = cursor.fetchone()
                conn.close()

                if row:
                    return dict(row)
            else:
                conn.close()

            return None

        except Exception as e:
            logger.error(f"Failed to get risk score: {e}", exc_info=True)
            return None

    def get_trust_tier(self, extension_id: str) -> Optional[Dict[str, Any]]:
        """
        Get trust tier for extension

        Args:
            extension_id: Extension identifier

        Returns:
            Trust tier information or None
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Check if trust_tiers table exists
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='trust_tiers'
            """)

            if cursor.fetchone():
                cursor.execute("""
                    SELECT *
                    FROM trust_tiers
                    WHERE extension_id = ?
                    ORDER BY assigned_at DESC
                    LIMIT 1
                """, (extension_id,))

                row = cursor.fetchone()
                conn.close()

                if row:
                    return dict(row)
            else:
                conn.close()

            return None

        except Exception as e:
            logger.error(f"Failed to get trust tier: {e}", exc_info=True)
            return None

    # ========================================================================
    # MEDIUM/HIGH RISK: Policy Evaluation (Goes Through Policy Engine)
    # ========================================================================

    def evaluate_policy(
        self,
        extension_id: str,
        action_id: str,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> PolicyDecisionResult:
        """
        Evaluate policy for execution request

        This is the ONLY way to request execution permission.
        Ops Assistant cannot bypass this.

        Args:
            extension_id: Extension identifier
            action_id: Action identifier
            session_id: Session ID (optional)
            user_id: User ID (optional)
            metadata: Additional metadata (optional)

        Returns:
            PolicyDecisionResult with decision and context
        """
        request = PolicyEvaluationRequest(
            extension_id=extension_id,
            action_id=action_id,
            session_id=session_id,
            user_id=user_id,
            metadata=metadata
        )

        logger.info(
            f"[OpsAssistant] Requesting policy evaluation for "
            f"{extension_id}/{action_id}"
        )

        result = self.policy_engine.evaluate(request)

        logger.info(
            f"[OpsAssistant] Policy decision: {result.decision.value} - {result.reason}"
        )

        return result

    def get_denial_statistics(self) -> Dict[str, Any]:
        """
        Get statistics on policy denials

        This helps demonstrate that governance is active.

        Returns:
            Statistics on denials and approvals
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Check if policy_decisions table exists
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='policy_decisions'
            """)

            if not cursor.fetchone():
                conn.close()
                return {
                    "total_decisions": 0,
                    "denied": 0,
                    "require_approval": 0,
                    "allowed": 0,
                    "denial_rate": 0.0
                }

            # Get overall stats
            cursor.execute("""
                SELECT
                    decision,
                    COUNT(*) as count
                FROM policy_decisions
                GROUP BY decision
            """)

            stats = {"total_decisions": 0, "denied": 0, "require_approval": 0, "allowed": 0}

            for row in cursor.fetchall():
                decision, count = row
                stats["total_decisions"] += count

                if decision == "deny":
                    stats["denied"] = count
                elif decision == "require_approval":
                    stats["require_approval"] = count
                elif decision == "allow":
                    stats["allowed"] = count

            # Calculate denial rate
            if stats["total_decisions"] > 0:
                denial_rate = (stats["denied"] + stats["require_approval"]) / stats["total_decisions"]
                stats["denial_rate"] = round(denial_rate * 100, 2)
            else:
                stats["denial_rate"] = 0.0

            conn.close()
            return stats

        except Exception as e:
            logger.error(f"Failed to get denial statistics: {e}", exc_info=True)
            return {
                "error": str(e),
                "total_decisions": 0,
                "denied": 0,
                "require_approval": 0,
                "allowed": 0,
                "denial_rate": 0.0
            }
