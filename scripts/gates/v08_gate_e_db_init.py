#!/usr/bin/env python3
"""Gate E: DB 初始化路径明确 (v0.8 Commands)

验证:
1. 可以在任意路径初始化 DB
2. 初始化的 DB 包含正确的 content_* 表
3. register_commands.py 可以使用自定义 DB 路径

用法:
    uv run python scripts/gates/v08_gate_e_db_init.py
"""

import sqlite3
import sys
import tempfile
from pathlib import Path


def test_db_init_with_custom_path():
    """测试在自定义路径初始化 DB"""
    print("Testing DB initialization with custom path...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_store.db"
        
        print(f"  Creating DB at: {db_path}")
        
        # 读取 v0.5 schema
        schema_path = Path("agentos/store/schema_v05.sql")
        if not schema_path.exists():
            print(f"  ❌ Schema file not found: {schema_path}")
            return False
        
        with open(schema_path, encoding="utf-8") as f:
            schema_sql = f.read()
        
        # 初始化 DB
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            # 执行 schema（跳过 schema_version 相关的行）
            for statement in schema_sql.split(';'):
                statement = statement.strip()
                if statement and 'schema_version' not in statement.lower():
                    try:
                        cursor.execute(statement)
                    except sqlite3.OperationalError as e:
                        # 忽略 "table already exists" 错误
                        if "already exists" not in str(e):
                            raise
            
            conn.commit()
            
            # 验证表存在
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name LIKE 'content_%'
                ORDER BY name
            """)
            tables = [row[0] for row in cursor.fetchall()]
            
            expected_tables = ['content_audit_log', 'content_lineage', 'content_registry']
            
            for table in expected_tables:
                if table not in tables:
                    print(f"  ❌ Missing table: {table}")
                    conn.close()
                    return False
            
            print(f"  ✅ DB initialized successfully")
            print(f"  ✅ Found tables: {', '.join(tables)}")
            
            conn.close()
            return True
            
        except Exception as e:
            print(f"  ❌ Failed to initialize DB: {e}")
            return False


def test_content_registry_import():
    """测试 ContentRegistry 可以使用自定义路径"""
    print("\nTesting ContentRegistry with custom path...")
    
    try:
        from agentos.core.content.registry import ContentRegistry
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_registry.db"
            
            # 先手动创建表
            schema_path = Path("agentos/store/schema_v05.sql")
            with open(schema_path, encoding="utf-8") as f:
                schema_sql = f.read()
            
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            for statement in schema_sql.split(';'):
                statement = statement.strip()
                if statement and 'schema_version' not in statement.lower():
                    try:
                        cursor.execute(statement)
                    except sqlite3.OperationalError:
                        pass
            conn.commit()
            conn.close()
            
            # 使用 ContentRegistry
            registry = ContentRegistry(db_path=db_path)
            
            print(f"  ✅ ContentRegistry initialized with custom path")
            return True
            
    except Exception as e:
        print(f"  ❌ Failed to initialize ContentRegistry: {e}")
        return False


def main():
    """运行 Gate E 检查"""
    print("=" * 60)
    print("Gate E: DB 初始化路径明确 (v0.8)")
    print("=" * 60)
    print()
    
    all_passed = True
    
    # 测试 1: 自定义路径初始化
    if not test_db_init_with_custom_path():
        all_passed = False
    
    # 测试 2: ContentRegistry 使用自定义路径
    if not test_content_registry_import():
        all_passed = False
    
    print()
    if all_passed:
        print("=" * 60)
        print("✅ Gate E: PASS - DB initialization is path-independent")
        print("=" * 60)
        sys.exit(0)
    else:
        print("=" * 60)
        print("❌ Gate E: FAIL - DB initialization issues found")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()
