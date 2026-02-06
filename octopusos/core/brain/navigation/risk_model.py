"""
Risk Model - 路径风险评估

核心功能：
- 计算路径置信度（confidence）
- 计算路径风险等级（risk_level）
- 生成路径评分（PathScore）

公式：
- confidence = evidence_weight / (evidence_weight + blind_spot_penalty + hop_penalty)
- risk_level = LOW/MEDIUM/HIGH based on blind_spot_count and coverage
"""

import logging
from typing import List
from .models import Path, PathScore, RiskLevel, CognitiveZone
from ..store import SQLiteStore

logger = logging.getLogger(__name__)


def compute_path_score(store: SQLiteStore, path: Path) -> PathScore:
    """
    计算路径评分

    Args:
        store: BrainOS 数据库
        path: 路径对象

    Returns:
        PathScore: 路径评分对象
    """
    # 1. 正向因子
    evidence_weight = float(path.total_evidence)

    # 覆盖多样性：不同来源数 / 3
    coverage_diversity = len(path.coverage_sources) / 3.0

    # 2. 负向因子
    # 盲区惩罚：每个盲区节点 -5 分
    blind_spot_penalty = float(path.blind_spot_count) * 5.0

    # 跳数惩罚：每跳 -0.5 分
    hop_penalty = float(path.total_hops) * 0.5

    # 3. 综合得分
    total_score = (
        evidence_weight +
        coverage_diversity * 10.0 -  # 放大多样性权重
        blind_spot_penalty -
        hop_penalty
    )

    # 4. 计算置信度（归一化到 0-1）
    confidence = compute_path_confidence(
        path.total_evidence,
        path.blind_spot_count,
        path.total_hops
    )

    # 5. 计算风险等级
    risk_level = compute_path_risk(
        path.blind_spot_count,
        path.coverage_sources
    )

    return PathScore(
        path_id=path.path_id,
        evidence_weight=evidence_weight,
        coverage_diversity=coverage_diversity,
        blind_spot_penalty=blind_spot_penalty,
        hop_penalty=hop_penalty,
        total_score=total_score,
        confidence=confidence,
        risk_level=risk_level
    )


def compute_path_confidence(
    total_evidence: int,
    blind_spot_count: int,
    total_hops: int
) -> float:
    """
    计算路径置信度（0-1）

    公式：
    confidence = evidence_weight / (evidence_weight + blind_spot_penalty + hop_penalty + 1)

    Args:
        total_evidence: 总证据数
        blind_spot_count: 盲区节点数
        total_hops: 跳数

    Returns:
        float: 置信度（0-1）
    """
    evidence_weight = float(total_evidence)
    blind_spot_penalty = float(blind_spot_count) * 5.0
    hop_penalty = float(total_hops) * 0.5

    denominator = evidence_weight + blind_spot_penalty + hop_penalty + 1.0

    confidence = evidence_weight / denominator

    # 额外惩罚：如果有盲区，最高置信度为 0.7
    if blind_spot_count > 0:
        confidence = min(confidence, 0.7)

    # 额外惩罚：如果跳数太多（>5），最高置信度为 0.6
    if total_hops > 5:
        confidence = min(confidence, 0.6)

    return min(1.0, max(0.0, confidence))


def compute_path_risk(
    blind_spot_count: int,
    coverage_sources: List[str]
) -> RiskLevel:
    """
    计算路径风险等级

    规则：
    - LOW: 无盲区 AND 至少 2 源覆盖
    - HIGH: 有 2+ 盲区 OR 零源覆盖
    - MEDIUM: 其他情况

    Args:
        blind_spot_count: 盲区节点数
        coverage_sources: 覆盖来源列表

    Returns:
        RiskLevel: 风险等级
    """
    if blind_spot_count == 0 and len(coverage_sources) >= 2:
        return RiskLevel.LOW

    if blind_spot_count >= 2 or len(coverage_sources) == 0:
        return RiskLevel.HIGH

    return RiskLevel.MEDIUM


def generate_recommendation_reason(
    path: Path,
    path_type: str
) -> str:
    """
    生成推荐理由

    Args:
        path: 路径对象
        path_type: 路径类型（SAFE/INFORMATIVE/CONSERVATIVE）

    Returns:
        str: 推荐理由
    """
    if path_type == "SAFE":
        return (
            f"This is the SAFE path: {path.total_evidence} evidence points, "
            f"{len(path.coverage_sources)} source types, "
            f"only {path.blind_spot_count} blind spot(s)."
        )
    elif path_type == "INFORMATIVE":
        return (
            f"This is the INFORMATIVE path: explores {len(path.coverage_sources)} "
            f"different knowledge sources with {path.total_evidence} evidence."
        )
    elif path_type == "CONSERVATIVE":
        return (
            f"This is the CONSERVATIVE path: avoids all blind spots, "
            f"stays within well-understood regions with {path.total_evidence} evidence."
        )
    else:
        return f"This path has {path.total_evidence} evidence and {path.total_hops} hops."
