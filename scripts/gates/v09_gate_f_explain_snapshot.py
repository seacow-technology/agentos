#!/usr/bin/env python3
"""Gate F: Explain 输出稳定性测试 (v0.9 Rules)

验证:
1. 在临时目录初始化 DB
2. 注册所有 rules
3. 对固定的 5 条 rules 执行 explain
4. 生成快照并与预期结构对比
5. 确保 explain 输出格式稳定

用法:
    uv run python scripts/gates/v09_gate_f_explain_snapshot.py
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
    
    # 固定的测试 rule IDs（覆盖不同严重级别）
    test_rule_ids = [
        "rule_r01_no_execution",                    # block, security
        "rule_r03_registry_only_references",        # error, references
        "rule_r07_change_budget_required",          # error, budget
        "rule_r09_evidence_refs_required_for_key_decisions",  # warn, evidence
        "rule_r12_rollback_plan_required_high_risk",  # error, risk-management
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
            
            # 2. 注册测试 rules
            registry = ContentRegistry(db_path=db_path)
            rules_dir = Path("docs/content/rules/p0")
            
            registered_count = 0
            for yaml_path in rules_dir.glob("*.yaml"):
                try:
                    with open(yaml_path, encoding="utf-8") as f:
                        rule_yaml = yaml.safe_load(f)
                    
                    # Convert to content format
                    import hashlib
                    from datetime import datetime, timezone
                    
                    content_str = json.dumps(rule_yaml, sort_keys=True)
                    checksum = hashlib.sha256(content_str.encode()).hexdigest()
                    
                    content = {
                        "id": rule_yaml["id"],
                        "type": "rule",
                        "version": rule_yaml["version"],
                        "metadata": {
                            "created_at": datetime.now(timezone.utc).isoformat(),
                            "checksum": checksum,
                            "is_root": True,
                        },
                        "spec": rule_yaml,
                    }
                    
                    registry.register(content)
                    registered_count += 1
                except Exception as e:
                    print(f"  ⚠️  Failed to register {yaml_path.name}: {e}")
            
            print(f"  ✅ Registered {registered_count} rules")
            
            # 3. 测试 explain 输出
            tracker = ContentLineageTracker(registry)
            explain_results = {}
            
            for rule_id in test_rule_ids:
                try:
                    content = registry.get(rule_id)
                    if not content:
                        print(f"  ❌ Rule not found: {rule_id}")
                        return False
                    
                    version = content["version"]
                    
                    # Get lineage explanation
                    lineage_explanation = tracker.explain_version(rule_id, version)
                    
                    # Get spec details
                    spec = content["spec"]
                    
                    # Build snapshot structure
                    snapshot = {
                        "id": rule_id,
                        "version": version,
                        "type": content["type"],
                        "status": content.get("status", "draft"),
                        "lineage_explanation": lineage_explanation,
                        "spec_structure": {
                            "has_title": "title" in spec,
                            "has_description": "description" in spec,
                            "has_rule": "rule" in spec,
                            "has_constraints": "constraints" in spec,
                            "has_lineage": "lineage" in spec,
                        },
                    }
                    
                    # Validate rule structure
                    if "rule" in spec:
                        rule_obj = spec["rule"]
                        snapshot["rule_structure"] = {
                            "has_severity": "severity" in rule_obj,
                            "has_scope": "scope" in rule_obj,
                            "has_when": "when" in rule_obj,
                            "has_then": "then" in rule_obj,
                            "has_evidence_required": "evidence_required" in rule_obj,
                            "severity": rule_obj.get("severity"),
                        }
                    
                    explain_results[rule_id] = snapshot
                    print(f"  ✅ {rule_id}: Explain output captured")
                    
                except Exception as e:
                    print(f"  ❌ Failed to explain {rule_id}: {e}")
                    return False
            
            # 4. 验证所有必需字段都存在
            for rule_id, snapshot in explain_results.items():
                spec_struct = snapshot["spec_structure"]
                
                required_fields = [
                    "has_title", "has_description", "has_rule",
                    "has_constraints", "has_lineage"
                ]
                
                missing_fields = [f for f in required_fields if not spec_struct.get(f)]
                
                if missing_fields:
                    print(f"  ❌ {rule_id}: Missing required fields: {missing_fields}")
                    return False
                
                # Validate rule structure
                if "rule_structure" in snapshot:
                    rule_struct = snapshot["rule_structure"]
                    rule_required = [
                        "has_severity", "has_scope", "has_when",
                        "has_then", "has_evidence_required"
                    ]
                    missing_rule_fields = [f for f in rule_required if not rule_struct.get(f)]
                    
                    if missing_rule_fields:
                        print(f"  ❌ {rule_id}: Missing rule fields: {missing_rule_fields}")
                        return False
            
            print(f"  ✅ All {len(test_rule_ids)} rules have complete explain output")
            
            # 5. 可选：保存快照到文件（用于回归测试）
            snapshot_file = Path("tests/snapshots/v09_explain_snapshot.json")
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
    print("Gate F: Explain 输出稳定性测试 (v0.9)")
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
