#!/usr/bin/env python3
"""
Step 1 Gates: Answer Resume Gates

Gate A1: Blocked must stop - BLOCKED 状态不产生后续产物
Gate A2: Resume must continue - Resume 后产生完整产物
Gate A3: AnswerPack coverage - Evidence refs 不下降
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, List


def gate_a1_blocked_must_stop(run_dir: Path) -> tuple[bool, str]:
    """
    Gate A1: BLOCKED 状态必须停止，不产生后续产物
    
    检查：
    - status.json 标记为 BLOCKED
    - 不存在 02_dryrun/exec_request.json
    - 不存在 03_executor/ 目录
    """
    status_file = run_dir / "01_intent" / "status.json"
    if not status_file.exists():
        return False, "Missing status.json"
    
    with open(status_file, "r", encoding="utf-8") as f:
        status = json.load(f)
    
    if status.get("status") != "BLOCKED":
        return False, f"Status is {status.get('status')}, expected BLOCKED"
    
    # 检查不应存在后续产物
    if (run_dir / "02_dryrun" / "exec_request.json").exists():
        return False, "exec_request.json exists (should not when BLOCKED)"
    
    if (run_dir / "03_executor").exists():
        return False, "03_executor/ exists (should not when BLOCKED)"
    
    return True, "BLOCKED status correctly stops pipeline"


def gate_a2_resume_must_continue(run_dir: Path) -> tuple[bool, str]:
    """
    Gate A2: Resume 后必须产生完整产物
    
    检查：
    - status.json 标记为 RESUMED
    - 存在 answer_pack.json
    - 存在 02_dryrun/exec_request.json
    - 存在 03_executor/sandbox_proof.json
    - 存在 resume_audit.jsonl 且包含 RESUMED 事件
    """
    status_file = run_dir / "01_intent" / "status.json"
    if not status_file.exists():
        return False, "Missing status.json"
    
    with open(status_file, "r", encoding="utf-8") as f:
        status = json.load(f)
    
    if status.get("status") != "RESUMED":
        return False, f"Status is {status.get('status')}, expected RESUMED"
    
    # 检查 answer_pack
    answer_pack_file = run_dir / "01_intent" / "answer_pack.json"
    if not answer_pack_file.exists():
        return False, "Missing answer_pack.json"
    
    # 检查后续产物存在
    if not (run_dir / "02_dryrun" / "exec_request.json").exists():
        return False, "Missing 02_dryrun/exec_request.json"
    
    if not (run_dir / "03_executor" / "sandbox_proof.json").exists():
        return False, "Missing 03_executor/sandbox_proof.json"
    
    # 检查审计日志
    audit_file = run_dir / "resume_audit.jsonl"
    if not audit_file.exists():
        return False, "Missing resume_audit.jsonl"
    
    with open(audit_file, "r", encoding="utf-8") as f:
        audit_log = [json.loads(line) for line in f]
    
    resumed_events = [e for e in audit_log if e.get("event") == "RESUME_APPLIED"]
    if not resumed_events:
        return False, "Missing RESUME_APPLIED event in audit log"
    
    return True, "Resume correctly produces all artifacts"


def gate_a3_answer_pack_coverage(run_dir: Path) -> tuple[bool, str]:
    """
    Gate A3: AnswerPack coverage - Evidence refs 不下降
    
    检查：
    - 每个 question 都有 answer
    - 每个 answer 都有 evidence_refs
    - evidence_refs 数量 >= question 的 min_evidence（如果有）
    """
    question_pack_file = run_dir / "01_intent" / "question_pack.json"
    answer_pack_file = run_dir / "01_intent" / "answer_pack.json"
    
    if not question_pack_file.exists():
        return False, "Missing question_pack.json"
    
    if not answer_pack_file.exists():
        return False, "Missing answer_pack.json"
    
    with open(question_pack_file, "r", encoding="utf-8") as f:
        question_pack = json.load(f)
    
    with open(answer_pack_file, "r", encoding="utf-8") as f:
        answer_pack = json.load(f)
    
    questions = question_pack.get("questions", [])
    answers = {a["question_id"]: a for a in answer_pack.get("answers", [])}
    
    errors = []
    
    for question in questions:
        q_id = question["question_id"]
        
        # 检查是否有 answer
        if q_id not in answers:
            errors.append(f"Missing answer for {q_id}")
            continue
        
        answer = answers[q_id]
        
        # 检查 evidence_refs
        evidence_refs = answer.get("evidence_refs", [])
        if not evidence_refs:
            errors.append(f"No evidence_refs for {q_id}")
            continue
        
        # 检查数量（如果 question 有 min_evidence 要求）
        min_evidence = question.get("min_evidence", 1)
        if len(evidence_refs) < min_evidence:
            errors.append(f"{q_id}: evidence_refs count {len(evidence_refs)} < min {min_evidence}")
    
    if errors:
        return False, f"Coverage issues: {'; '.join(errors)}"
    
    return True, f"All {len(questions)} questions have adequate evidence"


def run_gates(run_dir: Path) -> Dict[str, Any]:
    """运行所有 gates"""
    gates = [
        ("A1: Blocked must stop", gate_a1_blocked_must_stop),
        ("A2: Resume must continue", gate_a2_resume_must_continue),
        ("A3: AnswerPack coverage", gate_a3_answer_pack_coverage)
    ]
    
    results = {}
    all_passed = True
    
    print("🔒 Step 1 Answer Resume Gates")
    print("=" * 60)
    print(f"Run directory: {run_dir}\n")
    
    for name, gate_func in gates:
        try:
            passed, message = gate_func(run_dir)
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
    if len(sys.argv) < 2:
        print("Usage: python step1_answer_resume_gates.py <run_directory>")
        sys.exit(1)
    
    run_dir = Path(sys.argv[1])
    
    if not run_dir.exists():
        print(f"❌ Error: Run directory not found: {run_dir}")
        sys.exit(1)
    
    results = run_gates(run_dir)
    
    # 保存结果
    output_file = run_dir / "gate_results_step1.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    
    print(f"\nResults saved to: {output_file}")
    
    sys.exit(0 if results["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
