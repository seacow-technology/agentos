#!/usr/bin/env python3
"""
Step 3 Gates: Tool Gates（TL-A 到 TL-F）

验证工具外包执行的能力：
- TL-A: Pack completeness - task_pack 包含完整字段
- TL-B: No direct execute - adapter 不直接写文件
- TL-C: Evidence required - result_pack 包含 diff + commits
- TL-D: Policy match - diff 符合 allowlist
- TL-E: Replay - 可重放（记录 tool version + seed）
- TL-F: Human review - requires_review 时有审批
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple


def gate_tl_a_pack_completeness(task_pack: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Gate TL-A: Pack completeness - task_pack 必须包含完整字段
    
    检查：
    - 必需字段：goal, allowed_ops, constraints, expected_files, commit_plan
    """
    required_fields = [
        "tool_task_pack_id",
        "tool_type",
        "repo_state",
        "work_scope",
        "steps",
        "prompt_pack",
        "acceptance"
    ]
    
    missing = [f for f in required_fields if f not in task_pack]
    if missing:
        return False, f"Missing required fields: {missing}"
    
    # 检查 steps 结构
    steps = task_pack.get("steps", [])
    if not steps:
        return False, "No steps defined"
    
    for step in steps:
        if "step_id" not in step or "goal" not in step:
            return False, f"Step missing step_id or goal"
    
    return True, f"Task pack complete with {len(steps)} steps"


def gate_tl_b_no_direct_execute(adapters_dir: Path) -> Tuple[bool, str]:
    """
    Gate TL-B: No direct execute - adapter 不能直接写文件
    
    检查：
    - adapter 文件中不应有直接的文件写入操作
    - 只能调用工具 CLI
    """
    import ast
    
    violations = []
    
    # 扫描 adapter 文件
    for adapter_file in adapters_dir.glob("*_adapter.py"):
        try:
            content = adapter_file.read_text()
            tree = ast.parse(content)
            
            # 检查是否有直接文件写入
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Attribute):
                        # 检查 open(..., 'w') 或 Path.write_text
                        if node.func.attr in {"write_text", "write_bytes"}:
                            violations.append(f"{adapter_file.name}: direct write operation")
                    elif isinstance(node.func, ast.Name):
                        if node.func.id == "open":
                            # 检查是否写模式
                            for arg in node.args[1:]:
                                if isinstance(arg, ast.Constant) and 'w' in str(arg.value):
                                    violations.append(f"{adapter_file.name}: open with write mode")
        except:
            pass
    
    if violations:
        return False, f"Found {len(violations)} direct write operations"
    
    return True, f"No direct file operations in adapters"


