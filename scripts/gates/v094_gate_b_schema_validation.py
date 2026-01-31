#!/usr/bin/env python3
"""
v0.9.4 Gate B: Schema Batch Validation (冻结级 - 真正验证 v0.9.1 intent)

验证:
- 所有 NL requests 符合 nl_request.schema.json
- 所有 builder outputs 符合 intent_builder_output.schema.json  
- builder output 中的 execution_intent 符合 v0.9.1 intent.schema.json（完整验证）
"""

import json
import sys
from pathlib import Path

try:
    from jsonschema import validate, ValidationError, Draft202012Validator, RefResolver
except ImportError:
    print("❌ jsonschema not installed. Run: uv sync")
    sys.exit(1)

try:
    import yaml
except ImportError:
    print("❌ yaml not installed. Run: uv sync")
    sys.exit(1)

SCHEMA_DIR = Path("agentos/schemas/execution")
NL_DIR = Path("examples/nl")
FIXTURES_DIR = Path("fixtures/intent_builder/invalid")


def load_schema(schema_file):
    """Load JSON schema."""
    with open(schema_file, "r", encoding="utf-8") as f:
        return json.load(f)


def create_schema_resolver(schema_dir):
    """创建 schema resolver 以处理 $ref 引用"""
    # 加载所有 schemas
    schemas = {}
    for schema_file in schema_dir.glob("*.schema.json"):
        schema = load_schema(schema_file)
        schema_id = schema.get("$id", "")
        if schema_id:
            schemas[schema_id] = schema
    
    # 创建 RefResolver
    store = {uri: schema for uri, schema in schemas.items()}
    
    # 获取主 schema URI
    base_uri = "agentos://schemas/execution/"
    
    resolver = RefResolver(base_uri, {}, store=store)
    return resolver


def validate_with_resolver(instance, schema, resolver):
    """使用 resolver 验证 JSON"""
    validator = Draft202012Validator(schema, resolver=resolver)
    errors = list(validator.iter_errors(instance))
    return errors


def main():
    print("=" * 70)
    print("v0.9.4 Gate B: Schema Batch Validation (冻结级)")
    print("=" * 70)
    
    all_valid = True
    
    # 创建 schema resolver
    print(f"\n📦 Creating schema resolver...")
    resolver = create_schema_resolver(SCHEMA_DIR)
    print(f"   ✅ Resolver created with {len(resolver.store)} schemas")
    
    # 加载 schemas
    nl_schema_path = SCHEMA_DIR / "nl_request.schema.json"
    builder_output_schema_path = SCHEMA_DIR / "intent_builder_output.schema.json"
    intent_schema_path = SCHEMA_DIR / "intent.schema.json"
    
    if not nl_schema_path.exists():
        print(f"❌ Schema not found: {nl_schema_path}")
        return False
    
    if not builder_output_schema_path.exists():
        print(f"❌ Schema not found: {builder_output_schema_path}")
        return False
    
    if not intent_schema_path.exists():
        print(f"❌ Schema not found: {intent_schema_path}")
        return False
    
    nl_schema = load_schema(nl_schema_path)
    builder_output_schema = load_schema(builder_output_schema_path)
    intent_schema = load_schema(intent_schema_path)
    
    print(f"\n✅ Loaded schemas successfully")
    
    # 验证 NL requests
    print(f"\n📋 Validating NL requests against {nl_schema_path.name}...")
    
    nl_files = sorted(NL_DIR.glob("*.yaml"))
    if not nl_files:
        print(f"  ⚠️  No NL request files found in {NL_DIR}")
    
    for nl_file in nl_files:
        print(f"\n  Checking {nl_file.name}...")
        try:
            with open(nl_file, "r", encoding="utf-8") as f:
                nl_data = yaml.safe_load(f)
            
            # 验证 schema
            errors = validate_with_resolver(nl_data, nl_schema, resolver)
            
            if errors:
                print(f"    ❌ Schema validation FAILED:")
                for error in errors[:3]:  # Show first 3 errors
                    print(f"       - {error.message}")
                    if error.path:
                        print(f"         Path: {'.'.join(str(p) for p in error.path)}")
                all_valid = False
            else:
                print(f"    ✅ Schema validation PASSED")
                
                # Check required fields
                if "id" in nl_data:
                    print(f"       ID: {nl_data['id']}")
                if "schema_version" in nl_data:
                    print(f"       Version: {nl_data['schema_version']}")
        
        except Exception as e:
            print(f"    ❌ Error: {e}")
            all_valid = False
    
    # 验证 builder outputs（包括嵌套的 intent）
    print(f"\n📋 Validating builder outputs (including v0.9.1 intent)...")
    
    output_files = sorted(Path("examples/builder_outputs").glob("*.json")) if Path("examples/builder_outputs").exists() else []
    if not output_files:
        print(f"  ℹ️  No builder output files found (will be generated on first run)")
    
    for output_file in output_files:
        print(f"\n  Checking {output_file.name}...")
        try:
            with open(output_file, "r", encoding="utf-8") as f:
                output_data = json.load(f)
            
            # 1. 验证 builder output schema
            print(f"    [1/2] Validating builder output schema...")
            errors = validate_with_resolver(output_data, builder_output_schema, resolver)
            
            if errors:
                print(f"        ❌ Builder output schema validation FAILED:")
                for error in errors[:3]:
                    print(f"           - {error.message}")
                all_valid = False
            else:
                print(f"        ✅ Builder output schema PASSED")
            
            # 2. 验证嵌套的 execution_intent (v0.9.1)
            print(f"    [2/2] Validating nested execution_intent (v0.9.1)...")
            if "execution_intent" in output_data:
                intent_data = output_data["execution_intent"]
                intent_errors = validate_with_resolver(intent_data, intent_schema, resolver)
                
                if intent_errors:
                    print(f"        ❌ Intent schema (v0.9.1) validation FAILED:")
                    for error in intent_errors[:3]:
                        print(f"           - {error.message}")
                        if error.path:
                            print(f"             Path: {'.'.join(str(p) for p in error.path)}")
                    all_valid = False
                else:
                    print(f"        ✅ Intent schema (v0.9.1) PASSED")
            else:
                print(f"        ⚠️  No execution_intent field found")
        
        except Exception as e:
            print(f"    ❌ Error: {e}")
            import traceback
            traceback.print_exc()
            all_valid = False
    
    # 验证 invalid fixtures（只检查 JSON 格式正确）
    print(f"\n📋 Validating invalid fixtures (JSON loading)...")
    
    fixture_files = sorted(FIXTURES_DIR.glob("*.json"))
    if not fixture_files:
        print(f"  ⚠️  No fixture files found in {FIXTURES_DIR}")
    
    for fixture_file in fixture_files:
        print(f"\n  Checking {fixture_file.name}...")
        try:
            with open(fixture_file, "r", encoding="utf-8") as f:
                fixture_data = json.load(f)
            
            # Just verify it's valid JSON with basic structure
            if "id" in fixture_data and "schema_version" in fixture_data:
                print(f"    ✅ Valid JSON with basic structure")
            else:
                print(f"    ⚠️  Missing basic fields (id/schema_version)")
        
        except Exception as e:
            print(f"    ❌ Error loading fixture: {e}")
            all_valid = False
    
    # Summary
    print("\n" + "=" * 70)
    if all_valid:
        print("✅ Gate B: PASSED (冻结级 - 包含 v0.9.1 intent 验证)")
        print("=" * 70)
        return True
    else:
        print("❌ Gate B: FAILED")
        print("=" * 70)
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
