"""索引构建器 - 管理 FTS5 全文索引

负责:
- 构建和更新 SQLite FTS5 索引
- 管理 sources 和 chunks 表
- 增量更新 (只处理变更文件)
- 清理已删除文档

Gate 要求:
- #1: FTS5 Available性检测
- #2: 迁移幂等（IF NOT EXISTS）
- #9: 重建一致性
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from agentos.core.project_kb.types import Chunk, Source
from agentos.core.time import utc_now_iso



class FTS5NotAvailableError(RuntimeError):
    """FTS5 不Available异常"""
    pass


class ProjectKBIndexer:
    """ProjectKB 索引构建器"""

    def __init__(self, db_path: Path):
        """初始化索引器

        Args:
            db_path: 数据库路径 (use component_db_path("agentos"))
        """
        self.db_path = Path(db_path)

    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        # Gate #2: 启用 WAL 模式避免长事务锁
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def check_fts5_available(self) -> bool:
        """检查 FTS5 是否Available (Gate #1)
        
        Returns:
            True 如果 FTS5 Available
            
        Raises:
            FTS5NotAvailableError: 如果 FTS5 不Available
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA compile_options")
            options = [row[0] for row in cursor.fetchall()]
            
            # 检查是否启用 FTS5
            if not any("FTS5" in opt for opt in options):
                raise FTS5NotAvailableError(
                    "SQLite FTS5 not available in this environment. "
                    "Please rebuild SQLite with FTS5 enabled."
                )
            return True
        finally:
            conn.close()

    def ensure_schema(self):
        """确保 ProjectKB 表存在 (执行迁移)
        
        Gate #2: 迁移幂等 - 使用 IF NOT EXISTS
        """
        # Gate #1: 首先检查 FTS5 Available性
        self.check_fts5_available()
        
        conn = self._get_connection()
        
        # 读取迁移脚本
        migration_path = Path(__file__).parent.parent.parent / "store" / "migrations" / "v12_project_kb.sql"
        
        if migration_path.exists():
            with open(migration_path, "r", encoding="utf-8") as f:
                migration_sql = f.read()
            
            # Gate #2: 迁移是幂等的（IF NOT EXISTS）
            conn.executescript(migration_sql)
            conn.commit()
        
        conn.close()

    def get_existing_sources(self, repo_id: str) -> dict[str, Source]:
        """获取已存在的 sources

        Args:
            repo_id: 项目 ID

        Returns:
            source_id -> Source 映射
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT source_id, repo_id, path, file_hash, mtime, doc_type, language, tags
            FROM kb_sources
            WHERE repo_id = ?
            """,
            (repo_id,),
        )

        sources = {}
        for row in cursor.fetchall():
            sources[row["source_id"]] = Source(
                source_id=row["source_id"],
                repo_id=row["repo_id"],
                path=row["path"],
                file_hash=row["file_hash"],
                mtime=row["mtime"],
                doc_type=row["doc_type"],
                language=row["language"],
                tags=eval(row["tags"]) if row["tags"] else [],
            )

        conn.close()
        return sources

    def upsert_source(self, source: Source):
        """插入或更新 source

        Args:
            source: Source 对象
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        now = utc_now_iso()

        # 检查是否已存在
        cursor.execute(
            "SELECT created_at FROM kb_sources WHERE source_id = ?",
            (source.source_id,),
        )
        row = cursor.fetchone()
        created_at = row["created_at"] if row else now

        cursor.execute(
            """
            INSERT OR REPLACE INTO kb_sources 
            (source_id, repo_id, path, file_hash, mtime, doc_type, language, tags, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source.source_id,
                source.repo_id,
                source.path,
                source.file_hash,
                source.mtime,
                source.doc_type,
                source.language,
                str(source.tags),
                created_at,
                now,
            ),
        )

        conn.commit()
        conn.close()

    def delete_source(self, source_id: str):
        """删除 source 及其所有 chunks

        Args:
            source_id: Source ID

        Note:
            由于外键 CASCADE，chunks 和 fts 记录会自动删除
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM kb_sources WHERE source_id = ?", (source_id,))

        conn.commit()
        conn.close()

    def delete_chunks_by_source(self, source_id: str):
        """删除指定 source 的所有 chunks

        Args:
            source_id: Source ID
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM kb_chunks WHERE source_id = ?", (source_id,))

        conn.commit()
        conn.close()

    def clear_all_chunks(self, repo_id: str):
        """清空指定 repo 的所有 chunks（用于 reindex）

        Args:
            repo_id: Repository ID
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Delete all chunks for this repo
        cursor.execute(
            """
            DELETE FROM kb_chunks 
            WHERE source_id IN (
                SELECT source_id FROM kb_sources WHERE repo_id = ?
            )
            """,
            (repo_id,)
        )

        # Delete all sources for this repo
        cursor.execute("DELETE FROM kb_sources WHERE repo_id = ?", (repo_id,))

        conn.commit()
        conn.close()

    def insert_chunk(self, chunk: Chunk):
        """插入 chunk (触发器会自动更新 FTS5)

        Args:
            chunk: Chunk 对象
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        now = utc_now_iso()

        cursor.execute(
            """
            INSERT INTO kb_chunks 
            (chunk_id, source_id, heading, start_line, end_line, content, content_hash, token_count, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                chunk.chunk_id,
                chunk.source_id,
                chunk.heading,
                chunk.start_line,
                chunk.end_line,
                chunk.content,
                chunk.content_hash,
                chunk.token_count,
                now,
            ),
        )

        conn.commit()
        conn.close()

    def update_meta(self, key: str, value: str):
        """更新索引元数据

        Args:
            key: 元数据键
            value: 元数据值
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        now = utc_now_iso()

        cursor.execute(
            """
            INSERT OR REPLACE INTO kb_index_meta (key, value, updated_at)
            VALUES (?, ?, ?)
            """,
            (key, value, now),
        )

        conn.commit()
        conn.close()

    def rebuild_fts(self, allow_drift: bool = False) -> dict:
        """重建 FTS 索引（从 kb_chunks 全量同步）
        
        幂等操作：完全清空 FTS 表，然后 bulk insert，不依赖 triggers
        
        Args:
            allow_drift: 是否允许差异容忍（并发模式）。默认 False（要求 0 差异）
            
        Returns:
            dict: 重建统计信息 {
                "fts_count": int,
                "valid_chunk_count": int,
                "orphans_removed": int,
                "drift_ratio": float
            }
        """
        conn = self._get_connection()
        
        try:
            # 1. 完全清空 FTS 表（确保幂等）
            # 先禁用 triggers 避免递归
            conn.execute("PRAGMA recursive_triggers = OFF")
            conn.execute("DELETE FROM kb_chunks_fts")
            
            # 2. 从 kb_chunks 重新填充（bulk insert）
            # 只索引有效的 chunks（有对应 source，排除测试数据）
            conn.execute("""
                INSERT INTO kb_chunks_fts(rowid, chunk_id, path, heading, content)
                SELECT 
                    c.rowid,
                    c.chunk_id,
                    s.path,
                    c.heading,
                    c.content
                FROM kb_chunks c
                INNER JOIN kb_sources s ON c.source_id = s.source_id
                WHERE c.chunk_id NOT LIKE 'test_%'
            """)
            
            # 3. 优化 FTS 索引
            conn.execute("INSERT INTO kb_chunks_fts(kb_chunks_fts) VALUES('optimize')")
            
            # 4. 重新启用 triggers
            conn.execute("PRAGMA recursive_triggers = ON")
            
            conn.commit()
            
            # 5. 验证一致性
            fts_count = conn.execute("SELECT COUNT(*) FROM kb_chunks_fts").fetchone()[0]
            valid_chunk_count = conn.execute("""
                SELECT COUNT(*) 
                FROM kb_chunks c
                INNER JOIN kb_sources s ON c.source_id = s.source_id
                WHERE c.chunk_id NOT LIKE 'test_%'
            """).fetchone()[0]
            
            # 计算差异比例
            diff_ratio = abs(fts_count - valid_chunk_count) / max(valid_chunk_count, 1) if valid_chunk_count > 0 else 0
            
            # 默认要求强一致（0 差异）
            if fts_count != valid_chunk_count:
                if not allow_drift:
                    raise RuntimeError(
                        f"FTS rebuild verification failed (strict mode): "
                        f"FTS has {fts_count} rows but valid kb_chunks has {valid_chunk_count}. "
                        f"Use --allow-drift to tolerate minor differences in concurrent mode."
                    )
                # 允许容忍模式：<5% 差异
                elif diff_ratio > 0.05:
                    raise RuntimeError(
                        f"FTS rebuild verification failed: "
                        f"FTS has {fts_count} rows but valid kb_chunks has {valid_chunk_count} "
                        f"(diff ratio: {diff_ratio:.2%}, exceeds 5% threshold)"
                    )
            
            return {
                "fts_count": fts_count,
                "valid_chunk_count": valid_chunk_count,
                "orphans_removed": 0,  # 在 cleanup_orphan_chunks 中计算
                "drift_ratio": diff_ratio,
            }
        finally:
            conn.close()

    def get_meta(self, key: str) -> Optional[str]:
        """获取索引元数据

        Args:
            key: 元数据键

        Returns:
            元数据值，不存在返回 None
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT value FROM kb_index_meta WHERE key = ?", (key,))
        row = cursor.fetchone()

        conn.close()
        return row["value"] if row else None

    def get_chunk_count(self, repo_id: Optional[str] = None) -> int:
        """获取 chunk 数量

        Args:
            repo_id: 项目 ID (None 表示所有项目)

        Returns:
            Chunk 数量
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        if repo_id:
            cursor.execute(
                """
                SELECT COUNT(*) as count
                FROM kb_chunks c
                JOIN kb_sources s ON c.source_id = s.source_id
                WHERE s.repo_id = ?
                """,
                (repo_id,),
            )
        else:
            cursor.execute("SELECT COUNT(*) as count FROM kb_chunks")

        count = cursor.fetchone()["count"]
        conn.close()
        return count

    def count_chunks_by_source(self, source_id: str) -> int:
        """统计指定 source 的 chunk 数量

        Args:
            source_id: Source ID

        Returns:
            该 source 的 chunk 数量
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT COUNT(*) as count
            FROM kb_chunks
            WHERE source_id = ?
            """,
            (source_id,),
        )

        count = cursor.fetchone()["count"]
        conn.close()
        return count

    def get_chunks_stats_by_source(self, repo_id: Optional[str] = None) -> dict[str, int]:
        """按 source 统计 chunks 数量

        Args:
            repo_id: 项目 ID (None 表示所有项目)

        Returns:
            Dict[source_id, chunk_count]
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        if repo_id:
            cursor.execute(
                """
                SELECT c.source_id, COUNT(*) as count
                FROM kb_chunks c
                JOIN kb_sources s ON c.source_id = s.source_id
                WHERE s.repo_id = ?
                GROUP BY c.source_id
                """,
                (repo_id,),
            )
        else:
            cursor.execute(
                """
                SELECT source_id, COUNT(*) as count
                FROM kb_chunks
                GROUP BY source_id
                """
            )

        stats = {row["source_id"]: row["count"] for row in cursor.fetchall()}
        conn.close()
        return stats

    def cleanup_orphan_chunks(self) -> dict:
        """清理孤儿 chunks（没有对应 kb_sources 的 chunks）
        
        自动清理：
        - kb_chunks 中没有对应 source 的记录
        - kb_embeddings 中没有对应 chunk 的记录
        
        Returns:
            dict: 清理统计信息 {
                "orphan_chunks_removed": int,
                "orphan_embeddings_removed": int
            }
        """
        conn = self._get_connection()
        
        try:
            # 1. 查找孤儿 chunks
            orphan_chunks = conn.execute("""
                SELECT COUNT(*) 
                FROM kb_chunks c
                WHERE NOT EXISTS (
                    SELECT 1 FROM kb_sources s WHERE s.source_id = c.source_id
                )
            """).fetchone()[0]
            
            # 2. 删除孤儿 chunks（触发器会自动清理 FTS）
            if orphan_chunks > 0:
                conn.execute("""
                    DELETE FROM kb_chunks 
                    WHERE NOT EXISTS (
                        SELECT 1 FROM kb_sources s WHERE s.source_id = kb_chunks.source_id
                    )
                """)
            
            # 3. 清理孤儿 embeddings（如果表存在）
            orphan_embeddings = 0
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='kb_embeddings'"
            ).fetchall()
            
            if tables:
                orphan_embeddings = conn.execute("""
                    SELECT COUNT(*) 
                    FROM kb_embeddings e
                    WHERE NOT EXISTS (
                        SELECT 1 FROM kb_chunks c WHERE c.chunk_id = e.chunk_id
                    )
                """).fetchone()[0]
                
                if orphan_embeddings > 0:
                    conn.execute("""
                        DELETE FROM kb_embeddings 
                        WHERE NOT EXISTS (
                            SELECT 1 FROM kb_chunks c WHERE c.chunk_id = kb_embeddings.chunk_id
                        )
                    """)
            
            conn.commit()
            
            return {
                "orphan_chunks_removed": orphan_chunks,
                "orphan_embeddings_removed": orphan_embeddings,
            }
        finally:
            conn.close()

    def record_fts_signature(self, migration_version: str = "14"):
        """记录 FTS 表和触发器的版本签名
        
        在 kb_index_meta 中记录：
        - fts_mode: contentless
        - fts_columns: path, heading, content
        - trigger_set: ai, au, ad
        - migration_version: 14
        
        Args:
            migration_version: 迁移版本号（默认 "14"）
        """
        conn = self._get_connection()
        
        try:
            now = utc_now_iso()
            
            # 记录 FTS 签名
            signatures = [
                ("fts_mode", "contentless"),
                ("fts_columns", "path,heading,content"),
                ("trigger_set", "ai,au,ad"),
                ("migration_version", migration_version),
                ("fts_signature_updated_at", now),
            ]
            
            for key, value in signatures:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO kb_index_meta (key, value, updated_at)
                    VALUES (?, ?, ?)
                    """,
                    (key, value, now),
                )
            
            conn.commit()
        finally:
            conn.close()

    def get_fts_signature(self) -> dict:
        """获取 FTS 版本签名
        
        Returns:
            dict: FTS 签名信息 {
                "fts_mode": str,
                "fts_columns": str,
                "trigger_set": str,
                "migration_version": str,
                "fts_signature_updated_at": str
            }
        """
        conn = self._get_connection()
        
        try:
            keys = ["fts_mode", "fts_columns", "trigger_set", "migration_version", "fts_signature_updated_at"]
            signature = {}
            
            for key in keys:
                cursor = conn.execute(
                    "SELECT value FROM kb_index_meta WHERE key = ?",
                    (key,)
                )
                row = cursor.fetchone()
                signature[key] = row[0] if row else None
            
            return signature
        finally:
            conn.close()

