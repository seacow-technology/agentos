"""ProjectKB 数据模型定义

定义项目知识库的核心数据结构，遵循可审计原则。
"""

from __future__ import annotations


from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class Source:
    """文档源 - 对应 kb_sources 表"""

    source_id: str
    repo_id: str
    path: str
    file_hash: str
    mtime: int
    doc_type: Optional[str] = None  # adr/runbook/spec/guide/index
    language: str = "markdown"
    tags: list[str] = field(default_factory=list)


@dataclass
class Chunk:
    """文档片段 - 对应 kb_chunks 表"""

    chunk_id: str
    source_id: str
    heading: Optional[str]
    start_line: int
    end_line: int
    content: str
    content_hash: str
    token_count: Optional[int] = None

    @property
    def line_range(self) -> str:
        """返回行号范围字符串: L45-L68"""
        return f"L{self.start_line}-L{self.end_line}"


@dataclass
class Explanation:
    """检索结果解释 - 审计关键"""

    matched_terms: list[str]
    term_frequencies: dict[str, int]
    document_boost: float = 1.0
    recency_boost: float = 1.0
    path: Optional[str] = None
    heading: Optional[str] = None
    lines: Optional[str] = None

    # [P2] 向量评分 (可选)
    keyword_score: Optional[float] = None
    vector_score: Optional[float] = None
    rerank_delta: Optional[int] = None
    final_rank: Optional[int] = None
    alpha: Optional[float] = None  # 融合权重
    final_score: Optional[float] = None  # 融合后分数

    def to_dict(self) -> dict[str, Any]:
        """转换为字典，用于序列化"""
        result = {
            "matched_terms": self.matched_terms,
            "term_frequencies": self.term_frequencies,
            "document_boost": self.document_boost,
            "recency_boost": self.recency_boost,
        }
        if self.path:
            result["path"] = self.path
        if self.heading:
            result["heading"] = self.heading
        if self.lines:
            result["lines"] = self.lines
        if self.keyword_score is not None:
            result["keyword_score"] = self.keyword_score
        if self.vector_score is not None:
            result["vector_score"] = self.vector_score
        if self.rerank_delta is not None:
            result["rerank_delta"] = self.rerank_delta
        if self.final_rank is not None:
            result["final_rank"] = self.final_rank
        if self.alpha is not None:
            result["alpha"] = self.alpha
        if self.final_score is not None:
            result["final_score"] = self.final_score
        return result


@dataclass
class ChunkResult:
    """检索结果 - 包含片段和解释"""

    chunk_id: str
    content: str
    heading: Optional[str]
    path: str
    lines: str  # L45-L68 格式
    score: float
    explanation: Explanation

    def to_dict(self) -> dict[str, Any]:
        """转换为字典，用于序列化和 evidence_ref"""
        return {
            "chunk_id": self.chunk_id,
            "content": self.content,
            "heading": self.heading,
            "path": self.path,
            "lines": self.lines,
            "score": self.score,
            "explanation": self.explanation.to_dict(),
        }

    def to_evidence_ref(self) -> str:
        """转换为 evidence_ref 格式: kb:<chunk_id>:<path>#<lines>"""
        return f"kb:{self.chunk_id}:{self.path}#{self.lines}"


@dataclass
class RefreshReport:
    """索引刷新报告"""

    total_files: int
    changed_files: int
    deleted_files: int
    total_chunks: int
    new_chunks: int
    deleted_chunks: int
    duration_seconds: float
    errors: list[str] = field(default_factory=list)

    def summary(self) -> str:
        """生成人类可读摘要"""
        lines = [
            f"Indexed {self.total_files} documents, {self.total_chunks} chunks",
            f"Changed: {self.changed_files} files, {self.new_chunks} new chunks",
        ]
        if self.deleted_files > 0:
            lines.append(f"Deleted: {self.deleted_files} files, {self.deleted_chunks} chunks")
        if self.errors:
            lines.append(f"Errors: {len(self.errors)}")
        lines.append(f"Duration: {self.duration_seconds:.2f}s")
        return "\n".join(lines)


@dataclass
class SearchFilters:
    """检索过滤器"""

    scope: Optional[str] = None  # 路径前缀，如 "docs/architecture/"
    doc_type: Optional[str] = None  # adr/runbook/spec/guide
    tags: Optional[list[str]] = None
    mtime_after: Optional[int] = None  # Unix timestamp
    mtime_before: Optional[int] = None


# Document type weights for scoring
DOCUMENT_TYPE_WEIGHTS = {
    "adr": 1.5,  # 架构决策记录优先
    "runbook": 1.3,  # 操作手册次之
    "spec": 1.4,  # 规范文档
    "guide": 1.1,
    "index": 0.3,  # INDEX.md 降权
    "default": 1.0,
}
