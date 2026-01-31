#!/usr/bin/env python3
"""
TL-R2-LLAMACPP: llama.cpp Connectivity Gate

Step 4 扩展：验证 llama.cpp server 接入的连通性 + 边界正确性

检查：
1. Health Check（connected / unreachable / schema_mismatch）
2. Minimal Run（"Say 'ok'." → 返回非空）
3. Diff Valid（DiffVerifier 验证）
4. Power Boundary（wrote_files = False, committed = False）
5. Evidence 生成（outputs/gates/tl_r2_llamacpp/audit/run_tape.jsonl）

🔒 钉子 2：错误必须分类（运维排查必需）
🔒 钉子 3：output_kind 必须断言（Mode System 支点）

运行方式：
    AGENTOS_GATE_MODE=1 python scripts/gates/tl_r2_llamacpp_connectivity.py [repo_root]
"""

import sys
import os
import json
from pathlib import Path
from typing import Dict, Any, Tuple

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agentos.ext.tools import LlamaCppAdapter, ToolTask, DiffVerifier


def gate_llamacpp_health(adapter: LlamaCppAdapter) -> Tuple[bool, str]:
    """
    Gate LLC-A: Health Check
    
    检查：
    - health_check() 返回有效状态
    - 允许的状态：connected / unreachable / schema_mismatch
    
    🔒 钉子 2：错误分类断言（运维排查必需）
    """
    try:
        health = adapter.health_check()
        
        # 检查状态是否合法
        allowed_statuses = ["connected", "unreachable", "schema_mismatch", "not_configured"]
        if health.status not in allowed_statuses:
            return False, f"Invalid status '{health.status}'"
        
        # 🔒 钉子 2：强制错误分类
        if health.status != "connected":
            error_category = health.categorize_error()
            
            if health.status == "unreachable":
                # 必须是网络或运行时错误
                if error_category not in ["network", "runtime"]:
                    return False, f"unreachable must be 'network' or 'runtime', got '{error_category}'"
                return False, f"Service unreachable (category: {error_category}): {health.details} (ACTION: Start llama-server)"
            
            elif health.status == "schema_mismatch":
                # 必须是 schema 错误（开发者错误）
                if error_category != "schema":
                    return False, f"schema_mismatch must be 'schema' category, got '{error_category}'"
                return False, f"Schema mismatch (category: {error_category}): {health.details} (ACTION: Check llama.cpp response format)"
            
            else:
                return False, f"Not configured (category: {error_category}): {health.details}"
        
        # connected 是成功
        return True, f"Health check passed: {health.details}"
        
    except Exception as e:
        return False, f"Health check failed: {e}"


def gate_llamacpp_minimal_run(adapter: LlamaCppAdapter, repo_path: Path) -> Tuple[bool, str, Any]:
    """
    Gate LLC-B: Minimal Run
    
    检查：
    - 发送最小 prompt，拿回 ToolResult
    - 检查 diff 字段存在（允许 Mock）
    """
    os.environ["AGENTOS_GATE_MODE"] = "1"
    
    try:
        # 准备最小任务
        task = ToolTask(
            task_id="test_llamacpp",
            instruction="Say 'ok'.",
            repo_path=str(repo_path),
            allowed_paths=["README.md", "*.md"],
            forbidden_paths=[".git/**", ".env"],
            timeout_seconds=30
        )
        
        # 运行（允许 Mock）
        result = adapter.run(task, allow_mock=True)
        
        # 检查 result
        if not hasattr(result, 'diff'):
            return False, "ToolResult missing 'diff' field", None
        
        if not hasattr(result, 'status'):
            return False, "ToolResult missing 'status' field", None
        
        return True, f"Minimal run passed (status: {result.status}, mock: {result._mock_used})", result
        
    except Exception as e:
        return False, f"Run failed: {e}", None


def gate_llamacpp_diff_valid(result: Any) -> Tuple[bool, str]:
    """
    Gate LLC-C: Diff Valid
    
    检查：
    - 如果有 diff，验证格式（使用 DiffVerifier）
    """
    try:
        if not result.diff:
            # Mock 模式可能没有 diff
            if result._mock_used:
                return True, "No diff (mock mode)"
            else:
                return False, "No diff generated (non-mock)"
        
        # 验证 diff 格式
        validation = DiffVerifier.verify(
            result,
            allowed_paths=["README.md"],
            forbidden_paths=[".git/**"]
        )
        
        if not validation.is_valid:
            return False, f"Diff invalid: {validation.errors}"
        
        return True, "Diff validation passed"
        
    except Exception as e:
        return False, f"Diff validation failed: {e}"


def gate_llamacpp_power_boundary(result: Any) -> Tuple[bool, str]:
    """
    Gate LLC-D: Power Boundary
    
    检查：
    - ToolResult.wrote_files == False
    - ToolResult.committed == False
    """
    try:
        # 🔩 钉子 C：权力断点检查
        if result.wrote_files:
            return False, "Tool directly wrote files (violated boundary)"
        
        if result.committed:
            return False, "Tool directly committed (violated boundary)"
        
        return True, "Power boundary respected: no direct writes/commits"
        
    except Exception as e:
        return False, f"Boundary check failed: {e}"


