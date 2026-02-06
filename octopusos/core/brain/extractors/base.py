"""
BrainOS Base Extractor

定义所有抽取器的基础接口和契约。

抽取器职责：
1. 从源（repo/file/doc）提取实体和关系
2. 为每条关系生成证据链
3. 保证幂等性（同一输入产生同一输出）
4. 遵循只读原则（不修改源）

抽取器类型：
- Structural: 基于静态结构（文件系统、AST、import）
- Semantic: 基于语义理解（文档引用、术语提取、概念关联）
- Historical: 基于历史数据（Git commits、issue history）

性能要求：
- 增量抽取：仅处理变更部分
- 缓存友好：支持中间结果缓存
- 可中断：支持大仓库分批处理
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from pathlib import Path

from agentos.core.brain.models import Entity, Edge


@dataclass
class ExtractionResult:
    """
    抽取结果

    Attributes:
        entities: 提取的实体列表
        edges: 提取的关系边列表
        stats: 统计信息（entities_count, edges_count, duration_ms）
        errors: 错误列表（非致命错误，记录但不中断）
        metadata: 其他元数据（如版本、时间戳）
    """
    entities: List[Entity] = field(default_factory=list)
    edges: List[Edge] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def merge(self, other: "ExtractionResult") -> None:
        """
        合并另一个抽取结果

        Args:
            other: 另一个 ExtractionResult 对象
        """
        self.entities.extend(other.entities)
        self.edges.extend(other.edges)
        self.errors.extend(other.errors)
        # 合并 stats（累加数值）
        for key, value in other.stats.items():
            if isinstance(value, (int, float)):
                self.stats[key] = self.stats.get(key, 0) + value
            else:
                self.stats[key] = value
        # 合并 metadata（后者覆盖前者）
        self.metadata.update(other.metadata)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "entities": [e.to_dict() for e in self.entities],
            "edges": [e.to_dict() for e in self.edges],
            "stats": self.stats,
            "errors": self.errors,
            "metadata": self.metadata,
        }


class BaseExtractor(ABC):
    """
    抽取器基类

    所有抽取器必须继承此类并实现 extract() 方法。

    Frozen Contracts:
        - READONLY_PRINCIPLE: 不可修改任何源文件
        - PROVENANCE_PRINCIPLE: 每条边必须有证据链
        - IDEMPOTENCE_PRINCIPLE: 同一输入产生同一输出

    Attributes:
        name: 抽取器名称（用于日志和审计）
        version: 抽取器版本（影响幂等性）
        config: 配置参数（可选）
    """

    def __init__(
        self,
        name: str,
        version: str = "0.1.0",
        config: Optional[Dict[str, Any]] = None
    ):
        self.name = name
        self.version = version
        self.config = config or {}

    @abstractmethod
    def extract(
        self,
        repo_path: Path,
        incremental: bool = False,
        **kwargs
    ) -> ExtractionResult:
        """
        执行抽取

        Args:
            repo_path: 仓库根路径
            incremental: 是否增量抽取（仅处理变更）
            **kwargs: 其他参数（各抽取器自定义）

        Returns:
            ExtractionResult: 抽取结果

        Raises:
            ValueError: 参数无效
            RuntimeError: 抽取失败（如仓库不存在、权限问题）

        Contract Validation:
            - 必须遵循 READONLY_PRINCIPLE（不修改源）
            - 所有边必须有 evidence（PROVENANCE_PRINCIPLE）
            - 同一 repo_path + kwargs 必须产生同一结果（IDEMPOTENCE_PRINCIPLE）
        """
        pass

    def validate_readonly(self) -> bool:
        """
        验证只读原则

        子类可以覆盖此方法来添加自定义验证逻辑。

        Returns:
            bool: True if compliant

        Raises:
            RuntimeError: 如果检测到违反只读原则
        """
        # 默认通过（子类负责实现具体检查）
        return True

    def validate_provenance(self, result: ExtractionResult) -> bool:
        """
        验证证据链原则

        检查所有边是否都有证据。

        Args:
            result: 抽取结果

        Returns:
            bool: True if all edges have evidence

        Raises:
            ValueError: 如果发现没有证据的边
        """
        for edge in result.edges:
            if not edge.evidence:
                raise ValueError(
                    f"Edge {edge.id} ({edge.source} -> {edge.target}) "
                    f"violates PROVENANCE_PRINCIPLE: no evidence provided"
                )
        return True

    def get_metadata(self) -> Dict[str, Any]:
        """
        获取抽取器元数据

        用于审计和版本追踪。

        Returns:
            Dict with name, version, config
        """
        return {
            "extractor_name": self.name,
            "extractor_version": self.version,
            "config": self.config,
        }
