#!/usr/bin/env python3
"""
Gate GMD1: Design Mode No Diff (Static Assertion)

测试：design mode 禁止 diff（配置级验证）
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.gates._mode_gate_lib import assert_no_diff_mode, write_gate_results


def main():
    wall_start = time.perf_counter()
    
    print("=" * 60)
    print("Gate GMD1: Design Mode No Diff")
    print("=" * 60)
    
    # 执行断言
    internal_start = time.perf_counter()
    all_passed, assertions = assert_no_diff_mode("design")
    internal_duration = (time.perf_counter() - internal_start) * 1000
    
    # 打印结果
    for i, assertion in enumerate(assertions, 1):
        status = "✅ PASS" if assertion["passed"] else "❌ FAIL"
        print(f"\n[Test {i}] {assertion['name']}")
        print(f"{status}: actual={assertion['actual']}")
    
    wall_duration = (time.perf_counter() - wall_start) * 1000
    
    # 写入 evidence
    json_path = write_gate_results(
        gate_id="gmd1_design_no_diff",
        gate_name="Design Mode No Diff (Static Assertion)",
        status="PASS" if all_passed else "FAIL",
        mode_id="design",
        assertions=assertions,
        duration_ms=internal_duration,
        process_wall_time_ms=wall_duration
    )
    
    print("\n" + "=" * 60)
    print(f"{'✅ PASS' if all_passed else '❌ FAIL'}: Gate GMD1 (internal: {internal_duration:.2f}ms, process: {wall_duration:.2f}ms)")
    print(f"📄 Evidence: {json_path}")
    print("=" * 60)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
