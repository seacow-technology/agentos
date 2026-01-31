"""ProjectKB Service - 项目知识库统一门面

提供统一接口:
- search(): 检索文档
- get(): 获取片段
- refresh(): 刷新索引
- explain(): 解释结果

Gate 要求:
- #6: Fail-safe 行为（优雅降级）
"""

import time
from pathlib import Path
from typing import Optional

from agentos.core.project_kb.chunker import MarkdownChunker
from agentos.core.project_kb.config import ProjectKBConfig, load_config
from agentos.core.project_kb.explainer import ResultExplainer
from agentos.core.project_kb.indexer import ProjectKBIndexer, FTS5NotAvailableError
from agentos.core.project_kb.scanner import DocumentScanner
from agentos.core.project_kb.searcher import ProjectKBSearcher
from agentos.core.project_kb.types import (
    Chunk,
    ChunkResult,
    RefreshReport,
    SearchFilters,
)
from agentos.store import get_db_path


class ProjectKBService:
    """项目知识库服务 - 可审计的文档检索"""

    def __init__(
        self,
        root_dir: Optional[Path] = None,
        db_path: Optional[Path] = None,
        config: Optional[ProjectKBConfig] = None,
        config_path: Optional[Path] = None,
        fail_safe: bool = True,
    ):
        """初始化 ProjectKB 服务

        Args:
            root_dir: 项目根目录 (默认当前目录)
            db_path: 数据库路径 (默认 component_db_path("agentos"))
            config: 配置对象 (优先使用)
            config_path: 配置文件路径 (如果 config 为 None)
            fail_safe: 是否启用 fail-safe 模式（Gate #6）
        """
        self.root_dir = Path(root_dir or Path.cwd()).resolve()
        self.db_path = Path(db_path or get_db_path())
        self.fail_safe = fail_safe
        self._initialized = False
        self._init_error = None

        # 加载配置
        if config is None:
            config = load_config(config_path)
        self.config = config

        # 初始化组件
        self.scanner = DocumentScanner(
            root_dir=self.root_dir,
            scan_paths=config.scan_paths,
            exclude_patterns=config.exclude_patterns,
        )
        self.chunker = MarkdownChunker(
            min_tokens=config.chunk_size_min,
            max_tokens=config.chunk_size_max,
        )
        self.indexer = ProjectKBIndexer(db_path=self.db_path)
        self.searcher = ProjectKBSearcher(db_path=self.db_path)
        self.explainer = ResultExplainer()

        # Vector rerank 组件 (P2, 可选)
        self.embedding_manager = None
        self.reranker = None
        if config.vector_rerank.enabled:
            try:
                from agentos.core.project_kb.embedding import (
                    EmbeddingManager,
                    create_provider,
                )
                from agentos.core.project_kb.reranker import VectorReranker

                provider = create_provider(config.vector_rerank)
                self.embedding_manager = EmbeddingManager(self.db_path, provider)
                self.reranker = VectorReranker(self.embedding_manager, provider)
            except ImportError as e:
                if not fail_safe:
                    raise
                print(f"⚠️  Vector rerank unavailable: {e}")
                print(f"   Install with: pip install agentos[vector]")

        # Gate #6: Fail-safe 初始化
        try:
            self.indexer.ensure_schema()
            self._initialized = True
        except FTS5NotAvailableError as e:
            self._init_error = str(e)
            if not fail_safe:
                raise
        except Exception as e:
            self._init_error = f"Initialization failed: {e}"
            if not fail_safe:
                raise

    def _check_initialized(self):
        """检查是否已初始化（Gate #6）"""
        if not self._initialized:
            error_msg = self._init_error or "ProjectKB not initialized"
            if self.fail_safe:
                print(f"⚠️  ProjectKB Warning: {error_msg}")
                print(f"   Run 'agentos kb refresh' to initialize the index.")
                return False
            else:
                raise RuntimeError(error_msg)
        return True

    def search(
        self,
        query: str,
        scope: Optional[str] = None,
        filters: Optional[dict] = None,
        top_k: int = 10,
        explain: bool = True,
        use_rerank: Optional[bool] = None,
    ) -> list[ChunkResult]:
        """检索文档

        Args:
            query: 查询字符串
            scope: 路径前缀过滤 (如 "docs/architecture/")
            filters: 过滤器字典 (doc_type, tags, mtime_after, mtime_before)
            top_k: 返回结果数
            explain: 是否生成解释 (审计)
            use_rerank: 是否使用向量 rerank (None=使用配置默认值)

        Returns:
            ChunkResult 列表

        Example:
            >>> kb = ProjectKBService()
            >>> results = kb.search("JWT authentication", top_k=5)
            >>> for r in results:
            ...     print(r.path, r.score)
        """
        # Gate #6: Fail-safe 检查
        if not self._check_initialized():
            return []
        
        # 构建过滤器
        search_filters = SearchFilters(scope=scope)
        if filters:
            if "doc_type" in filters:
                search_filters.doc_type = filters["doc_type"]
            if "tags" in filters:
                search_filters.tags = filters["tags"]
            if "mtime_after" in filters:
                search_filters.mtime_after = filters["mtime_after"]
            if "mtime_before" in filters:
                search_filters.mtime_before = filters["mtime_before"]

        try:
            # 判断是否使用 rerank
            should_rerank = use_rerank if use_rerank is not None else self.config.vector_rerank.enabled
            
            # 如果启用 rerank，先召回更多候选
            candidate_k = self.config.vector_rerank.candidate_k if should_rerank and self.reranker else top_k
            
            # 执行关键词检索
            results = self.searcher.search(
                query=query,
                filters=search_filters,
                top_k=candidate_k,
            )
            
            # 向量 rerank (如果启用)
            if should_rerank and self.reranker:
                results = self.reranker.rerank(query, results, self.config.vector_rerank)
            
            return results[:top_k]
        except Exception as e:
            if self.fail_safe:
                print(f"⚠️  ProjectKB Search Warning: {e}")
                return []
            else:
                raise

    def get(self, chunk_id: str) -> Optional[dict]:
        """按 ID 获取片段 (含完整上下文)

        Args:
            chunk_id: Chunk ID

        Returns:
            Chunk 字典，不存在返回 None

        Example:
            >>> kb = ProjectKBService()
            >>> chunk = kb.get("chunk_abc123")
            >>> print(chunk["content"])
        """
        return self.searcher.get_chunk_by_id(chunk_id)

    def refresh(self, changed_only: bool = True) -> RefreshReport:
        """刷新索引 (扫描文档并更新)

        Args:
            changed_only: 是否只处理变更文件 (增量刷新)

        Returns:
            RefreshReport 刷新报告

        Example:
            >>> kb = ProjectKBService()
            >>> report = kb.refresh(changed_only=True)
            >>> print(report.summary())
        """
        start_time = time.time()

        # 获取已存在的 sources
        existing_sources = {}
        if changed_only:
            existing_sources = self.indexer.get_existing_sources(self.scanner.repo_id)

        # 扫描文档
        total_files = 0
        changed_files = 0
        new_chunks = 0
        errors = []

        for file_path, source, is_changed in self.scanner.scan(existing_sources):
            total_files += 1

            if not is_changed and changed_only:
                continue

            changed_files += 1

            try:
                # 更新 source
                self.indexer.upsert_source(source)

                # 删除旧 chunks
                if is_changed:
                    self.indexer.delete_chunks_by_source(source.source_id)

                # 切片并索引
                for chunk in self.chunker.chunk_file(source.source_id, file_path):
                    self.indexer.insert_chunk(chunk)
                    new_chunks += 1

            except Exception as e:
                errors.append(f"{source.path}: {str(e)}")

        # 查找已删除文档
        deleted_sources = []
        deleted_chunks = 0
        if changed_only:
            deleted_sources = self.scanner.find_deleted(existing_sources)
            for source_id in deleted_sources:
                # 统计 chunks 数量 (删除前)
                chunk_count = self.indexer.count_chunks_by_source(source_id)
                deleted_chunks += chunk_count
                self.indexer.delete_source(source_id)

        # 更新元数据
        self.indexer.update_meta("last_refresh", str(int(time.time())))

        # 计算总 chunks
        total_chunks = self.indexer.get_chunk_count(self.scanner.repo_id)

        duration = time.time() - start_time

        # P2: 增量更新 embeddings (如果启用)
        if self.embedding_manager and self.config.vector_rerank.enabled:
            print("\nRefreshing embeddings...")
            chunks_to_embed = self._get_chunks_for_embedding(changed_only)
            if chunks_to_embed:
                embed_stats = self.embedding_manager.refresh_embeddings(chunks_to_embed)
                print(
                    f"  Embeddings: {embed_stats['processed']} processed, "
                    f"{embed_stats['skipped']} skipped"
                )

        return RefreshReport(
            total_files=total_files,
            changed_files=changed_files,
            deleted_files=len(deleted_sources),
            total_chunks=total_chunks,
            new_chunks=new_chunks,
            deleted_chunks=deleted_chunks,
            duration_seconds=duration,
            errors=errors,
        )

    def explain(self, result: ChunkResult) -> str:
        """生成人类可读的结果解释 (审计)

        Args:
            result: ChunkResult 对象

        Returns:
            可读解释文本

        Example:
            >>> kb = ProjectKBService()
            >>> results = kb.search("JWT")
            >>> print(kb.explain(results[0]))
        """
        return self.explainer.explain_result(result)

    def explain_all(self, results: list[ChunkResult], query: str) -> str:
        """生成所有结果的汇总解释

        Args:
            results: ChunkResult 列表
            query: 原始查询

        Returns:
            汇总解释文本
        """
        return self.explainer.explain_results(results, query)

    def stats(self) -> dict:
        """获取 ProjectKB 统计信息

        Returns:
            统计信息字典

        Example:
            >>> kb = ProjectKBService()
            >>> stats = kb.stats()
            >>> print(stats["total_chunks"])
        """
        stats_dict = {
            "total_chunks": self.indexer.get_chunk_count(),
            "schema_version": self.indexer.get_meta("schema_version"),
            "last_refresh": self.indexer.get_meta("last_refresh"),
        }
        
        # P2: 添加 embedding 统计 (如果启用)
        if self.embedding_manager:
            embed_stats = self.embedding_manager.get_stats()
            stats_dict["embeddings"] = {
                "total": embed_stats["total"],
                "by_model": embed_stats["by_model"],
                "latest_built_at": embed_stats["latest_built_at"],
            }
            
            # 计算覆盖率
            total_chunks = stats_dict["total_chunks"]
            if total_chunks > 0:
                stats_dict["embeddings"]["coverage"] = embed_stats["total"] / total_chunks
        
        return stats_dict

    def _get_chunks_for_embedding(self, changed_only: bool) -> list[Chunk]:
        """获取需要生成 embedding 的 chunks

        Args:
            changed_only: 是否只获取变更的 chunks

        Returns:
            Chunk 列表
        """
        import sqlite3

        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if changed_only:
            # 只获取没有 embedding 或 content_hash 不匹配的 chunks
            query = """
                SELECT c.chunk_id, c.source_id, c.heading, c.start_line, c.end_line,
                       c.content, c.content_hash, c.token_count
                FROM kb_chunks c
                LEFT JOIN kb_embeddings e ON c.chunk_id = e.chunk_id
                WHERE e.chunk_id IS NULL OR e.content_hash != c.content_hash
            """
        else:
            # 获取所有 chunks
            query = """
                SELECT chunk_id, source_id, heading, start_line, end_line,
                       content, content_hash, token_count
                FROM kb_chunks
            """

        cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()

        chunks = []
        for row in rows:
            chunk = Chunk(
                chunk_id=row["chunk_id"],
                source_id=row["source_id"],
                heading=row["heading"],
                start_line=row["start_line"],
                end_line=row["end_line"],
                content=row["content"],
                content_hash=row["content_hash"],
                token_count=row["token_count"],
            )
            chunks.append(chunk)

        return chunks

