#!/usr/bin/env python3
"""Gate E5: Incremental Consistency Check

验证: 修改文档后 embedding 同步更新

红线: 旧 embedding 会导致错误的 rerank 结果
"""

import sys
import tempfile
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def check_incremental_consistency():
    """检查增量一致性"""
    try:
        from agentos.core.project_kb.config import ProjectKBConfig, VectorRerankConfig
        from agentos.core.project_kb.service import ProjectKBService

        # 只在 vector 依赖Available时检查
        try:
            import sentence_transformers
        except ImportError:
            print("✓ Gate E5: SKIP (vector dependencies not installed)")
            return True

        # 创建临时目录和测试文档
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            docs_dir = tmpdir_path / "docs"
            docs_dir.mkdir()

            # 创建测试文档
            test_doc = docs_dir / "test.md"
            test_doc.write_text("# Authentication\n\nOriginal content about JWT tokens.")

            # 初始化 ProjectKB (启用 vector rerank)
            config = ProjectKBConfig()
            config.scan_paths = ["docs/**/*.md"]
            config.vector_rerank = VectorRerankConfig(enabled=True)

            kb_service = ProjectKBService(root_dir=tmpdir_path, config=config)

            # 第一次刷新（建立索引 + embeddings）
            kb_service.refresh(changed_only=False)

            if not kb_service.embedding_manager:
                print("✗ Gate E5: FAIL (embedding_manager not initialized)")
                return False

            # 获取初始 embedding
            chunks_before = kb_service._get_chunks_for_embedding(changed_only=False)
            if not chunks_before:
                print("✗ Gate E5: FAIL (no chunks after first refresh)")
                return False

            chunk_id = chunks_before[0].chunk_id
            content_hash_before = chunks_before[0].content_hash

            # 修改文档
            test_doc.write_text("# Authentication\n\nModified content with OAuth2 details.")

            # 增量刷新
            kb_service.refresh(changed_only=True)

            # 检查 embedding 是否更新
            chunks_after = kb_service._get_chunks_for_embedding(changed_only=False)
            chunk_after = next((c for c in chunks_after if c.chunk_id == chunk_id), None)

            if not chunk_after:
                print("✗ Gate E5: FAIL (chunk not found after update)")
                return False

            if chunk_after.content_hash == content_hash_before:
                print("✗ Gate E5: FAIL (content_hash not updated)")
                return False

            # 检查 embedding 表中的 content_hash 是否匹配
            embeddings = kb_service.embedding_manager.get_embeddings([chunk_id])
            if not embeddings or embeddings[0] is None:
                print("✗ Gate E5: FAIL (embedding not found after update)")
                return False

            # 从数据库读取 embedding 的 content_hash
            import sqlite3

            conn = sqlite3.connect(str(kb_service.db_path))
            cursor = conn.cursor()
            cursor.execute(
                "SELECT content_hash FROM kb_embeddings WHERE chunk_id = ?", (chunk_id,)
            )
            row = cursor.fetchone()
            conn.close()

            if not row:
                print("✗ Gate E5: FAIL (embedding record not found)")
                return False

            embedding_hash = row[0]
            if embedding_hash != chunk_after.content_hash:
                print("✗ Gate E5: FAIL (embedding content_hash mismatch)")
                print(f"  Chunk hash: {chunk_after.content_hash}")
                print(f"  Embedding hash: {embedding_hash}")
                return False

            print("✓ Gate E5: PASS (embedding updated with content)")
            return True

    except Exception as e:
        print(f"✗ Gate E5: ERROR ({e})")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = check_incremental_consistency()
    sys.exit(0 if success else 1)
