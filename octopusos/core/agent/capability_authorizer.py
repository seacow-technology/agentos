"""
Capability Authorizer - AgentOS v3

授权检查引擎，协调：
1. Agent Profile检查
2. Capability Registry Grant检查
3. Governance Policy检查
4. Risk Score检查
5. Escalation处理

Design Philosophy:
- 防御性授权（默认拒绝）
- 多层检查（Profile → Grant → Policy → Risk）
- 完整审计追踪
- 性能优化（缓存常见检查）
"""

import logging
import sqlite3
from typing import Dict, Any, Optional
from functools import lru_cache

from agentos.core.time import utc_now_ms
from agentos.core.agent.models import (
    AuthorizationResult,
    EscalationPolicy,
)
from agentos.core.agent.agent_profile import AgentCapabilityProfile


logger = logging.getLogger(__name__)


class CapabilityAuthorizer:
    """
    Capability authorization engine.

    Coordinates authorization checks across:
    - Agent profiles (can_use)
    - Capability grants (has_capability)
    - Governance policies (check_permission)
    - Risk scores (calculate_risk_score)

    Usage:
        from agentos.core.capability.registry import get_capability_registry
        from agentos.core.capability.domains.governance import get_governance_engine

        registry = get_capability_registry()
        governance = get_governance_engine()

        authorizer = CapabilityAuthorizer(registry, governance)

        result = authorizer.authorize(
            agent_id="chat_agent",
            capability_id="state.memory.read",
            context={"operation": "read"}
        )

        if result.allowed:
            # Execute operation
            pass
    """

    def __init__(
        self,
        registry: Any,  # CapabilityRegistry
        governance: Any,  # GovernanceEngine
        db_path: Optional[str] = None,
    ):
        """
        Initialize authorizer.

        Args:
            registry: CapabilityRegistry instance
            governance: GovernanceEngine instance
            db_path: Optional database path for profile storage
        """
        self.registry = registry
        self.governance = governance

        if db_path is None:
            from agentos.store import get_db_path
            db_path = get_db_path()

        self.db_path = db_path

        # Profile cache (in-memory for now)
        self._profiles: Dict[str, AgentCapabilityProfile] = {}

        logger.info("CapabilityAuthorizer initialized")

    def authorize(
        self,
        agent_id: str,
        capability_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> AuthorizationResult:
        """
        Authorize capability invocation.

        Multi-stage authorization:
        1. Check Agent Profile (can_use)
        2. Check Capability Grant (has_capability)
        3. Check Governance Policy (check_permission)
        4. Check Risk Score
        5. Handle escalation if needed

        Args:
            agent_id: Agent identifier
            capability_id: Capability to authorize
            context: Additional context for decision

        Returns:
            AuthorizationResult with decision and reasoning
        """
        start_ms = utc_now_ms()
        context = context or {}

        logger.debug(
            f"Authorization check: agent={agent_id}, capability={capability_id}"
        )

        # ===================================================================
        # Stage 1: Check Agent Profile
        # ===================================================================

        profile = self.get_profile(agent_id)
        if profile is None:
            # No profile = untrusted agent
            return self._deny(
                agent_id=agent_id,
                capability_id=capability_id,
                reason=f"No profile found for agent '{agent_id}', defaulting to deny",
                checked_at_ms=start_ms,
            )

        # Check if profile allows capability
        if not profile.can_use(capability_id):
            return self._deny(
                agent_id=agent_id,
                capability_id=capability_id,
                reason=f"Agent profile forbids capability '{capability_id}'",
                checked_at_ms=start_ms,
            )

        logger.debug(f"Stage 1 passed: Profile allows {capability_id}")

        # ===================================================================
        # Stage 2: Check Capability Grant
        # ===================================================================

        if not self.registry.has_capability(agent_id, capability_id):
            # No grant - trigger escalation policy
            return self._handle_escalation(
                agent_id=agent_id,
                capability_id=capability_id,
                profile=profile,
                context=context,
                checked_at_ms=start_ms,
            )

        logger.debug(f"Stage 2 passed: Grant exists for {capability_id}")

        # ===================================================================
        # Stage 3: Check Governance Policy
        # ===================================================================

        policy_result = self.governance.check_permission(
            agent_id=agent_id,
            capability_id=capability_id,
            context=context,
        )

        if not policy_result.allowed:
            return AuthorizationResult(
                allowed=False,
                reason=f"Denied by governance: {policy_result.reason}",
                policy_violations=[policy_result.reason],
                risk_score=policy_result.risk_score,
                checked_at_ms=start_ms,
            )

        logger.debug(f"Stage 3 passed: Governance allows {capability_id}")

        # ===================================================================
        # Stage 4: Check Risk Score
        # ===================================================================

        from agentos.core.capability.domains.governance.models import GovernanceContext

        gov_context = GovernanceContext(
            agent_id=agent_id,
            capability_id=capability_id,
            operation=context.get("operation", "unknown"),
            parameters=context.get("parameters", {}),
            trust_tier=self._get_trust_tier_from_profile(profile),
            estimated_cost=context.get("estimated_cost"),
            estimated_tokens=context.get("estimated_tokens"),
            side_effects=context.get("side_effects", []),
            project_id=context.get("project_id"),
            metadata=context,
        )

        risk_score = self.governance.calculate_risk_score(
            capability_id=capability_id,
            context=gov_context,
        )

        # Check if risk requires approval
        if risk_score.mitigation_required:
            # Check if agent tier is sufficient for risk level
            if profile.tier.value < self._get_required_tier_for_risk(risk_score.level):
                return self._deny(
                    agent_id=agent_id,
                    capability_id=capability_id,
                    reason=(
                        f"Risk level {risk_score.level.value} requires tier >= "
                        f"{self._get_required_tier_for_risk(risk_score.level)}, "
                        f"agent has tier {profile.tier.value}"
                    ),
                    risk_score=risk_score.score,
                    checked_at_ms=start_ms,
                )

        logger.debug(f"Stage 4 passed: Risk acceptable ({risk_score.level.value})")

        # ===================================================================
        # Stage 5: Allow
        # ===================================================================

        duration_ms = utc_now_ms() - start_ms
        if duration_ms > 10:
            logger.warning(
                f"Authorization check took {duration_ms}ms (target: <10ms) "
                f"for agent={agent_id}, capability={capability_id}"
            )

        return AuthorizationResult(
            allowed=True,
            reason="All authorization checks passed",
            risk_score=risk_score.score,
            checked_at_ms=start_ms,
            context={
                "duration_ms": duration_ms,
                "risk_level": risk_score.level.value,
                "tier": profile.tier.value,
            },
        )

    def _handle_escalation(
        self,
        agent_id: str,
        capability_id: str,
        profile: AgentCapabilityProfile,
        context: Dict[str, Any],
        checked_at_ms: int,
    ) -> AuthorizationResult:
        """
        Handle capability escalation based on profile policy.

        Args:
            agent_id: Agent identifier
            capability_id: Capability requested
            profile: Agent profile
            context: Request context
            checked_at_ms: Check timestamp

        Returns:
            AuthorizationResult
        """
        policy = profile.escalation_policy

        if policy == EscalationPolicy.DENY:
            return self._deny(
                agent_id=agent_id,
                capability_id=capability_id,
                reason="No grant exists, escalation policy=deny",
                checked_at_ms=checked_at_ms,
            )

        elif policy == EscalationPolicy.REQUEST_APPROVAL:
            # Create escalation request
            from agentos.core.agent.escalation_engine import EscalationEngine

            engine = EscalationEngine(db_path=self.db_path)
            request_id = engine.create_request(
                agent_id=agent_id,
                capability_id=capability_id,
                reason=context.get("reason", "Agent requested capability at runtime"),
                context=context,
            )

            return AuthorizationResult(
                allowed=False,
                reason=f"Approval required for '{capability_id}'",
                requires_approval=True,
                escalation_request_id=request_id,
                checked_at_ms=checked_at_ms,
            )

        elif policy == EscalationPolicy.TEMPORARY_GRANT:
            # Grant temporary capability (24h)
            logger.warning(
                f"Temporary grant issued for {agent_id} -> {capability_id} "
                f"(this should be rare!)"
            )

            expires_at_ms = utc_now_ms() + (24 * 60 * 60 * 1000)  # 24h

            self.registry.grant_capability(
                agent_id=agent_id,
                capability_id=capability_id,
                granted_by="system:auto-escalation",
                expires_at_ms=expires_at_ms,
                reason="Temporary escalation grant",
            )

            return AuthorizationResult(
                allowed=True,
                reason=f"Temporary grant issued (expires in 24h)",
                checked_at_ms=checked_at_ms,
                context={"expires_at_ms": expires_at_ms},
            )

        elif policy == EscalationPolicy.LOG_ONLY:
            # Log but allow (monitoring mode)
            logger.warning(
                f"LOG_ONLY escalation: {agent_id} using {capability_id} without grant"
            )

            # Log to audit trail
            self._log_escalation(
                agent_id=agent_id,
                capability_id=capability_id,
                policy="log_only",
                allowed=True,
            )

            return AuthorizationResult(
                allowed=True,
                reason="Allowed by LOG_ONLY escalation policy (monitoring mode)",
                checked_at_ms=checked_at_ms,
            )

        else:
            # Unknown policy - fail safe
            return self._deny(
                agent_id=agent_id,
                capability_id=capability_id,
                reason=f"Unknown escalation policy: {policy}",
                checked_at_ms=checked_at_ms,
            )

    def _deny(
        self,
        agent_id: str,
        capability_id: str,
        reason: str,
        risk_score: Optional[float] = None,
        checked_at_ms: Optional[int] = None,
    ) -> AuthorizationResult:
        """
        Create denial result and log.

        Args:
            agent_id: Agent identifier
            capability_id: Capability requested
            reason: Denial reason
            risk_score: Optional risk score
            checked_at_ms: Check timestamp

        Returns:
            AuthorizationResult (denied)
        """
        logger.info(
            f"Authorization denied: agent={agent_id}, "
            f"capability={capability_id}, reason={reason}"
        )

        # Log denial to audit trail
        self._log_denial(
            agent_id=agent_id,
            capability_id=capability_id,
            reason=reason,
        )

        return AuthorizationResult(
            allowed=False,
            reason=reason,
            risk_score=risk_score,
            checked_at_ms=checked_at_ms or utc_now_ms(),
        )

    def _log_denial(self, agent_id: str, capability_id: str, reason: str):
        """Log authorization denial to audit trail"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO capability_invocations (
                    agent_id, capability_id, operation, allowed, reason, timestamp_ms
                )
                VALUES (?, ?, ?, 0, ?, ?)
                """,
                (agent_id, capability_id, "authorization_check", reason, utc_now_ms()),
            )

            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to log denial: {e}")

    def _log_escalation(
        self, agent_id: str, capability_id: str, policy: str, allowed: bool
    ):
        """Log escalation event"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO capability_invocations (
                    agent_id, capability_id, operation, allowed,
                    reason, context_json, timestamp_ms
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    agent_id,
                    capability_id,
                    "escalation",
                    1 if allowed else 0,
                    f"Escalation policy={policy}",
                    f'{{"policy": "{policy}"}}',
                    utc_now_ms(),
                ),
            )

            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to log escalation: {e}")

    def get_profile(self, agent_id: str) -> Optional[AgentCapabilityProfile]:
        """
        Get agent profile.

        First checks in-memory cache, then database.

        Args:
            agent_id: Agent identifier

        Returns:
            AgentCapabilityProfile or None if not found
        """
        # Check cache
        if agent_id in self._profiles:
            return self._profiles[agent_id]

        # Load from database
        profile = self._load_profile_from_db(agent_id)
        if profile:
            self._profiles[agent_id] = profile

        return profile

    def register_profile(self, profile: AgentCapabilityProfile):
        """
        Register agent profile.

        Stores in both memory cache and database.

        Args:
            profile: AgentCapabilityProfile to register
        """
        # Store in cache
        self._profiles[profile.agent_id] = profile

        # Store in database
        self._save_profile_to_db(profile)

        logger.info(f"Registered profile for agent: {profile.agent_id}")

    def _load_profile_from_db(
        self, agent_id: str
    ) -> Optional[AgentCapabilityProfile]:
        """Load profile from database"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT agent_id, agent_type, tier, allowed_capabilities_json,
                       forbidden_capabilities_json, default_capability_level,
                       escalation_policy
                FROM agent_profiles
                WHERE agent_id = ?
                """,
                (agent_id,),
            )

            row = cursor.fetchone()
            conn.close()

            if row is None:
                return None

            import json

            from agentos.core.agent.models import AgentTier, EscalationPolicy

            profile = AgentCapabilityProfile(
                agent_id=row["agent_id"],
                tier=AgentTier(row["tier"]),
                allowed_capabilities=json.loads(row["allowed_capabilities_json"]),
                forbidden_capabilities=json.loads(
                    row["forbidden_capabilities_json"] or "[]"
                ),
                default_level=row["default_capability_level"],
                escalation_policy=EscalationPolicy(row["escalation_policy"]),
                agent_type=row["agent_type"],
            )

            return profile

        except Exception as e:
            logger.error(f"Failed to load profile for {agent_id}: {e}")
            return None

    def _save_profile_to_db(self, profile: AgentCapabilityProfile):
        """Save profile to database"""
        try:
            import json

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            now_ms = utc_now_ms()

            cursor.execute(
                """
                INSERT OR REPLACE INTO agent_profiles (
                    agent_id, agent_type, tier, allowed_capabilities_json,
                    forbidden_capabilities_json, default_capability_level,
                    escalation_policy, created_at_ms, updated_at_ms
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    profile.agent_id,
                    profile.agent_type,
                    profile.tier.value,
                    json.dumps(profile.allowed_capabilities),
                    json.dumps(profile.forbidden_capabilities),
                    profile.default_level,
                    profile.escalation_policy.value,
                    now_ms,
                    now_ms,
                ),
            )

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Failed to save profile for {profile.agent_id}: {e}")

    def _get_trust_tier_from_profile(self, profile: AgentCapabilityProfile):
        """Convert AgentTier to GovernanceTrustTier"""
        from agentos.core.capability.domains.governance.models import TrustTier

        mapping = {
            0: TrustTier.T0,
            1: TrustTier.T1,
            2: TrustTier.T2,
            3: TrustTier.T3,
        }
        return mapping.get(profile.tier.value, TrustTier.T0)

    def _get_required_tier_for_risk(self, risk_level) -> int:
        """Get minimum tier required for risk level"""
        from agentos.core.capability.domains.governance.models import RiskLevel

        # Risk level → minimum tier mapping
        mapping = {
            RiskLevel.LOW: 1,  # Tier 1+
            RiskLevel.MEDIUM: 2,  # Tier 2+
            RiskLevel.HIGH: 3,  # Tier 3+
            RiskLevel.CRITICAL: 3,  # Tier 3+ (may require override)
        }
        return mapping.get(risk_level, 3)
