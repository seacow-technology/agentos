#!/usr/bin/env python3
"""
EX Gate B - Executor Schema 验证

验证所有Executor schemas的有效性
"""

import sys
import json
from pathlib import Path
import jsonschema

EXIT_CODE = 0
PROJECT_ROOT = Path(__file__).parent.parent.parent


def validate_schema_file(schema_path: Path, schema_name: str):
    """验证单个schema文件"""
    global EXIT_CODE
    
    try:
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
        
        # 验证是否是有效的JSON Schema
        # 使用Draft 2020-12 validator
        from jsonschema import Draft202012Validator
        Draft202012Validator.check_schema(schema)
        
        print(f"✓ {schema_name}: Valid JSON Schema")
        return True
        
    except json.JSONDecodeError as e:
        print(f"✗ {schema_name}: Invalid JSON - {e}")
        EXIT_CODE = 1
        return False
    except jsonschema.SchemaError as e:
        print(f"✗ {schema_name}: Invalid Schema - {e}")
        EXIT_CODE = 1
        return False
    except Exception as e:
        print(f"✗ {schema_name}: Error - {e}")
        EXIT_CODE = 1
        return False


def main():
    global EXIT_CODE
    
    print("=" * 60)
    print("EX Gate B - Executor Schema Validation")
    print("=" * 60)
    print()
    
    schemas = [
        ("agentos/schemas/executor/execution_request.schema.json", "Execution Request"),
        ("agentos/schemas/executor/execution_result.schema.json", "Execution Result"),
        ("agentos/schemas/executor/run_tape.schema.json", "Run Tape"),
        ("agentos/schemas/executor/sandbox_policy.schema.json", "Sandbox Policy"),
    ]
    
    for schema_file, schema_name in schemas:
        schema_path = PROJECT_ROOT / schema_file
        if schema_path.exists():
            validate_schema_file(schema_path, schema_name)
        else:
            print(f"✗ {schema_name}: File not found")
            EXIT_CODE = 1
    
    print()
    print("=" * 60)
    if EXIT_CODE == 0:
        print("✅ EX Gate B: ALL SCHEMAS VALID")
    else:
        print("❌ EX Gate B: SCHEMA VALIDATION FAILED")
    print("=" * 60)
    
    return EXIT_CODE


if __name__ == "__main__":
    sys.exit(main())
