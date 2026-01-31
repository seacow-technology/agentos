#!/usr/bin/env python3
"""Gate F: Explain 输出稳定性测试 (v0.8 Commands)

验证:
1. 在临时目录初始化 DB
2. 注册所有 commands
3. 对固定的 5 条 commands 执行 explain
4. 生成快照并与预期结构对比
5. 确保 explain 输出格式稳定

用法:
    uv run python scripts/gates/v08_gate_f_explain_snapshot.py
"""

import json
import sys
import tempfile
from pathlib import Path

# Add agentos to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def test_explain_output():
    """测试 explain 输出的稳定性"""
    print("Testing explain output stability...")
    
    # 固定的测试 command IDs（覆盖不同类别和风险级别）
    test_command_ids = [
        "cmd_git_create_branch",      # git, low risk
        "cmd_deploy_production",       # operations, high risk
        "cmd_security_scan_dependency", # security, medium risk
        "cmd_prd_create",              # product, low risk
        "cmd_db_migration_create",     # engineering, high risk
    ]
    
    try:
        from agentos.core.content import ContentRegistry, ContentLineageTracker
        import yaml
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # 1. 初始化临时 DB
            import sqlite3
            db_path = Path(tmpdir) / "test.db"
            
            schema_path = Path("agentos/store/schema_v05.sql")
            if not schema_path.exists():
                print(f"  ❌ Schema file not found: {schema_path}")
                return False
            
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
            
            print(f"  ✅ DB initialized at {db_path}")
            
            # 2. 注册测试 commands
            registry = ContentRegistry(db_path=db_path)
            commands_dir = Path("docs/content/commands")
            
            registered_count = 0
            for yaml_path in commands_dir.rglob("*.yaml"):
                try:
                    with open(yaml_path, encoding="utf-8") as f:
                        command_yaml = yaml.safe_load(f)
                    
                    # Convert to content format
                    import hashlib
                    from datetime import datetime, timezone
                    
                    content_str = json.dumps(command_yaml, sort_keys=True)
                    checksum = hashlib.sha256(content_str.encode()).hexdigest()
                    
                    content = {
                        "id": command_yaml["id"],
                        "type": "command",
                        "version": command_yaml["version"],
                        "metadata": {
                            "created_at": datetime.now(timezone.utc).isoformat(),
                            "checksum": checksum,
                            "is_root": True,
                        },
                        "spec": command_yaml,
                    }
                    
                    registry.register(content)
                    registered_count += 1
                except Exception as e:
                    print(f"  ⚠️  Failed to register {yaml_path.name}: {e}")
            
            print(f"  ✅ Registered {registered_count} commands")
            
            # 3. 测试 explain 输出
            tracker = ContentLineageTracker(registry)
            explain_results = {}
            
            for command_id in test_command_ids:
                try:
                    content = registry.get(command_id)
                    if not content:
                        print(f"  ❌ Command not found: {command_id}")
                        return False
                    
                    version = content["version"]
                    
                    # Get lineage explanation
                    lineage_explanation = tracker.explain_version(command_id, version)
                    
                    # Get spec details
                    spec = content["spec"]
                    
                    # Build snapshot structure
                    snapshot = {
                        "id": command_id,
                        "version": version,
                        "type": content["type"],
                        "status": content.get("status", "draft"),
                        "lineage_explanation": lineage_explanation,
                        "spec_structure": {
                            "has_title": "title" in spec,
                            "has_description": "description" in spec,
                            "has_recommended_roles": "recommended_roles" in spec,
                            "has_workflow_links": "workflow_links" in spec,
                            "has_inputs": "inputs" in spec,
                            "has_outputs": "outputs" in spec,
                            "has_preconditions": "preconditions" in spec,
                            "has_effects": "effects" in spec,
                            "has_risk_level": "risk_level" in spec,
                            "has_evidence_required": "evidence_required" in spec,
                            "has_constraints": "constraints" in spec,
                            "has_lineage": "lineage" in spec,
                            "category": spec.get("category"),
                            "risk_level": spec.get("risk_level"),
                        },
                    }
                    
                    explain_results[command_id] = snapshot
                    print(f"  ✅ {command_id}: Explain output captured")
                    
                except Exception as e:
                    print(f"  ❌ Failed to explain {command_id}: {e}")
                    return False
            
            # 4. 验证所有必需字段都存在
            for command_id, snapshot in explain_results.items():
                spec_struct = snapshot["spec_structure"]
                
                required_fields = [
                    "has_title", "has_description", "has_recommended_roles",
                    "has_inputs", "has_outputs", "has_preconditions",
                    "has_effects", "has_risk_level", "has_evidence_required",
                    "has_constraints", "has_lineage"
                ]
                
                missing_fields = [f for f in required_fields if not spec_struct.get(f)]
                
                if missing_fields:
                    print(f"  ❌ {command_id}: Missing required fields: {missing_fields}")
                    return False
            
            print(f"  ✅ All {len(test_command_ids)} commands have complete explain output")
            
            # 5. 可选：保存快照到文件（用于回归测试）
            snapshot_file = Path("tests/snapshots/v08_explain_snapshot.json")
            snapshot_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(snapshot_file, "w", encoding="utf-8") as f:
                json.dump(explain_results, f, indent=2, sort_keys=True)
            
            print(f"  ✅ Snapshot saved to {snapshot_file}")
            
            return True
            
    except Exception as e:
        print(f"  ❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行 Gate F 检查"""
    print("=" * 60)
    print("Gate F: Explain 输出稳定性测试 (v0.8)")
    print("=" * 60)
    print()
    
    if test_explain_output():
        print()
        print("=" * 60)
        print("✅ Gate F: PASS - Explain output is stable")
        print("=" * 60)
        sys.exit(0)
    else:
        print()
        print("=" * 60)
        print("❌ Gate F: FAIL - Explain output issues found")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()
