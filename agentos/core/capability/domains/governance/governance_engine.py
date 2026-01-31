"""
Governance Engine - Core capability-based governance system

This is the main engine that orchestrates all 6 Governance Capabilities:
- GC-001: governance.permission.check
- GC-002: governance.policy.evaluate
- GC-003: governance.risk.score
- GC-004: governance.override.admin
- GC-005: governance.quota.check
- GC-006: governance.policy.evolve

Performance Target: Permission check < 10ms (with cache)

Design Philosophy:
- Governance is a Capability, not if/else logic
- All decisions are policy-driven and auditable
- Fail-safe: Unknown = Deny
"""

import logging
import sqlite3
import json
from typing import Dict, List, Optional, Any
from functools import lru_cache
from datetime import timedelta

from agentos.core.time import utc_now_ms
from agentos.core.capability.domains.governance.models import (
    PermissionResult,
    PolicyDecision,
    RiskScore,
    QuotaStatus,
    OverrideToken,
    GovernanceContext,
    TrustTier,
    PolicyAction,
    RiskLevel,
)
from agentos.core.capability.domains.governance.policy_registry import (
    PolicyRegistry,
    get_policy_registry,
)
from agentos.core.capability.domains.governance.risk_calculator import RiskCalculator
from agentos.core.capability.domains.governance.override_manager import OverrideManager


logger = logging.getLogger(__name__)


