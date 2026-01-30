"""
BrainOS Extractors

抽取器负责从各种源（Git/代码/文档）提取实体和关系。

所有抽取器必须：
1. 继承 BaseExtractor
2. 实现 extract() 方法
3. 遵循只读原则（READONLY_PRINCIPLE）
4. 为每条关系提供证据链（PROVENANCE_PRINCIPLE）
5. 保证幂等性（IDEMPOTENCE_PRINCIPLE）

v0.1 抽取器：
- GitExtractor: 从 Git 历史提取 Commit → File 关系
- DocExtractor: 从文档提取 Doc → File/Term 引用
- CodeExtractor: 从代码提取 File → File 依赖
- TermExtractor: 提取领域术语和 MENTIONS 关系

TODO v0.2+:
- ASTExtractor: 深度 AST 分析
- APIExtractor: API 定义和使用
- TestExtractor: 测试覆盖和关联
"""

from .base import BaseExtractor, ExtractionResult
from .git_extractor import GitExtractor
from .doc_extractor import DocExtractor
from .code_extractor import CodeExtractor
from .term_extractor import TermExtractor

__all__ = [
    "BaseExtractor",
    "ExtractionResult",
    "GitExtractor",
    "DocExtractor",
    "CodeExtractor",
    "TermExtractor",
]
