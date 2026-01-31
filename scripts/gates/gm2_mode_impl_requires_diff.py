#!/usr/bin/env python3
"""
Gate GM2: Implementation Requires Diff（最小可签版本）

测试：implementation mode 必须有 output_kind == "diff"
"""

import sys
import json
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agentos.core.mode import get_mode


def main():
    wall_start = time.perf_counter()
    internal_start = time.perf_counter()
    
    print("=" * 60)
    print("Gate GM2: Implementation Requires Diff")
    print("=" * 60)
    
    assertions = []
    all_passed = True
    
    # 测试 1: implementation 要求 output_kind == "diff"
    print("\n[Test 1] implementation 要求 output_kind == 'diff'")
    impl_mode = get_mode("implementation")
    required = impl_mode.get_required_output_kind()
    passed = required == "diff"
    assertions.append({
        "name": "implementation.get_required_output_kind()",
        "expected": "diff",
        "actual": required,
        "passed": passed
    })
    if passed:
        print(f"✅ PASS: implementation.get_required_output_kind() == 'diff'")
    else:
        print(f"❌ FAIL: Expected 'diff', got '{required}'")
        all_passed = False
    
    # 测试 2: design/chat 禁止 diff (output_kind != "diff")
    print("\n[Test 2] design/chat 禁止 diff")
    for mode_id in ["design", "chat"]:
        mode = get_mode(mode_id)
        required = mode.get_required_output_kind()
        passed = required != "diff"
        assertions.append({
            "name": f"{mode_id}.get_required_output_kind()",
            "expected_constraint": "!= 'diff'",
            "actual": required,
            "passed": passed
        })
        if passed:
            print(f"✅ PASS: {mode_id}.get_required_output_kind() != 'diff' (actual: '{required}')")
        else:
            print(f"❌ FAIL: {mode_id} should not return 'diff', got '{required}'")
            all_passed = False
    
    # 测试 3: 一致性检查（allows_diff 与 output_kind）
    print("\n[Test 3] allows_diff 与 output_kind 一致性")
    for mode_id in ["implementation", "design", "chat", "planning"]:
        mode = get_mode(mode_id)
        allows_diff = mode.allows_diff()
        required = mode.get_required_output_kind()
        
        # 逻辑：allows_diff=True → output_kind="diff"
        #       allows_diff=False → output_kind!="diff"
        if allows_diff:
            passed = required == "diff"
        else:
            passed = required != "diff"
        
        assertions.append({
            "name": f"{mode_id} consistency",
            "expected_logic": "allows_diff=True <=> output_kind='diff'",
            "actual": {"allows_diff": allows_diff, "output_kind": required},
            "passed": passed
        })
        
        if passed:
            print(f"✅ PASS: {mode_id}: allows_diff={allows_diff}, output_kind='{required}'")
        else:
            print(f"❌ FAIL: {mode_id}: inconsistent state")
            all_passed = False
    
    internal_duration = (time.perf_counter() - internal_start) * 1000
    wall_duration = (time.perf_counter() - wall_start) * 1000
    
    # 生成 gate_results.json
    output_dir = Path("outputs/gates/gm2_impl_requires_diff/reports")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    result = {
        "gate_id": "gm2_impl_requires_diff",
        "gate_name": "Implementation Requires Diff",
        "status": "PASS" if all_passed else "FAIL",
        "mode_id": "multiple",
        "assertions": assertions,
        "duration_ms": round(internal_duration, 2),
        "process_wall_time_ms": round(wall_duration, 2),
        "timestamp": time.time()
    }
    
    with open(output_dir / "gate_results.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    
    print("\n" + "=" * 60)
    print(f"{'✅ Gate GM2 PASSED' if all_passed else '❌ Gate GM2 FAILED'}")
    print(f"📄 Evidence: {output_dir / 'gate_results.json'}")
    print("=" * 60)
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
