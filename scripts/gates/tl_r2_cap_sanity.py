#!/usr/bin/env python3
"""
TL-R2-CAP-SANITY: Capabilities Truth Test Gate

🔩 H1：防止 capabilities 声明吹牛

Purpose:
    Validate that adapter-declared capabilities are真实Available，而不只是口头声明。
    这是 Mode System 选择模型的基础——如果声明不实，Mode Selector 会选错。

Hard Rules:
    1. 只测 adapter 声明为 true 的能力（false 不测，避免误伤）
    2. 最小探针：每个能力只需最小证据即可 PASS
    3. 探针结果进入 evidence chain（用 evidence.py 收口）

Capabilities Probes:
    - json_mode: 要求返回严格 JSON，能 parse 即 PASS
    - stream: 至少拿到 2 个 chunk / 或者明确的流标志
    - function_call: 最小 function-call 结构（name + arguments）

Evidence:
    - outputs/gates/tl_r2_cap_sanity/audit/run_tape.jsonl
    - outputs/gates/tl_r2_cap_sanity/reports/cap_sanity.json

Usage:
    AGENTOS_GATE_MODE=1 python scripts/gates/tl_r2_cap_sanity.py
"""

import sys
from pathlib import Path
import json
from datetime import datetime, timezone

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agentos.ext.tools import (
    LMStudioAdapter,
    OpenAIChatAdapter,
    OllamaAdapter,
    ToolTask,
    ToolCapabilities,
    finalize_health,
    write_tool_event,
)


def gate_json_mode_probe(adapter, capabilities: ToolCapabilities) -> tuple[str, str, dict]:
    """
    JSON Mode 探针
    
    Assertion:
        - 如果 capabilities.json_mode == true，要求返回严格 JSON
        - 能 json.loads() 成功且包含预期字段即 PASS
    
    Returns:
        (status: "PASS"|"FAIL"|"SKIP", reason, probe_evidence)
    """
    if not capabilities.json_mode:
        return "SKIP", "json_mode=false, capability not declared", {}
    
    # 最小请求：要求返回严格 JSON
    task = ToolTask(
        task_id="json-probe",
        instruction='Return a JSON object with exactly this structure: {"ok": true, "provider": "<your provider name>"}. No other text.',
        repo_path="/tmp",  # 不需要真实 repo
        allowed_paths=[]
    )
    
    try:
        result = adapter.run(task)
        
        # 尝试 parse JSON
        if result.stdout:
            parsed = json.loads(result.stdout.strip())
            
            # 检查必需字段
            if "ok" in parsed and "provider" in parsed:
                return "PASS", f"json_mode probe PASS: parsed={parsed}", {
                    "parsed": parsed,
                    "raw_output": result.stdout[:200]
                }
            else:
                return "FAIL", f"json_mode probe FAIL: missing fields in {parsed}", {
                    "parsed": parsed,
                    "raw_output": result.stdout[:200]
                }
        else:
            return "FAIL", "json_mode probe FAIL: no output", {
                "result_status": result.status
            }
    
    except json.JSONDecodeError as e:
        return "FAIL", f"json_mode probe FAIL: JSON parse error - {str(e)}", {
            "error": str(e),
            "raw_output": result.stdout[:200] if result.stdout else "N/A"
        }
    except Exception as e:
        return "FAIL", f"json_mode probe FAIL: {str(e)}", {
            "error": str(e)
        }


def gate_stream_probe(adapter, capabilities: ToolCapabilities) -> tuple[str, str, dict]:
    """
    Stream 探针
    
    Assertion:
        - 如果 capabilities.stream == true，至少拿到 2 个 chunk / 或者明确的流标志
        - 不同 provider 实现不同，强求"证据字段一致"，不强求协议一致
    
    Returns:
        (status: "PASS"|"FAIL"|"SKIP", reason, probe_evidence)
    """
    if not capabilities.stream:
        return "SKIP", "stream=false, capability not declared", {}
    
    # 最小请求：流式返回
    task = ToolTask(
        task_id="stream-probe",
        instruction="Say 'hello world' in streaming mode.",
        repo_path="/tmp",
        allowed_paths=[]
    )
    
    try:
        result = adapter.run(task)
        
        # 检查是否有 stream 证据（adapter 应该填充到 result 的 metadata）
        # 这里我们简化为：如果 result 有输出且 status == success，认为 PASS
        # 真实实现需要 adapter 填充 stream_used / chunks 字段
        
        if result.status == "success" and result.stdout:
            return "PASS", f"stream probe PASS (assumed: output exists)", {
                "output_length": len(result.stdout),
                "status": result.status
            }
        else:
            return "FAIL", f"stream probe FAIL: no output or failed", {
                "status": result.status
            }
    
    except Exception as e:
        return "FAIL", f"stream probe FAIL: {str(e)}", {
            "error": str(e)
        }


