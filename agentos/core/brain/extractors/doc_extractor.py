"""
BrainOS Doc Extractor

从文档（Markdown/RST）提取信息，构建 Doc 实体和 REFERENCES/MENTIONS 关系。

提取内容：
1. Doc 实体（路径、类型、标题）
2. REFERENCES 关系（Doc → File/Capability）
3. MENTIONS 关系（Doc → Term）

识别模式：
- 文件引用：[link](path/to/file.py)、`agentos/core/task/manager.py`
- 术语引用：**术语**、`术语`、标题中的关键词
- 能力引用：明确的 feature/capability 标记

证据来源：
- source_type: "doc_link" / "doc_mention" / "doc_heading"
- source_ref: "doc_path:line"
- span: 包含引用的文本片段

文档类型识别：
- ADR: docs/adr/*.md, docs/architecture/ADR*.md
- README: **/README.md
- Guide: docs/**/*.md (非 ADR)
- Spec: docs/**/*spec*.md
"""

import re
import os
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple, Set
import glob
import hashlib

from .base import BaseExtractor, ExtractionResult
from agentos.core.brain.models import (
    Entity, EntityType, Doc, Edge, EdgeType, Evidence, Term, Capability, File
)


class DocExtractor(BaseExtractor):
    """
    文档抽取器

    从 Markdown 文档提取 Doc 实体和 REFERENCES/MENTIONS 关系。

    Config:
        doc_patterns: 文档路径模式（默认 ["docs/**/*.md", "README.md"]）
        exclude_patterns: 排除的路径模式
        min_term_length: 最小术语长度（默认 3）

    Example:
        >>> extractor = DocExtractor(config={"doc_patterns": ["docs/**/*.md"]})
        >>> result = extractor.extract(Path("/path/to/repo"))
        >>> print(f"Extracted {len(result.entities)} docs")
    """

    # 默认文档扫描模式
    DEFAULT_DOC_PATTERNS = [
        "docs/**/*.md",
        "docs/adr/**/*.md",
        "README.md",
        "CONTRIBUTING.md",
        "SECURITY.md",
        "GOVERNANCE.md"
    ]

    # 排除模式
    EXCLUDE_PATTERNS = [
        "**/node_modules/**",
        "**/.git/**",
        "**/build/**",
        "**/dist/**",
        "**/__pycache__/**",
        "**/venv/**",
        "**/.venv/**"
    ]

    # 文件引用正则模式
    FILE_REFERENCE_PATTERNS = [
        # Markdown 链接中的文件路径
        r'\[.*?\]\(([a-zA-Z0-9_/\-\.]+\.(py|js|ts|tsx|json|yaml|yml))\)',
        # 代码块中的文件路径
        r'`([a-zA-Z0-9_/\-\.]+\.(py|js|ts|tsx|json|yaml|yml))`',
        # 直接路径（agentos 开头）
        r'\b(agentos/[a-zA-Z0-9_/\-\.]+\.py)\b',
        # 明确标记的路径
        r'(?:file:|path:)\s*([a-zA-Z0-9_/\-\.]+)',
    ]

    # Capability 关键词
    CAPABILITY_KEYWORDS = [
        "extension system",
        "task manager",
        "planning guard",
        "boundary enforcement",
        "governance",
        "capability runner",
        "execution gate",
        "replay mechanism",
        "retry strategy",
        "audit system",
        "brain os",
        "brainos",
        "knowledge graph"
    ]

    # 停用词（排除）
    STOP_WORDS = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "should",
        "could", "can", "may", "might", "must", "shall", "this", "that",
        "these", "those", "i", "you", "he", "she", "it", "we", "they",
        "and", "or", "but", "not", "for", "with", "from", "to", "of", "in",
        "on", "at", "by", "as"
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(
            name="DocExtractor",
            version="0.1.0",
            config=config
        )
        self.doc_patterns = self.config.get("doc_patterns", self.DEFAULT_DOC_PATTERNS)
        self.exclude_patterns = self.config.get("exclude_patterns", self.EXCLUDE_PATTERNS)
        self.min_term_length = self.config.get("min_term_length", 3)

    def extract(
        self,
        repo_path: Path,
        incremental: bool = False,
        **kwargs
    ) -> ExtractionResult:
        """
        提取文档信息

        Args:
            repo_path: 仓库根路径
            incremental: 是否增量抽取（当前版本忽略）
            **kwargs: 其他参数

        Returns:
            ExtractionResult with Doc entities, REFERENCES edges, MENTIONS edges
        """
        repo_path = Path(repo_path).resolve()

        if not repo_path.exists():
            return ExtractionResult(
                entities=[],
                edges=[],
                stats={"docs_processed": 0, "references_extracted": 0, "mentions_extracted": 0},
                errors=[f"Repository path does not exist: {repo_path}"],
                metadata=self.get_metadata()
            )

        entities = []
        edges = []
        errors = []

        # 扫描文档文件
        doc_files = self._scan_docs(repo_path)

        # 处理每个文档
        for doc_path in doc_files:
            try:
                doc_result = self._process_document(repo_path, doc_path)
                entities.extend(doc_result['entities'])
                edges.extend(doc_result['edges'])
            except Exception as e:
                errors.append(f"Error processing {doc_path}: {str(e)}")

        # 统计
        references_count = sum(1 for edge in edges if edge.type == EdgeType.REFERENCES)
        mentions_count = sum(1 for edge in edges if edge.type == EdgeType.MENTIONS)

        stats = {
            "docs_processed": len(doc_files),
            "references_extracted": references_count,
            "mentions_extracted": mentions_count,
            "total_entities": len(entities),
            "total_edges": len(edges)
        }

        return ExtractionResult(
            entities=entities,
            edges=edges,
            stats=stats,
            errors=errors,
            metadata=self.get_metadata()
        )

    def _scan_docs(self, repo_path: Path) -> List[Path]:
        """扫描文档文件"""
        doc_files = []

        for pattern in self.doc_patterns:
            full_pattern = str(repo_path / pattern)
            matches = glob.glob(full_pattern, recursive=True)
            doc_files.extend([Path(m) for m in matches])

        # 去重
        doc_files = list(set(doc_files))

        # 排除不需要的文件
        filtered_docs = []
        for doc_file in doc_files:
            relative_path = doc_file.relative_to(repo_path)

            # 检查是否匹配排除模式
            excluded = False
            for exclude_pattern in self.exclude_patterns:
                if relative_path.match(exclude_pattern.replace("**", "*")):
                    excluded = True
                    break

            if not excluded and doc_file.exists() and doc_file.is_file():
                filtered_docs.append(doc_file)

        return sorted(filtered_docs)

    def _process_document(self, repo_path: Path, doc_path: Path) -> Dict[str, List]:
        """处理单个文档"""
        relative_path = doc_path.relative_to(repo_path)
        relative_path_str = str(relative_path)

        # 读取文档内容
        content = self._read_file(doc_path)
        if content is None:
            return {'entities': [], 'edges': []}

        # 识别文档类型
        doc_type = self._identify_doc_type(relative_path)

        # 提取标题
        title = self._extract_title(content) or doc_path.stem

        # 创建 Doc 实体
        doc_key = f"doc:{relative_path_str}"
        doc_id = self._generate_id(doc_key)

        doc_entity = Doc(
            id=doc_id,
            key=doc_key,
            name=title,
            doc_type=doc_type,
            format="markdown",
            path=relative_path_str,
            size=len(content),
            modified_at=int(doc_path.stat().st_mtime)
        )

        entities = [doc_entity]
        edges = []

        # 提取文件引用（REFERENCES: Doc → File）
        file_refs = self._extract_file_references(content, relative_path_str)
        for file_path, line_num, context in file_refs:
            file_key = f"file:{file_path}"
            file_id = self._generate_id(file_key)

            # 创建 File 实体（如果不存在）
            file_entity = File(
                id=file_id,
                key=file_key,
                name=Path(file_path).name,
                path=file_path
            )
            entities.append(file_entity)

            # 创建 REFERENCES 边
            edge_key = f"REFERENCES|{doc_key}|{file_key}"
            edge_id = self._generate_id(edge_key)

            evidence = Evidence(
                source_type="doc_link",
                source_ref=f"{relative_path_str}:{line_num}",
                span=context,
                confidence=0.9
            )

            edge = Edge(
                id=edge_id,
                source=doc_key,
                target=file_key,
                type=EdgeType.REFERENCES,
                evidence=[evidence],
                attrs={"reference_type": "file"}
            )
            edges.append(edge)

        # 提取 Capability 引用（REFERENCES: Doc → Capability）
        capability_refs = self._extract_capability_references(content, relative_path_str)
        for capability_name, line_num, context in capability_refs:
            cap_key = f"capability:{capability_name}"
            cap_id = self._generate_id(cap_key)

            # 创建 Capability 实体
            cap_entity = Capability(
                id=cap_id,
                key=cap_key,
                name=capability_name,
                capability_type="feature"
            )
            entities.append(cap_entity)

            # 创建 REFERENCES 边
            edge_key = f"REFERENCES|{doc_key}|{cap_key}"
            edge_id = self._generate_id(edge_key)

            evidence = Evidence(
                source_type="doc_mention",
                source_ref=f"{relative_path_str}:{line_num}",
                span=context,
                confidence=0.8
            )

            edge = Edge(
                id=edge_id,
                source=doc_key,
                target=cap_key,
                type=EdgeType.REFERENCES,
                evidence=[evidence],
                attrs={"reference_type": "capability"}
            )
            edges.append(edge)

        # 提取术语（MENTIONS: Doc → Term）
        terms = self._extract_mentions(content, relative_path_str)
        for term, line_num, context in terms:
            term_key = f"term:{term}"
            term_id = self._generate_id(term_key)

            # 创建 Term 实体
            term_entity = Term(
                id=term_id,
                key=term_key,
                name=term,
                term=term
            )
            entities.append(term_entity)

            # 创建 MENTIONS 边
            edge_key = f"MENTIONS|{doc_key}|{term_key}"
            edge_id = self._generate_id(edge_key)

            evidence = Evidence(
                source_type="doc_heading" if line_num < 10 else "doc_text",
                source_ref=f"{relative_path_str}:{line_num}",
                span=context,
                confidence=0.7
            )

            edge = Edge(
                id=edge_id,
                source=doc_key,
                target=term_key,
                type=EdgeType.MENTIONS,
                evidence=[evidence],
                attrs={"frequency": 1}
            )
            edges.append(edge)

        return {'entities': entities, 'edges': edges}

    def _read_file(self, file_path: Path) -> Optional[str]:
        """读取文件内容（支持多种编码）"""
        encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']

        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    return f.read()
            except (UnicodeDecodeError, OSError):
                continue

        return None

    def _identify_doc_type(self, relative_path: Path) -> str:
        """识别文档类型"""
        path_str = str(relative_path).lower()

        if 'adr' in path_str or 'architecture/adr' in path_str:
            return "adr"
        elif 'readme.md' in path_str:
            return "readme"
        elif 'guide' in path_str:
            return "guide"
        elif 'spec' in path_str:
            return "spec"
        else:
            return "doc"

    def _extract_title(self, content: str) -> Optional[str]:
        """提取文档标题（第一个 # 标题）"""
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('# '):
                return line[2:].strip()
        return None

    def _extract_file_references(self, content: str, doc_path: str) -> List[Tuple[str, int, str]]:
        """提取文件引用"""
        references = []
        lines = content.split('\n')

        for line_num, line in enumerate(lines, start=1):
            for pattern in self.FILE_REFERENCE_PATTERNS:
                matches = re.finditer(pattern, line)
                for match in matches:
                    file_path = match.group(1)
                    # 规范化路径
                    file_path = file_path.strip().replace('\\', '/')

                    # 提取上下文（最多60个字符）
                    start = max(0, match.start() - 20)
                    end = min(len(line), match.end() + 40)
                    context = line[start:end].strip()

                    references.append((file_path, line_num, context))

        # 去重（同一文件只保留第一次引用）
        seen = set()
        unique_refs = []
        for file_path, line_num, context in references:
            if file_path not in seen:
                seen.add(file_path)
                unique_refs.append((file_path, line_num, context))

        return unique_refs

    def _extract_capability_references(self, content: str, doc_path: str) -> List[Tuple[str, int, str]]:
        """提取 Capability 引用"""
        references = []
        lines = content.split('\n')

        for line_num, line in enumerate(lines, start=1):
            line_lower = line.lower()
            for capability in self.CAPABILITY_KEYWORDS:
                if capability in line_lower:
                    # 提取上下文
                    context = line.strip()[:100]
                    references.append((capability, line_num, context))

        # 去重
        seen = set()
        unique_refs = []
        for cap, line_num, context in references:
            if cap not in seen:
                seen.add(cap)
                unique_refs.append((cap, line_num, context))

        return unique_refs

    def _extract_mentions(self, content: str, doc_path: str) -> List[Tuple[str, int, str]]:
        """提取术语（从标题和强调文本）"""
        mentions = []
        lines = content.split('\n')

        for line_num, line in enumerate(lines, start=1):
            # 从标题提取
            if line.strip().startswith('#'):
                heading_text = re.sub(r'^#+\s*', '', line.strip())
                terms = self._extract_terms_from_text(heading_text)
                for term in terms:
                    mentions.append((term, line_num, heading_text[:100]))

            # 从粗体/斜体提取
            bold_matches = re.finditer(r'\*\*([^*]+)\*\*', line)
            for match in bold_matches:
                text = match.group(1)
                terms = self._extract_terms_from_text(text)
                for term in terms:
                    context = line[max(0, match.start()-20):min(len(line), match.end()+20)].strip()
                    mentions.append((term, line_num, context))

            # 从代码块提取
            code_matches = re.finditer(r'`([^`]+)`', line)
            for match in code_matches:
                text = match.group(1)
                # 只提取非路径的术语
                if '/' not in text and '.' not in text:
                    terms = self._extract_terms_from_text(text)
                    for term in terms:
                        context = line[max(0, match.start()-20):min(len(line), match.end()+20)].strip()
                        mentions.append((term, line_num, context))

        # 去重
        seen = set()
        unique_mentions = []
        for term, line_num, context in mentions:
            if term not in seen:
                seen.add(term)
                unique_mentions.append((term, line_num, context))

        return unique_mentions

    def _extract_terms_from_text(self, text: str) -> List[str]:
        """从文本中提取术语"""
        # 分词（简单按空格和标点分割）
        words = re.findall(r'\b[a-zA-Z][a-zA-Z0-9_]*\b', text)

        terms = []
        for word in words:
            word_lower = word.lower()
            # 过滤停用词和短词
            if (word_lower not in self.STOP_WORDS and
                len(word) >= self.min_term_length):
                terms.append(word_lower)

        return terms

    def _generate_id(self, key: str) -> str:
        """生成确定性 ID（基于 key）"""
        return hashlib.md5(key.encode()).hexdigest()[:16]
