"""文档扫描器 - 扫描项目文档并检测变更

负责:
- 扫描配置路径下的 markdown 文档
- 计算文件哈希检测变更
- 推断文档类型 (adr/runbook/spec/guide)
- 支持增量扫描 (只处理变更文件)
"""

import hashlib
import re
from pathlib import Path
from typing import Iterator, Optional

from agentos.core.project_kb.types import Source


class DocumentScanner:
    """文档扫描器 - 发现和追踪项目文档"""

    # 默认扫描路径
    DEFAULT_SCAN_PATHS = [
        "docs/**/*.md",
        "README.md",
        "adr/**/*.md",
    ]

    # 默认排除模式
    DEFAULT_EXCLUDE_PATTERNS = [
        "node_modules/**",
        ".history/**",
        ".git/**",
        "venv/**",
        "__pycache__/**",
        "dist/**",
        "bin/**",
        "build/**",
        "*.png",
        "*.jpg",
        "*.jpeg",
        "*.gif",
        "*.pdf",
        "*.zip",
        "*.tar.gz",
    ]

    # 文档类型推断规则
    DOC_TYPE_PATTERNS = {
        "adr": [
            r"adr/",
            r"decisions?/",
            r"architecture.*decision",
        ],
        "runbook": [
            r"runbooks?/",
            r"operations?/",
            r"playbooks?/",
        ],
        "spec": [
            r"specs?/",
            r"specifications?/",
            r"requirements?/",
        ],
        "guide": [
            r"guides?/",
            r"tutorials?/",
            r"howto/",
        ],
        "index": [
            r"/?index\.md$",
            r"/?readme\.md$",
        ],
    }

    def __init__(
        self,
        root_dir: Path,
        scan_paths: Optional[list[str]] = None,
        exclude_patterns: Optional[list[str]] = None,
        repo_id: Optional[str] = None,
    ):
        """初始化扫描器

        Args:
            root_dir: 项目根目录
            scan_paths: 扫描路径模式列表 (支持 glob)
            exclude_patterns: 排除路径模式列表
            repo_id: 项目标识 (默认使用 root_dir 哈希)
        """
        self.root_dir = Path(root_dir).resolve()
        self.scan_paths = scan_paths or self.DEFAULT_SCAN_PATHS
        self.exclude_patterns = exclude_patterns or self.DEFAULT_EXCLUDE_PATTERNS
        self.repo_id = repo_id or self._compute_repo_id()

    def _compute_repo_id(self) -> str:
        """计算项目 ID (基于路径哈希)"""
        return hashlib.sha256(str(self.root_dir).encode()).hexdigest()[:12]

    def scan(self, existing_sources: Optional[dict[str, Source]] = None) -> Iterator[tuple[Path, Source, bool]]:
        """扫描文档并生成 Source 对象

        Args:
            existing_sources: 已存在的 source_id -> Source 映射 (用于增量检测)

        Yields:
            (file_path, source, is_changed) 元组
            - file_path: 文件绝对路径
            - source: Source 对象
            - is_changed: 是否变更 (新增或内容变化)
        """
        existing_sources = existing_sources or {}
        seen_paths = set()

        for pattern in self.scan_paths:
            for file_path in self._glob_files(pattern):
                if self._should_exclude(file_path):
                    continue

                rel_path = str(file_path.relative_to(self.root_dir))
                seen_paths.add(rel_path)

                # 计算文件哈希
                file_hash = self._compute_file_hash(file_path)
                mtime = int(file_path.stat().st_mtime)

                # 推断文档类型
                doc_type = self._infer_doc_type(rel_path)

                # 生成 source_id
                source_id = self._generate_source_id(rel_path)

                # 检查是否变更
                is_changed = True
                if source_id in existing_sources:
                    existing = existing_sources[source_id]
                    is_changed = existing.file_hash != file_hash

                source = Source(
                    source_id=source_id,
                    repo_id=self.repo_id,
                    path=rel_path,
                    file_hash=file_hash,
                    mtime=mtime,
                    doc_type=doc_type,
                )

                yield file_path, source, is_changed

    def find_deleted(self, existing_sources: dict[str, Source]) -> list[str]:
        """查找已删除的文档

        Args:
            existing_sources: 已存在的 source_id -> Source 映射

        Returns:
            已删除文档的 source_id 列表
        """
        current_paths = set()
        for pattern in self.scan_paths:
            for file_path in self._glob_files(pattern):
                if not self._should_exclude(file_path):
                    rel_path = str(file_path.relative_to(self.root_dir))
                    current_paths.add(rel_path)

        deleted = []
        for source_id, source in existing_sources.items():
            if source.path not in current_paths:
                deleted.append(source_id)

        return deleted

    def _glob_files(self, pattern: str) -> Iterator[Path]:
        """Glob 匹配文件"""
        try:
            yield from self.root_dir.glob(pattern)
        except Exception:
            # 忽略无效模式
            pass

    def _should_exclude(self, file_path: Path) -> bool:
        """检查是否应排除该文件"""
        rel_path = str(file_path.relative_to(self.root_dir))
        for pattern in self.exclude_patterns:
            # 简单匹配 (支持 ** 和 *)
            if self._match_pattern(rel_path, pattern):
                return True
        return False

    def _match_pattern(self, path: str, pattern: str) -> bool:
        """简单的路径模式匹配"""
        # 将 glob 模式转换为正则
        regex = pattern.replace("**", ".*").replace("*", "[^/]*")
        return re.search(regex, path) is not None

    def _compute_file_hash(self, file_path: Path) -> str:
        """计算文件 SHA256 哈希"""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _infer_doc_type(self, path: str) -> str:
        """推断文档类型"""
        path_lower = path.lower()
        for doc_type, patterns in self.DOC_TYPE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, path_lower):
                    return doc_type
        return "default"

    def _generate_source_id(self, path: str) -> str:
        """生成 source_id (基于 repo_id + path)"""
        combined = f"{self.repo_id}:{path}"
        return f"src_{hashlib.sha256(combined.encode()).hexdigest()[:16]}"