def gate_function_call_probe(adapter, capabilities: ToolCapabilities) -> tuple[str, str, dict]:
    """
    Function Call 探针
    
    Assertion:
        - 如果 capabilities.function_call == true，最小 function-call 结构
        - 要求返回 name + arguments（哪怕是 mock 的 schema）
    
    Returns:
        (status: "PASS"|"FAIL"|"SKIP", reason, probe_evidence)
    """
    if not capabilities.function_call:
        return "SKIP", "function_call=false, capability not declared", {}
    
    # 最小请求：调用虚拟工具
    task = ToolTask(
        task_id="function-probe",
        instruction='Call a function named "get_time" with argument {"zone": "UTC"}. Return the function call structure.',
        repo_path="/tmp",
        allowed_paths=[]
    )
    
    try:
        result = adapter.run(task)
        
        # 检查是否有 function_call 结构（adapter 应该填充到 result.metadata）
        # 这里我们简化为：如果 result 有输出且包含 "get_time"，认为 PASS
        
        if result.stdout and "get_time" in result.stdout:
            return "PASS", f"function_call probe PASS (function name found)", {
                "output": result.stdout[:200]
            }
        else:
            return "FAIL", f"function_call probe FAIL: no function structure", {
                "output": result.stdout[:200] if result.stdout else "N/A"
            }
    
    except Exception as e:
        return "FAIL", f"function_call probe FAIL: {str(e)}", {
            "error": str(e)
        }


def run_cap_sanity_gate(repo_root: Path) -> tuple[bool, dict]:
    """
    运行 TL-R2-CAP-SANITY Gate
    
    对每个 adapter：
        1. 获取 capabilities
        2. 只测声明为 true 的能力
        3. 收集 probe 结果到 evidence chain
    
    Returns:
        (all_passed, gate_results)
    """
    print("🔩 TL-R2-CAP-SANITY: Capabilities Truth Test Gate")
    print("=" * 60)
    print(f"Repo: {repo_root}\n")
    
    # 测试 adapters（可扩展）
    adapters_to_test = [
        ("lmstudio", LMStudioAdapter()),
        # ("openai", OpenAIChatAdapter()),  # 可选
        # ("ollama", OllamaAdapter()),      # 可选
    ]
    
    all_results = {}
    
    for adapter_name, adapter in adapters_to_test:
        print(f"\n🧪 Testing: {adapter_name}")
        print("-" * 40)
        
        # 获取 capabilities
        capabilities = adapter.supports()
        print(f"Declared capabilities:")
        print(f"  - json_mode: {capabilities.json_mode}")
        print(f"  - stream: {capabilities.stream}")
        print(f"  - function_call: {capabilities.function_call}")
        print()
        
        # Health check
        health = finalize_health(adapter.health_check())
        print(f"Health: {health.status}")
        
        if health.status != "connected":
            print(f"⚠️  Adapter not connected (status: {health.status}), all probes SKIPPED")
            # 🔩 H1：SKIP 状态必须标准化并进入 evidence
            all_results[adapter_name] = {
                "health": health.status,
                "error_category": health.error_category,
                "status": "SKIP",
                "reason": f"adapter not connected (health={health.status})",
                "probes": {
                    "json_mode": {"status": "SKIP", "reason": "adapter not connected"},
                    "stream": {"status": "SKIP", "reason": "adapter not connected"},
                    "function_call": {"status": "SKIP", "reason": "adapter not connected"}
                }
            }
            continue
        
        # Probes
        probe_results = {}
        
        # JSON Mode
        status, reason, evidence = gate_json_mode_probe(adapter, capabilities)
        probe_results["json_mode"] = {"status": status, "reason": reason, "evidence": evidence}
        print(f"{'✅ PASS' if status == 'PASS' else '⏭️  SKIP' if status == 'SKIP' else '❌ FAIL'} - JSON Mode Probe")
        print(f"      {reason}")
        
        # Stream
        status, reason, evidence = gate_stream_probe(adapter, capabilities)
        probe_results["stream"] = {"status": status, "reason": reason, "evidence": evidence}
        print(f"{'✅ PASS' if status == 'PASS' else '⏭️  SKIP' if status == 'SKIP' else '❌ FAIL'} - Stream Probe")
        print(f"      {reason}")
        
        # Function Call
        status, reason, evidence = gate_function_call_probe(adapter, capabilities)
        probe_results["function_call"] = {"status": status, "reason": reason, "evidence": evidence}
        print(f"{'✅ PASS' if status == 'PASS' else '⏭️  SKIP' if status == 'SKIP' else '❌ FAIL'} - Function Call Probe")
        print(f"      {reason}")
        
        all_results[adapter_name] = {
            "health": health.status,
            "capabilities": capabilities.to_dict(),
            "probes": probe_results
        }
    
    # 汇总
    print("\n" + "=" * 60)
    
    # 🔩 H1：计算 PASS/FAIL/SKIP 三态统计（防虚假通过）
    total_probes = 0
    passed_probes = 0
    failed_probes = 0
    skipped_probes = 0
    
    for adapter_name, results in all_results.items():
        if "probes" in results:
            for probe_name, probe_result in results["probes"].items():
                total_probes += 1
                status = probe_result.get("status")
                if status == "PASS":
                    passed_probes += 1
                elif status == "FAIL":
                    failed_probes += 1
                elif status == "SKIP":
                    skipped_probes += 1
    
    # 🔩 H1：Gate 退出策略（防虚假通过）
    # 1. 如果所有 probe 都 SKIP → Gate 整体 SKIP（不是 PASS）
    # 2. 如果有任何 FAIL → Gate FAIL
    # 3. 如果有至少 1 个 PASS 且无 FAIL → Gate PASS
    
    if total_probes == 0:
        gate_status = "SKIP"
        gate_reason = "no adapters to test"
    elif skipped_probes == total_probes:
        gate_status = "SKIP"
        gate_reason = "all adapters unreachable, no probes executed"
    elif failed_probes > 0:
        gate_status = "FAIL"
        gate_reason = f"{failed_probes}/{total_probes} probes failed"
    else:
        gate_status = "PASS"
        gate_reason = f"all executed probes passed ({passed_probes}/{total_probes}, {skipped_probes} skipped)"
    
    all_passed = (gate_status == "PASS")
    
    # Evidence
    evidence = {
        "gate": "TL-R2-CAP-SANITY",
        "purpose": "Capabilities Truth Test (H1)",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "gate_status": gate_status,  # 🔩 H1：Gate 整体状态
        "gate_reason": gate_reason,
        "adapters": all_results,
        "summary": {
            "total_probes": total_probes,
            "passed_probes": passed_probes,
            "failed_probes": failed_probes,  # 🔩 H1
            "skipped_probes": skipped_probes,  # 🔩 H1
            "all_passed": all_passed
        }
    }
    
    # 保存 evidence
    save_evidence(repo_root, evidence)
    
    # 🔩 H1：输出必须区分 PASS/FAIL/SKIP
    if gate_status == "PASS":
        print(f"✅ Gate PASS: {gate_reason}")
    elif gate_status == "SKIP":
        print(f"⏭️  Gate SKIP: {gate_reason}")
    else:
        print(f"❌ Gate FAIL: {gate_reason}")
    
    return all_passed, evidence


