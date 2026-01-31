#!/usr/bin/env python3
"""Gate B: Schema 批量验证 (v0.9 Rules)

验证:
1. rule.schema.json 存在并可加载
2. 所有 12 个 YAML 文件通过 schema 验证

用法:
    uv run python scripts/gates/v09_gate_b_schema_validation.py
"""

import sys
from pathlib import Path

# Add agentos to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def test_schema_validation():
    """测试所有 rules 的 schema 验证"""
    print("Testing schema validation...")
    
    try:
        from agentos.core.content.schema_loader import ContentSchemaLoader
        import yaml
        from jsonschema import validate, ValidationError
        
        # Load schema
        schema_loader = ContentSchemaLoader()
        try:
            schema = schema_loader.load_schema("content/rule.schema.json")
            print("  ✅ rule.schema.json loaded successfully")
        except Exception as e:
            print(f"  ❌ Failed to load schema: {e}")
            return False
        
        # Validate all rules
        rules_dir = Path("docs/content/rules/p0")
        if not rules_dir.exists():
            print(f"  ❌ Rules directory not found: {rules_dir}")
            return False
        
        yaml_files = list(rules_dir.glob("*.yaml")) + list(rules_dir.glob("*.yml"))
        
        if len(yaml_files) == 0:
            print("  ❌ No YAML files found")
            return False
        
        print(f"  Found {len(yaml_files)} rule files to validate")
        
        success_count = 0
        failure_count = 0
        
        for yaml_path in yaml_files:
            try:
                with open(yaml_path, encoding="utf-8") as f:
                    rule_data = yaml.safe_load(f)
                
                # Validate against schema
                validate(instance=rule_data, schema=schema)
                
                print(f"  ✅ {yaml_path.name}: Schema validation passed")
                success_count += 1
                
            except ValidationError as e:
                print(f"  ❌ {yaml_path.name}: Schema validation failed")
                print(f"     Error: {e.message}")
                print(f"     Path: {list(e.path)}")
                failure_count += 1
            except Exception as e:
                print(f"  ❌ {yaml_path.name}: Unexpected error: {e}")
                failure_count += 1
        
        print(f"\n  Validation Results: {success_count} success, {failure_count} failures")
        
        if failure_count > 0:
            return False
        
        # Expected: exactly 12 rules
        if success_count != 12:
            print(f"  ❌ Expected 12 rules, validated {success_count}")
            return False
        
        print("  ✅ All 12 rules passed schema validation")
        return True
        
    except Exception as e:
        print(f"  ❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行 Gate B 检查"""
    print("=" * 60)
    print("Gate B: Schema 批量验证 (v0.9)")
    print("=" * 60)
    print()
    
    if test_schema_validation():
        print()
        print("=" * 60)
        print("✅ Gate B: PASS - All rules passed schema validation")
        print("=" * 60)
        sys.exit(0)
    else:
        print()
        print("=" * 60)
        print("❌ Gate B: FAIL - Schema validation issues found")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()