def gate_llamacpp_result_structure(result: Any) -> Tuple[bool, str]:
    """
    Gate LLC-E: Result Structure
    
    检查：
    - ToolResult 包含必需字段
    - 包括 Step 4 新增的 model_id / provider
    
    🔒 钉子 3：output_kind 必须存在（Mode System 支点）
    """
    required_fields = [
        "tool", "status", "diff", "files_touched", "line_count", "tool_run_id",
        "model_id", "provider",  # Step 4 扩展
        "output_kind"  # 🔒 钉子 3：Mode System 必需
    ]
    
    try:
        for field in required_fields:
            if not hasattr(result, field):
                return False, f"ToolResult missing field '{field}'"
        
        # 检查 provider 是否合法
        if result.provider not in ["cloud", "local", None]:
            return False, f"Invalid provider '{result.provider}'"
        
        # 🔒 钉子 3：检查 output_kind 是否合法
        allowed_output_kinds = ["diff", "plan", "analysis", "explanation", "diagnosis"]
        if result.output_kind not in allowed_output_kinds:
            return False, f"Invalid output_kind '{result.output_kind}', must be one of {allowed_output_kinds}"
        
        # 🔒 钉子 3：实施模式必须是 diff
        if result.output_kind != "diff":
            return False, f"Implementation mode requires output_kind='diff', got '{result.output_kind}'"
        
        return True, f"Result structure valid: all required fields present, output_kind={result.output_kind}"
        
    except Exception as e:
        return False, f"Structure check failed: {e}"


def run_llamacpp_gate(repo_root: Path) -> Dict[str, Any]:
    """运行 llama.cpp Connectivity Gate"""
    
    print("🔒 TL-R2-LLAMACPP: llama.cpp Connectivity Gate")
    print("=" * 60)
    print(f"Repo: {repo_root}\n")
    
    adapter = LlamaCppAdapter()
    
    gates = [
        ("LLC-A: Health Check", lambda: gate_llamacpp_health(adapter)),
        ("LLC-B: Minimal Run", lambda: gate_llamacpp_minimal_run(adapter, repo_root)),
        ("LLC-C: Diff Valid", None),  # 需要 result
        ("LLC-D: Power Boundary", None),  # 需要 result
        ("LLC-E: Result Structure", None),  # 需要 result
    ]
    
    results = {}
    all_passed = True
    result_obj = None
    
    # Run A and B first
    for name, gate_func in gates[:2]:
        try:
            if name == "LLC-B: Minimal Run":
                passed, message, result_obj = gate_func()
            else:
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
    
    # Run C, D, E if we have result
    if result_obj:
        remaining_gates = [
            ("LLC-C: Diff Valid", lambda: gate_llamacpp_diff_valid(result_obj)),
            ("LLC-D: Power Boundary", lambda: gate_llamacpp_power_boundary(result_obj)),
            ("LLC-E: Result Structure", lambda: gate_llamacpp_result_structure(result_obj)),
        ]
        
        for name, gate_func in remaining_gates:
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
    
    # Generate evidence
    evidence = generate_evidence(adapter, result_obj, results, all_passed)
    save_evidence(repo_root, evidence)
    
    if all_passed:
        print(f"✅ All gates passed ({passed_count}/{total_count})")
        return {"status": "PASS", "gates": results, "evidence": evidence}
    else:
        print(f"❌ Some gates failed ({passed_count}/{total_count})")
        return {"status": "FAIL", "gates": results, "evidence": evidence}


def generate_evidence(adapter, result, gate_results, all_passed) -> Dict[str, Any]:
    """生成 Evidence"""
    health = adapter.health_check()
    
    evidence = {
        "provider": "llamacpp",
        "health": {
            "status": health.status,
            "details": health.details,
            "checked_at": health.checked_at
        },
        "gates": gate_results,
        "gate_passed": all_passed
    }
    
    if result:
        evidence["tool_result"] = result.to_dict()
    
    return evidence


def save_evidence(repo_root: Path, evidence: Dict[str, Any]) -> None:
    """保存 Evidence 到文件"""
    # 创建输出目录
    output_dir = repo_root / "outputs" / "gates" / "tl_r2_llamacpp"
    audit_dir = output_dir / "audit"
    reports_dir = output_dir / "reports"
    
    audit_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    # 保存 health_summary.json
    health_file = reports_dir / "health_summary.json"
    with open(health_file, "w", encoding="utf-8") as f:
        json.dump({
            "provider": evidence["provider"],
            "status": evidence["health"]["status"],
            "checked_at": evidence["health"]["checked_at"],
            "details": evidence["health"]["details"],
            "gate_passed": evidence["gate_passed"]
        }, f, indent=2)
    
    print(f"\n📄 Health summary: {health_file}")
    
    # 保存 gate_results.json
    gate_file = reports_dir / "gate_results.json"
    with open(gate_file, "w", encoding="utf-8") as f:
        json.dump(evidence, f, indent=2)
    
    print(f"📄 Gate results: {gate_file}")
    
    # 保存 run_tape.jsonl（如果有 tool_result）
    if "tool_result" in evidence:
        tape_file = audit_dir / "run_tape.jsonl"
        with open(tape_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(evidence["tool_result"]) + "\n")
        
        print(f"📄 Run tape: {tape_file}")


def main():
    repo_root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    
    if not repo_root.exists():
        print(f"❌ Error: Repository not found: {repo_root}")
        sys.exit(1)
    
    results = run_llamacpp_gate(repo_root)
    
    sys.exit(0 if results["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