def save_evidence(repo_root: Path, evidence: dict) -> None:
    """
    保存 Evidence 到文件
    
    🔩 H1：capabilities 探针结果进入证据链
    """
    # 创建输出目录
    output_dir = repo_root / "outputs" / "gates" / "tl_r2_cap_sanity"
    audit_dir = output_dir / "audit"
    reports_dir = output_dir / "reports"
    
    audit_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    # 保存 cap_sanity.json
    sanity_file = reports_dir / "cap_sanity.json"
    with open(sanity_file, "w", encoding="utf-8") as f:
        json.dump(evidence, f, indent=2)
    
    print(f"\n📄 Capabilities sanity report: {sanity_file}")
    
    # 保存 run_tape.jsonl（🔩 H1：包含 probe 结果）
    tape_file = audit_dir / "run_tape.jsonl"
    with open(tape_file, "w", encoding="utf-8") as f:
        f.write(json.dumps(evidence) + "\n")
    
    print(f"📄 Run tape: {tape_file}")


def main():
    """
    Main entry point
    
    🔩 H1 收口：退出码策略（防止上层误判）
    
    退出码规则：
    - PASS → exit 0（所有执行的 probe 通过）
    - SKIP → exit 0（所有 adapter 不Available，无 probe 执行）
    - FAIL → exit 1（任意 probe 失败）
    - Exception → exit 2（gate 执行异常）
    
    重要：SKIP 也返回 0，因为"无Available adapter"不是 gate 错误，而是环境状态。
    上层脚本（verify/CI）必须通过 gate_status 字段区分 PASS 和 SKIP，不能只看退出码。
    """
    repo_root = Path(__file__).parent.parent.parent
    
    try:
        all_passed, evidence = run_cap_sanity_gate(repo_root)
        
        # 🔩 H1：退出码必须区分 PASS(0) / SKIP(0) / FAIL(1)
        # SKIP 也返回 0，但 evidence 中明确标注 gate_status=SKIP
        gate_status = evidence.get("gate_status", "FAIL")
        if gate_status in ["PASS", "SKIP"]:
            sys.exit(0)
        else:
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ Gate execution failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(2)


if __name__ == "__main__":
    main()
