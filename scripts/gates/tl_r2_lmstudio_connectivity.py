#!/usr/bin/env python3
"""
TL-R2-LMSTUDIO: LM Studio Connectivity Gate

Step 4 扩展：验证 LM Studio 本地模型接入的连通性 + 边界正确性

检查：
1. Health Check（connected / model_missing 允许明确报错）
2. Minimal Run（"Say 'ok'." → 返回非空）
3. Diff Valid（DiffVerifier 验证）
4. Power Boundary（wrote_files = False, committed = False）
5. Evidence 生成（outputs/gates/tl_r2_lmstudio/audit/run_tape.jsonl）

🔒 钉子 2：错误必须分类（运维排查必需）
🔒 钉子 3：output_kind 必须断言（Mode System 支点）

运行方式：
    AGENTOS_GATE_MODE=1 python scripts/gates/tl_r2_lmstudio_connectivity.py [repo_root]
"""

import sys
import os
import json
from pathlib import Path
from typing import Dict, Any, Tuple

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agentos.ext.tools import (
    LMStudioAdapter,
    ToolTask,
    DiffVerifier,
    finalize_tool_result,
    finalize_health,
    assert_h2_evidence,
)


def gate_lmstudio_health(adapter: LMStudioAdapter) -> Tuple[bool, str]:
    """
    Gate LMS-A: Health Check
    
    检查：
    - health_check() 返回有效状态
    - 允许的状态：connected / not_configured / unreachable / model_missing
    
    🔒 钉子 2：错误分类断言（运维排查必需）
    """
    try:
        health = adapter.health_check()
        
        # 检查状态是否合法
        allowed_statuses = ["connected", "not_configured", "unreachable", "model_missing"]
        if health.status not in allowed_statuses:
            return False, f"Invalid status '{health.status}'"
        
        # 🔒 钉子 2：强制错误分类
        if health.status != "connected":
            error_category = health.categorize_error()
            
            if health.status == "model_missing":
                # 必须是操作性错误（model 类别）
                if error_category != "model":
                    return False, f"model_missing must be 'model' category, got '{error_category}'"
                return False, f"Model not loaded (category: {error_category}): {health.details} (ACTION: Load a model in LM Studio UI)"
            
            elif health.status == "unreachable":
                # 必须是网络或运行时错误
                if error_category not in ["network", "runtime"]:
                    return False, f"unreachable must be 'network' or 'runtime', got '{error_category}'"
                return False, f"Service unreachable (category: {error_category}): {health.details} (ACTION: Start LM Studio)"
            
            else:
                return False, f"Not configured (category: {error_category}): {health.details}"
        
        # connected 是成功
        return True, f"Health check passed: {health.details}"
        
    except Exception as e:
        return False, f"Health check failed: {e}"


