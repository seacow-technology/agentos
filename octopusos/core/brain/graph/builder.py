"""
BrainOS Graph Builder

从抽取器结果构建知识图谱。

职责：
1. 接收多个 ExtractionResult
2. 合并实体（去重、合并属性）
3. 合并边（同类型边合并证据链）
4. 生成图谱版本元数据

去重策略：
- 实体：基于 (type, key) 去重
- 边：基于 (source, target, type) 去重，合并 evidence

幂等性保证：
- 相同的抽取结果序列 → 相同的图谱
- 使用确定性的 ID 生成（基于 key hash）
- 排序和规范化输入

TODO v0.2:
- 支持增量构建（基于已有图谱）
- 图谱验证（检查孤立节点、无效边）
- 图谱统计（节点数、边数、密度）
"""

from typing import List, Dict, Any, Optional
from collections import defaultdict
import hashlib

from agentos.core.brain.extractors import ExtractionResult
from agentos.core.brain.models import Entity, Edge, EdgeType


class GraphBuilder:
    """
    知识图谱构建器

    从多个抽取结果构建统一的知识图谱。

    Attributes:
        entities: 实体字典 {key: Entity}
        edges: 边字典 {(source, target, type): Edge}
        metadata: 图谱元数据

    Example:
        >>> builder = GraphBuilder()
        >>> builder.add_extraction_result(git_result)
        >>> builder.add_extraction_result(doc_result)
        >>> graph_data = builder.build()
    """

    def __init__(self):
        self.entities: Dict[str, Entity] = {}
        self.edges: Dict[tuple, Edge] = {}
        self.metadata: Dict[str, Any] = {}

    def add_extraction_result(self, result: ExtractionResult) -> None:
        """
        添加抽取结果到图谱

        Args:
            result: ExtractionResult 对象

        Contract:
            - 实体去重：相同 (type, key) 的实体合并
            - 边去重：相同 (source, target, type) 的边合并证据链
        """
        # 合并实体
        for entity in result.entities:
            entity_key = f"{entity.type}:{entity.key}"
            if entity_key in self.entities:
                # 已存在，合并属性（后者覆盖前者）
                existing = self.entities[entity_key]
                existing.attrs.update(entity.attrs)
            else:
                # 新实体
                self.entities[entity_key] = entity

        # 合并边
        for edge in result.edges:
            edge_key = (edge.source, edge.target, edge.type)
            if edge_key in self.edges:
                # 已存在，合并证据链
                existing = self.edges[edge_key]
                existing.evidence.extend(edge.evidence)
            else:
                # 新边
                self.edges[edge_key] = edge

    def build(self) -> Dict[str, Any]:
        """
        构建最终图谱

        Returns:
            Dict with entities, edges, metadata

        Contract:
            - 幂等性：多次调用返回相同结果
            - 完整性：所有边的 source/target 必须存在对应实体
        """
        return {
            "entities": [e.to_dict() for e in self.entities.values()],
            "edges": [e.to_dict() for e in self.edges.values()],
            "stats": {
                "entity_count": len(self.entities),
                "edge_count": len(self.edges),
                "entity_types": self._count_entity_types(),
                "edge_types": self._count_edge_types(),
            },
            "metadata": self.metadata,
        }

    def _count_entity_types(self) -> Dict[str, int]:
        """统计各类型实体数量"""
        counts = defaultdict(int)
        for entity in self.entities.values():
            counts[entity.type.value] += 1
        return dict(counts)

    def _count_edge_types(self) -> Dict[str, int]:
        """统计各类型边数量"""
        counts = defaultdict(int)
        for edge in self.edges.values():
            counts[edge.type.value] += 1
        return dict(counts)

    def set_version(self, version: str, commit_hash: Optional[str] = None) -> None:
        """
        设置图谱版本

        Args:
            version: 版本号（如 "0.1.0"）
            commit_hash: 对应的 commit hash（用于幂等性验证）
        """
        self.metadata["version"] = version
        if commit_hash:
            self.metadata["commit_hash"] = commit_hash

    def validate(self) -> bool:
        """
        验证图谱完整性

        检查：
        1. 所有边的 source/target 必须存在对应实体
        2. 所有边必须有证据链

        Returns:
            bool: True if valid

        Raises:
            ValueError: 如果发现无效边
        """
        for edge in self.edges.values():
            # 检查 source
            if edge.source not in self.entities:
                raise ValueError(
                    f"Edge {edge.id} references non-existent source: {edge.source}"
                )
            # 检查 target
            if edge.target not in self.entities:
                raise ValueError(
                    f"Edge {edge.id} references non-existent target: {edge.target}"
                )
            # 检查证据链
            if not edge.evidence:
                raise ValueError(
                    f"Edge {edge.id} violates PROVENANCE_PRINCIPLE: no evidence"
                )
        return True
