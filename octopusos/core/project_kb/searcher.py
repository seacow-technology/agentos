"""检索引擎 - BM25 关键词搜索

负责:
- 使用 SQLite FTS5 进行关键词检索
- BM25 相关性评分
- 支持路径/类型过滤
- 生成详细的评分解释 (审计关键)
"""

import re
import sqlite3
from pathlib import Path
from typing import Any, Optional

from agentos.core.project_kb.types import (
    DOCUMENT_TYPE_WEIGHTS,
    ChunkResult,
    Explanation,
    SearchFilters,
)


class ProjectKBSearcher:
    """ProjectKB 检索引擎 - 基于 FTS5 的关键词搜索"""

    def __init__(self, db_path: Path):
        """初始化检索器

        Args:
            db_path: 数据库路径
        """
        self.db_path = Path(db_path)

    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def search(
        self,
        query: str,
        filters: Optional[SearchFilters] = None,
        top_k: int = 10,
    ) -> list[ChunkResult]:
        """关键词检索

        Args:
            query: 查询字符串
            filters: 过滤器
            top_k: 返回结果数

        Returns:
            ChunkResult 列表 (按评分降序)
        """
        filters = filters or SearchFilters()

        # 构建 FTS5 查询
        fts_query = self._prepare_fts_query(query)

        # 构建 SQL 查询
        sql, params = self._build_search_query(fts_query, filters, top_k)

        # 执行查询
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()

        # 转换为 ChunkResult
        results = []
        for rank, row in enumerate(rows, start=1):
            result = self._row_to_result(row, query, rank)
            results.append(result)

        return results

    def _prepare_fts_query(self, query: str) -> str:
        """准备 FTS5 查询字符串

        Args:
            query: 原始查询

        Returns:
            FTS5 查询语法
        """
        # 简单处理: 分词 + OR 连接
        # TODO: 支持更复杂的查询语法 (短语、布尔运算)
        terms = query.split()
        # FTS5 默认 OR 搜索
        return " OR ".join(terms)

    def _build_search_query(
        self,
        fts_query: str,
        filters: SearchFilters,
        top_k: int,
    ) -> tuple[str, list[Any]]:
        """构建 SQL 查询

        Args:
            fts_query: FTS5 查询
            filters: 过滤器
            top_k: 结果数

        Returns:
            (sql, params) 元组
        """
        sql = """
        SELECT 
            c.chunk_id,
            c.heading,
            c.start_line,
            c.end_line,
            c.content,
            s.path,
            s.doc_type,
            s.mtime,
            fts.rank as fts_rank
        FROM kb_chunks_fts fts
        JOIN kb_chunks c ON fts.rowid = c.rowid
        JOIN kb_sources s ON c.source_id = s.source_id
        WHERE kb_chunks_fts MATCH ?
        """

        params: list[Any] = [fts_query]

        # 应用过滤器
        if filters.scope:
            sql += " AND s.path LIKE ?"
            params.append(f"{filters.scope}%")

        if filters.doc_type:
            sql += " AND s.doc_type = ?"
            params.append(filters.doc_type)

        if filters.mtime_after:
            sql += " AND s.mtime >= ?"
            params.append(filters.mtime_after)

        if filters.mtime_before:
            sql += " AND s.mtime <= ?"
            params.append(filters.mtime_before)

        # 排序和限制
        sql += " ORDER BY fts.rank LIMIT ?"
        params.append(top_k)

        return sql, params

    def _row_to_result(self, row: sqlite3.Row, query: str, rank: int) -> ChunkResult:
        """将数据库行转换为 ChunkResult

        Args:
            row: 数据库行
            query: 原始查询
            rank: 排名 (1-based)

        Returns:
            ChunkResult 对象
        """
        # 提取匹配词
        matched_terms = self._extract_matched_terms(row["content"], query)

        # 计算词频
        term_frequencies = {}
        content_lower = row["content"].lower()
        for term in matched_terms:
            term_frequencies[term] = content_lower.count(term.lower())

        # 计算文档权重
        doc_type = row["doc_type"] or "default"
        document_boost = DOCUMENT_TYPE_WEIGHTS.get(doc_type, 1.0)

        # 计算新鲜度权重 (exp decay: 30天半衰期)
        recency_boost = self._calculate_recency_boost(row["mtime"])

        # 计算最终评分 (FTS5 rank 是负数，越小越好)
        base_score = abs(row["fts_rank"])
        final_score = base_score * document_boost * recency_boost

        # 构建解释
        explanation = Explanation(
            matched_terms=matched_terms,
            term_frequencies=term_frequencies,
            document_boost=document_boost,
            recency_boost=recency_boost,
            path=row["path"],
            heading=row["heading"],
            lines=f"L{row['start_line']}-L{row['end_line']}",
        )

        return ChunkResult(
            chunk_id=row["chunk_id"],
            content=row["content"],
            heading=row["heading"],
            path=row["path"],
            lines=f"L{row['start_line']}-L{row['end_line']}",
            score=final_score,
            explanation=explanation,
        )

    def _calculate_recency_boost(self, mtime: int) -> float:
        """计算新鲜度权重 (指数衰减)

        Args:
            mtime: 文档修改时间戳

        Returns:
            权重系数 (1.0 - 1.5)
        """
        import math
        import time

        # 计算距离现在的天数
        now = time.time()
        days_old = (now - mtime) / 86400  # 秒转天

        # 指数衰减: boost = 1.0 + 0.5 * exp(-days_old / 30)
        # 刚更新: boost ≈ 1.5
        # 30天: boost ≈ 1.18
        # 90天: boost ≈ 1.03
        boost = 1.0 + 0.5 * math.exp(-days_old / 30)
        return boost

    def _extract_matched_terms(self, content: str, query: str) -> list[str]:
        """提取匹配的词

        Args:
            content: 文档内容
            query: 查询字符串

        Returns:
            匹配词列表
        """
        query_terms = set(query.lower().split())
        content_lower = content.lower()

        matched = []
        for term in query_terms:
            if term in content_lower:
                matched.append(term)

        return matched

    def get_chunk_by_id(self, chunk_id: str) -> Optional[dict]:
        """按 ID 获取 chunk (含 source 信息)

        Args:
            chunk_id: Chunk ID

        Returns:
            Chunk 字典，不存在返回 None
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT 
                c.chunk_id,
                c.heading,
                c.start_line,
                c.end_line,
                c.content,
                c.content_hash,
                c.token_count,
                s.source_id,
                s.path,
                s.doc_type,
                s.mtime
            FROM kb_chunks c
            JOIN kb_sources s ON c.source_id = s.source_id
            WHERE c.chunk_id = ?
            """,
            (chunk_id,),
        )

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return {
            "chunk_id": row["chunk_id"],
            "heading": row["heading"],
            "start_line": row["start_line"],
            "end_line": row["end_line"],
            "content": row["content"],
            "content_hash": row["content_hash"],
            "token_count": row["token_count"],
            "source_id": row["source_id"],
            "path": row["path"],
            "doc_type": row["doc_type"],
            "mtime": row["mtime"],
        }