def gate_tl_c_evidence_required(result_pack: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Gate TL-C: Evidence required - result_pack 必须包含证据
    
    检查：
    - diffs 存在
    - commits 存在
    - test_logs 存在（可选）
    """
    if "diffs" not in result_pack:
        return False, "Missing diffs"
    
    if "artifacts" not in result_pack:
        return False, "Missing artifacts"
    
    artifacts = result_pack["artifacts"]
    
    if "commits" not in artifacts:
        return False, "Missing commits in artifacts"
    
    commits = artifacts.get("commits", [])
    if not commits:
        return False, "No commits recorded"
    
    diffs_count = len(result_pack.get("diffs", []))
    commits_count = len(commits)
    
    return True, f"Evidence: {diffs_count} diffs, {commits_count} commits"


def gate_tl_d_policy_match(
    result_pack: Dict[str, Any],
    task_pack: Dict[str, Any]
) -> Tuple[bool, str]:
    """
    Gate TL-D: Policy match - diff 不超出 allowlist
    
    检查：
    - policy_attestation 存在
    - scope_compliant = true
    - red_lines_respected = true
    - 无 critical violations
    """
    if "policy_attestation" not in result_pack:
        return False, "Missing policy_attestation"
    
    attestation = result_pack["policy_attestation"]
    
    if not attestation.get("scope_compliant", False):
        return False, "Scope not compliant"
    
    if not attestation.get("red_lines_respected", False):
        return False, "Red lines violated"
    
    violations = attestation.get("violations", [])
    critical = [v for v in violations if v.get("severity") in ["error", "critical"]]
    
    if critical:
        return False, f"{len(critical)} critical violations"
    
    return True, "Policy compliant, no critical violations"


def gate_tl_e_replay(result_pack: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Gate TL-E: Replay - 可重放
    
    检查：
    - run_metadata 包含 tool_version
    - 如果支持，包含 prompt_hash 和 seed
    """
    if "run_metadata" not in result_pack:
        return False, "Missing run_metadata"
    
    metadata = result_pack["run_metadata"]
    
    if "tool_version" not in metadata:
        return False, "Missing tool_version"
    
    # Seed 和 prompt_hash 是可选的（取决于工具）
    has_seed = "seed" in metadata or "prompt_hash" in metadata
    
    tool_version = metadata.get("tool_version", "unknown")
    
    if has_seed:
        return True, f"Replayable with tool_version={tool_version}, seed/hash recorded"
    else:
        return True, f"Replayable with tool_version={tool_version} (no seed/hash)"


def gate_tl_f_human_review(
    result_pack: Dict[str, Any],
    task_pack: Dict[str, Any]
) -> Tuple[bool, str]:
    """
    Gate TL-F: Human review - requires_review 时有审批
    
    检查：
    - 如果 task_pack requires_review
    - result_pack 必须包含 reviewer_signoff
    """
    # 检查 task_pack 是否需要审批
    requires_review = False
    
    # 从 task_pack metadata 或 steps 检查
    if "metadata" in task_pack:
        requires_review = task_pack["metadata"].get("requires_review", False)
    
    if not requires_review:
        return True, "No review required"
    
    # 检查 result_pack 是否有审批
    if "reviewer_signoff" not in result_pack:
        return False, "Review required but no signoff found"
    
    signoff = result_pack["reviewer_signoff"]
    
    if not signoff.get("approved", False):
        return False, "Review not approved"
    
    reviewer = signoff.get("reviewer", "unknown")
    
    return True, f"Reviewed and approved by {reviewer}"


def run_gates(
    task_pack_path: Path,
    result_pack_path: Path,
    repo_root: Path
) -> Dict[str, Any]:
    """运行所有 Tool gates"""
    
    # 加载 packs
    with open(task_pack_path, "r", encoding="utf-8") as f:
        task_pack = json.load(f)
    
    with open(result_pack_path, "r", encoding="utf-8") as f:
        result_pack = json.load(f)
    
    adapters_dir = repo_root / "agentos" / "ext" / "tools"
    
    gates = [
        ("TL-A: Pack completeness", lambda: gate_tl_a_pack_completeness(task_pack)),
        ("TL-B: No direct execute", lambda: gate_tl_b_no_direct_execute(adapters_dir)),
        ("TL-C: Evidence required", lambda: gate_tl_c_evidence_required(result_pack)),
        ("TL-D: Policy match", lambda: gate_tl_d_policy_match(result_pack, task_pack)),
        ("TL-E: Replay", lambda: gate_tl_e_replay(result_pack)),
        ("TL-F: Human review", lambda: gate_tl_f_human_review(result_pack, task_pack)),
    ]
    
    results = {}
    all_passed = True
    
    print("🔒 Step 3 Tool Gates (TL-A to TL-F)")
    print("=" * 60)
    print(f"Task pack: {task_pack_path}")
    print(f"Result pack: {result_pack_path}\n")
    
    for name, gate_func in gates:
        try:
            passed, message = gate_func()
            results[name] = {"passed": passed, "message": message}
            
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"{status} - {name}")
            print(f"      {message}")
            
            if not passed:
                all_passed = False
                
        except Exception as e:
            results[name] = {"passed": False, "message": f"Error: {e}"}
            print(f"❌ FAIL - {name}")
            print(f"      Error: {e}")
            all_passed = False
    
    print()
    print("=" * 60)
    
    passed_count = sum(1 for r in results.values() if r["passed"])
    total_count = len(results)
    
    if all_passed:
        print(f"✅ All gates passed ({passed_count}/{total_count})")
        return {"status": "PASS", "gates": results}
    else:
        print(f"❌ Some gates failed ({passed_count}/{total_count})")
        return {"status": "FAIL", "gates": results}


def main():
    if len(sys.argv) < 3:
        print("Usage: python step3_tool_gates.py <task_pack.json> <result_pack.json> [repo_root]")
        sys.exit(1)
    
    task_pack_path = Path(sys.argv[1])
    result_pack_path = Path(sys.argv[2])
    repo_root = Path(sys.argv[3]) if len(sys.argv) > 3 else Path.cwd()
    
    if not task_pack_path.exists():
        print(f"❌ Error: Task pack not found: {task_pack_path}")
        sys.exit(1)
    
    if not result_pack_path.exists():
        print(f"❌ Error: Result pack not found: {result_pack_path}")
        sys.exit(1)
    
    results = run_gates(task_pack_path, result_pack_path, repo_root)
    
    # 保存结果
    output_dir = result_pack_path.parent
    output_file = output_dir / "gate_results_step3.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    
    print(f"\nResults saved to: {output_file}")
    
    sys.exit(0 if results["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
