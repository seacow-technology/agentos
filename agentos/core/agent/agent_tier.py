"""
Agent Tier System - AgentOS v3

Agent信任等级管理系统：
1. Tier定义（0-3）
2. Tier升级/降级
3. Auto-grant capabilities
4. Tier transition history

Design Philosophy:
- 只能升级，不能降级（安全考虑）
- Tier升级需要ADMIN权限
- 完整的升级历史追踪
- Tier决定基础权限
"""

import logging
import sqlite3
from typing import List, Dict, Any, Optional

from agentos.core.time import utc_now_ms
from agentos.core.agent.models import AgentTier, AgentTierTransition


logger = logging.getLogger(__name__)


class InvalidTierTransitionError(Exception):
    """Raised when tier transition is invalid"""

    pass


class InsufficientPermissionError(Exception):
    """Raised when user lacks permission for operation"""

    pass


class AgentTierSystem:
    """
    Agent Tier Management System.

    Manages:
    - Tier definitions and metadata
    - Tier upgrades (with permission checks)
    - Auto-grant capabilities
    - Tier transition history

    Usage:
        from agentos.core.capability.registry import get_capability_registry

        tier_system = AgentTierSystem()
        registry = get_capability_registry()

        # Upgrade agent tier
        tier_system.upgrade_tier(
            agent_id="chat_agent",
            from_tier=AgentTier.T1_READ_ONLY,
            to_tier=AgentTier.T2_PROPOSE,
            changed_by="admin:alice",
            reason="Agent demonstrated reliable behavior"
        )

        # Auto-grant new tier capabilities
        tier_system.auto_grant_tier_capabilities(
            agent_id="chat_agent",
            tier=AgentTier.T2_PROPOSE,
            registry=registry
        )
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize tier system.

        Args:
            db_path: Optional database path
        """
        if db_path is None:
            from agentos.store import get_db_path
            db_path = get_db_path()

        self.db_path = db_path

        logger.info("AgentTierSystem initialized")

    def get_tier_info(self, tier: AgentTier) -> Dict[str, Any]:
        """
        Get tier metadata.

        Args:
            tier: AgentTier enum

        Returns:
            Dictionary with tier info
        """
        return {
            "tier": tier.value,
            "name": tier.name_str,
            "description": tier.description,
            "max_capabilities": tier.max_capabilities,
            "auto_grant_capabilities": tier.auto_grant_capabilities,
        }

    def get_all_tiers_info(self) -> List[Dict[str, Any]]:
        """
        Get info for all tiers.

        Returns:
            List of tier info dictionaries
        """
        return [
            self.get_tier_info(AgentTier.T0_UNTRUSTED),
            self.get_tier_info(AgentTier.T1_READ_ONLY),
            self.get_tier_info(AgentTier.T2_PROPOSE),
            self.get_tier_info(AgentTier.T3_TRUSTED),
        ]

    def upgrade_tier(
        self,
        agent_id: str,
        from_tier: AgentTier,
        to_tier: AgentTier,
        changed_by: str,
        reason: str,
        governance_engine: Optional[Any] = None,
    ) -> AgentTierTransition:
        """
        Upgrade agent tier.

        Only upgrades allowed, no downgrades (security consideration).

        Args:
            agent_id: Agent identifier
            from_tier: Current tier
            to_tier: Target tier
            changed_by: Who is making the change
            reason: Reason for upgrade
            governance_engine: Optional governance engine for permission check

        Returns:
            AgentTierTransition record

        Raises:
            InvalidTierTransitionError: If transition is invalid
            InsufficientPermissionError: If user lacks permission
        """
        # Validate transition
        if to_tier.value <= from_tier.value:
            raise InvalidTierTransitionError(
                f"Can only upgrade tiers, not downgrade. "
                f"Attempted: {from_tier.name} -> {to_tier.name}"
            )

        # Check permission (if governance engine provided)
        if governance_engine:
            perm_result = governance_engine.check_permission(
                agent_id=changed_by,
                capability_id="governance.agent.upgrade_tier",
                context={"target_agent": agent_id, "to_tier": to_tier.value},
            )

            if not perm_result.allowed:
                raise InsufficientPermissionError(
                    f"User '{changed_by}' lacks permission to upgrade agent tiers. "
                    f"Reason: {perm_result.reason}"
                )

        # Create transition record
        now_ms = utc_now_ms()
        transition = AgentTierTransition(
            agent_id=agent_id,
            from_tier=from_tier,
            to_tier=to_tier,
            changed_by=changed_by,
            reason=reason,
            changed_at_ms=now_ms,
        )

        # Save to database
        self._store_tier_change(transition)

        logger.info(
            f"Agent tier upgraded: {agent_id} from {from_tier.name} to {to_tier.name} "
            f"by {changed_by}"
        )

        return transition

    def auto_grant_tier_capabilities(
        self,
        agent_id: str,
        tier: AgentTier,
        registry: Any,  # CapabilityRegistry
        granted_by: str = "system:tier-upgrade",
    ):
        """
        Auto-grant capabilities for tier.

        Args:
            agent_id: Agent identifier
            tier: Target tier
            registry: CapabilityRegistry instance
            granted_by: Who is granting (default: system)
        """
        capabilities = tier.auto_grant_capabilities

        logger.info(
            f"Auto-granting {len(capabilities)} capabilities to {agent_id} "
            f"for tier {tier.name}"
        )

        for capability_id in capabilities:
            # Check if already granted
            if registry.has_capability(agent_id, capability_id):
                logger.debug(f"Capability {capability_id} already granted, skipping")
                continue

            # Grant capability
            registry.grant_capability(
                agent_id=agent_id,
                capability_id=capability_id,
                granted_by=granted_by,
                reason=f"Auto-grant for tier {tier.name}",
            )

            logger.debug(f"Auto-granted {capability_id} to {agent_id}")

        logger.info(f"Auto-grant complete for {agent_id}")

    def get_tier_history(self, agent_id: str) -> List[AgentTierTransition]:
        """
        Get tier transition history for agent.

        Args:
            agent_id: Agent identifier

        Returns:
            List of AgentTierTransition records (newest first)
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT agent_id, from_tier, to_tier, changed_by, reason, changed_at_ms
            FROM agent_tier_history
            WHERE agent_id = ?
            ORDER BY changed_at_ms DESC
            """,
            (agent_id,),
        )

        rows = cursor.fetchall()
        conn.close()

        transitions = []
        for row in rows:
            transition = AgentTierTransition(
                agent_id=row["agent_id"],
                from_tier=AgentTier(row["from_tier"]),
                to_tier=AgentTier(row["to_tier"]),
                changed_by=row["changed_by"],
                reason=row["reason"],
                changed_at_ms=row["changed_at_ms"],
            )
            transitions.append(transition)

        return transitions

    def get_current_tier(self, agent_id: str) -> Optional[AgentTier]:
        """
        Get current tier for agent.

        Looks up most recent tier transition in history.

        Args:
            agent_id: Agent identifier

        Returns:
            AgentTier or None if no history
        """
        history = self.get_tier_history(agent_id)
        if history:
            return history[0].to_tier
        return None

    def get_tier_stats(self) -> Dict[str, Any]:
        """
        Get tier system statistics.

        Returns:
            Dictionary with stats
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Count agents per tier
        cursor.execute(
            """
            SELECT to_tier, COUNT(DISTINCT agent_id) as agent_count
            FROM (
                SELECT agent_id, to_tier,
                       ROW_NUMBER() OVER (PARTITION BY agent_id ORDER BY changed_at_ms DESC) as rn
                FROM agent_tier_history
            )
            WHERE rn = 1
            GROUP BY to_tier
            """
        )

        tier_counts = {}
        for row in cursor.fetchall():
            tier_counts[AgentTier(row["to_tier"]).name_str] = row["agent_count"]

        # Total transitions
        cursor.execute("SELECT COUNT(*) as count FROM agent_tier_history")
        total_transitions = cursor.fetchone()["count"]

        # Recent transitions
        cursor.execute(
            """
            SELECT COUNT(*) as count FROM agent_tier_history
            WHERE changed_at_ms > ?
            """,
            (utc_now_ms() - 24 * 60 * 60 * 1000,),  # Last 24h
        )
        recent_transitions = cursor.fetchone()["count"]

        conn.close()

        return {
            "tier_counts": tier_counts,
            "total_transitions": total_transitions,
            "recent_transitions_24h": recent_transitions,
        }

    def _store_tier_change(self, transition: AgentTierTransition):
        """Store tier transition to database"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO agent_tier_history (
                agent_id, from_tier, to_tier, changed_by, reason, changed_at_ms
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                transition.agent_id,
                transition.from_tier.value,
                transition.to_tier.value,
                transition.changed_by,
                transition.reason,
                transition.changed_at_ms,
            ),
        )

        conn.commit()
        conn.close()

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn


# ===================================================================
# Helper Functions
# ===================================================================


def initialize_agent_tier(
    agent_id: str,
    initial_tier: AgentTier,
    reason: str,
    tier_system: Optional[AgentTierSystem] = None,
) -> AgentTierTransition:
    """
    Initialize agent with starting tier.

    Args:
        agent_id: Agent identifier
        initial_tier: Starting tier
        reason: Reason for initialization
        tier_system: Optional tier system instance

    Returns:
        AgentTierTransition record
    """
    if tier_system is None:
        tier_system = AgentTierSystem()

    # Create transition from T0 to initial tier
    transition = tier_system.upgrade_tier(
        agent_id=agent_id,
        from_tier=AgentTier.T0_UNTRUSTED,
        to_tier=initial_tier,
        changed_by="system:initialization",
        reason=reason,
        governance_engine=None,  # Skip permission check for initialization
    )

    return transition
