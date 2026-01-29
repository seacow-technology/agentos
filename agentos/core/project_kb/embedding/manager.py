"""Embedding Manager - 管理 chunk embeddings

负责:
- 批量生成 embeddings
- 增量更新 (基于 content_hash)
- 持久化到 SQLite
- 检索 embeddings
"""

import sqlite3
import time
from pathlib import Path

import numpy as np

from agentos.core.project_kb.embedding.provider import IEmbeddingProvider
from agentos.core.project_kb.types import Chunk


class EmbeddingManager:
    """Embedding 管理器"""

    def __init__(self, db_path: Path, provider: IEmbeddingProvider):
        """初始化 manager

        Args:
            db_path: 数据库路径
            provider: Embedding provider
        """
        self.db_path = Path(db_path)
        self.provider = provider

        # 确保 embedding 表存在
        self._ensure_schema()

    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self):
        """确保 embedding 表存在"""
        from pathlib import Path

        migration_path = (
            Path(__file__).parent.parent.parent.parent
            / "store"
            / "migrations"
            / "v13_vector_embeddings.sql"
        )

        if migration_path.exists():
            conn = self._get_connection()
            with open(migration_path, "r", encoding="utf-8") as f:
                migration_sql = f.read()
            conn.executescript(migration_sql)
            conn.commit()
            conn.close()

    def build_embeddings(
        self, chunks: list[Chunk], batch_size: int = 32, show_progress: bool = True
    ) -> dict:
        """批量生成 embeddings

        Args:
            chunks: Chunk 列表
            batch_size: 批量大小
            show_progress: 是否显示进度

        Returns:
            统计信息 dict
        """
        if not chunks:
            return {"total": 0, "processed": 0, "skipped": 0, "errors": 0}

        total = len(chunks)
        processed = 0
        skipped = 0
        errors = 0

        for i in range(0, total, batch_size):
            batch = chunks[i : i + batch_size]

            if show_progress:
                print(f"Processing batch {i//batch_size + 1}/{(total + batch_size - 1)//batch_size}...")

            try:
                # 检查哪些 chunk 需要生成 embedding
                chunks_to_process = []
                for chunk in batch:
                    if not self._has_embedding(chunk.chunk_id, chunk.content_hash):
                        chunks_to_process.append(chunk)
                    else:
                        skipped += 1

                if not chunks_to_process:
                    continue

                # 批量生成 embeddings
                texts = [c.content for c in chunks_to_process]
                vectors = self.provider.embed_texts(texts)

                # 保存到数据库
                for chunk, vector in zip(chunks_to_process, vectors):
                    self._save_embedding(chunk.chunk_id, chunk.content_hash, vector)
                    processed += 1

            except Exception as e:
                print(f"Error processing batch: {e}")
                errors += len(batch)

        return {
            "total": total,
            "processed": processed,
            "skipped": skipped,
            "errors": errors,
        }

    def refresh_embeddings(self, chunks: list[Chunk], batch_size: int = 32) -> dict:
        """增量刷新 embeddings (只处理变更的 chunks)

        Args:
            chunks: Chunk 列表
            batch_size: 批量大小

        Returns:
            统计信息 dict
        """
        return self.build_embeddings(chunks, batch_size, show_progress=False)

    def get_embeddings(self, chunk_ids: list[str]) -> list[np.ndarray | None]:
        """批量获取 embeddings

        Args:
            chunk_ids: Chunk ID 列表

        Returns:
            Embedding 列表 (缺失的为 None)
        """
        if not chunk_ids:
            return []

        conn = self._get_connection()
        cursor = conn.cursor()

        # 构建 IN 查询
        placeholders = ",".join(["?"] * len(chunk_ids))
        query = f"""
            SELECT chunk_id, vector, dims
            FROM kb_embeddings
            WHERE chunk_id IN ({placeholders})
        """

        cursor.execute(query, chunk_ids)
        rows = cursor.fetchall()
        conn.close()

        # 构建结果映射
        embedding_map = {}
        for row in rows:
            chunk_id = row["chunk_id"]
            vector_bytes = row["vector"]
            dims = row["dims"]

            # 反序列化 vector
            vector = np.frombuffer(vector_bytes, dtype=np.float32)
            embedding_map[chunk_id] = vector

        # 按原始顺序返回 (缺失的为 None)
        return [embedding_map.get(chunk_id) for chunk_id in chunk_ids]

    def delete_embeddings(self, chunk_ids: list[str]):
        """删除 embeddings

        Args:
            chunk_ids: Chunk ID 列表
        """
        if not chunk_ids:
            return

        conn = self._get_connection()
        cursor = conn.cursor()

        placeholders = ",".join(["?"] * len(chunk_ids))
        cursor.execute(f"DELETE FROM kb_embeddings WHERE chunk_id IN ({placeholders})", chunk_ids)

        conn.commit()
        conn.close()

    def get_stats(self) -> dict:
        """获取 embedding 统计信息

        Returns:
            统计信息 dict
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # 总数
        cursor.execute("SELECT COUNT(*) as count FROM kb_embeddings")
        total = cursor.fetchone()["count"]

        # 按模型分组
        cursor.execute(
            """
            SELECT model, COUNT(*) as count
            FROM kb_embeddings
            GROUP BY model
        """
        )
        by_model = {row["model"]: row["count"] for row in cursor.fetchall()}

        # 最近更新时间
        cursor.execute("SELECT MAX(built_at) as latest FROM kb_embeddings")
        latest_row = cursor.fetchone()
        latest = latest_row["latest"] if latest_row["latest"] else None

        conn.close()

        return {
            "total": total,
            "by_model": by_model,
            "latest_built_at": latest,
        }

    def clear_all_embeddings(self):
        """清空所有 embeddings（用于 reindex）"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM kb_embeddings")
        cursor.execute("DELETE FROM kb_embedding_meta")
        conn.commit()
        conn.close()

    def _has_embedding(self, chunk_id: str, content_hash: str) -> bool:
        """检查是否已有 embedding (且 content_hash 匹配)

        Args:
            chunk_id: Chunk ID
            content_hash: Content hash

        Returns:
            是否已有有效的 embedding
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT content_hash
            FROM kb_embeddings
            WHERE chunk_id = ?
            """,
            (chunk_id,),
        )

        row = cursor.fetchone()
        conn.close()

        if not row:
            return False

        # 检查 content_hash 是否匹配
        return row["content_hash"] == content_hash

    def _save_embedding(self, chunk_id: str, content_hash: str, vector: np.ndarray):
        """保存 embedding 到数据库

        Args:
            chunk_id: Chunk ID
            content_hash: Content hash
            vector: Embedding vector (numpy array)
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # 序列化 vector
        vector_bytes = vector.astype(np.float32).tobytes()

        cursor.execute(
            """
            INSERT OR REPLACE INTO kb_embeddings 
            (chunk_id, model, dims, vector, content_hash, built_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                chunk_id,
                self.provider.model_name,
                self.provider.dims,
                vector_bytes,
                content_hash,
                int(time.time()),
            ),
        )

        conn.commit()
        conn.close()
