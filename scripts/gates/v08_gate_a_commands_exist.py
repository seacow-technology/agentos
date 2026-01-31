#!/usr/bin/env python3
"""Gate A: Command 内容存在性检查

验证:
1. docs/content/commands/ 目录存在 40 个 YAML 文件（分布在 10 个子目录）
2. 每个 command YAML 的基本结构正确
3. 所有必需的 command ID 存在

用法:
    uv run python scripts/gates/v08_gate_a_commands_exist.py
"""

import sys
from pathlib import Path

import yaml


def check_commands_exist() -> tuple[bool, list[str]]:
    """检查 40 个 command YAML 文件是否存在"""
    commands_dir = Path("docs/content/commands")
    
    if not commands_dir.exists():
        return False, [f"❌ Directory not found: {commands_dir}"]
    
    # Expected categories and counts
    expected_structure = {
        "git": 8,
        "product": 4,
        "design": 3,
        "architecture": 3,
        "engineering": 5,
        "quality": 3,
        "security": 3,
        "operations": 6,
        "incident": 3,
        "documentation": 2,
    }
    
    errors = []
    total_found = 0
    found_commands = set()
    command_id_to_file = {}  # Track ID -> filename mapping for uniqueness check
    
    for category, expected_count in expected_structure.items():
        category_dir = commands_dir / category
        
        if not category_dir.exists():
            errors.append(f"❌ Category directory not found: {category}")
            continue
        
        yaml_files = list(category_dir.glob("*.yaml")) + list(category_dir.glob("*.yml"))
        
        if len(yaml_files) != expected_count:
            errors.append(
                f"❌ {category}: Expected {expected_count} YAML files, found {len(yaml_files)}"
            )
        
        # Validate each file
        for yaml_file in yaml_files:
            try:
                with open(yaml_file, encoding="utf-8") as f:
                    command_data = yaml.safe_load(f)
                
                # Verify basic required fields
                required_fields = [
                    "id",
                    "type",
                    "version",
                    "category",
                    "title",
                    "description",
                    "recommended_roles",
                    "inputs",
                    "outputs",
                    "preconditions",
                    "effects",
                    "risk_level",
                    "evidence_required",
                    "constraints",
                    "lineage",
                ]
                
                for field in required_fields:
                    if field not in command_data:
                        errors.append(f"❌ {yaml_file.name}: Missing required field '{field}'")
                
                if "id" in command_data:
                    command_id = command_data["id"]
                    
                    # Check ID uniqueness
                    if command_id in command_id_to_file:
                        errors.append(
                            f"❌ Duplicate ID '{command_id}' found in {yaml_file.name} "
                            f"(already in {command_id_to_file[command_id]})"
                        )
                    else:
                        command_id_to_file[command_id] = yaml_file.name
                        found_commands.add(command_id)
                    
                    # Verify ID format
                    if not command_id.startswith("cmd_"):
                        errors.append(f"❌ {yaml_file.name}: ID must start with 'cmd_', got '{command_id}'")
                    
                    # Verify filename matches ID (strongly recommended)
                    expected_filename = f"{command_id}.yaml"
                    if yaml_file.name != expected_filename:
                        errors.append(
                            f"❌ {yaml_file.name}: Filename should match ID, expected '{expected_filename}'"
                        )
                    
                    # Verify type is 'command'
                    if command_data.get("type") != "command":
                        errors.append(f"❌ {yaml_file.name}: type must be 'command', got '{command_data.get('type')}'")
                    
                    # Verify category matches directory
                    if command_data.get("category") != category:
                        errors.append(
                            f"❌ {yaml_file.name}: category '{command_data.get('category')}' doesn't match directory '{category}'"
                        )
                
                total_found += 1
                
            except Exception as e:
                errors.append(f"❌ Failed to parse {yaml_file.name}: {e}")
    
    # Check total count (STRICT: must be exactly 40)
    if total_found != 40:
        errors.append(f"❌ STRICT REQUIREMENT: Expected exactly 40 command YAML files, found {total_found}")
    
    # Check ID uniqueness (STRICT: must be 40 unique IDs)
    if len(found_commands) != 40:
        errors.append(f"❌ STRICT REQUIREMENT: Expected 40 unique command IDs, found {len(found_commands)}")
    
    if errors:
        return False, errors
    
    return True, [
        f"✅ Found all 40 command YAML files across 10 categories",
        f"✅ All 40 command IDs are unique",
        f"✅ All filenames match their command IDs"
    ]


def main():
    """运行 Gate A 检查"""
    print("=" * 60)
    print("Gate A: Command 内容存在性检查")
    print("=" * 60)
    print()
    
    all_passed = True
    
    # 检查 commands 目录
    passed, messages = check_commands_exist()
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
