"""
Trust Tier Default Policies

定义不同信任层级的默认治理策略。

Trust Tier 是"默认治理强度"，不是权限或 enable/disable。
不同的信任层级自动应用不同的配额、副作用策略和 admin token 需求。

Architecture:
- T0 (local_extension): 最高信任，最宽松的策略
- T1 (local_mcp): 本地 MCP，高信任
- T2 (remote_mcp): 远程 MCP，中等信任，需要更严格的控制
- T3 (cloud_mcp): 云端 MCP，最低信任，最严格的限制
"""

import logging
from agentos.core.capabilities.capability_models import TrustTier, RiskLevel

logger = logging.getLogger(__name__)


# Trust Tier → 默认风险级别
# 信任层级越低，默认风险级别越高
TRUST_TIER_RISK_MAPPING = {
    TrustTier.T0: RiskLevel.LOW,
    TrustTier.T1: RiskLevel.MED,
    TrustTier.T2: RiskLevel.HIGH,
    TrustTier.T3: RiskLevel.CRITICAL,
}


# Trust Tier → 默认配额
# 信任层级越低，配额越严格
TRUST_TIER_QUOTA_DEFAULTS = {
    TrustTier.T0: {
        "calls_per_minute": 1000,
        "max_concurrent": 20,
        "max_runtime_ms": 600000,  # 10 minutes
    },
    TrustTier.T1: {
        "calls_per_minute": 100,
        "max_concurrent": 10,
        "max_runtime_ms": 300000,  # 5 minutes
    },
    TrustTier.T2: {
        "calls_per_minute": 20,
        "max_concurrent": 5,
        "max_runtime_ms": 120000,  # 2 minutes
    },
    TrustTier.T3: {
        "calls_per_minute": 10,
        "max_concurrent": 2,
        "max_runtime_ms": 60000,  # 1 minute
    },
}


# Trust Tier → 副作用策略
# 信任层级越低，副作用限制越严格
TRUST_TIER_SIDE_EFFECTS_POLICY = {
    TrustTier.T0: {
        "allow_side_effects": True,
        "blacklisted_effects": [],
    },
    TrustTier.T1: {
        "allow_side_effects": True,
        "blacklisted_effects": [],
    },
    TrustTier.T2: {
        "allow_side_effects": True,  # 有条件允许
        "blacklisted_effects": ["payments", "cloud.resource_delete"],
    },
    TrustTier.T3: {
        "allow_side_effects": False,  # 默认不允许副作用
        "blacklisted_effects": [
            "payments",
            "cloud.key_write",
            "cloud.resource_delete",
            "fs.delete",
            "system.exec"
        ],
    },
}


# Trust Tier → Admin Token 需求
# 信任层级越低，越可能需要 admin token
TRUST_TIER_ADMIN_TOKEN_REQUIRED = {
    TrustTier.T0: False,
    TrustTier.T1: False,
    TrustTier.T2: False,  # 但有副作用时可能需要
    TrustTier.T3: True,   # 默认需要
}


def get_default_risk_level(trust_tier: TrustTier) -> RiskLevel:
    """
    获取信任层级的默认风险级别

    Args:
        trust_tier: 信任层级

    Returns:
        RiskLevel: 默认风险级别
    """
    risk = TRUST_TIER_RISK_MAPPING.get(trust_tier, RiskLevel.MED)
    logger.debug(f"Default risk level for {trust_tier.value}: {risk.value}")
    return risk


def get_default_quota(trust_tier: TrustTier) -> dict:
    """
    获取信任层级的默认配额

    Args:
        trust_tier: 信任层级

    Returns:
        dict: 默认配额配置 (calls_per_minute, max_concurrent, max_runtime_ms)
    """
    quota = TRUST_TIER_QUOTA_DEFAULTS.get(
        trust_tier,
        TRUST_TIER_QUOTA_DEFAULTS[TrustTier.T1]
    )
    logger.debug(f"Default quota for {trust_tier.value}: {quota}")
    return quota


def should_require_admin_token(
    trust_tier: TrustTier,
    has_side_effects: bool = False
) -> bool:
    """
    判断是否需要 admin token

    规则:
    - T3 默认需要 admin token
    - T2 + 副作用需要 admin token
    - T0, T1 不需要 admin token

    Args:
        trust_tier: 信任层级
        has_side_effects: 是否有副作用

    Returns:
        bool: 是否需要 admin token
    """
    base_requirement = TRUST_TIER_ADMIN_TOKEN_REQUIRED.get(trust_tier, False)

    # T2 + 副作用 → 需要 token
    if trust_tier == TrustTier.T2 and has_side_effects:
        logger.debug(f"Admin token required for {trust_tier.value} with side effects")
        return True

    if base_requirement:
        logger.debug(f"Admin token required for {trust_tier.value} (base requirement)")

    return base_requirement


def get_side_effects_policy(trust_tier: TrustTier) -> dict:
    """
    获取副作用策略

    Args:
        trust_tier: 信任层级

    Returns:
        dict: 副作用策略 (allow_side_effects, blacklisted_effects)
    """
    policy = TRUST_TIER_SIDE_EFFECTS_POLICY.get(
        trust_tier,
        TRUST_TIER_SIDE_EFFECTS_POLICY[TrustTier.T1]
    )
    logger.debug(
        f"Side effects policy for {trust_tier.value}: "
        f"allow={policy['allow_side_effects']}, "
        f"blacklist={policy['blacklisted_effects']}"
    )
    return policy
