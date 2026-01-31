#!/usr/bin/env python3
"""
TL-R2-OKIND-N1: output_kind ↔ Diff Verifier Binding Gate

🔩 H3：防止模式软化的核心钉子（Negative Gate）

Purpose:
    Enforce strict semantic consistency between output_kind and diff content.
    This is the core nail preventing "mode softening" in Mode System.

Hard Rules:
    1. output_kind == "diff" → diff must be non-empty + DiffVerifier.is_valid == true
    2. output_kind != "diff" → diff must be empty (no smuggling)
    3. Evidence chain must record output_kind + diff_validation summary

Assertions:
    - LMS-OK1: output_kind 声明正确
    - LMS-OK2: diff 与 output_kind 语义一致
    - LMS-OK3: DiffVerifier 绑定验证通过

Evidence:
    - outputs/gates/tl_r2_okind_n1/audit/run_tape.jsonl
    - outputs/gates/tl_r2_okind_n1/reports/gate_results.json

Usage:
    AGENTOS_GATE_MODE=1 python scripts/gates/tl_r2_okind_n1.py
"""

import sys
from pathlib import Path
import json
from datetime import datetime, timezone

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agentos.ext.tools import (
    LMStudioAdapter,
    ToolTask,
    DiffVerifier,
    finalize_tool_result,
    finalize_health,
    assert_h3_output_kind,
    create_diff_validation_summary,  # 🔩 H3-1
)


def gate_okind_declaration(adapter, result) -> tuple[bool, str]:
    """
    LMS-OK1: output_kind 声明正确
    
    Assertion:
        - output_kind 必须在枚举中
        - output_kind 默认为 "diff"（实施模式）
    """
    valid_kinds = ["diff", "plan", "analysis", "explanation", "diagnosis"]
    
    if result.output_kind not in valid_kinds:
        return False, f"output_kind='{result.output_kind}' is not in {valid_kinds}"
    
    return True, f"output_kind='{result.output_kind}' is valid"


def gate_okind_semantic_consistency(adapter, result, diff_verifier) -> tuple[bool, str]:
    """
    LMS-OK2: diff 与 output_kind 语义一致
    
    Assertion:
        - output_kind == "diff" → diff 非空
        - output_kind != "diff" → diff 为空
    """
    if result.output_kind == "diff":
        # 规则1：实施模式必须有 diff
        if not result.diff or result.diff.strip() == "":
            return False, (
                f"output_kind='diff' but diff is empty. "
                f"Implementation mode requires non-empty diff."
            )
        
        return True, f"output_kind='diff' and diff is non-empty (length={len(result.diff)})"
    
    else:
        # 规则2：非实施模式禁止 diff（防夹带）
        if result.diff and result.diff.strip() != "":
            return False, (
                f"output_kind='{result.output_kind}' but diff is not empty (length={len(result.diff)}). "
                f"Non-diff modes cannot produce diffs (power boundary violation)."
            )
        
        return True, f"output_kind='{result.output_kind}' and diff is empty (correct)"


def gate_okind_diff_verifier_binding(adapter, task, result, diff_verifier) -> tuple[bool, str]:
    """
    LMS-OK3: DiffVerifier 绑定验证通过
    
    Assertion:
        - 如果 output_kind == "diff"，DiffVerifier.is_valid 必须为 true
        - 如果 output_kind != "diff"，跳过验证
    """
    if result.output_kind != "diff":
        return True, f"output_kind='{result.output_kind}', DiffVerifier not applicable"
    
    # output_kind == "diff"，必须验证
    validation = diff_verifier.verify(result, task.allowed_paths, task.forbidden_paths)
    
    if not validation.is_valid:
        return False, (
            f"output_kind='diff' but DiffVerifier rejected: {validation.error_message}"
        )
    
    return True, (
        f"output_kind='diff' and DiffVerifier valid "
        f"(warnings: {len(validation.warnings)})"
    )


