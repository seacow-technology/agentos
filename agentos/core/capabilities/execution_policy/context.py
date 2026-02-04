"""
Policy Context Builder

Builds PolicyContext from various data sources:
- Trust Tier Engine (D3)
- Risk Scorer (D2)
- Authorization Service (C3)
- Sandbox Availability (D1)
"""

import logging
from typing import Optional
from .models import PolicyContext, PolicyEvaluationRequest

logger = logging.getLogger(__name__)


class PolicyContextBuilder:
    """
    Builds policy evaluation context from multiple sources

    Integrates with:
    - D3: Trust Tier Engine
    - D2: Risk Scorer
    - C3: Authorization Service
    - D1: Sandbox availability
    """

    def __init__(self, db_path: str):
        """
        Initialize context builder

        Args:
            db_path: Path to database for queries
        """
        self.db_path = db_path

    def build_context(self, request: PolicyEvaluationRequest) -> PolicyContext:
        """
        Build policy context from request

        Args:
            request: Policy evaluation request

        Returns:
            PolicyContext with all information gathered
        """
        # 1. Get Trust Tier (D3)
        tier = self._get_tier(request.extension_id, request.action_id)

        # 2. Get Risk Score (D2)
        risk_score = self._get_risk_score(request.extension_id, request.action_id)

        # 3. Check Authorization (C3)
        auth_allowed, auth_status = self._check_authorization(request)

        # 4. Check Sandbox Availability (D1)
        sandbox_available = self._check_sandbox_available()

        # 5. Get execution count
        execution_count_today = self._get_execution_count_today(
            request.extension_id,
            request.action_id
        )

        # 6. Get Trust State (E5: Phase E integration)
        trust_state = self._get_trust_state(request.extension_id, request.action_id)

        return PolicyContext(
            extension_id=request.extension_id,
            action_id=request.action_id,
            session_id=request.session_id,
            tier=tier,
            risk_score=risk_score,
            auth_allowed=auth_allowed,
            auth_status=auth_status,
            sandbox_available=sandbox_available,
            request_metadata=request.metadata,
            execution_count_today=execution_count_today,
            trust_state=trust_state
        )

    def _get_tier(self, extension_id: str, action_id: str) -> str:
        """
        Get trust tier for extension/action

        Integration with D3: Trust Tier Engine

        Args:
            extension_id: Extension identifier
            action_id: Action identifier

        Returns:
            Trust tier value (e.g., "LOW", "MED", "HIGH")
        """
        try:
            # Try to use trust tier from manifest or default
            from agentos.core.capabilities.sandbox.risk_detector import get_extension_risk_level
            risk_level = get_extension_risk_level(extension_id)
            return risk_level.value
        except Exception as e:
            logger.warning(f"Failed to get tier for {extension_id}: {e}")
            # Default to MED for safety
            return "MED"

    def _get_risk_score(self, extension_id: str, action_id: str) -> float:
        """
        Get risk score for extension/action

        Integration with D2: Risk Scorer

        Args:
            extension_id: Extension identifier
            action_id: Action identifier

        Returns:
            Risk score (0-100)
        """
        try:
            from agentos.core.capabilities.risk.scorer import RiskScorer

            scorer = RiskScorer(self.db_path)
            risk_result = scorer.calculate_risk(extension_id, action_id, window_days=30)
            return risk_result.score
        except Exception as e:
            logger.warning(f"Failed to calculate risk score for {extension_id}: {e}")
            # Return conservative default
            return 50.0

    def _check_authorization(
        self,
        request: PolicyEvaluationRequest
    ) -> tuple[bool, str]:
        """
        Check authorization for extension/action

        Integration with C3: Authorization Framework

        Args:
            request: Policy evaluation request

        Returns:
            (allowed, status) tuple
        """
        try:
            from agentos.core.capabilities.governance import (
                ExtensionGovernanceService,
                AuthorizationRequest,
            )

            governance = ExtensionGovernanceService(self.db_path)

            auth_request = AuthorizationRequest(
                extension_id=request.extension_id,
                action_id=request.action_id,
                session_id=request.session_id,
                user_id=request.user_id
            )

            auth_result = governance.check_authorization(auth_request)

            if auth_result.allowed:
                return (True, "active")
            else:
                # Check if it's revoked or just not authorized
                reason = auth_result.reason or "not_authorized"
                if "revoked" in reason.lower():
                    return (False, "revoked")
                return (False, "denied")

        except Exception as e:
            logger.warning(f"Failed to check authorization for {request.extension_id}: {e}")
            # Default to denied for safety
            return (False, "error")

    def _check_sandbox_available(self) -> bool:
        """
        Check if sandbox is available

        Integration with D1: Sandbox

        Returns:
            True if sandbox is available, False otherwise
        """
        try:
            from agentos.core.capabilities.sandbox import DockerSandbox

            sandbox = DockerSandbox()
            return sandbox.is_available()
        except Exception as e:
            logger.warning(f"Failed to check sandbox availability: {e}")
            return False

    def _get_execution_count_today(
        self,
        extension_id: str,
        action_id: str
    ) -> int:
        """
        Get execution count for today

        Args:
            extension_id: Extension identifier
            action_id: Action identifier

        Returns:
            Number of executions today
        """
        try:
            import sqlite3
            from datetime import datetime, timedelta

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Calculate today's start timestamp (midnight UTC)
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            today_start_ms = int(today_start.timestamp() * 1000)

            # Query execution count
            if action_id == "*":
                query = """
                    SELECT COUNT(*)
                    FROM extension_executions
                    WHERE extension_id = ?
                      AND started_at >= ?
                """
                params = (extension_id, today_start_ms)
            else:
                query = """
                    SELECT COUNT(*)
                    FROM extension_executions
                    WHERE extension_id = ?
                      AND action_id = ?
                      AND started_at >= ?
                """
                params = (extension_id, action_id, today_start_ms)

            cursor.execute(query, params)
            count = cursor.fetchone()[0]
            conn.close()

            return count

        except Exception as e:
            logger.warning(f"Failed to get execution count for {extension_id}: {e}")
            return 0

    def _get_trust_state(self, extension_id: str, action_id: str) -> Optional[str]:
        """
        Get trust evolution state for extension/action

        Integration with E5: Trust Evolution Engine

        Trust States:
        - EARNING: Building trust (cautious)
        - STABLE: Trust established (normal)
        - DEGRADING: Trust declining (strict)

        Args:
            extension_id: Extension identifier
            action_id: Action identifier

        Returns:
            Trust state ("EARNING", "STABLE", "DEGRADING") or None if not available
        """
        try:
            # Try to get trust state from trust history
            # For now, we'll use a simple heuristic based on recent execution history
            import sqlite3
            from datetime import datetime, timedelta

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get recent execution statistics (last 7 days)
            seven_days_ago = datetime.utcnow() - timedelta(days=7)
            seven_days_ago_ms = int(seven_days_ago.timestamp() * 1000)

            query = """
                SELECT
                    COUNT(*) as total_executions,
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_count,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failure_count
                FROM extension_executions
                WHERE extension_id = ?
                  AND started_at >= ?
            """

            if action_id != "*":
                query += " AND action_id = ?"
                params = (extension_id, seven_days_ago_ms, action_id)
            else:
                params = (extension_id, seven_days_ago_ms)

            cursor.execute(query, params)
            result = cursor.fetchone()
            conn.close()

            if result is None or result[0] == 0:
                # No recent execution history - EARNING (needs to prove itself)
                return "EARNING"

            total_executions = result[0]
            success_count = result[1] or 0
            failure_count = result[2] or 0

            # Calculate success rate
            success_rate = success_count / total_executions if total_executions > 0 else 0.0

            # Determine trust state based on success rate and execution count
            if success_rate >= 0.95 and total_executions >= 10:
                # High success rate with sufficient history → STABLE
                return "STABLE"
            elif success_rate >= 0.80:
                # Good success rate → EARNING (still building trust)
                return "EARNING"
            else:
                # Poor success rate → DEGRADING (trust declining)
                return "DEGRADING"

        except Exception as e:
            logger.warning(f"Failed to get trust state for {extension_id}: {e}")
            # Default to EARNING (neutral/cautious)
            return "EARNING"
