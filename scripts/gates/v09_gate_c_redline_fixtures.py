#!/usr/bin/env python3
"""Gate C: 红线负向 Fixtures 测试 (v0.9 Rules)

验证:
1. 4 个负向 fixtures 存在
2. 每个 fixture 被 RuleRedlineValidator 正确拒绝

用法:
    uv run python scripts/gates/v09_gate_c_redline_fixtures.py
"""

import sys
from pathlib import Path

# Add agentos to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def test_redline_fixtures():
    """测试红线 fixtures 是否被正确拒绝"""
    print("Testing redline fixtures...")
    
    try:
        from agentos.core.gates.validate_rule_redlines import RuleRedlineValidator, RuleRedlineViolation
        import yaml
        
        validator = RuleRedlineValidator()
        
        # Expected fixtures (each violates a specific red line)
        fixtures = [
            ("rule_has_execute_field.yaml", "RL1", "execution field"),
            ("rule_missing_evidence_required.yaml", "RL2", "evidence_required empty"),
            ("rule_missing_lineage.yaml", "RL5", "lineage missing"),
            ("rule_unstructured_when_then.yaml", "RL3", "unstructured when/then"),
        ]
        
        fixtures_dir = Path("fixtures/rules/invalid")
        if not fixtures_dir.exists():
            print(f"  ❌ Fixtures directory not found: {fixtures_dir}")
            return False
        
        all_passed = True
        
        for filename, redline, description in fixtures:
            fixture_path = fixtures_dir / filename
            
            if not fixture_path.exists():
                print(f"  ❌ Fixture not found: {filename}")
                all_passed = False
                continue
            
            try:
                with open(fixture_path, encoding="utf-8") as f:
                    rule_data = yaml.safe_load(f)
                
                # Try to validate - should raise RuleRedlineViolation
                validator.validate(rule_data)
                
                # If we get here, validation passed (but it shouldn't!)
                print(f"  ❌ {filename}: Expected {redline} violation ({description}), but validation passed")
                all_passed = False
                
            except RuleRedlineViolation as e:
                # Check if correct red line was triggered
                error_message = str(e)
                if redline in error_message:
                    print(f"  ✅ {filename}: Correctly rejected ({redline}: {description})")
                else:
                    print(f"  ⚠️  {filename}: Rejected, but wrong red line (expected {redline})")
                    print(f"     Error: {error_message}")
                    all_passed = False
            except Exception as e:
                print(f"  ❌ {filename}: Unexpected error: {e}")
                all_passed = False
        
        return all_passed
        
    except Exception as e:
        print(f"  ❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行 Gate C 检查"""
    print("=" * 60)
    print("Gate C: 红线负向 Fixtures 测试 (v0.9)")
    print("=" * 60)
    print()
    
    if test_redline_fixtures():
        print()
        print("=" * 60)
        print("✅ Gate C: PASS - All fixtures correctly rejected")
        print("=" * 60)
        sys.exit(0)
    else:
        print()
        print("=" * 60)
        print("❌ Gate C: FAIL - Fixture validation issues found")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()
