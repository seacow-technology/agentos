#!/usr/bin/env python3
"""Gate C: Command 红线负向 Fixtures 测试

验证:
1. 4 个负向 fixtures 存在（对应 C1-C4 红线）
2. Schema/Validator 正确拒绝这些 fixtures
3. 确保红线强制执行有效

用法:
    uv run python scripts/gates/v08_gate_c_redline_fixtures.py
"""

import sys
from pathlib import Path

import yaml

# Add agentos to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agentos.core.gates.validate_command_redlines import (
    CommandRedlineValidator,
    CommandRedlineViolation,
)


def test_redline_fixtures() -> tuple[int, int, list[str]]:
    """测试红线负向 fixtures

    Returns:
        (correct_rejections, failures, messages)
    """
    fixtures_dir = Path("fixtures/commands/invalid")
    
    if not fixtures_dir.exists():
        return 0, 0, [f"❌ Fixtures directory not found: {fixtures_dir}"]
    
    expected_fixtures = [
        "command_has_executable_payload.yaml",  # C1
        "command_has_agent_binding.yaml",  # C2
        "command_missing_effects.yaml",  # C3
        "command_missing_lineage.yaml",  # C4
    ]
    
    validator = CommandRedlineValidator()
    correct_rejections = 0
    failures = 0
    messages = []
    
    for fixture_name in expected_fixtures:
        fixture_path = fixtures_dir / fixture_name
        
        if not fixture_path.exists():
            failures += 1
            messages.append(f"❌ Fixture not found: {fixture_name}")
            continue
        
        try:
            with open(fixture_path, encoding="utf-8") as f:
                command_data = yaml.safe_load(f)
            
            # Try to validate - should raise CommandRedlineViolation
            try:
                validator.validate(command_data)
                # If we get here, validation passed (bad - should have been rejected)
                failures += 1
                messages.append(
                    f"❌ {fixture_name}: Validation PASSED (should have been REJECTED)"
                )
            except CommandRedlineViolation as e:
                # Expected: validation raised exception
                correct_rejections += 1
                messages.append(f"✅ {fixture_name}: Correctly rejected")
                messages.append(f"   Reason: {str(e)[:100]}...")
        
        except Exception as e:
            failures += 1
            messages.append(f"❌ {fixture_name}: Unexpected error: {e}")
    
    return correct_rejections, failures, messages


def main():
    """运行 Gate C 检查"""
    print("=" * 60)
    print("Gate C: Command 红线负向 Fixtures 测试")
    print("=" * 60)
    print()
    
    correct, failures, messages = test_redline_fixtures()
    
    for msg in messages:
        print(msg)
    
    print()
    print("=" * 60)
    print(f"Results: {correct} correctly rejected, {failures} failures")
    print("=" * 60)
    
    if failures > 0 or correct != 4:
        print("\n❌ Gate C: FAIL - Red line enforcement issues detected")
        sys.exit(1)
    else:
        print("\n✅ Gate C: PASS - All red lines correctly enforced")
        sys.exit(0)


if __name__ == "__main__":
    main()
