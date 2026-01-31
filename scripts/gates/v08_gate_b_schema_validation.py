#!/usr/bin/env python3
"""Gate B: Command Schema 批量校验

验证:
1. 加载 command.schema.json
2. 批量验证所有 YAML 文件符合 schema
3. 输出验证报告（passed/failed）

用法:
    uv run python scripts/gates/v08_gate_b_schema_validation.py
"""

import sys
from pathlib import Path

import yaml

# Add agentos to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agentos.core.content.schema_loader import ContentSchemaLoader


def validate_all_commands() -> tuple[int, int, list[str]]:
    """验证所有 command YAML 文件

    Returns:
        (success_count, failure_count, error_messages)
    """
    commands_dir = Path("docs/content/commands")
    schema_loader = ContentSchemaLoader()
    
    try:
        # Load schema
        schema = schema_loader.load_schema("content/command.schema.json")
    except Exception as e:
        return 0, 0, [f"❌ Failed to load command schema: {e}"]
    
    # Get all YAML files
    yaml_files = []
    for subdir in commands_dir.iterdir():
        if subdir.is_dir():
            yaml_files.extend(subdir.glob("*.yaml"))
            yaml_files.extend(subdir.glob("*.yml"))
    
    if not yaml_files:
        return 0, 0, [f"❌ No YAML files found in {commands_dir}"]
    
    success_count = 0
    failure_count = 0
    errors = []
    
    for yaml_file in sorted(yaml_files):
        try:
            with open(yaml_file, encoding="utf-8") as f:
                command_data = yaml.safe_load(f)
            
            command_id = command_data.get("id", "unknown")
            
            # Validate against schema
            from jsonschema import validate, ValidationError
            
            try:
                validate(instance=command_data, schema=schema)
                success_count += 1
                print(f"✅ {command_id}: Schema validation passed")
            except ValidationError as e:
                failure_count += 1
                errors.append(f"❌ {command_id}: {e.message}")
                errors.append(f"   Path: {list(e.path)}")
        
        except Exception as e:
            failure_count += 1
            errors.append(f"❌ {yaml_file.name}: Unexpected error: {e}")
    
    return success_count, failure_count, errors


def main():
    """运行 Gate B 检查"""
    print("=" * 60)
    print("Gate B: Command Schema 批量校验")
    print("=" * 60)
    print()
    
    success, failure, errors = validate_all_commands()
    
    print()
    print("=" * 60)
    print(f"Results: {success} passed, {failure} failed")
    print("=" * 60)
    
    if errors:
        print("\nErrors:")
        for error in errors:
            print(error)
    
    if failure > 0:
        print("\n❌ Gate B: FAIL - Some commands failed schema validation")
        sys.exit(1)
    else:
        print("\n✅ Gate B: PASS - All commands passed schema validation")
        sys.exit(0)


if __name__ == "__main__":
    main()
