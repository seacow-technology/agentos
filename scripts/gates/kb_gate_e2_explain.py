#!/usr/bin/env python3
"""Gate E2: Explain Completeness Check

验证: rerank 开启时，explain 必须包含所有向量评分字段

红线: 缺失字段会破坏可审计性
"""

import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agentos.core.project_kb.service import ProjectKBService


def check_explain_completeness():
    """检查 explain 完整性"""
    try:
        kb_service = ProjectKBService()

        # 只在 vector rerank 启用时检查
        if not kb_service.config.vector_rerank.enabled:
            print("✓ Gate E2: SKIP (vector rerank not enabled)")
            return True

        if not kb_service.reranker:
            print("✗ Gate E2: FAIL (reranker not initialized)")
            return False

        # 执行一次搜索（使用 rerank）
        results = kb_service.search(
            query="test authentication security",
            top_k=3,
            use_rerank=True,
        )

        if not results:
            print("✓ Gate E2: SKIP (no search results)")
            return True

        # 检查第一个结果的 explanation
        result = results[0]
        exp = result.explanation

        # 必须字段
        required_fields = [
            ("keyword_score", exp.keyword_score),
            ("vector_score", exp.vector_score),
            ("alpha", exp.alpha),
            ("final_score", exp.final_score),
            ("rerank_delta", exp.rerank_delta),
            ("final_rank", exp.final_rank),
        ]

        missing = []
        for field_name, field_value in required_fields:
            if field_value is None:
                missing.append(field_name)

        if missing:
            print(f"✗ Gate E2: FAIL (missing fields: {', '.join(missing)})")
            return False
        else:
            print("✓ Gate E2: PASS (all explain fields present)")
            return True

    except Exception as e:
        print(f"✗ Gate E2: ERROR ({e})")
        return False


if __name__ == "__main__":
    success = check_explain_completeness()
    sys.exit(0 if success else 1)
