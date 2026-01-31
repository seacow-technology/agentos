"""
Agent Capability Profile - AgentOS v3

Agent的Capability配置文件，定义：
1. Agent的信任等级(Tier)
2. 允许使用的Capabilities（支持通配符）
3. 禁止使用的Capabilities（优先级高于allowed）
4. 默认权限级别
5. 权限升级策略

Design Philosophy:
- 白名单+黑名单双重控制
- Forbidden优先于Allowed（安全第一）
- 支持通配符匹配（action.execute.*）
- Tier决定基础权限
"""

import fnmatch
import json
import logging
from typing import List, Dict, Any, Optional

from agentos.core.agent.models import AgentTier, EscalationPolicy

logger = logging.getLogger(__name__)


class AgentCapabilityProfile:
    """
    Agent Capability Profile - Agent权限配置文件

    定义Agent可以使用哪些Capabilities，以及权限升级策略。

    Attributes:
        agent_id: Agent唯一标识
        tier: 信任等级（0-3）
        allowed_capabilities: 允许使用的capabilities（支持通配符）
        forbidden_capabilities: 禁止使用的capabilities（优先级最高）
        default_level: 默认权限级别
        escalation_policy: 权限不足时的处理策略

    Usage:
        profile = AgentCapabilityProfile(
            agent_id="chat_agent",
            tier=AgentTier.T2_PROPOSE,
            allowed_capabilities=["state.read", "decision.*"],
            forbidden_capabilities=["action.execute.*"]
        )

        # 检查权限
        if profile.can_use("state.memory.read"):
            # 允许
            pass
    """

    def __init__(
        self,
        agent_id: str,
        tier: AgentTier,
        allowed_capabilities: List[str],
        forbidden_capabilities: Optional[List[str]] = None,
        default_level: str = "read",
        escalation_policy: EscalationPolicy = EscalationPolicy.DENY,
        agent_type: str = "agent",
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize agent capability profile.

        Args:
            agent_id: Agent identifier
            tier: Trust tier (0-3)
            allowed_capabilities: List of allowed capabilities (wildcards supported)
            forbidden_capabilities: List of forbidden capabilities (highest priority)
            default_level: Default capability level (read/propose/write)
            escalation_policy: Policy when capability not granted
            agent_type: Type of agent (decision_maker, executor, analyzer, etc.)
            metadata: Additional metadata
        """
        self.agent_id = agent_id
        self.tier = tier
        self.allowed_capabilities = allowed_capabilities
        self.forbidden_capabilities = forbidden_capabilities or []
        self.default_level = default_level
        self.escalation_policy = escalation_policy
        self.agent_type = agent_type
        self.metadata = metadata or {}

        # Validation
        self._validate()

        logger.debug(
            f"Created AgentCapabilityProfile: agent={agent_id}, tier={tier.name}, "
            f"allowed={len(allowed_capabilities)}, forbidden={len(self.forbidden_capabilities)}"
        )

    def _validate(self):
        """Validate profile configuration"""
        # Check tier capability limit
        if len(self.allowed_capabilities) > self.tier.max_capabilities:
            logger.warning(
                f"Agent {self.agent_id} has {len(self.allowed_capabilities)} capabilities, "
                f"exceeding tier {self.tier.name} limit of {self.tier.max_capabilities}"
            )

        # Check for conflicts between allowed and forbidden
        for allowed in self.allowed_capabilities:
            for forbidden in self.forbidden_capabilities:
                # Simple overlap check (not perfect with wildcards)
                if allowed == forbidden:
                    logger.warning(
                        f"Agent {self.agent_id}: capability '{allowed}' is both "
                        f"allowed and forbidden. Forbidden takes precedence."
                    )

    def can_use(self, capability_id: str) -> bool:
        """
        Check if agent can use capability based on profile.

        Logic:
        1. Check forbidden list (wildcards supported) - if matched, deny
        2. Check allowed list (wildcards supported) - if matched, allow
        3. Otherwise, deny

        Args:
            capability_id: Capability to check (e.g., "state.memory.read")

        Returns:
            True if allowed, False otherwise
        """
        # Step 1: Check forbidden (highest priority)
        for pattern in self.forbidden_capabilities:
            if fnmatch.fnmatch(capability_id, pattern):
                logger.debug(
                    f"Agent {self.agent_id}: capability '{capability_id}' "
                    f"forbidden by pattern '{pattern}'"
                )
                return False

        # Step 2: Check allowed
        for pattern in self.allowed_capabilities:
            if fnmatch.fnmatch(capability_id, pattern):
                logger.debug(
                    f"Agent {self.agent_id}: capability '{capability_id}' "
                    f"allowed by pattern '{pattern}'"
                )
                return True

        # Step 3: Default deny
        logger.debug(
            f"Agent {self.agent_id}: capability '{capability_id}' "
            f"not in allowed list, denied"
        )
        return False

    def get_tier_capabilities(self) -> List[str]:
        """
        Get capabilities automatically granted by tier.

        Returns:
            List of capability IDs
        """
        return self.tier.auto_grant_capabilities

    def get_all_allowed_capabilities(self) -> List[str]:
        """
        Get all allowed capabilities (explicit + tier-based).

        Note: This returns patterns, not expanded capabilities.

        Returns:
            List of capability patterns
        """
        tier_caps = self.get_tier_capabilities()
        all_caps = list(set(self.allowed_capabilities + tier_caps))
        return all_caps

    def check_tier_limit(self) -> bool:
        """
        Check if agent is within tier capability limit.

        Returns:
            True if within limit, False otherwise
        """
        current_count = len(self.allowed_capabilities)
        max_count = self.tier.max_capabilities
        return current_count <= max_count

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert profile to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "agent_id": self.agent_id,
            "tier": self.tier.value,
            "tier_name": self.tier.name_str,
            "allowed_capabilities": self.allowed_capabilities,
            "forbidden_capabilities": self.forbidden_capabilities,
            "default_level": self.default_level,
            "escalation_policy": self.escalation_policy.value,
            "agent_type": self.agent_type,
            "metadata": self.metadata,
            "tier_capabilities": self.get_tier_capabilities(),
            "within_tier_limit": self.check_tier_limit(),
        }

    def to_json(self) -> str:
        """
        Convert profile to JSON string.

        Returns:
            JSON string
        """
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentCapabilityProfile":
        """
        Create profile from dictionary.

        Args:
            data: Dictionary representation

        Returns:
            AgentCapabilityProfile instance
        """
        return cls(
            agent_id=data["agent_id"],
            tier=AgentTier(data["tier"]),
            allowed_capabilities=data["allowed_capabilities"],
            forbidden_capabilities=data.get("forbidden_capabilities", []),
            default_level=data.get("default_level", "read"),
            escalation_policy=EscalationPolicy(
                data.get("escalation_policy", "deny")
            ),
            agent_type=data.get("agent_type", "agent"),
            metadata=data.get("metadata", {}),
        )

    @classmethod
    def from_json(cls, json_str: str) -> "AgentCapabilityProfile":
        """
        Create profile from JSON string.

        Args:
            json_str: JSON string

        Returns:
            AgentCapabilityProfile instance
        """
        data = json.loads(json_str)
        return cls.from_dict(data)

    def __repr__(self) -> str:
        """String representation"""
        return (
            f"AgentCapabilityProfile(agent_id='{self.agent_id}', "
            f"tier={self.tier.name}, "
            f"allowed={len(self.allowed_capabilities)}, "
            f"forbidden={len(self.forbidden_capabilities)})"
        )


# ===================================================================
# Predefined Agent Profiles (Examples)
# ===================================================================


def create_chat_agent_profile() -> AgentCapabilityProfile:
    """
    Create profile for chat agent.

    Chat agent:
    - Tier 2 (Propose)
    - Can read state and propose memory changes
    - Cannot execute actions
    - Cannot write memory directly (only propose)
    """
    return AgentCapabilityProfile(
        agent_id="chat_agent",
        tier=AgentTier.T2_PROPOSE,
        agent_type="decision_maker",
        allowed_capabilities=[
            "state.read",
            "state.memory.propose",
            "decision.infoneed.classify",
            "evidence.query",
        ],
        forbidden_capabilities=[
            "action.execute.*",
            "state.memory.write",  # Only propose, not direct write
            "governance.override.*",
        ],
        escalation_policy=EscalationPolicy.REQUEST_APPROVAL,
    )


def create_executor_agent_profile() -> AgentCapabilityProfile:
    """
    Create profile for executor agent.

    Executor agent:
    - Tier 3 (Trusted)
    - Can execute local actions
    - Can write evidence
    - Cannot modify governance
    """
    return AgentCapabilityProfile(
        agent_id="executor_agent",
        tier=AgentTier.T3_TRUSTED,
        agent_type="executor",
        allowed_capabilities=[
            "state.read",
            "state.write",
            "action.execute.local",
            "action.execute.network",
            "evidence.write",
        ],
        forbidden_capabilities=[
            "action.execute.cloud",
            "governance.override.*",
            "governance.policy.evolve",
        ],
        escalation_policy=EscalationPolicy.REQUEST_APPROVAL,
    )


def create_analyzer_agent_profile() -> AgentCapabilityProfile:
    """
    Create profile for analyzer agent.

    Analyzer agent:
    - Tier 1 (Read-Only)
    - Can only read state and query evidence
    - Cannot make any changes
    """
    return AgentCapabilityProfile(
        agent_id="analyzer_agent",
        tier=AgentTier.T1_READ_ONLY,
        agent_type="analyzer",
        allowed_capabilities=[
            "state.read",
            "evidence.query",
        ],
        forbidden_capabilities=[
            "state.write",
            "state.memory.propose",
            "action.execute.*",
            "governance.*",
        ],
        escalation_policy=EscalationPolicy.DENY,
    )


def create_untrusted_agent_profile(agent_id: str) -> AgentCapabilityProfile:
    """
    Create profile for untrusted agent.

    Untrusted agent:
    - Tier 0 (Untrusted)
    - No capabilities
    - Complete isolation
    """
    return AgentCapabilityProfile(
        agent_id=agent_id,
        tier=AgentTier.T0_UNTRUSTED,
        agent_type="untrusted",
        allowed_capabilities=[],
        forbidden_capabilities=["*"],  # Forbid everything
        escalation_policy=EscalationPolicy.DENY,
    )
