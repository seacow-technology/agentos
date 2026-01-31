#!/usr/bin/env python3
"""Gate G-FTS-01: FTS5 Trigger 健康检查

验证:
1. 所有 triggers (INSERT/UPDATE/DELETE) 存在
2. Triggers 能正常执行
3. FTS 表和 chunks 表保持同步
"""

import sys
import tempfile
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agentos.core.project_kb import ProjectKBService


def main():
    print("Gate G-FTS-01: FTS5 Trigger Health Check")
    print("=" * 60)
    
    try:
        kb_service = ProjectKBService()
        conn = kb_service.indexer._get_connection()
        
        # 1. 检查 triggers 存在
        print("\n1. Checking triggers...")
        triggers = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE 'kb_chunks_a%'"
        ).fetchall()
        
        trigger_names = [t[0] for t in triggers]
        required = ["kb_chunks_ai", "kb_chunks_ad", "kb_chunks_au"]
        
        for req in required:
            if req in trigger_names:
                print(f"  ✓ {req} exists")
            else:
                print(f"  ✗ {req} missing")
                return 1
        
        # 2. 测试 INSERT trigger
        print("\n2. Testing INSERT trigger...")
        test_source_id = f"test_gate_fts_{id(conn)}"
        test_chunk_id = f"test_chunk_fts_{id(conn)}"
        
        # 插入测试 source
        conn.execute("""
            INSERT OR REPLACE INTO kb_sources 
            (source_id, repo_id, path, file_hash, mtime, created_at, updated_at)
            VALUES (?, 'test', 'test.md', 'hash123', 0, datetime('now'), datetime('now'))
        """, (test_source_id,))
        
        # 插入测试 chunk（应触发 INSERT trigger）
        conn.execute("""
            INSERT INTO kb_chunks 
            (chunk_id, source_id, heading, start_line, end_line, content, content_hash, created_at)
            VALUES (?, ?, 'Test Heading', 1, 10, 'Test content for FTS', 'hash456', datetime('now'))
        """, (test_chunk_id, test_source_id))
        
        conn.commit()
        
        # 验证 FTS 表有数据
        fts_row = conn.execute(
            "SELECT chunk_id, path FROM kb_chunks_fts WHERE chunk_id = ?", 
            (test_chunk_id,)
        ).fetchone()
        
        if fts_row:
            print(f"  ✓ INSERT trigger works (chunk_id={fts_row[0]}, path={fts_row[1]})")
        else:
            print(f"  ✗ INSERT trigger failed: chunk not in FTS")
            return 1
        
        # 3. 测试 UPDATE trigger
        print("\n3. Testing UPDATE trigger...")
        conn.execute("""
            UPDATE kb_chunks SET content = 'Updated content for FTS test'
            WHERE chunk_id = ?
        """, (test_chunk_id,))
        conn.commit()
        
        fts_row_updated = conn.execute(
            "SELECT content FROM kb_chunks_fts WHERE chunk_id = ?",
            (test_chunk_id,)
        ).fetchone()
        
        if fts_row_updated and "Updated" in fts_row_updated[0]:
            print(f"  ✓ UPDATE trigger works")
        else:
            print(f"  ✗ UPDATE trigger failed")
            return 1
        
        # 4. 测试 DELETE trigger
        print("\n4. Testing DELETE trigger...")
        conn.execute("DELETE FROM kb_chunks WHERE chunk_id = ?", (test_chunk_id,))
        conn.commit()
        
        fts_row_after_delete = conn.execute(
            "SELECT COUNT(*) FROM kb_chunks_fts WHERE chunk_id = ?",
            (test_chunk_id,)
        ).fetchone()[0]
        
        if fts_row_after_delete == 0:
            print(f"  ✓ DELETE trigger works")
        else:
            print(f"  ✗ DELETE trigger failed: chunk still in FTS")
            return 1
        
        # 清理测试数据
        conn.execute("DELETE FROM kb_sources WHERE source_id = ?", (test_source_id,))
        conn.commit()
        
        print("\n" + "=" * 60)
        print("✅ Gate G-FTS-01 PASSED")
        return 0
        
    except Exception as e:
        print(f"\n❌ Gate G-FTS-01 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
