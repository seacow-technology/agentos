"""ProjectKB - 项目知识库检索系统

为 AgentOS 提供可审计的项目文档检索能力。

核心原则:
- 可审计: 每条检索结果都能解释"为什么命中"
- 关键词优先: BM25/FTS5 确保可解释的排序
- 向量可选: 仅用于 rerank，不作为唯一召回方式
- 证据链: 所有结果可追溯到 file:line:hash
"""

from agentos.core.project_kb.service import ProjectKBService
from agentos.core.project_kb.types import (
    Chunk,
    ChunkResult,
    RefreshReport,
    Source,
)

__all__ = [
    "ProjectKBService",
    "Chunk",
    "ChunkResult",
    "RefreshReport",
    "Source",
]
