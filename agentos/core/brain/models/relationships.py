"""
BrainOS Relationship Models

定义实体之间的关系（边）和证据链。

关系类型（Edges v0.1）：
1. MODIFIES - Commit → File
2. REFERENCES - Doc → File/Term/Capability
3. MENTIONS - File/Doc/Commit → Term
4. DEPENDS_ON - File/Module → File/Module
5. IMPLEMENTS - File/Symbol → Capability

每条边必须包含：
- source: 源节点 ID
- target: 目标节点 ID
- type: 关系类型
- evidence: 证据链（provenance）

证据链要素：
- source_type: 证据来源类型（code/doc/commit/ast）
- source_ref: 具体引用位置（文件路径:行号:列号）
- span: 文本片段（可选）
- confidence: 置信度 (0.0-1.0)
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from enum import Enum
import json


class EdgeType(str, Enum):
    """关系类型枚举"""
    MODIFIES = "modifies"          # Commit → File
    REFERENCES = "references"      # Doc → File/Term/Capability
    MENTIONS = "mentions"          # File/Doc/Commit → Term
    DEPENDS_ON = "depends_on"      # File → File
    IMPLEMENTS = "implements"      # File/Symbol → Capability


@dataclass
class Evidence:
    """
    证据链/溯源信息

    每条关系边必须有证据支撑，用于回答"这条关系是从哪里来的"。

    Attributes:
        source_type: 证据来源类型（code/doc/commit/ast/import）
        source_ref: 具体引用位置（格式：path:line:col 或 commit:hash）
        span: 相关文本片段（可选，用于展示上下文）
        confidence: 置信度（0.0-1.0），默认 1.0 表示确定
        metadata: 其他元数据（如抽取方法、时间戳等）

    Examples:
        >>> Evidence(
        ...     source_type="import",
        ...     source_ref="agentos/core/task/manager.py:10:0",
        ...     span="from agentos.core.task.models import Task",
        ...     confidence=1.0
        ... )
    """
    source_type: str
    source_ref: str
    span: Optional[str] = None
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "source_type": self.source_type,
            "source_ref": self.source_ref,
            "span": self.span,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }

    def to_json(self) -> str:
        """转换为 JSON 字符串"""
        return json.dumps(self.to_dict())


@dataclass
class Edge:
    """
    实体关系边

    连接两个实体的有向边，必须包含证据链。

    Attributes:
        id: 边的唯一标识符
        source: 源节点 ID
        target: 目标节点 ID
        type: 关系类型（见 EdgeType）
        evidence: 证据链列表（至少一条）
        attrs: 扩展属性

    Frozen Contract:
        - 每条边必须有至少一条证据（PROVENANCE_PRINCIPLE）
        - 边的创建不可修改原仓库内容（READONLY_PRINCIPLE）
        - 同一源节点和目标节点的同类型边应合并证据（IDEMPOTENCE_PRINCIPLE）
    """
    id: str
    source: str
    target: str
    type: EdgeType
    evidence: List[Evidence]
    attrs: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """验证证据链必须存在"""
        if not self.evidence:
            raise ValueError(
                f"Edge {self.id} violates PROVENANCE_PRINCIPLE: "
                "Every edge MUST have at least one evidence"
            )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "source": self.source,
            "target": self.target,
            "type": self.type.value,
            "evidence": [e.to_dict() for e in self.evidence],
            "attrs": self.attrs,
        }

    def to_json(self) -> str:
        """转换为 JSON 字符串"""
        return json.dumps(self.to_dict())

    def add_evidence(self, evidence: Evidence) -> None:
        """
        添加新证据到边

        用于合并重复边的证据链。

        Args:
            evidence: 新的证据对象
        """
        self.evidence.append(evidence)

    def merge_with(self, other: "Edge") -> None:
        """
        合并另一条同类型边的证据

        Args:
            other: 另一条边对象（必须有相同的 source, target, type）

        Raises:
            ValueError: 如果边的 source/target/type 不匹配
        """
        if (self.source != other.source or
            self.target != other.target or
            self.type != other.type):
            raise ValueError(
                f"Cannot merge edges: "
                f"({self.source}-[{self.type}]->{self.target}) != "
                f"({other.source}-[{other.type}]->{other.target})"
            )

        for evidence in other.evidence:
            self.add_evidence(evidence)


# 预定义的边类型约束（用于验证）
EDGE_TYPE_CONSTRAINTS = {
    EdgeType.MODIFIES: {
        "source_types": ["commit"],
        "target_types": ["file"],
        "description": "Commit modifies File"
    },
    EdgeType.REFERENCES: {
        "source_types": ["doc"],
        "target_types": ["file", "term", "capability"],
        "description": "Doc references File/Term/Capability"
    },
    EdgeType.MENTIONS: {
        "source_types": ["file", "doc", "commit"],
        "target_types": ["term"],
        "description": "File/Doc/Commit mentions Term"
    },
    EdgeType.DEPENDS_ON: {
        "source_types": ["file"],
        "target_types": ["file"],
        "description": "File depends on File"
    },
    EdgeType.IMPLEMENTS: {
        "source_types": ["file", "symbol"],
        "target_types": ["capability"],
        "description": "File/Symbol implements Capability"
    },
}


def validate_edge_type(
    edge_type: EdgeType,
    source_type: str,
    target_type: str
) -> bool:
    """
    验证边类型是否符合约束

    Args:
        edge_type: 边类型
        source_type: 源节点类型
        target_type: 目标节点类型

    Returns:
        bool: True if valid, False otherwise

    Raises:
        ValueError: 如果边类型不符合约束
    """
    constraints = EDGE_TYPE_CONSTRAINTS.get(edge_type)
    if not constraints:
        raise ValueError(f"Unknown edge type: {edge_type}")

    if source_type not in constraints["source_types"]:
        raise ValueError(
            f"Invalid source type '{source_type}' for edge type {edge_type}. "
            f"Expected one of: {constraints['source_types']}"
        )

    if target_type not in constraints["target_types"]:
        raise ValueError(
            f"Invalid target type '{target_type}' for edge type {edge_type}. "
            f"Expected one of: {constraints['target_types']}"
        )

    return True
