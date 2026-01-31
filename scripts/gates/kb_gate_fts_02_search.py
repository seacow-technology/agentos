#!/usr/bin/env python3
"""Gate G-FTS-02: Search 非空回归

验证:
1. refresh 后能检索到已知文档
2. 删除文档后不再命中
3. FTS 搜索返回非空结果
"""

import sys
import tempfile
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agentos.core.project_kb import ProjectKBService


def main():
    print("Gate G-FTS-02: Search Non-Empty Regression")
    print("=" * 60)
    
    try:
        kb_service = ProjectKBService()
        
        # 1. 检查当前索引状态
        print("\n1. Checking index state...")
        total_chunks = kb_service.indexer.get_chunk_count()
        print(f"  Total chunks: {total_chunks}")
        
        if total_chunks == 0:
            print("  ⚠️  Index empty, running refresh first...")
            kb_service.refresh()
            total_chunks = kb_service.indexer.get_chunk_count()
            print(f"  Total chunks after refresh: {total_chunks}")
        
        if total_chunks == 0:
            print("  ✗ No chunks after refresh (possible scan path issue)")
            return 1
        
        # 2. 测试基本搜索（使用高频词）
        print("\n2. Testing basic search...")
        test_queries = ["the", "project", "system", "documentation"]
        
        for query in test_queries:
            results = kb_service.search(query, top_k=5, explain=False)
            if results:
                print(f"  ✓ Query '{query}' found {len(results)} results")
                break
        else:
            print(f"  ✗ No results for any test query")
            return 1
        
        # 3. 创建测试文档并验证
        print("\n3. Testing new document indexing...")
        from pathlib import Path
        root_dir = Path.cwd()
        test_file = root_dir / "docs" / f"gate_test_{id(kb_service)}.md"
        test_unique_word = f"UniqueGateTestWord{id(kb_service)}"
        
        try:
            # 创建测试文档
            test_file.parent.mkdir(parents=True, exist_ok=True)
            test_file.write_text(f"# Gate Test\n\n{test_unique_word} for search validation.\n")
            
            # Refresh
            kb_service.refresh()
            
            # 搜索唯一词
            results = kb_service.search(test_unique_word, top_k=1, explain=False)
            
            if results and len(results) > 0:
                print(f"  ✓ New document indexed and searchable")
            else:
                print(f"  ✗ New document not found in search")
                return 1
            
            # 4. 测试删除后不再命中
            print("\n4. Testing deletion cleanup...")
            test_file.unlink()
            kb_service.refresh()
            
            results_after_delete = kb_service.search(test_unique_word, top_k=1, explain=False)
            
            if len(results_after_delete) == 0:
                print(f"  ✓ Deleted document no longer in index")
            else:
                print(f"  ✗ Deleted document still in index")
                return 1
        
        finally:
            # 清理
            if test_file.exists():
                test_file.unlink()
        
        print("\n" + "=" * 60)
        print("✅ Gate G-FTS-02 PASSED")
        return 0
        
    except Exception as e:
        print(f"\n❌ Gate G-FTS-02 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
