#!/usr/bin/env python3
"""
Gate GM1: Non-Implementation Diff Must Fail（最小可签版本）

测试：非 implementation mode 不能 apply diff
"""

import sys
import json
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agentos.core.mode import get_mode, ModeViolationError


def main():
    wall_start = time.perf_counter()
    internal_start = time.perf_counter()
    
    print("=" * 60)
    print("Gate GM1: Non-Implementation Diff Must Fail")
    print("=" * 60)
    
    assertions = []
    all_passed = True
    
    # 测试 1: design mode 不允许 commit
    print("\n[Test 1] design mode 不允许 commit")
    design_mode = get_mode("design")
    allows_commit = design_mode.allows_commit()
    passed = not allows_commit
    assertions.append({
        "name": "design.allows_commit()",
        "expected": False,
        "actual": allows_commit,
        "passed": passed
    })
    if passed:
        print("✅ PASS: design.allows_commit() == False")
    else:
        print("❌ FAIL: design should not allow commit")
        all_passed = False
    
    # 测试 2: chat mode 不允许 diff
    print("\n[Test 2] chat mode 不允许 diff")
    chat_mode = get_mode("chat")
    allows_diff = chat_mode.allows_diff()
    passed = not allows_diff
    assertions.append({
        "name": "chat.allows_diff()",
        "expected": False,
        "actual": allows_diff,
        "passed": passed
    })
    if passed:
        print("✅ PASS: chat.allows_diff() == False")
    else:
        print("❌ FAIL: chat should not allow diff")
        all_passed = False
    
    # 测试 3: implementation mode 允许
    print("\n[Test 3] implementation mode 允许 commit/diff")
    impl_mode = get_mode("implementation")
    impl_commit = impl_mode.allows_commit()
    impl_diff = impl_mode.allows_diff()
    passed = impl_commit and impl_diff
    assertions.append({
        "name": "implementation.allows_commit() and allows_diff()",
        "expected": True,
        "actual": {"commit": impl_commit, "diff": impl_diff},
        "passed": passed
    })
    if passed:
        print("✅ PASS: implementation allows commit and diff")
    else:
        print("❌ FAIL: implementation should allow commit and diff")
        all_passed = False
    
    # 测试 4: ModeViolationError Available
    print("\n[Test 4] ModeViolationError 异常Available")
    try:
        raise ModeViolationError(
            "Test error",
            mode_id="design",
            operation="apply_diff",
            error_category="config"
        )
    except ModeViolationError as e:
        passed = e.mode_id == "design" and e.error_category == "config"
        assertions.append({
            "name": "ModeViolationError exception",
            "expected": {"mode_id": "design", "error_category": "config"},
            "actual": {"mode_id": e.mode_id, "error_category": e.error_category},
            "passed": passed
        })
        if passed:
            print("✅ PASS: ModeViolationError works correctly")
        else:
            print("❌ FAIL: ModeViolationError fields incorrect")
            all_passed = False
    
    internal_duration = (time.perf_counter() - internal_start) * 1000
    wall_duration = (time.perf_counter() - wall_start) * 1000
    
    # 生成 gate_results.json
    output_dir = Path("outputs/gates/gm1_non_impl_diff_denied/reports")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    result = {
        "gate_id": "gm1_non_impl_diff_denied",
        "gate_name": "Non-Implementation Diff Must Fail",
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
    print(f"{'✅ Gate GM1 PASSED' if all_passed else '❌ Gate GM1 FAILED'}")
    print(f"📄 Evidence: {output_dir / 'gate_results.json'}")
    print("=" * 60)
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
