#!/usr/bin/env python3
"""Gate E6: Performance Threshold Check

验证: candidate_k 上限检查，防止性能退化

红线: candidate_k 过大会导致 embedding 检索缓慢
"""

import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agentos.core.project_kb.service import ProjectKBService


def check_performance_threshold():
    """检查性能阈值"""
    try:
        kb_service = ProjectKBService()

        # 只在 vector rerank 启用时检查
        if not kb_service.config.vector_rerank.enabled:
            print("✓ Gate E6: SKIP (vector rerank not enabled)")
            return True

        # 检查 candidate_k 阈值
        candidate_k = kb_service.config.vector_rerank.candidate_k
        max_threshold = 100

        if candidate_k > max_threshold:
            print(f"✗ Gate E6: FAIL (candidate_k {candidate_k} > {max_threshold})")
            print(f"  Large candidate_k may cause performance issues")
            print(f"  Recommended: 50-100")
            return False
        else:
            print(f"✓ Gate E6: PASS (candidate_k {candidate_k} <= {max_threshold})")
            return True

    except Exception as e:
        print(f"✗ Gate E6: ERROR ({e})")
        return False


if __name__ == "__main__":
    success = check_performance_threshold()
    sys.exit(0 if success else 1)
