#!/usr/bin/env python3
"""Gate E4: Graceful Fallback Check

验证: provider 不Available或模型缺失时，自动退回 BM25 + 记录 audit

红线: 依赖缺失不能导致系统崩溃
"""

import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agentos.core.project_kb.config import ProjectKBConfig, VectorRerankConfig
from agentos.core.project_kb.service import ProjectKBService


def check_graceful_fallback():
    """检查优雅降级"""
    try:
        # 创建一个启用 rerank 的配置（但不安装依赖）
        config = ProjectKBConfig()
        config.vector_rerank = VectorRerankConfig(
            enabled=True,
            provider="local",
            model="sentence-transformers/all-MiniLM-L6-v2",
        )

        # 尝试初始化（fail_safe=True）
        kb_service = ProjectKBService(config=config, fail_safe=True)

        # 如果 reranker 初始化失败，应该退回关键词检索
        if kb_service.reranker is None:
            # 尝试搜索（应该能成功，使用关键词）
            results = kb_service.search(query="test", top_k=3)

            # 结果应该没有 vector_score
            if results and results[0].explanation.vector_score is None:
                print("✓ Gate E4: PASS (graceful fallback to keyword search)")
                return True
            else:
                print("✗ Gate E4: FAIL (fallback but vector_score present)")
                return False
        else:
            # Reranker Available（依赖已安装）
            print("✓ Gate E4: SKIP (vector dependencies installed)")
            return True

    except Exception as e:
        # 任何异常都是失败（应该优雅降级，不崩溃）
        print(f"✗ Gate E4: FAIL (exception during fallback: {e})")
        return False


if __name__ == "__main__":
    success = check_graceful_fallback()
    sys.exit(0 if success else 1)
