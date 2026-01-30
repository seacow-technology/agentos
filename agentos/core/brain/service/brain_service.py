"""
BrainOS Query Service

提供知识图谱查询接口。

查询类型：
1. Why Query - 追溯原因
   - 输入：实体 ID 或 key（如 file path）
   - 输出：相关的 Doc/ADR/Commit + 证据链
   - 示例："为什么 task/manager.py 要实现重试机制？"

2. Impact Query - 影响分析
   - 输入：实体 ID 或 key
   - 输出：依赖它的实体列表 + 依赖边
   - 示例："修改 task/models.py 会影响哪些模块？"

3. Trace Query - 演进追踪
   - 输入：术语或概念
   - 输出：提到它的 Commit/Doc/File，按时间排序
   - 示例："追溯 'planning_guard' 概念的演进历史"

4. Map Query - 子图提取
   - 输入：种子实体 + 跳数（hops）
   - 输出：子图（nodes + edges）
   - 示例："围绕 'extensions' 能力输出子图谱"

契约：
- 所有查询必须带 graph_version
- 所有结果必须带 evidence_refs
- 查询应是只读的（不修改图谱）

TODO v0.2:
- 实现真实的查询逻辑（基于 SQLiteStore）
- 支持查询参数（limit, offset, depth）
- 查询性能优化（索引、缓存）
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from pathlib import Path

from agentos.core.brain.store import SQLiteStore


@dataclass
class QueryResult:
    """
    查询结果

    Attributes:
        nodes: 节点列表（实体）
        edges: 边列表（关系）
        evidence_refs: 证据链引用列表
        graph_version: 使用的图谱版本
        stats: 统计信息（节点数、边数、查询时间）
        metadata: 其他元数据

    Contract:
        - graph_version 必须存在
        - evidence_refs 至少有一条（PROVENANCE_PRINCIPLE）
    """
    nodes: List[Dict[str, Any]] = field(default_factory=list)
    edges: List[Dict[str, Any]] = field(default_factory=list)
    evidence_refs: List[str] = field(default_factory=list)
    graph_version: str = ""
    stats: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """验证必要字段"""
        if not self.graph_version:
            raise ValueError("QueryResult must have graph_version")

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "nodes": self.nodes,
            "edges": self.edges,
            "evidence_refs": self.evidence_refs,
            "graph_version": self.graph_version,
            "stats": self.stats,
            "metadata": self.metadata,
        }


class BrainService:
    """
    BrainOS 查询服务

    提供 Why/Impact/Trace/Map 四类查询。

    Attributes:
        store: SQLiteStore 实例
        default_version: 默认使用的图谱版本（如 "latest"）

    Example:
        >>> service = BrainService(store)
        >>> result = service.why_query("agentos/core/task/manager.py")
        >>> print(f"Found {len(result.nodes)} related docs")
    """

    def __init__(self, store: SQLiteStore, default_version: str = "latest"):
        self.store = store
        self.default_version = default_version

    def why_query(
        self,
        seed: str,
        version: Optional[str] = None,
        limit: int = 10
    ) -> QueryResult:
        """
        Why Query - 追溯原因

        查询与给定实体相关的文档、ADR、Commit，回答"为什么"。

        Args:
            seed: 种子实体（ID 或 key，如 file path）
            version: 图谱版本（默认使用 latest）
            limit: 返回数量限制

        Returns:
            QueryResult with related Docs/ADRs/Commits

        Algorithm (v0.1):
            1. 找到 seed 实体（File）
            2. 查找指向它的 REFERENCES 边（Doc → File）
            3. 查找指向它的 MODIFIES 边（Commit → File）
            4. 返回相关的 Doc 和 Commit 实体
            5. 收集所有证据链引用

        TODO v0.2:
            - 支持传递查询（Doc → Term → File）
            - 支持相关性排序（基于证据置信度）
            - 支持时间范围过滤
        """
        version = version or self.default_version

        # TODO v0.2: 实现真实查询逻辑
        return QueryResult(
            nodes=[],
            edges=[],
            evidence_refs=[],
            graph_version=version,
            stats={
                "query_type": "why",
                "seed": seed,
                "nodes_count": 0,
                "edges_count": 0,
            }
        )

    def impact_query(
        self,
        seed: str,
        version: Optional[str] = None,
        limit: int = 20
    ) -> QueryResult:
        """
        Impact Query - 影响分析

        查询依赖给定实体的所有实体，分析变更影响范围。

        Args:
            seed: 种子实体（ID 或 key）
            version: 图谱版本
            limit: 返回数量限制

        Returns:
            QueryResult with dependent entities

        Algorithm (v0.1):
            1. 找到 seed 实体（File）
            2. 查找从它出发的 DEPENDS_ON 边（File → File）
            3. 查找引用它的 REFERENCES 边（Doc → File）
            4. 返回所有依赖实体 + 依赖边
            5. 收集证据链

        TODO v0.2:
            - 支持传递依赖（A → B → C）
            - 区分直接依赖和间接依赖
            - 计算影响范围得分
        """
        version = version or self.default_version

        # TODO v0.2: 实现真实查询逻辑
        return QueryResult(
            nodes=[],
            edges=[],
            evidence_refs=[],
            graph_version=version,
            stats={
                "query_type": "impact",
                "seed": seed,
                "nodes_count": 0,
                "edges_count": 0,
            }
        )

    def trace_query(
        self,
        term: str,
        version: Optional[str] = None,
        limit: int = 50
    ) -> QueryResult:
        """
        Trace Query - 演进追踪

        追踪术语或概念的演进历史，按时间排序。

        Args:
            term: 术语或概念（如 "planning_guard"）
            version: 图谱版本
            limit: 返回数量限制

        Returns:
            QueryResult with Commits/Docs/Files, sorted by time

        Algorithm (v0.1):
            1. 查找 Term 实体（匹配 term）
            2. 查找所有 MENTIONS 边（* → Term）
            3. 返回源实体（Commit/Doc/File）
            4. 按时间排序（Commit.date, Doc.modified_date）
            5. 收集证据链（span 包含出现位置）

        TODO v0.2:
            - 支持模糊匹配和别名
            - 支持术语演化图（term → related terms over time）
            - 提取关键里程碑（如首次引入、重大变更）
        """
        version = version or self.default_version

        # TODO v0.2: 实现真实查询逻辑
        return QueryResult(
            nodes=[],
            edges=[],
            evidence_refs=[],
            graph_version=version,
            stats={
                "query_type": "trace",
                "term": term,
                "nodes_count": 0,
                "edges_count": 0,
            }
        )

    def map_query(
        self,
        seed: str,
        hops: int = 2,
        version: Optional[str] = None,
        limit: int = 100
    ) -> QueryResult:
        """
        Map Query - 子图提取

        围绕种子实体提取子图（N-hop neighborhood）。

        Args:
            seed: 种子实体（ID 或 key）
            hops: 跳数（默认 2）
            version: 图谱版本
            limit: 返回节点数量限制

        Returns:
            QueryResult with subgraph (nodes + edges)

        Algorithm (v0.1):
            1. 从 seed 实体开始
            2. BFS 遍历 N 跳：
               - 收集所有出边和入边
               - 收集目标节点
            3. 返回子图（所有节点 + 边）
            4. 收集证据链

        TODO v0.2:
            - 支持边类型过滤（只要 DEPENDS_ON 边）
            - 支持节点类型过滤（只要 File 和 Doc）
            - 子图可视化友好的格式（如 Cytoscape JSON）
        """
        version = version or self.default_version

        # TODO v0.2: 实现真实查询逻辑
        return QueryResult(
            nodes=[],
            edges=[],
            evidence_refs=[],
            graph_version=version,
            stats={
                "query_type": "map",
                "seed": seed,
                "hops": hops,
                "nodes_count": 0,
                "edges_count": 0,
            }
        )