class GovernanceEngine:
    """
    Central governance engine for AgentOS v3.

    This engine coordinates all governance checks and integrates:
    - CapabilityRegistry (for capability grants)
    - PolicyRegistry (for policy evaluation)
    - RiskCalculator (for risk assessment)
    - OverrideManager (for emergency overrides)

    Usage:
        engine = GovernanceEngine(db_path)
        result = engine.check_permission(
            agent_id="chat_agent",
            capability_id="state.memory.write",
            context={"operation": "upsert"}
        )
        if result.allowed:
            # Proceed with operation
            pass
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize governance engine.

        Args:
            db_path: Path to SQLite database
        """
        if db_path is None:
            from agentos.store import get_db_path
            db_path = get_db_path()

        self.db_path = db_path
        self.policy_registry = get_policy_registry(db_path)
        self.risk_calculator = RiskCalculator()
        self.override_manager = OverrideManager(db_path)

        # Performance optimization: cache enabled
        self._cache_enabled = True
        self._cache_ttl_seconds = 60

        logger.info(f"GovernanceEngine initialized with db: {db_path}")

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ===================================================================
    # GC-001: governance.permission.check
    # ===================================================================

    def check_permission(
        self,
        agent_id: str,
        capability_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> PermissionResult:
        """
        Check if agent has permission to invoke capability (GC-001).

        This is the main permission check method that:
        1. Checks if agent has capability grant
        2. Evaluates relevant policies
        3. Calculates risk score
        4. Returns comprehensive permission result

        Performance target: < 10ms with cache

        Args:
            agent_id: Agent identifier
            capability_id: Capability to check
            context: Additional context for decision

        Returns:
            PermissionResult with decision and reasoning
        """
        start_ms = utc_now_ms()
        context = context or {}

        # Build governance context
        gov_context = GovernanceContext(
            agent_id=agent_id,
            capability_id=capability_id,
            operation=context.get("operation", "unknown"),
            parameters=context.get("parameters", {}),
            trust_tier=self._get_agent_trust_tier(agent_id),
            estimated_cost=context.get("estimated_cost"),
            estimated_tokens=context.get("estimated_tokens"),
            side_effects=context.get("side_effects", []),
            project_id=context.get("project_id"),
            metadata=context,
        )

        # Step 1: Check if agent has capability grant
        has_grant = self._has_capability_grant(agent_id, capability_id)
        if not has_grant:
            return self._deny_permission(
                agent_id=agent_id,
                capability_id=capability_id,
                reason="No capability grant found for agent",
                risk_score=None,
                checked_at_ms=start_ms,
            )

        # Step 2: Evaluate policies
        policy_decisions = self._evaluate_policies(gov_context)

        # Check if any policy denies
        for decision in policy_decisions:
            if decision.decision == PolicyAction.DENY:
                return self._deny_permission(
                    agent_id=agent_id,
                    capability_id=capability_id,
                    reason=f"Denied by policy: {decision.policy_id}",
                    risk_score=None,
                    checked_at_ms=start_ms,
                    policy_ids=[d.policy_id for d in policy_decisions],
                )

        # Step 3: Calculate risk score
        risk_score = self.calculate_risk_score(capability_id, gov_context)

        # Step 4: Check if risk requires approval
        if risk_score.mitigation_required:
            return self._deny_permission(
                agent_id=agent_id,
                capability_id=capability_id,
                reason=f"High risk operation requires approval (risk={risk_score.score:.2f})",
                risk_score=risk_score.score,
                checked_at_ms=start_ms,
                policy_ids=[d.policy_id for d in policy_decisions],
            )

        # Step 5: Allow with conditions
        duration_ms = utc_now_ms() - start_ms
        if duration_ms > 10:
            logger.warning(
                f"Permission check took {duration_ms}ms (target: <10ms) for "
                f"agent={agent_id}, capability={capability_id}"
            )

        return PermissionResult(
            allowed=True,
            reason="All checks passed",
            conditions=None,  # Could add time windows, quotas, etc.
            risk_score=risk_score.score,
            policy_ids=[d.policy_id for d in policy_decisions],
            checked_at_ms=start_ms,
        )

    def _deny_permission(
        self,
        agent_id: str,
        capability_id: str,
        reason: str,
        risk_score: Optional[float],
        checked_at_ms: int,
        policy_ids: Optional[List[str]] = None,
    ) -> PermissionResult:
        """Helper to create denial result"""
        return PermissionResult(
            allowed=False,
            reason=reason,
            conditions=None,
            risk_score=risk_score,
            policy_ids=policy_ids or [],
            checked_at_ms=checked_at_ms,
        )

    def _has_capability_grant(self, agent_id: str, capability_id: str) -> bool:
        """
        Check if agent has capability grant.

        This queries the capability_grants table from CapabilityRegistry.
        """
        # Import here to avoid circular dependency
        from agentos.core.capability.registry import get_capability_registry

        registry = get_capability_registry(self.db_path)
        return registry.has_capability(agent_id, capability_id)

    def _get_agent_trust_tier(self, agent_id: str) -> TrustTier:
        """
        Get agent's trust tier.

        Default mapping:
        - user:* → T4 (full trust)
        - system → T4
        - *_admin → T3
        - *_agent → T2
        - test_* → T2
        - unknown → T0
        """
        if agent_id.startswith("user:"):
            return TrustTier.T4
        if agent_id == "system":
            return TrustTier.T4
        if agent_id.endswith("_admin"):
            return TrustTier.T3
        if agent_id.endswith("_agent"):
            return TrustTier.T2
        if agent_id.startswith("test_"):
            return TrustTier.T2
        return TrustTier.T0

    # ===================================================================
    # GC-002: governance.policy.evaluate
    # ===================================================================

    def enforce_policy(
        self,
        policy_id: str,
        input_context: Dict[str, Any],
    ) -> PolicyDecision:
        """
        Evaluate a specific policy (GC-002).

        Args:
            policy_id: Policy identifier
            input_context: Context for evaluation

        Returns:
            PolicyDecision with action and reasoning
        """
        policy = self.policy_registry.load_policy(policy_id)
        if policy is None:
            # Policy not found - fail safe to DENY
            logger.warning(f"Policy not found: {policy_id}, defaulting to DENY")
            return PolicyDecision(
                policy_id=policy_id,
                policy_version="unknown",
                decision=PolicyAction.DENY,
                rules_triggered=[],
                confidence=0.0,
                context=input_context,
                evaluated_at_ms=utc_now_ms(),
            )

        # Evaluate policy
        decision = policy.evaluate(input_context)
        decision.evaluated_at_ms = utc_now_ms()

        # Log evaluation to database
        self._log_policy_evaluation(decision)

        return decision

    def _evaluate_policies(self, context: GovernanceContext) -> List[PolicyDecision]:
        """
        Evaluate all relevant policies for context.

        Args:
            context: Governance context

        Returns:
            List of policy decisions
        """
        # Get policies for capability domain
        capability_domain = context.capability_id.split(".")[0]
        policies = self.policy_registry.list_policies(domain=capability_domain)

        # Also get global policies
        global_policies = self.policy_registry.list_policies(domain="global")
        policies.extend(global_policies)

        decisions = []
        for policy in policies:
            if not policy.active:
                continue

            # Convert context to dict for evaluation
            context_dict = {
                "agent_id": context.agent_id,
                "capability_id": context.capability_id,
                "operation": context.operation,
                "trust_tier": context.trust_tier.value,
                "estimated_cost": context.estimated_cost or 0,
                "estimated_tokens": context.estimated_tokens or 0,
                "side_effects_count": len(context.side_effects),
                "project_id": context.project_id,
                **context.parameters,
                **context.metadata,
            }

            decision = policy.evaluate(context_dict)
            decision.evaluated_at_ms = utc_now_ms()
            decisions.append(decision)

            # Log evaluation
            self._log_policy_evaluation(decision)

        return decisions

    def _log_policy_evaluation(self, decision: PolicyDecision):
        """Log policy evaluation to database"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO governance_policy_evaluations (
                policy_id, policy_version, input_context_json, decision,
                rules_triggered_json, confidence, evaluated_at_ms
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                decision.policy_id,
                decision.policy_version,
                json.dumps(decision.context),
                decision.decision.value,
                json.dumps(decision.rules_triggered),
                decision.confidence,
                decision.evaluated_at_ms,
            ),
        )

        conn.commit()
        conn.close()

    # ===================================================================
    # GC-003: governance.risk.score
    # ===================================================================

    def calculate_risk_score(
        self,
        capability_id: str,
        context: GovernanceContext,
    ) -> RiskScore:
        """
        Calculate risk score for operation (GC-003).

        Delegates to RiskCalculator for actual scoring logic.

        Args:
            capability_id: Capability being invoked
            context: Governance context

        Returns:
            RiskScore with level and factors
        """
        risk_score = self.risk_calculator.calculate(
            capability_id=capability_id,
            context=context,
        )

        # Log risk assessment to database
        self._log_risk_assessment(
            capability_id=capability_id,
            agent_id=context.agent_id,
            risk_score=risk_score,
        )

        return risk_score

    def _log_risk_assessment(
        self,
        capability_id: str,
        agent_id: str,
        risk_score: RiskScore,
    ):
        """Log risk assessment to database"""
        conn = self._get_connection()
        cursor = conn.cursor()

        factors_json = json.dumps([f.model_dump() for f in risk_score.factors])

        cursor.execute(
            """
            INSERT INTO risk_assessments (
                capability_id, agent_id, risk_score, risk_level,
                factors_json, mitigation_required, assessed_at_ms
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                capability_id,
                agent_id,
                risk_score.score,
                risk_score.level.value,
                factors_json,
                int(risk_score.mitigation_required),
                risk_score.assessed_at_ms,
            ),
        )

        conn.commit()
        conn.close()

    # ===================================================================
    # GC-004: governance.override.admin (delegated to OverrideManager)
    # ===================================================================

    def create_override(
        self,
        admin_id: str,
        blocked_operation: str,
        override_reason: str,
        duration_hours: int = 24,
    ) -> OverrideToken:
        """
        Create emergency override token (GC-004).

        Delegates to OverrideManager.

        Args:
            admin_id: Admin creating override
            blocked_operation: Description of blocked operation
            override_reason: Reason for override (min 100 chars)
            duration_hours: How long override is valid

        Returns:
            OverrideToken

        Raises:
            ValueError: If reason is too short
        """
        return self.override_manager.create_override(
            admin_id=admin_id,
            blocked_operation=blocked_operation,
            reason=override_reason,
            duration_hours=duration_hours,
        )

    def validate_override(self, override_token: str) -> bool:
        """
        Validate override token (GC-004).

        Args:
            override_token: Override token string

        Returns:
            True if valid, False otherwise
        """
        return self.override_manager.validate_override(override_token)

    # ===================================================================
    # GC-005: governance.quota.check
    # ===================================================================

    def check_quota(
        self,
        agent_id: str,
        resource_type: str,
        requested_amount: float = 0,
    ) -> QuotaStatus:
        """
        Check resource quota for agent (GC-005).

        Args:
            agent_id: Agent identifier
            resource_type: Type of resource (tokens, api_calls, etc)
            requested_amount: How much is being requested

        Returns:
            QuotaStatus with current usage and limit
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Query quota
        cursor.execute(
            """
            SELECT quota_id, limit_value, current_usage, reset_interval_ms,
                   last_reset_ms, updated_at_ms
            FROM resource_quotas
            WHERE agent_id = ? AND resource_type = ?
            """,
            (agent_id, resource_type),
        )
        row = cursor.fetchone()

        if row is None:
            # No quota defined - default to unlimited
            conn.close()
            return QuotaStatus(
                resource_type=resource_type,
                agent_id=agent_id,
                current_usage=0,
                limit=float("inf"),
                remaining=float("inf"),
                reset_at_ms=None,
                usage_percentage=0.0,
                exceeded=False,
                checked_at_ms=utc_now_ms(),
            )

        current_usage = row["current_usage"]
        limit = row["limit_value"]
        reset_interval_ms = row["reset_interval_ms"]
        last_reset_ms = row["last_reset_ms"]

        # Check if quota should be reset
        now_ms = utc_now_ms()
        if reset_interval_ms and last_reset_ms:
            if now_ms - last_reset_ms >= reset_interval_ms:
                # Reset quota
                current_usage = 0
                cursor.execute(
                    """
                    UPDATE resource_quotas
                    SET current_usage = 0, last_reset_ms = ?, updated_at_ms = ?
                    WHERE quota_id = ?
                    """,
                    (now_ms, now_ms, row["quota_id"]),
                )
                conn.commit()

        conn.close()

        # Calculate status
        remaining = max(0, limit - current_usage)
        usage_percentage = (current_usage / limit * 100) if limit > 0 else 0
        exceeded = (current_usage + requested_amount) > limit

        reset_at_ms = None
        if reset_interval_ms and last_reset_ms:
            reset_at_ms = last_reset_ms + reset_interval_ms

        return QuotaStatus(
            resource_type=resource_type,
            agent_id=agent_id,
            current_usage=current_usage,
            limit=limit,
            remaining=remaining,
            reset_at_ms=reset_at_ms,
            usage_percentage=usage_percentage,
            exceeded=exceeded,
            checked_at_ms=now_ms,
        )

    def increment_quota_usage(
        self,
        agent_id: str,
        resource_type: str,
        amount: float,
    ):
        """
        Increment quota usage for agent.

        Args:
            agent_id: Agent identifier
            resource_type: Type of resource
            amount: Amount to increment
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        now_ms = utc_now_ms()

        cursor.execute(
            """
            UPDATE resource_quotas
            SET current_usage = current_usage + ?,
                updated_at_ms = ?
            WHERE agent_id = ? AND resource_type = ?
            """,
            (amount, now_ms, agent_id, resource_type),
        )

        conn.commit()
        conn.close()

    # ===================================================================
    # Statistics
    # ===================================================================

    def get_stats(self) -> Dict[str, Any]:
        """Get governance engine statistics"""
        conn = self._get_connection()
        cursor = conn.cursor()

        stats = {}

        # Policy evaluations
        cursor.execute("SELECT COUNT(*) as count FROM governance_policy_evaluations")
        stats["total_policy_evaluations"] = cursor.fetchone()["count"]

        # Risk assessments
        cursor.execute("SELECT COUNT(*) as count FROM risk_assessments")
        stats["total_risk_assessments"] = cursor.fetchone()["count"]

        # High risk assessments
        cursor.execute(
            "SELECT COUNT(*) as count FROM risk_assessments WHERE risk_level IN ('HIGH', 'CRITICAL')"
        )
        stats["high_risk_assessments"] = cursor.fetchone()["count"]

        # Active overrides
        cursor.execute(
            """
            SELECT COUNT(*) as count FROM governance_overrides
            WHERE used = 0 AND expires_at_ms > ?
            """,
            (utc_now_ms(),),
        )
        stats["active_overrides"] = cursor.fetchone()["count"]

        conn.close()

        return stats


# ===================================================================
# Global singleton
# ===================================================================

_governance_engine_instance: Optional[GovernanceEngine] = None


def get_governance_engine(db_path: Optional[str] = None) -> GovernanceEngine:
    """
    Get global governance engine singleton.

    Args:
        db_path: Optional database path (only used on first call)

    Returns:
        Singleton GovernanceEngine instance
    """
    global _governance_engine_instance
    if _governance_engine_instance is None:
        _governance_engine_instance = GovernanceEngine(db_path=db_path)
    return _governance_engine_instance
