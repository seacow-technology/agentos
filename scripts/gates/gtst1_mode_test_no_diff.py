#!/usr/bin/env python3
"""
Gate GTST1: Test Mode No Diff (Static Assertion)

测试：test mode 禁止 diff 操作
- allows_commit() == False
- allows_diff() == False
- get_required_output_kind() != "diff"
"""

import sys
import json
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agentos.core.mode import get_mode


def save_evidence(gate_id: str, gate_name: str, evidence: dict):
    """保存 evidence 到文件"""
    output_dir = Path(__file__).parent.parent.parent / "outputs" / "gates" / gate_id
    reports_dir = output_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    evidence_file = reports_dir / "gate_results.json"
    with open(evidence_file, "w", encoding="utf-8") as f:
        json.dump(evidence, f, indent=2)
    
    print(f"\n📁 Evidence saved to: {evidence_file}")


def main():
    gate_id = "gtst1_mode_test_no_diff"
    gate_name = "Test Mode No Diff (Static Assertion)"
    mode_id = "test"
    
    print("=" * 60)
    print(f"Gate {gate_id.upper()}: {gate_name}")
    print("=" * 60)
    
    # Wall time: 整个脚本执行时间
    wall_start = time.perf_counter()
    
    # Internal time: 核心逻辑执行时间
    start_time = time.perf_counter()
    assertions = []
    all_passed = True
    
    # Assertion 1: allows_commit() == False
    print(f"\n[Assertion 1] {mode_id}.allows_commit() == False")
    try:
        mode = get_mode(mode_id)
        actual = mode.allows_commit()
        expected = False
        passed = (actual == expected)
        
        if passed:
            print(f"✅ PASS: {mode_id}.allows_commit() == False")
        else:
            print(f"❌ FAIL: expected {expected}, got {actual}")
            all_passed = False
        
        assertions.append({
            "name": f"{mode_id}.allows_commit()",
            "expected": expected,
            "actual": actual,
            "passed": passed
        })
    except Exception as e:
        print(f"❌ FAIL: {e}")
        assertions.append({
            "name": f"{mode_id}.allows_commit()",
            "expected": False,
            "actual": None,
            "passed": False,
            "error": str(e)
        })
        all_passed = False
    
    # Assertion 2: allows_diff() == False
    print(f"\n[Assertion 2] {mode_id}.allows_diff() == False")
    try:
        mode = get_mode(mode_id)
        actual = mode.allows_diff()
        expected = False
        passed = (actual == expected)
        
        if passed:
            print(f"✅ PASS: {mode_id}.allows_diff() == False")
        else:
            print(f"❌ FAIL: expected {expected}, got {actual}")
            all_passed = False
        
        assertions.append({
            "name": f"{mode_id}.allows_diff()",
            "expected": expected,
            "actual": actual,
            "passed": passed
        })
    except Exception as e:
        print(f"❌ FAIL: {e}")
        assertions.append({
            "name": f"{mode_id}.allows_diff()",
            "expected": False,
            "actual": None,
            "passed": False,
            "error": str(e)
        })
        all_passed = False
    
    # Assertion 3: get_required_output_kind() != "diff"
    print(f"\n[Assertion 3] {mode_id}.get_required_output_kind() != 'diff'")
    try:
        mode = get_mode(mode_id)
        actual = mode.get_required_output_kind()
        # 健壮断言：不依赖具体是 "" 还是 None
        passed = (actual != "diff" and actual in ["", None])
        
        if passed:
            print(f"✅ PASS: {mode_id}.get_required_output_kind() = '{actual}' (not 'diff')")
        else:
            print(f"❌ FAIL: expected != 'diff', got '{actual}'")
            all_passed = False
        
        assertions.append({
            "name": f"{mode_id}.get_required_output_kind()",
            "expected": "!= 'diff' (empty or None)",
            "actual": actual,
            "passed": passed
        })
    except Exception as e:
        print(f"❌ FAIL: {e}")
        assertions.append({
            "name": f"{mode_id}.get_required_output_kind()",
            "expected": "!= 'diff'",
            "actual": None,
            "passed": False,
            "error": str(e)
        })
        all_passed = False
    
    # Internal duration: 核心逻辑耗时（3位小数，毫秒）
    elapsed_internal = time.perf_counter() - start_time
    duration_ms_internal = round(elapsed_internal * 1000, 3)
    
    # 保存 evidence（对齐 GM1/GM2 schema）
    evidence = {
        "gate_id": gate_id,
        "gate_name": gate_name,
        "status": "PASS" if all_passed else "FAIL",
        "mode_id": mode_id,
        "assertions": assertions,
        "duration_ms_internal": duration_ms_internal,
        "timestamp": time.time()
    }
    
    save_evidence(gate_id, gate_name, evidence)
    
    # Process wall time: 包含 evidence 落盘的进程内墙钟（2位小数，不含 uv 启动）
    wall_elapsed = time.perf_counter() - wall_start
    process_wall_time_ms = round(wall_elapsed * 1000, 2)
    
    # 补充 process_wall_time 到 evidence（更新文件）
    evidence["process_wall_time_ms"] = process_wall_time_ms
    output_dir = Path(__file__).parent.parent.parent / "outputs" / "gates" / gate_id
    evidence_file = output_dir / "reports" / "gate_results.json"
    with open(evidence_file, "w", encoding="utf-8") as f:
        json.dump(evidence, f, indent=2)
    
    print("\n" + "=" * 60)
    if all_passed:
        print(f"✅ Gate {gate_id.upper()} PASSED (internal: {duration_ms_internal}ms, process_wall: {process_wall_time_ms}ms)")
    else:
        print(f"❌ Gate {gate_id.upper()} FAILED (internal: {duration_ms_internal}ms, process_wall: {process_wall_time_ms}ms)")
    print("=" * 60)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
