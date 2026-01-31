"""Gate: ProjectKB Explain 验证

验证所有检索结果都有完整 explain 输出（审计红线）
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agentos.core.project_kb.service import ProjectKBService


def gate_explain_completeness():
    """验证 explain 完整性"""
    print("=" * 70)
    print("Gate: ProjectKB Explain Completeness")
    print("=" * 70)
    
    # 初始化 service
    kb = ProjectKBService()
    
    # 执行搜索
    test_queries = [
        "authentication",
        "deployment",
        "docker",
    ]
    
    all_valid = True
    
    for query in test_queries:
        print(f"\nTesting query: {query}")
        results = kb.search(query, top_k=3)
        
        if not results:
            print(f"  [SKIP] No results for '{query}'")
            continue
        
        for i, result in enumerate(results, 1):
            print(f"  Result {i}:")
            
            # 验证必需字段
            if not result.chunk_id:
                print(f"    ❌ Missing chunk_id")
                all_valid = False
            
            if not result.path:
                print(f"    ❌ Missing path")
                all_valid = False
            
            if not result.explanation:
                print(f"    ❌ Missing explanation")
                all_valid = False
            else:
                exp = result.explanation
                
                # 验证 explanation 字段
                if not exp.matched_terms:
                    print(f"    ❌ Missing matched_terms")
                    all_valid = False
                
                if exp.term_frequencies is None:
                    print(f"    ❌ Missing term_frequencies")
                    all_valid = False
                
                if exp.document_boost is None:
                    print(f"    ❌ Missing document_boost")
                    all_valid = False
                
                if exp.recency_boost is None:
                    print(f"    ❌ Missing recency_boost")
                    all_valid = False
            
            if all_valid:
                print(f"    ✓ Complete explanation")
    
    print("\n" + "=" * 70)
    if all_valid:
        print("✅ Gate PASSED: All results have complete explanations")
        print("=" * 70)
        return True
    else:
        print("❌ Gate FAILED: Some results missing explanation fields")
        print("=" * 70)
        return False


if __name__ == "__main__":
    success = gate_explain_completeness()
    sys.exit(0 if success else 1)
