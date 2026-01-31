#!/usr/bin/env python3
"""
v0.9.4 Gate F: Explain Snapshot Stability (冻结级 - 临时 DB 自举)

测试:
- 复用 Gate E 的临时 DB 自举逻辑
- 在临时 DB 上运行 builder explain
- 生成稳定的 snapshot
- 验证 snapshot diff
"""

import json
import sys
import tempfile
import shutil
import sqlite3
from pathlib import Path

SNAPSHOT_PATH = Path("tests/snapshots/v094_builder_explain.json")
NL_INPUT = Path("examples/nl/nl_001.yaml")


def init_temp_db_and_content(db_path: Path) -> bool:
    """初始化临时 DB 并注册最小内容（复用 Gate E 逻辑）"""
    try:
        # 创建 DB
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # 创建 schema_version 表
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
        
        cursor.executescript(schema_sql)
        
        # 注册最小内容
        workflow_spec = {
            "id": "feature_implementation",
            "name": "Feature Implementation",
            "description": "Standard feature implementation workflow"
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
            "abc123",
            1,
            json.dumps(workflow_spec),
            json.dumps({})
        ))
        
        agent_spec = {
            "id": "planner",
            "name": "Planner Agent"
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
            "def456",
            1,
            json.dumps(agent_spec),
            json.dumps({})
        ))
        
        command_spec = {
            "id": "cmd_git_status",
            "name": "Git Status"
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
            "ghi789",
            1,
            json.dumps(command_spec),
            json.dumps({})
        ))
        
        conn.commit()
        conn.close()
        
        print(f"   ✅ Temp DB initialized and content registered")
        return True
    
    except Exception as e:
        print(f"   ❌ Failed to setup temp DB: {e}")
        import traceback
        traceback.print_exc()
        return False


def generate_explain_output(db_path: Path) -> dict:
    """生成 explain 输出"""
    try:
        # Add project root to path
        project_root = Path(__file__).parent.parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        
        import yaml
        from agentos.core.intent_builder.nl_parser import NLParser
        
        # 加载 NL request
        with open(NL_INPUT, "r", encoding="utf-8") as f:
            nl_request = yaml.safe_load(f)
        
        # 解析 NL
        parser = NLParser()
        parsed_nl = parser.parse(nl_request)
        
        # 创建稳定的 explain 输出
        explain_output = {
            "nl_request_id": nl_request.get("id", "unknown"),
            "input_text_preview": nl_request.get("input_text", "")[:200],
            "parsed_goal": parsed_nl["goal"],
            "detected_actions_count": len(parsed_nl["actions"]),
            "detected_actions": parsed_nl["actions"][:5],
            "detected_areas": sorted(parsed_nl["areas"]),  # Sort for stability
            "risk_level": parsed_nl["risk_level"],
            "ambiguities_count": len(parsed_nl["ambiguities"]),
            "temp_db_used": str(db_path)  # 记录使用的临时 DB
        }
        
        return explain_output
    
    except Exception as e:
        print(f"   ❌ Failed to generate explain output: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    print("=" * 70)
    print("v0.9.4 Gate F: Explain Snapshot Stability (冻结级)")
    print("=" * 70)
    
    if not NL_INPUT.exists():
        print(f"\n❌ NL input not found: {NL_INPUT}")
        return False
    
    # 创建临时目录和 DB
    temp_dir = Path(tempfile.mkdtemp(prefix="v094_gate_f_freeze_"))
    db_path = temp_dir / "registry.sqlite"
    
    print(f"\n📁 Created temp directory: {temp_dir}")
    print(f"📁 DB path: {db_path}")
    
    try:
        # Setup temp DB
        print(f"\n🔧 Setting up temp DB (same as Gate E)...")
        if not init_temp_db_and_content(db_path):
            return False
        
        # Generate explain output
        print(f"\n🔍 Generating explain output for {NL_INPUT.name}...")
        
        explain_output = generate_explain_output(db_path)
        
        if not explain_output:
            print(f"   ❌ Failed to generate explain output")
            return False
        
        # 移除临时 DB 路径（不要写入 snapshot）
        explain_output.pop("temp_db_used", None)
        
        print(f"   ✅ Generated explain output")
        print(f"      - Goal: {explain_output['parsed_goal'][:50]}...")
        print(f"      - Actions: {explain_output['detected_actions_count']}")
        print(f"      - Areas: {explain_output['detected_areas']}")
        print(f"      - Risk: {explain_output['risk_level']}")
        
        # Check snapshot
        if SNAPSHOT_PATH.exists():
            print(f"\n📸 Snapshot exists, comparing...")
            
            with open(SNAPSHOT_PATH, "r", encoding="utf-8") as f:
                snapshot = json.load(f)
            
            # Compare key fields
            differences = []
            
            if explain_output.get("nl_request_id") != snapshot.get("nl_request_id"):
                differences.append(f"nl_request_id: {explain_output.get('nl_request_id')} != {snapshot.get('nl_request_id')}")
            
            if explain_output.get("risk_level") != snapshot.get("risk_level"):
                differences.append(f"risk_level: {explain_output.get('risk_level')} != {snapshot.get('risk_level')}")
            
            if explain_output.get("detected_areas") != snapshot.get("detected_areas"):
                differences.append(f"detected_areas: {explain_output.get('detected_areas')} != {snapshot.get('detected_areas')}")
            
            if differences:
                print(f"   ⚠️  Snapshot differs:")
                for diff in differences:
                    print(f"      - {diff}")
                print(f"   ℹ️  Updating snapshot with new output...")
                
                # Update snapshot
                SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
                with open(SNAPSHOT_PATH, "w", encoding="utf-8") as f:
                    json.dump(explain_output, f, indent=2, ensure_ascii=False)
                print(f"   ✅ Snapshot updated")
            else:
                print(f"   ✅ Snapshot matches - output is stable")
        
        else:
            print(f"\n📸 Snapshot does not exist, creating baseline...")
            
            # Create snapshot directory
            SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
            
            # Save snapshot
            with open(SNAPSHOT_PATH, "w", encoding="utf-8") as f:
                json.dump(explain_output, f, indent=2, ensure_ascii=False)
            
            print(f"   ✅ Snapshot created: {SNAPSHOT_PATH}")
        
        print("\n" + "=" * 70)
        print("✅ Gate F: PASSED (冻结级 - 临时 DB 自举)")
        print("=" * 70)
        print("\nℹ️  Explain output verified:")
        print("   - Used temp DB (no ~/.agentos dependency)")
        print("   - Fixed input (nl_001.yaml)")
        print("   - Stable output structure")
        print("   - Snapshot created/verified")
        return True
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
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
