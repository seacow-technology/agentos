"""
Mode Gate Helper Library

轻量级工具，仅供 scripts/gates 内部使用，避免代码重复。
不要依赖外部 evidence 系统，保持最小依赖。
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Any


def load_mode(mode_id: str):
    """加载 mode 实例（避免重复 import）"""
    import sys
    from pathlib import Path
    
    # 确保 agentos 在路径中
    project_root = Path(__file__).parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    
    from agentos.core.mode import get_mode
    return get_mode(mode_id)


def assert_no_diff_mode(mode_id: str) -> tuple[bool, List[Dict[str, Any]]]:
    """
    断言非 diff mode（design/planning/debug/chat/ops/test/release）
    
    返回: (all_passed, assertions)
    """
    mode = load_mode(mode_id)
    assertions = []
    all_passed = True
    
    # 断言 1: 不允许 commit
    allows_commit = mode.allows_commit()
    assertions.append({
        "name": f"{mode_id}.allows_commit()",
        "expected": False,
        "actual": allows_commit,
        "passed": not allows_commit
    })
    if allows_commit:
        all_passed = False
    
    # 断言 2: 不允许 diff
    allows_diff = mode.allows_diff()
    assertions.append({
        "name": f"{mode_id}.allows_diff()",
        "expected": False,
        "actual": allows_diff,
        "passed": not allows_diff
    })
    if allows_diff:
        all_passed = False
    
    # 断言 3: required_output_kind 不是 "diff"（允许未来扩展）
    required_kind = mode.get_required_output_kind()
    is_not_diff = required_kind != "diff"
    assertions.append({
        "name": f"{mode_id}.get_required_output_kind()",
        "expected_constraint": "!= 'diff'",
        "actual": required_kind,
        "passed": is_not_diff
    })
    if not is_not_diff:
        all_passed = False
    
    return all_passed, assertions


def write_gate_results(
    gate_id: str,
    gate_name: str,
    status: str,
    mode_id: str,
    assertions: List[Dict[str, Any]],
    duration_ms: float,
    process_wall_time_ms: float
) -> Path:
    """
    写入标准 gate_results.json
    
    duration_ms: gate 逻辑执行时间（内部 perf_counter）
    process_wall_time_ms: 进程内墙钟时间（从 main 到退出）
    
    返回: JSON 文件路径
    """
    output_dir = Path(f"outputs/gates/{gate_id}/reports")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    result = {
        "gate_id": gate_id,
        "gate_name": gate_name,
        "status": status,
        "mode_id": mode_id,
        "assertions": assertions,
        "duration_ms": round(duration_ms, 2),
        "process_wall_time_ms": round(process_wall_time_ms, 2),
        "timestamp": time.time()
    }
    
    json_path = output_dir / "gate_results.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    
    return json_path
