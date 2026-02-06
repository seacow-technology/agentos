"""
P3-A Navigation 数据模型

核心概念：
- Path（路径）：一系列证据连接的节点序列
- Zone（区域）：当前节点所在的认知区域（CORE/EDGE/NEAR_BLIND）
- PathRecommendation（路径推荐）：包含风险、置信度的推荐路径
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Dict


class CognitiveZone(Enum):
    """认知区域分类"""
    CORE = "CORE"              # 核心区：多源覆盖、高证据密度
    EDGE = "EDGE"              # 边缘区：单源覆盖、中等证据密度
    NEAR_BLIND = "NEAR_BLIND"  # 近盲区：零源或单源、低证据密度


class PathType(Enum):
    """路径类型"""
    SAFE = "SAFE"                    # 最安全：高证据、低盲区
    INFORMATIVE = "INFORMATIVE"      # 最信息增量：探索新区域
    CONSERVATIVE = "CONSERVATIVE"    # 最保守：避开盲区


class RiskLevel(Enum):
    """风险等级"""
    LOW = "LOW"        # 低风险：无盲区、高证据
    MEDIUM = "MEDIUM"  # 中风险：少量盲区或中等证据
    HIGH = "HIGH"      # 高风险：多盲区或低证据


@dataclass
class PathNode:
    """路径节点（路径中的一个步骤）"""
    entity_id: str
    entity_type: str
    entity_name: str

    # 从上一节点到这个节点的边信息
    edge_id: Optional[str]  # None for seed node
    edge_type: Optional[str]
    evidence_count: int

    # 节点自身的认知属性
    zone: CognitiveZone
    is_blind_spot: bool
    coverage_sources: List[str]

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "entity_name": self.entity_name,
            "edge_id": self.edge_id,
            "edge_type": self.edge_type,
            "evidence_count": self.evidence_count,
            "zone": self.zone.value,
            "is_blind_spot": self.is_blind_spot,
            "coverage_sources": self.coverage_sources
        }


@dataclass
class Path:
    """路径（完整的导航路径）"""
    path_id: str
    path_type: PathType
    nodes: List[PathNode]

    # 路径整体评分
    confidence: float  # 0-1, 路径可信度
    risk_level: RiskLevel

    # 路径统计
    total_hops: int
    total_evidence: int  # 所有边的证据总数
    coverage_sources: List[str]  # 路径覆盖的所有来源
    blind_spot_count: int  # 路径中的盲区节点数

    # 为什么推荐这条路径
    recommendation_reason: str

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "path_id": self.path_id,
            "path_type": self.path_type.value,
            "nodes": [node.to_dict() for node in self.nodes],
            "confidence": self.confidence,
            "risk_level": self.risk_level.value,
            "total_hops": self.total_hops,
            "total_evidence": self.total_evidence,
            "coverage_sources": self.coverage_sources,
            "blind_spot_count": self.blind_spot_count,
            "recommendation_reason": self.recommendation_reason
        }


@dataclass
class NavigationResult:
    """导航结果"""
    seed_entity: str
    goal_entity: Optional[str]  # None if exploring

    # 当前位置
    current_zone: CognitiveZone
    current_zone_description: str

    # 推荐路径（最多 3 条）
    paths: List[Path]

    # 如果无路可达
    no_path_reason: Optional[str]

    # 元数据
    computed_at: str
    graph_version: str

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "seed_entity": self.seed_entity,
            "goal_entity": self.goal_entity,
            "current_zone": self.current_zone.value,
            "current_zone_description": self.current_zone_description,
            "paths": [path.to_dict() for path in self.paths],
            "no_path_reason": self.no_path_reason,
            "computed_at": self.computed_at,
            "graph_version": self.graph_version
        }


@dataclass
class ZoneMetrics:
    """区域指标（用于判断当前区域）"""
    entity_id: str

    # 证据密度
    evidence_count: int
    evidence_density: float  # 相对于邻居的平均值

    # 覆盖来源
    coverage_sources: List[str]
    coverage_ratio: float  # len(sources) / 3

    # 盲区情况
    is_blind_spot: bool
    blind_spot_severity: Optional[float]

    # 拓扑位置
    in_degree: int
    out_degree: int
    centrality: float  # 简单中心性：(in + out) / avg_degree

    # 综合评分
    zone_score: float  # 0-1, 越高越核心

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "entity_id": self.entity_id,
            "evidence_count": self.evidence_count,
            "evidence_density": self.evidence_density,
            "coverage_sources": self.coverage_sources,
            "coverage_ratio": self.coverage_ratio,
            "is_blind_spot": self.is_blind_spot,
            "blind_spot_severity": self.blind_spot_severity,
            "in_degree": self.in_degree,
            "out_degree": self.out_degree,
            "centrality": self.centrality,
            "zone_score": self.zone_score
        }


@dataclass
class PathScore:
    """路径评分（用于排序路径）"""
    path_id: str

    # 正向因子
    evidence_weight: float  # Σ evidence_count
    coverage_diversity: float  # 覆盖来源多样性

    # 负向因子
    blind_spot_penalty: float  # Σ blind_spot_severity
    hop_penalty: float  # 距离惩罚

    # 综合得分
    total_score: float
    confidence: float
    risk_level: RiskLevel

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "path_id": self.path_id,
            "evidence_weight": self.evidence_weight,
            "coverage_diversity": self.coverage_diversity,
            "blind_spot_penalty": self.blind_spot_penalty,
            "hop_penalty": self.hop_penalty,
            "total_score": self.total_score,
            "confidence": self.confidence,
            "risk_level": self.risk_level.value
        }
