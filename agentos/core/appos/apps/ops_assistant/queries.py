"""
Status Queries - LOW Risk Operations

These operations are read-only and always allowed.
They demonstrate the "safe path" through governance.

Expected behavior:
- 100% success rate
- No policy evaluation needed
- Trust Tier: LOW
"""

import logging
from typing import Dict, List, Any, Optional

from .client import GovernanceAPIClient

logger = logging.getLogger(__name__)


class StatusQueries:
    """
    System Status Queries (LOW Risk)

    These queries are read-only and demonstrate operations that
    should ALWAYS succeed because they have minimal risk.

    Design Principle:
    - No writes
    - No state changes
    - No authorization needed
    - Always returns information (never fails silently)
    """

    def __init__(self, db_path: str):
        """
        Initialize status queries

        Args:
            db_path: Path to AgentOS database
        """
        self.client = GovernanceAPIClient(db_path)

    def get_context_status(self, session_id: str) -> Dict[str, Any]:
        """
        Query context version and status

        This is a LOW risk operation - just reading state.

        Args:
            session_id: Session identifier

        Returns:
            Context status information
        """
        logger.info(f"[StatusQueries] Getting context status for session {session_id}")

        # In MVP, return mock data
        # In production, this would query actual context service
        return {
            "session_id": session_id,
            "status": "active",
            "version": "1.0.0",
            "last_updated": "2026-02-02T00:00:00Z",
            "risk_level": "LOW",
            "message": "Context is healthy"
        }

    def get_recent_executions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Query recent extension executions

        This is a LOW risk operation - just reading execution history.

        Args:
            limit: Maximum number of results

        Returns:
            List of recent execution records
        """
        logger.info(f"[StatusQueries] Getting recent executions (limit={limit})")

        executions = self.client.get_recent_executions(limit)

        logger.info(f"[StatusQueries] Found {len(executions)} recent executions")

        return executions

    def get_extension_risk(self, extension_id: str) -> Dict[str, Any]:
        """
        Query extension risk score

        This is a LOW risk operation - just reading risk assessment.

        Args:
            extension_id: Extension identifier

        Returns:
            Risk score information
        """
        logger.info(f"[StatusQueries] Getting risk score for {extension_id}")

        risk_info = self.client.get_risk_score(extension_id)

        if risk_info:
            return {
                "extension_id": extension_id,
                "score": risk_info.get("score", 0.0),
                "calculated_at": risk_info.get("calculated_at"),
                "factors": risk_info.get("factors", [])
            }
        else:
            # No risk score found - return default
            return {
                "extension_id": extension_id,
                "score": 0.0,
                "calculated_at": None,
                "factors": [],
                "message": "No risk score available (extension may be new)"
            }

    def get_extension_tier(self, extension_id: str) -> Dict[str, Any]:
        """
        Query extension trust tier

        This is a LOW risk operation - just reading trust assessment.

        Args:
            extension_id: Extension identifier

        Returns:
            Trust tier information
        """
        logger.info(f"[StatusQueries] Getting trust tier for {extension_id}")

        tier_info = self.client.get_trust_tier(extension_id)

        if tier_info:
            return {
                "extension_id": extension_id,
                "tier": tier_info.get("tier", "UNKNOWN"),
                "assigned_at": tier_info.get("assigned_at"),
                "reason": tier_info.get("reason", "")
            }
        else:
            # No tier found - return default
            return {
                "extension_id": extension_id,
                "tier": "UNKNOWN",
                "assigned_at": None,
                "reason": "No trust tier assigned (extension may be new)"
            }

    def get_policy_decisions(
        self,
        extension_id: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Query recent policy decisions

        This is a LOW risk operation - just reading audit trail.

        Args:
            extension_id: Filter by extension (optional)
            limit: Maximum number of results

        Returns:
            List of policy decision records
        """
        logger.info(
            f"[StatusQueries] Getting policy decisions "
            f"(extension={extension_id}, limit={limit})"
        )

        decisions = self.client.get_policy_decisions(extension_id, limit)

        logger.info(f"[StatusQueries] Found {len(decisions)} policy decisions")

        return decisions

    def get_extension_info(self, extension_id: str) -> Optional[Dict[str, Any]]:
        """
        Query extension information

        This is a LOW risk operation - just reading extension metadata.

        Args:
            extension_id: Extension identifier

        Returns:
            Extension information or None
        """
        logger.info(f"[StatusQueries] Getting extension info for {extension_id}")

        return self.client.get_extension_info(extension_id)

    def get_governance_health(self) -> Dict[str, Any]:
        """
        Query overall governance health

        This demonstrates that governance is active by showing
        denial statistics.

        Returns:
            Governance health metrics
        """
        logger.info("[StatusQueries] Getting governance health")

        stats = self.client.get_denial_statistics()

        # Calculate health status
        denial_rate = stats.get("denial_rate", 0.0)

        if denial_rate < 10:
            health = "HEALTHY"
            message = "Governance is active but permissive"
        elif denial_rate < 30:
            health = "ACTIVE"
            message = "Governance is actively protecting the system"
        elif denial_rate < 60:
            health = "STRICT"
            message = "Governance is strictly enforcing policies"
        else:
            health = "LOCKED_DOWN"
            message = "Governance is in lockdown mode"

        return {
            "health": health,
            "message": message,
            "statistics": stats,
            "risk_level": "LOW"
        }

    def demonstrate_success(self) -> Dict[str, Any]:
        """
        Demonstrate that LOW risk operations always succeed

        This method shows that the "safe path" through governance
        is always available.

        Returns:
            Success demonstration results
        """
        logger.info("[StatusQueries] Demonstrating LOW risk success")

        results = {
            "test": "LOW_RISK_OPERATIONS",
            "expected": "100% success rate",
            "results": []
        }

        # Test 1: Get recent executions
        try:
            executions = self.get_recent_executions(limit=5)
            results["results"].append({
                "operation": "get_recent_executions",
                "status": "SUCCESS",
                "count": len(executions)
            })
        except Exception as e:
            results["results"].append({
                "operation": "get_recent_executions",
                "status": "FAILED",
                "error": str(e)
            })

        # Test 2: Get governance health
        try:
            health = self.get_governance_health()
            results["results"].append({
                "operation": "get_governance_health",
                "status": "SUCCESS",
                "health": health["health"]
            })
        except Exception as e:
            results["results"].append({
                "operation": "get_governance_health",
                "status": "FAILED",
                "error": str(e)
            })

        # Test 3: Get policy decisions
        try:
            decisions = self.get_policy_decisions(limit=5)
            results["results"].append({
                "operation": "get_policy_decisions",
                "status": "SUCCESS",
                "count": len(decisions)
            })
        except Exception as e:
            results["results"].append({
                "operation": "get_policy_decisions",
                "status": "FAILED",
                "error": str(e)
            })

        # Calculate success rate
        success_count = sum(1 for r in results["results"] if r["status"] == "SUCCESS")
        total_count = len(results["results"])
        results["success_rate"] = f"{success_count}/{total_count} ({success_count/total_count*100:.1f}%)"

        logger.info(f"[StatusQueries] LOW risk demonstration: {results['success_rate']}")

        return results
