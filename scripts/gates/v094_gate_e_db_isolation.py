#!/usr/bin/env python3
"""
v0.9.4 Gate E: DB Path Isolation (冻结级 - 临时 DB 自举)

测试:
- 在临时目录创建 DB
- 初始化 schema (v0.5 content tables)
- 注册最小内容集合 (1 workflow + 1 agent + 1 command)
- IntentBuilder 可以在该 DB 上工作
- 完全不依赖 ~/.agentos
"""

import json
import sys
import tempfile
import shutil
import sqlite3
from pathlib import Path

def init_temp_db(db_path: Path) -> bool:
    """在临时路径初始化 DB schema"""
    try:
        # 创建 DB 文件
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # 先创建 schema_version 表（v0.5 schema 需要）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version TEXT PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 读取 v0.5 schema
        project_root = Path(__file__).parent.parent.parent
        schema_file = project_root / "agentos" / "store" / "schema_v05.sql"
        
        if not schema_file.exists():
            print(f"   ❌ Schema file not found: {schema_file}")
            return False
        
        with open(schema_file, "r", encoding="utf-8") as f:
            schema_sql = f.read()
        
        # 执行 schema
        cursor.executescript(schema_sql)
        conn.commit()
        conn.close()
        
        print(f"   ✅ DB initialized with v0.5 schema")
        return True
    
    except Exception as e:
        print(f"   ❌ Failed to init DB: {e}")
        return False


def register_minimal_content(db_path: Path) -> bool:
    """注册最小内容集合"""
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # 1. 注册一个 workflow
        workflow_spec = {
            "id": "feature_implementation",
            "name": "Feature Implementation",
            "description": "Standard feature implementation workflow",
            "phases": ["design", "implement", "test", "review"]
        }
        
        cursor.execute("""
            INSERT INTO content_registry 
            (id, type, version, status, checksum, is_root, spec, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "feature_implementation",
            "workflow",
            "1.0.0",
            "active",
            "abc123def456",  # 简化的 checksum
            1,  # is_root
            json.dumps(workflow_spec),
            json.dumps({"tags": ["feature"]})
        ))
        
        # 2. 注册一个 agent
        agent_spec = {
            "id": "planner",
            "name": "Planner Agent",
            "description": "Planning and design agent",
            "capabilities": ["planning", "design"]
        }
        
        cursor.execute("""
            INSERT INTO content_registry 
            (id, type, version, status, checksum, is_root, spec, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "planner",
            "agent",
            "1.0.0",
            "active",
            "def456ghi789",
            1,
            json.dumps(agent_spec),
            json.dumps({"roles": ["planning"]})
        ))
        
        # 3. 注册一个 command
        command_spec = {
            "id": "cmd_git_status",
            "name": "Git Status",
            "description": "Check git repository status",
            "command": "git status"
        }
        
        cursor.execute("""
            INSERT INTO content_registry 
            (id, type, version, status, checksum, is_root, spec, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "cmd_git_status",
            "command",
            "1.0.0",
            "active",
            "ghi789jkl012",
            1,
            json.dumps(command_spec),
            json.dumps({"category": "git"})
        ))
        
        conn.commit()
        
        # 验证注册成功
        cursor.execute("SELECT COUNT(*) FROM content_registry WHERE status='active'")
        count = cursor.fetchone()[0]
        
        conn.close()
        
        print(f"   ✅ Registered {count} content items")
        return count >= 3
    
    except Exception as e:
        print(f"   ❌ Failed to register content: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_registry_query(db_path: Path) -> bool:
    """测试 ContentRegistry 可以查询临时 DB"""
    try:
        # Add project root to path
        project_root = Path(__file__).parent.parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        
        from agentos.core.content.registry import ContentRegistry
        
        # 创建 registry 实例（指向临时 DB，传 Path 对象）
        registry = ContentRegistry(db_path=db_path)
        
        # 测试查询
        workflows = registry.list(type_="workflow", status="active")
        agents = registry.list(type_="agent", status="active")
        commands = registry.list(type_="command", status="active")
        
        print(f"   ✅ Registry can query temp DB:")
        print(f"      - Workflows: {len(workflows)}")
        print(f"      - Agents: {len(agents)}")
        print(f"      - Commands: {len(commands)}")
        
        return len(workflows) > 0 and len(agents) > 0 and len(commands) > 0
    
    except Exception as e:
        print(f"   ❌ Failed to query registry: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_builder_with_temp_db(db_path: Path) -> bool:
    """测试 IntentBuilder 可以使用临时 DB"""
    try:
        project_root = Path(__file__).parent.parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        
        from agentos.core.content.registry import ContentRegistry
        from agentos.core.intent_builder.builder import IntentBuilder
        
        # 创建 registry（传 Path 对象）
        registry = ContentRegistry(db_path=db_path)
        
        # 创建 builder
        builder = IntentBuilder(registry=registry)
        
        # 创建简单的 NL request
        nl_request = {
            "id": "nl_req_test",
            "schema_version": "0.9.4",
            "project_id": "test_project",
            "input_text": "Implement a new feature with tests",
            "context_hints": {},
            "created_at": "2026-01-25T10:00:00Z",
            "checksum": "test123",
            "lineage": {
                "introduced_in": "0.9.4",
                "derived_from": [],
                "supersedes": []
            }
        }
        
        # 运行 builder
        output = builder.build_intent(nl_request, policy="full_auto")
        
        print(f"   ✅ Builder can work with temp DB")
        print(f"      - Generated intent: {output.get('execution_intent', {}).get('id', 'N/A')}")
        
        return "execution_intent" in output
    
    except Exception as e:
        print(f"   ❌ Failed to run builder: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("=" * 70)
    print("v0.9.4 Gate E: DB Path Isolation (冻结级 - 临时 DB 自举)")
    print("=" * 70)
    
    # 创建临时目录
    temp_dir = Path(tempfile.mkdtemp(prefix="v094_gate_e_freeze_"))
    db_path = temp_dir / "registry.sqlite"
    
    print(f"\n📁 Created temp directory: {temp_dir}")
    print(f"📁 DB path: {db_path}")
    
    try:
        # Test 1: 初始化 DB schema
        print("\n🧪 Test 1: Initialize DB schema (v0.5)...")
        if not init_temp_db(db_path):
            return False
        
        # Test 2: 注册最小内容
        print("\n🧪 Test 2: Register minimal content...")
        if not register_minimal_content(db_path):
            return False
        
        # Test 3: ContentRegistry 查询
        print("\n🧪 Test 3: ContentRegistry can query temp DB...")
        if not test_registry_query(db_path):
            return False
        
        # Test 4: IntentBuilder 使用临时 DB
        print("\n🧪 Test 4: IntentBuilder works with temp DB...")
        if not test_builder_with_temp_db(db_path):
            return False
        
        print("\n" + "=" * 70)
        print("✅ Gate E: PASSED (冻结级 - 临时 DB 自举成功)")
        print("=" * 70)
        print("\nℹ️  Temp DB self-bootstrapping verified:")
        print("   - Created DB from scratch in temp directory")
        print("   - Initialized v0.5 schema")
        print("   - Registered minimal content (1 workflow, 1 agent, 1 command)")
        print("   - Registry can query the temp DB")
        print("   - IntentBuilder can work with the temp DB")
        print("   - No dependency on ~/.agentos")
        return True
    
    except Exception as e:
        print(f"\n❌ Gate E failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Cleanup
        print(f"\n🧹 Cleaning up temp directory: {temp_dir}")
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
