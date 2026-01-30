"""
BrainOS Term Extractor

提取领域术语（Terms）和 MENTIONS 关系。

提取内容：
1. Term 实体（领域术语、技术名词）
2. MENTIONS 关系（File/Doc/Commit → Term）

术语识别策略（v0.1）：
1. 预定义术语表（可配置）
2. 大写模式识别（如 BrainOS, AgentOS, TaskManager）
3. 文档中的粗体/代码块标记
4. ADR 中的 "Decision" 部分的关键词

证据来源：
- source_type: "term_pattern" / "term_definition" / "term_dict"
- source_ref: "file_path:line:col"
- span: 包含术语的句子或段落

术语分类：
- technical: 技术术语（API, REST, SQLite）
- domain: 领域术语（Task, Executor, Pipeline）
- project: 项目特定（BrainOS, AgentOS, Capability）

TODO v0.2:
- 基于 NER（命名实体识别）的自动术语提取
- 术语聚类和别名识别（task vs Task vs TaskModel）
- 术语定义提取（从文档中的定义列表）
- 术语关系（synonym, hypernym, hyponym）
"""

from pathlib import Path
from typing import Optional, Dict, Any, Set

from .base import BaseExtractor, ExtractionResult
from agentos.core.brain.models import Term, Edge, EdgeType, Evidence


class TermExtractor(BaseExtractor):
    """
    领域术语抽取器

    从文件、文档、提交消息中提取术语和 MENTIONS 关系。

    Config:
        term_dict: 预定义术语字典（默认包含 AgentOS 核心术语）
        min_frequency: 最小出现频率（默认 3）
        case_sensitive: 是否区分大小写（默认 False）
        extract_from: 提取源列表（默认 ["code", "doc", "commit"]）

    Example:
        >>> extractor = TermExtractor(config={"min_frequency": 5})
        >>> result = extractor.extract(Path("/path/to/repo"))
        >>> print(f"Extracted {len(result.entities)} terms")
    """

    # AgentOS 预定义术语表（v0.1）
    DEFAULT_TERMS = {
        # 核心概念
        "AgentOS", "BrainOS", "Task", "Executor", "Pipeline",
        "Capability", "Extension", "Provider", "Session",
        # 技术术语
        "API", "WebUI", "CLI", "REST", "SQLite", "WebSocket",
        "State Machine", "Retry Strategy", "Execution Plan",
        # 领域术语
        "Intent", "Context", "Knowledge", "Memory", "Audit",
        "Governance", "Boundary", "Planning Guard", "Evidence",
        # 架构术语
        "ADR", "Frozen Contract", "Provenance", "Idempotence",
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(
            name="TermExtractor",
            version="0.1.0",
            config=config
        )
        # 合并配置中的术语字典
        self.term_dict: Set[str] = set(self.DEFAULT_TERMS)
        if self.config.get("term_dict"):
            self.term_dict.update(self.config["term_dict"])

    def extract(
        self,
        repo_path: Path,
        incremental: bool = False,
        **kwargs
    ) -> ExtractionResult:
        """
        提取术语和 MENTIONS 关系

        Args:
            repo_path: 仓库根路径
            incremental: 是否增量抽取
            **kwargs:
                entities: 已提取的其他实体（用于创建 MENTIONS 边）

        Returns:
            ExtractionResult with Term entities and MENTIONS edges

        Implementation Strategy (v0.1):
            1. 遍历所有 File 和 Doc 实体
            2. 对每个实体的内容：
               - 匹配 term_dict 中的术语
               - 记录术语出现位置
               - 如果出现频率 >= min_frequency，创建 Term 实体
               - 为每次出现创建 MENTIONS 边 (File/Doc → Term)
               - 生成证据链（source_ref=位置, span=上下文）
            3. 返回 ExtractionResult

        TODO v0.2:
            - 实现真实的文本扫描（读取文件内容）
            - 使用 NER 模型自动识别术语
            - 处理术语变体（case, plural, abbreviation）
            - 提取术语共现关系（term co-occurrence）
        """
        # v0.1: 仅定义接口，不实现
        return ExtractionResult(
            entities=[],
            edges=[],
            stats={
                "terms_extracted": 0,
                "mentions_created": 0,
                "sources_scanned": 0,
            },
            metadata=self.get_metadata()
        )
