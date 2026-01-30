"""
BrainOS Data Models

定义 BrainOS 的实体和关系模型。

实体类型（Entities v0.1）：
- Repo: 仓库节点
- File: 文件节点
- Symbol: 代码符号（类、函数等）
- Doc: 文档节点
- Commit: 提交记录
- Term: 领域术语
- Capability: 能力/特性

关系类型（Edges v0.1）：
- MODIFIES: Commit → File
- REFERENCES: Doc → File/Term/Capability
- MENTIONS: File/Doc/Commit → Term
- DEPENDS_ON: File/Module → File/Module
- IMPLEMENTS: File/Symbol → Capability

所有模型遵循冻结契约：
- 不可修改原仓库内容
- 每个关系必须有证据链（provenance）
- 同一 commit 构建结果一致
"""

from .entities import Entity, EntityType, Repo, File, Symbol, Doc, Commit, Term, Capability
from .relationships import Edge, EdgeType, Evidence

__all__ = [
    "Entity",
    "EntityType",
    "Repo",
    "File",
    "Symbol",
    "Doc",
    "Commit",
    "Term",
    "Capability",
    "Edge",
    "EdgeType",
    "Evidence",
]
