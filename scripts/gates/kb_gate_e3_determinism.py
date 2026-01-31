#!/usr/bin/env python3
"""Gate E3: Determinism Check

验证: 同一 query 多次执行结果稳定（在相同库状态下）

红线: 结果不稳定会破坏用户信任
"""

import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agentos.core.project_kb.service import ProjectKBService


def check_determinism():
    """检查结果确定性"""
    try:
        kb_service = ProjectKBService()

        # 只在 vector rerank 启用时检查
        if not kb_service.config.vector_rerank.enabled:
            print("✓ Gate E3: SKIP (vector rerank not enabled)")
            return True

        if not kb_service.reranker:
            print("✗ Gate E3: FAIL (reranker not initialized)")
            return False

        # 执行 3 次相同搜索
        query = "authentication security JWT"
        runs = []

        for i in range(3):
            results = kb_service.search(query=query, top_k=5, use_rerank=True)
            # 记录 chunk_id 序列
            chunk_ids = [r.chunk_id for r in results]
            runs.append(chunk_ids)

        # 检查所有结果是否相同
        if all(run == runs[0] for run in runs):
            print("✓ Gate E3: PASS (results deterministic)")
            return True
        else:
            print("✗ Gate E3: FAIL (results vary across runs)")
            print(f"  Run 1: {runs[0][:3]}")
            print(f"  Run 2: {runs[1][:3]}")
            print(f"  Run 3: {runs[2][:3]}")
            return False

    except Exception as e:
        print(f"✗ Gate E3: ERROR ({e})")
        return False


if __name__ == "__main__":
    success = check_determinism()
    sys.exit(0 if success else 1)
