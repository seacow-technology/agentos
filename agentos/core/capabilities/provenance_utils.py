"""
Provenance Utilities

溯源信息的应用场景工具。
"""

from typing import List, Optional
from agentos.core.capabilities.governance_models.provenance import ProvenanceStamp, TrustTier
from agentos.core.capabilities.capability_models import ToolResult


def filter_results_by_trust_tier(
    results: List[ToolResult],
    min_trust_tier: TrustTier
) -> List[ToolResult]:
    """
    根据信任层级过滤结果

    应用场景：在决策时只使用高信任级别的结果

    Args:
        results: 工具结果列表
        min_trust_tier: 最低信任层级

    Returns:
        过滤后的结果
    """
    trust_tier_order = [TrustTier.T0, TrustTier.T1, TrustTier.T2, TrustTier.T3]
    min_index = trust_tier_order.index(min_trust_tier)

    filtered = []
    for result in results:
        if result.provenance is None:
            continue
        try:
            tier_index = trust_tier_order.index(
                TrustTier(result.provenance.trust_tier)
            )
            if tier_index <= min_index:
                filtered.append(result)
        except (ValueError, KeyError):
            # Invalid trust tier, skip
            continue

    return filtered


def compare_results_by_env(
    results: List[ToolResult]
) -> dict:
    """
    比较不同环境的结果

    应用场景：分析同一工具在不同环境的行为差异

    Args:
        results: 工具结果列表（同一工具，不同环境）

    Returns:
        环境对比报告
    """
    env_groups = {}

    for result in results:
        if result.provenance is None:
            continue

        env_key = (
            result.provenance.execution_env.host,
            result.provenance.execution_env.platform
        )

        if env_key not in env_groups:
            env_groups[env_key] = []

        env_groups[env_key].append(result)

    return {
        "total_environments": len(env_groups),
        "environments": env_groups
    }


def verify_result_origin(
    result: ToolResult,
    expected_source_id: str,
    expected_trust_tier: Optional[TrustTier] = None
) -> bool:
    """
    验证结果来源

    应用场景：确保结果来自预期的能力来源

    Args:
        result: 工具结果
        expected_source_id: 预期来源 ID
        expected_trust_tier: 预期信任层级

    Returns:
        是否匹配
    """
    if result.provenance is None:
        return False

    if result.provenance.source_id != expected_source_id:
        return False

    if expected_trust_tier:
        if result.provenance.trust_tier != expected_trust_tier.value:
            return False

    return True