def run_lmstudio_okind_gate(repo_root: Path) -> tuple[bool, dict]:
    """
    运行 TL-R2-OKIND-N1 Gate（基于 LM Studio adapter）
    
    Returns:
        (all_passed, gate_results)
    """
    print("🔩 TL-R2-OKIND-N1: output_kind ↔ Diff Verifier Binding Gate")
    print("=" * 60)
    print(f"Repo: {repo_root}\n")
    
    # 初始化
    adapter = LMStudioAdapter()
    diff_verifier = DiffVerifier()
    
    # 最小任务（生成 diff）
    task = ToolTask(
        task_id="okind-test-1",
        instruction="Generate a simple README diff to test output_kind=diff validation. Add one line to README.md.",
        repo_path=str(repo_root),
        allowed_paths=["README.md", "docs/**"]
    )
    
    # 运行 adapter
    print("Running minimal task...")
    result = adapter.run(task)
    
    # 🔩 H2 + H3：使用系统级规范
    health = finalize_health(adapter.health_check())
    result = finalize_tool_result(result, adapter, health=health, task=task)
    
    # 🔩 H3-1：运行 DiffVerifier 并填充 diff_validation
    if result.output_kind == "diff" and result.diff:
        validation = diff_verifier.verify(result, task.allowed_paths, task.forbidden_paths)
        result.diff_validation = create_diff_validation_summary(validation)
    
    print(f"Result: status={result.status}, output_kind={result.output_kind}, "
          f"diff_length={len(result.diff) if result.diff else 0}")
    if result.diff_validation:
        print(f"Diff Validation: is_valid={result.diff_validation['is_valid']}, "
              f"errors={result.diff_validation['errors_count']}, "
              f"warnings={result.diff_validation['warnings_count']}\n")
    else:
        print()
    
    # Sub-gates
    gate_results = {}
    
    # OK1: output_kind 声明
    passed, reason = gate_okind_declaration(adapter, result)
    gate_results["LMS-OK1"] = {"passed": passed, "reason": reason}
    print(f"{'✅ PASS' if passed else '❌ FAIL'} - LMS-OK1: output_kind Declaration")
    print(f"      {reason}")
    
    # OK2: 语义一致性
    passed, reason = gate_okind_semantic_consistency(adapter, result, diff_verifier)
    gate_results["LMS-OK2"] = {"passed": passed, "reason": reason}
    print(f"{'✅ PASS' if passed else '❌ FAIL'} - LMS-OK2: Semantic Consistency")
    print(f"      {reason}")
    
    # OK3: DiffVerifier 绑定
    passed, reason = gate_okind_diff_verifier_binding(adapter, task, result, diff_verifier)
    gate_results["LMS-OK3"] = {"passed": passed, "reason": reason}
    print(f"{'✅ PASS' if passed else '❌ FAIL'} - LMS-OK3: DiffVerifier Binding")
    print(f"      {reason}")
    
    # 汇总
    all_passed = all(g["passed"] for g in gate_results.values())
    passed_count = sum(1 for g in gate_results.values() if g["passed"])
    total_count = len(gate_results)
    
    print("\n" + "=" * 60)
    
    # Evidence
    evidence = {
        "provider": "lmstudio",
        "gate": "TL-R2-OKIND-N1",
        "purpose": "output_kind ↔ Diff Verifier Binding (H3)",
        "health": {
            "status": health.status,
            "details": health.details,
            "checked_at": health.checked_at,
            "error_category": health.error_category
        },
        "tool_result": result.to_dict(),
        "gates": gate_results,
        "gate_passed": all_passed
    }
    
    # 🔩 H3：断言 output_kind
    h3_passed, h3_errors = assert_h3_output_kind(evidence)
    if not h3_passed:
        print("\n⚠️  H3 output_kind 绑定不一致:")
        for error in h3_errors:
            print(f"   - {error}")
    else:
        print("✅ H3 output_kind 绑定验证通过")
    
    # 保存 evidence
    save_evidence(repo_root, evidence)
    
    if all_passed:
        print(f"✅ All gates passed ({passed_count}/{total_count})")
    else:
        print(f"❌ Some gates failed ({passed_count}/{total_count})")
    
    return all_passed, evidence


def save_evidence(repo_root: Path, evidence: dict) -> None:
    """
    保存 Evidence 到文件
    
    🔩 H3：断言 output_kind 完整性
    """
    # 创建输出目录
    output_dir = repo_root / "outputs" / "gates" / "tl_r2_okind_n1"
    audit_dir = output_dir / "audit"
    reports_dir = output_dir / "reports"
    
    audit_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    # 保存 gate_results.json
    gate_file = reports_dir / "gate_results.json"
    with open(gate_file, "w", encoding="utf-8") as f:
        json.dump(evidence, f, indent=2)
    
    print(f"\n📄 Gate results: {gate_file}")
    
    # 保存 run_tape.jsonl（🔩 H3：包含 output_kind + diff_validation）
    if "tool_result" in evidence:
        tape_file = audit_dir / "run_tape.jsonl"
        with open(tape_file, "w", encoding="utf-8") as f:
            f.write(json.dumps(evidence["tool_result"]) + "\n")
        
        print(f"📄 Run tape: {tape_file}")


def main():
    """Main entry point"""
    repo_root = Path(__file__).parent.parent.parent
    
    try:
        all_passed, evidence = run_lmstudio_okind_gate(repo_root)
        sys.exit(0 if all_passed else 1)
    except Exception as e:
        print(f"\n❌ Gate execution failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(2)


if __name__ == "__main__":
    main()
