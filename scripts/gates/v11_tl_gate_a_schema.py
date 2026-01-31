#!/usr/bin/env python3
"""TL Gate A - Tools Schema验证"""
import sys, json
from pathlib import Path

EXIT_CODE, PROJECT_ROOT = 0, Path(__file__).parent.parent.parent

def main():
    global EXIT_CODE
    print("=" * 60 + "\nTL Gate A - Tools Schema Validation\n" + "=" * 60 + "\n")
    
    schemas = [
        ("agentos/schemas/tools/tool_task_pack.schema.json", "ToolTaskPack"),
        ("agentos/schemas/tools/tool_result_pack.schema.json", "ToolResultPack"),
    ]
    
    for schema_file, name in schemas:
        path = PROJECT_ROOT / schema_file
        if path.exists():
            try:
                with open(path, encoding="utf-8") as f:
                    schema = json.load(f)
                from jsonschema import Draft202012Validator
                Draft202012Validator.check_schema(schema)
                print(f"✓ {name}: Valid")
            except Exception as e:
                print(f"✗ {name}: {e}")
                EXIT_CODE = 1
        else:
            print(f"✗ {name}: Not found")
            EXIT_CODE = 1
    
    print("\n" + "=" * 60)
    print("✅ TL Gate A: PASSED" if EXIT_CODE == 0 else "❌ TL Gate A: FAILED")
    print("=" * 60)
    return EXIT_CODE

if __name__ == "__main__":
    sys.exit(main())
