#!/usr/bin/env python3
"""Gate E1: Embedding Coverage Check

验证: 当 rerank 启用时，候选 topK 中 embedding 覆盖率必须 >= 95%

红线: 低覆盖率会导致 rerank 结果不稳定
"""

import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agentos.core.project_kb.service import ProjectKBService


def check_embedding_coverage():
    """检查 embedding 覆盖率"""
    try:
        kb_service = ProjectKBService()

        # 只在 vector rerank 启用时检查
        if not kb_service.config.vector_rerank.enabled:
            print("✓ Gate E1: SKIP (vector rerank not enabled)")
            return True

        if not kb_service.embedding_manager:
            print("✗ Gate E1: FAIL (embedding_manager not initialized)")
            return False

        # 获取统计信息
        total_chunks = kb_service.indexer.get_chunk_count()
        embed_stats = kb_service.embedding_manager.get_stats()
        total_embeddings = embed_stats["total"]

        if total_chunks == 0:
            print("✓ Gate E1: SKIP (no chunks indexed)")
            return True

        # 计算覆盖率
        coverage = (total_embeddings / total_chunks) * 100

        # 阈值: 95%
        threshold = 95.0

        if coverage >= threshold:
            print(f"✓ Gate E1: PASS (coverage {coverage:.1f}% >= {threshold}%)")
            return True
        else:
            print(f"✗ Gate E1: FAIL (coverage {coverage:.1f}% < {threshold}%)")
            print(f"  Chunks: {total_chunks}, Embeddings: {total_embeddings}")
            print(f"  Run: agentos kb embed build")
            return False

    except Exception as e:
        print(f"✗ Gate E1: ERROR ({e})")
        return False


if __name__ == "__main__":
    success = check_embedding_coverage()
    sys.exit(0 if success else 1)
