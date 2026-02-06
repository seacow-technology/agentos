"""
Policy Engine

The final arbiter for extension execution decisions.
Evaluates policy rules and returns ALLOW/DENY/REQUIRE_APPROVAL decisions.

This is a non-bypassable governance layer that:
1. Integrates with D1-D3 (Sandbox/Risk/Tier)
2. Integrates with C3 (Authorization)
3. Applies policy rules in priority order
4. Logs all decisions to audit trail

Created: 2026-02-02 (Phase D4)
"""

import logging
import sqlite3
from datetime import datetime
from typing import Optional

from agentos.core.time.clock import utc_now
from .models import (
    PolicyDecision,
    PolicyDecisionResult,
    PolicyEvaluationRequest,
    PolicyContext
)
from .context import PolicyContextBuilder
from .rules import ALL_RULES

logger = logging.getLogger(__name__)


class PolicyEngine:
    """
    Policy Engine - Final execution arbiter

    This engine is the LAST checkpoint before extension execution.
    All extension executions MUST pass through this engine.

    Decision Flow:
    1. Build context from D1-D3 and C3
    2. Evaluate rules in priority order
    3. Return first matching rule's decision
    4. Log all DENY/REQUIRE_APPROVAL to audit

    Non-Bypassable:
    - No execution without policy evaluation
    - All decisions are logged
    - Clear reason for every DENY/REQUIRE_APPROVAL
    """

    def __init__(self, db_path: str):
        """
        Initialize policy engine

        Args:
            db_path: Path to database for queries and audit logging
        """
        self.db_path = db_path
        self.context_builder = PolicyContextBuilder(db_path)

    def evaluate(
        self,
        request: PolicyEvaluationRequest
    ) -> PolicyDecisionResult:
        """
        Evaluate policy for execution request

        This is the main entry point for policy evaluation.

        Args:
            request: Policy evaluation request

        Returns:
            PolicyDecisionResult with decision, reason, and context
        """
        # 1. Build context
        context = self.context_builder.build_context(request)

        logger.info(
            f"[PolicyEngine] Evaluating {request.extension_id}/{request.action_id} "
            f"(tier={context.tier}, risk={context.risk_score:.1f}, "
            f"auth={context.auth_status}, sandbox={context.sandbox_available}, "
            f"trust={context.trust_state})"
        )

        # 2. Evaluate rules in priority order
        for rule_func in ALL_RULES:
            decision, reason, rule_name = rule_func(context)

            if decision is not None:
                # Rule matched
                logger.info(
                    f"[PolicyEngine] Rule matched: {rule_name} → {decision.value} "
                    f"(reason: {reason})"
                )

                result = PolicyDecisionResult(
                    decision=decision,
                    reason=reason,
                    rules_applied=[rule_name],
                    context=context,
                    decided_at=utc_now()
                )

                # Log decision to audit
                self._log_decision(result)

                return result

        # 3. No rule matched - default to ALLOW
        logger.info(
            f"[PolicyEngine] No restrictive rules matched - ALLOW "
            f"({request.extension_id}/{request.action_id})"
        )

        result = PolicyDecisionResult(
            decision=PolicyDecision.ALLOW,
            reason="All policy checks passed",
            rules_applied=["DEFAULT_ALLOW"],
            context=context,
            decided_at=utc_now()
        )

        # Log ALLOW decision (optional, for complete audit trail)
        self._log_decision(result)

        return result

    def _log_decision(self, result: PolicyDecisionResult):
        """
        Log policy decision to audit trail

        All DENY and REQUIRE_APPROVAL decisions MUST be logged.
        ALLOW decisions can be logged for complete audit trail.

        Args:
            result: Policy decision result
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Create policy_decisions table if not exists
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS policy_decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    extension_id TEXT NOT NULL,
                    action_id TEXT NOT NULL,
                    session_id TEXT,
                    decision TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    rules_applied TEXT NOT NULL,
                    tier TEXT NOT NULL,
                    risk_score REAL NOT NULL,
                    auth_status TEXT NOT NULL,
                    sandbox_available INTEGER NOT NULL,
                    execution_count_today INTEGER NOT NULL,
                    trust_state TEXT,
                    decided_at INTEGER NOT NULL
                )
            """)

            # Insert decision
            cursor.execute("""
                INSERT INTO policy_decisions (
                    extension_id,
                    action_id,
                    session_id,
                    decision,
                    reason,
                    rules_applied,
                    tier,
                    risk_score,
                    auth_status,
                    sandbox_available,
                    execution_count_today,
                    trust_state,
                    decided_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result.context.extension_id,
                result.context.action_id,
                result.context.session_id,
                result.decision.value,
                result.reason,
                ",".join(result.rules_applied),
                result.context.tier,
                result.context.risk_score,
                result.context.auth_status,
                1 if result.context.sandbox_available else 0,
                result.context.execution_count_today,
                result.context.trust_state,
                int(result.decided_at.timestamp() * 1000)
            ))

            conn.commit()
            conn.close()

            logger.debug(
                f"[PolicyEngine] Logged decision: {result.decision.value} "
                f"for {result.context.extension_id}/{result.context.action_id}"
            )

        except Exception as e:
            logger.error(f"[PolicyEngine] Failed to log decision: {e}", exc_info=True)
            # Don't fail the decision because of logging error

    def get_recent_decisions(
        self,
        extension_id: Optional[str] = None,
        limit: int = 100
    ) -> list[dict]:
        """
        Get recent policy decisions for audit review

        Args:
            extension_id: Filter by extension ID (optional)
            limit: Maximum number of results

        Returns:
            List of decision records
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if extension_id:
                query = """
                    SELECT *
                    FROM policy_decisions
                    WHERE extension_id = ?
                    ORDER BY decided_at DESC
                    LIMIT ?
                """
                cursor.execute(query, (extension_id, limit))
            else:
                query = """
                    SELECT *
                    FROM policy_decisions
                    ORDER BY decided_at DESC
                    LIMIT ?
                """
                cursor.execute(query, (limit,))

            rows = cursor.fetchall()
            conn.close()

            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"[PolicyEngine] Failed to get recent decisions: {e}")
            return []
