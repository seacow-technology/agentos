#!/usr/bin/env python3
"""Gate A: Rule 内容存在性检查

验证:
1. docs/content/rules/p0/ 目录存在 12 个 YAML 文件
2. 每个 rule YAML 的基本结构正确
3. 所有必需的 rule ID 存在且唯一

用法:
    uv run python scripts/gates/v09_gate_a_rules_exist.py
"""

import sys
from pathlib import Path

import yaml


def check_rules_exist() -> tuple[bool, list[str]]:
    """检查 12 个 rule YAML 文件是否存在"""
    rules_dir = Path("docs/content/rules/p0")
    
    if not rules_dir.exists():
        return False, [f"❌ Directory not found: {rules_dir}"]
    
    # Expected: exactly 12 rules
    expected_count = 12
    
    errors = []
    found_rules = set()
    rule_id_to_file = {}  # Track ID -> filename mapping for uniqueness check
    
    yaml_files = list(rules_dir.glob("*.yaml")) + list(rules_dir.glob("*.yml"))
    
    if len(yaml_files) != expected_count:
        errors.append(
            f"❌ STRICT REQUIREMENT: Expected exactly {expected_count} rule YAML files, found {len(yaml_files)}"
        )
    
    # Validate each file
    for yaml_file in yaml_files:
        try:
            with open(yaml_file, encoding="utf-8") as f:
                rule_data = yaml.safe_load(f)
            
            # Verify basic required fields
            required_fields = [
                "id",
                "type",
                "version",
                "title",
                "description",
                "status",
                "lineage",
                "rule",
                "constraints",
            ]
            
            for field in required_fields:
                if field not in rule_data:
                    errors.append(f"❌ {yaml_file.name}: Missing required field '{field}'")
            
            if "id" in rule_data:
                rule_id = rule_data["id"]
                
                # Check ID uniqueness
                if rule_id in rule_id_to_file:
                    errors.append(
                        f"❌ Duplicate ID '{rule_id}' found in {yaml_file.name} "
                        f"(already in {rule_id_to_file[rule_id]})"
                    )
                else:
                    rule_id_to_file[rule_id] = yaml_file.name
                    found_rules.add(rule_id)
                
                # Verify ID format
                if not rule_id.startswith("rule_r"):
                    errors.append(f"❌ {yaml_file.name}: ID must start with 'rule_r', got '{rule_id}'")
                
                # Verify filename matches ID (strongly recommended)
                expected_filename = f"{rule_id}.yaml"
                if yaml_file.name != expected_filename:
                    errors.append(
                        f"❌ {yaml_file.name}: Filename should match ID, expected '{expected_filename}'"
                    )
                
                # Verify type is 'rule'
                if rule_data.get("type") != "rule":
                    errors.append(f"❌ {yaml_file.name}: type must be 'rule', got '{rule_data.get('type')}'")
            
        except Exception as e:
            errors.append(f"❌ Failed to parse {yaml_file.name}: {e}")
    
    # Check ID uniqueness (STRICT: must be exactly 12 unique IDs)
    if len(found_rules) != expected_count:
        errors.append(f"❌ STRICT REQUIREMENT: Expected {expected_count} unique rule IDs, found {len(found_rules)}")
    
    if errors:
        return False, errors
    
    return True, [
        f"✅ Found all {expected_count} rule YAML files in p0/ directory",
        f"✅ All {expected_count} rule IDs are unique",
        f"✅ All filenames match their rule IDs"
    ]


def main():
    """运行 Gate A 检查"""
    print("=" * 60)
    print("Gate A: Rule 内容存在性检查")
    print("=" * 60)
    print()
    
    all_passed = True
    
    # 检查 rules 目录
    passed, messages = check_rules_exist()
    for msg in messages:
        print(msg)
    if not passed:
        all_passed = False
    print()
    
    if all_passed:
        print("=" * 60)
        print("✅ Gate A: PASS - All checks passed")
        print("=" * 60)
        sys.exit(0)
    else:
        print("=" * 60)
        print("❌ Gate A: FAIL - Some checks failed")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()