def gate_lmstudio_minimal_run(adapter: LMStudioAdapter, repo_path: Path) -> Tuple[bool, str, Any]:
    """
    Gate LMS-B: Minimal Run
    
    检查：
    - 发送最小 prompt，拿回 ToolResult
    - 检查 diff 字段存在（允许 Mock）
    """
    os.environ["AGENTOS_GATE_MODE"] = "1"
    
    try:
        # 准备最小任务
        task = ToolTask(
            task_id="test_lmstudio",
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


def gate_lmstudio_diff_valid(result: Any) -> Tuple[bool, str]:
    """
    Gate LMS-C: Diff Valid
    
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


def gate_lmstudio_power_boundary(result: Any) -> Tuple[bool, str]:
    """
    Gate LMS-D: Power Boundary
    
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


def gate_lmstudio_result_structure(result: Any) -> Tuple[bool, str]:
    """
    Gate LMS-E: Result Structure
    
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


def run_lmstudio_gate(repo_root: Path) -> Dict[str, Any]:
    """运行 LM Studio Connectivity Gate"""
    
    print("🔒 TL-R2-LMSTUDIO: LM Studio Connectivity Gate")
    print("=" * 60)
    print(f"Repo: {repo_root}\n")
    
    adapter = LMStudioAdapter()
    
    gates = [
        ("LMS-A: Health Check", lambda: gate_lmstudio_health(adapter)),
        ("LMS-B: Minimal Run", lambda: gate_lmstudio_minimal_run(adapter, repo_root)),
        ("LMS-C: Diff Valid", None),  # 需要 result
        ("LMS-D: Power Boundary", None),  # 需要 result
        ("LMS-E: Result Structure", None),  # 需要 result
    ]
    
    results = {}
    all_passed = True
    result_obj = None
    
    # Run A and B first
    for name, gate_func in gates[:2]:
        try:
            if name == "LMS-B: Minimal Run":
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
            ("LMS-C: Diff Valid", lambda: gate_lmstudio_diff_valid(result_obj)),
            ("LMS-D: Power Boundary", lambda: gate_lmstudio_power_boundary(result_obj)),
            ("LMS-E: Result Structure", lambda: gate_lmstudio_result_structure(result_obj)),
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
    """
    生成 Evidence
    
    🔩 H2：使用通用 evidence 层，Gate 禁止自己推断
    """
    health = adapter.health_check()
    
    # 🔩 H2：使用系统级规范（不在 gate 推断）
    health = finalize_health(health)
    
    if result:
        result = finalize_tool_result(result, adapter, health)
    
    evidence = {
        "provider": "lmstudio",
        "health": {
            "status": health.status,
            "details": health.details,
            "checked_at": health.checked_at,
            "error_category": health.error_category  # 🔩 H2：来自 finalize_health
        },
        "gates": gate_results,
        "gate_passed": all_passed
    }
    
    if result:
        evidence["tool_result"] = result.to_dict()
    
    return evidence


def save_evidence(repo_root: Path, evidence: Dict[str, Any]) -> None:
    """
    保存 Evidence 到文件
    
    🔩 H2：断言 evidence 完整性（系统级规范）
    """
    # 🔩 H2：断言（不允许退化）
    passed, errors = assert_h2_evidence(evidence)
    if not passed:
        print(f"\n⚠️  H2 Evidence 不完整:")
        for error in errors:
            print(f"   - {error}")
    
    # 创建输出目录
    output_dir = repo_root / "outputs" / "gates" / "tl_r2_lmstudio"
    audit_dir = output_dir / "audit"
    reports_dir = output_dir / "reports"
    
    audit_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    # 保存 health_summary.json（🔩 H2：包含 error_category）
    health_file = reports_dir / "health_summary.json"
    with open(health_file, "w", encoding="utf-8") as f:
        json.dump({
            "provider": evidence["provider"],
            "status": evidence["health"]["status"],
            "checked_at": evidence["health"]["checked_at"],
            "details": evidence["health"]["details"],
            "error_category": evidence["health"]["error_category"],  # 🔩 H2
            "gate_passed": evidence["gate_passed"]
        }, f, indent=2)
    
    print(f"\n📄 Health summary: {health_file}")
    
    # 保存 gate_results.json
    gate_file = reports_dir / "gate_results.json"
    with open(gate_file, "w", encoding="utf-8") as f:
        json.dump(evidence, f, indent=2)
    
    print(f"📄 Gate results: {gate_file}")
    
    # 保存 run_tape.jsonl（如果有 tool_result）（🔩 H2：覆盖写入，不追加）
    if "tool_result" in evidence:
        tape_file = audit_dir / "run_tape.jsonl"
        with open(tape_file, "w", encoding="utf-8") as f:  # 'w' 覆盖，不是 'a'
            f.write(json.dumps(evidence["tool_result"]) + "\n")
        
        print(f"📄 Run tape: {tape_file}")
    
    # 🔩 H2：显示断言结果
    if passed:
        print("✅ H2 Evidence 完整性检查通过")
    else:
        print("❌ H2 Evidence 完整性检查失败")


def main():
    repo_root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    
    if not repo_root.exists():
        print(f"❌ Error: Repository not found: {repo_root}")
        sys.exit(1)
    
    results = run_lmstudio_gate(repo_root)
    
    sys.exit(0 if results["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
