#!/usr/bin/env python3
"""Gate G-KB-STAT-DRIFT: Stats 漂移检测

验证:
1. refresh 前后 chunk 数异常波动 (>30%) 必须给出原因
2. 防止误删/误扫导致索引"瘦身"
3. 提供 stats diff 辅助诊断
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agentos.core.project_kb import ProjectKBService


def main():
    print("Gate G-KB-STAT-DRIFT: Stats Drift Detection")
    print("=" * 60)
    
    try:
        kb_service = ProjectKBService()
        
        # 1. 获取初始状态
        print("\n1. Capturing initial state...")
        initial_chunks = kb_service.indexer.get_chunk_count()
        initial_sources = len(kb_service.indexer.get_existing_sources(kb_service.scanner.repo_id))
        
        print(f"  Initial chunks: {initial_chunks}")
        print(f"  Initial sources: {initial_sources}")
        
        if initial_chunks == 0:
            print("  ⚠️  Empty index, running first refresh...")
            kb_service.refresh()
            initial_chunks = kb_service.indexer.get_chunk_count()
            initial_sources = len(kb_service.indexer.get_existing_sources(kb_service.scanner.repo_id))
            print(f"  After refresh - chunks: {initial_chunks}, sources: {initial_sources}")
        
        # 2. 执行 refresh（应该是增量，变化不大）
        print("\n2. Running refresh...")
        report = kb_service.refresh()
        
        final_chunks = kb_service.indexer.get_chunk_count()
        final_sources = len(kb_service.indexer.get_existing_sources(kb_service.scanner.repo_id))
        
        print(f"  Final chunks: {final_chunks}")
        print(f"  Final sources: {final_sources}")
        
        # 3. 计算变化率
        print("\n3. Checking drift...")
        
        if initial_chunks > 0:
            chunk_drift = abs(final_chunks - initial_chunks) / initial_chunks
            print(f"  Chunk drift: {chunk_drift * 100:.1f}%")
            
            if chunk_drift > 0.3:  # >30% 波动
                print(f"  ⚠️  DRIFT WARNING: >30% change in chunks!")
                print(f"     Changed files: {report.changed_files}")
                print(f"     New chunks: {report.new_chunks}")
                
                # 如果没有明显的文件变更，这是可疑的
                if report.changed_files < initial_sources * 0.1:  # <10% 文件变更
                    print(f"  ✗ Suspicious drift: large chunk change but few file changes")
                    print(f"     This may indicate:")
                    print(f"     - Scan path changed")
                    print(f"     - Exclude patterns changed")
                    print(f"     - File deletion not properly tracked")
                    return 1
                else:
                    print(f"  ✓ Drift explained by file changes")
            else:
                print(f"  ✓ Drift within acceptable range (<30%)")
        
        # 4. 验证 FTS 同步
        print("\n4. Verifying FTS sync...")
        conn = kb_service.indexer._get_connection()
        fts_count = conn.execute("SELECT COUNT(*) FROM kb_chunks_fts").fetchone()[0]
        conn.close()
        
        if fts_count == final_chunks:
            print(f"  ✓ FTS in sync ({fts_count} rows)")
        else:
            print(f"  ✗ FTS out of sync: FTS={fts_count}, chunks={final_chunks}")
            return 1
        
        print("\n" + "=" * 60)
        print("✅ Gate G-KB-STAT-DRIFT PASSED")
        return 0
        
    except Exception as e:
        print(f"\n❌ Gate G-KB-STAT-DRIFT FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
