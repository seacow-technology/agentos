#!/usr/bin/env python3
"""
TL-R2: Multi-Model Connectivity Gate

Step 4 Runtime 核心验证：
验证多模型接入的连通性 + 边界正确性

检查：
1. health_check() - 每个 adapter 都能正确报告状态
2. minimal_run() - 发送最小 prompt，拿回 diff
3. diff_valid() - diff 格式正确
4. no_direct_write() - Tool 没有直接写 repo
5. result_structure() - ToolResult 字段完整

允许的状态：
- connected（Available）
- not_configured（缺 token / endpoint）
- invalid_token（token 错误）
- unreachable（网络 / 服务不可达）
- model_missing（本地模型不存在）

不允许：
- Tool 直接写文件
- Tool 直接 commit
- diff 格式不正确
- ToolResult 缺少字段
"""

import sys
import os
from pathlib import Path
from typing import Dict, Any, List, Tuple
import tempfile
import subprocess

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agentos.ext.tools import (
    ClaudeCliAdapter,
    OpenAIChatAdapter,
    OllamaAdapter,
    ToolTask,
    DiffVerifier
)


def gate_r2_health_check(adapter_configs: List[Dict[str, Any]]) -> Tuple[bool, str]:
    """
    Gate R2-A: Health Check - 每个 adapter 都能报告健康状态
    
    检查：
    - adapter.health_check() 返回有效状态
    - 允许的状态：connected / not_configured / invalid_token / unreachable / model_missing
    """
    results = []
    
    for config in adapter_configs:
        adapter_name = config["name"]
        adapter = config["adapter"]
        
        try:
            health = adapter.health_check()
            
            # 检查状态是否合法
            allowed_statuses = ["connected", "not_configured", "invalid_token", "unreachable", "model_missing"]
            if health.status not in allowed_statuses:
                return False, f"{adapter_name}: invalid status '{health.status}'"
            
            results.append({
                "adapter": adapter_name,
                "status": health.status,
                "details": health.details
            })
            
        except Exception as e:
            return False, f"{adapter_name}: health_check() failed: {e}"
    
    # 统计
    connected = sum(1 for r in results if r["status"] == "connected")
    total = len(results)
    
    return True, f"Health check passed: {connected}/{total} connected"


def gate_r2_minimal_run(adapter_configs: List[Dict[str, Any]], repo_path: Path) -> Tuple[bool, str]:
    """
    Gate R2-B: Minimal Run - 发送最小 prompt，拿回 diff（或 mock）
    
    检查：
    - 如果 adapter 是 connected，尝试运行最小任务
    - 拿回 ToolResult
    - 检查 diff 字段存在
    
    允许：
    - Mock 模式（Gate 环境）
    - not_configured / unreachable / model_missing 跳过
    """
    results = []
    
    # 设置 Gate 模式（允许 Mock）
    os.environ["AGENTOS_GATE_MODE"] = "1"
    
    for config in adapter_configs:
        adapter_name = config["name"]
        adapter = config["adapter"]
        
        # 先检查健康状态
        health = adapter.health_check()
        
        if health.status != "connected":
            results.append({
                "adapter": adapter_name,
                "skipped": True,
                "reason": f"Not connected ({health.status})"
            })
            continue
        
        try:
            # 准备最小任务
            task = ToolTask(
                task_id=f"test_{adapter_name}",
                instruction="Add a comment to README.md: 'Multi-model connectivity test'",
                repo_path=str(repo_path),
                allowed_paths=["README.md", "*.md"],
                forbidden_paths=[".git/**", ".env"],
                timeout_seconds=30
            )
            
            # 运行（允许 Mock）
            result = adapter.run(task, allow_mock=True)
            
            # 检查 result
            if not hasattr(result, 'diff'):
                return False, f"{adapter_name}: ToolResult missing 'diff' field"
            
            if not hasattr(result, 'status'):
                return False, f"{adapter_name}: ToolResult missing 'status' field"
            
            results.append({
                "adapter": adapter_name,
                "status": result.status,
                "has_diff": bool(result.diff),
                "mock_used": getattr(result, '_mock_used', False)
            })
            
        except Exception as e:
            return False, f"{adapter_name}: run() failed: {e}"
    
    # 统计
    ran = sum(1 for r in results if not r.get("skipped", False))
    skipped = sum(1 for r in results if r.get("skipped", False))
    
    return True, f"Minimal run passed: {ran} ran, {skipped} skipped"


def gate_r2_diff_valid(adapter_configs: List[Dict[str, Any]], repo_path: Path) -> Tuple[bool, str]:
    """
    Gate R2-C: Diff Valid - diff 格式正确
    
    检查：
    - 如果 adapter 产出了 diff，验证格式
    - 使用 DiffVerifier
    """
    os.environ["AGENTOS_GATE_MODE"] = "1"
    
    results = []
    
    for config in adapter_configs:
        adapter_name = config["name"]
        adapter = config["adapter"]
        
        health = adapter.health_check()
        if health.status != "connected":
            continue
        
        try:
            task = ToolTask(
                task_id=f"test_{adapter_name}",
                instruction="Add a comment to README.md",
                repo_path=str(repo_path),
                allowed_paths=["README.md"],
                forbidden_paths=[".git/**"],
                timeout_seconds=30
            )
            
            result = adapter.run(task, allow_mock=True)
            
            # 如果有 diff，验证
            if result.diff:
                validation = DiffVerifier.verify(
                    result,
                    allowed_paths=["README.md"],
                    forbidden_paths=[".git/**"]
                )
                
                if not validation.is_valid:
                    return False, f"{adapter_name}: diff invalid: {validation.errors}"
                
                results.append({
                    "adapter": adapter_name,
                    "valid": True
                })
            else:
                # Mock 模式可能没有 diff
                results.append({
                    "adapter": adapter_name,
                    "valid": True,
                    "no_diff": True
                })
                
        except Exception as e:
            return False, f"{adapter_name}: diff validation failed: {e}"
    
    checked = len(results)
    return True, f"Diff validation passed: {checked} adapters checked"


def gate_r2_no_direct_write(adapter_configs: List[Dict[str, Any]], repo_path: Path) -> Tuple[bool, str]:
    """
    Gate R2-D: No Direct Write - Tool 没有直接写 repo
    
    检查：
    - ToolResult.wrote_files == False
    - ToolResult.committed == False
    """
    os.environ["AGENTOS_GATE_MODE"] = "1"
    
    for config in adapter_configs:
        adapter_name = config["name"]
        adapter = config["adapter"]
        
        health = adapter.health_check()
        if health.status != "connected":
            continue
        
        try:
            task = ToolTask(
                task_id=f"test_{adapter_name}",
                instruction="Add a comment",
                repo_path=str(repo_path),
                allowed_paths=["README.md"],
                forbidden_paths=[],
                timeout_seconds=30
            )
            
            result = adapter.run(task, allow_mock=True)
            
            # 🔩 钉子 C：权力断点检查
            if result.wrote_files:
                return False, f"{adapter_name}: Tool directly wrote files (violated boundary)"
            
            if result.committed:
                return False, f"{adapter_name}: Tool directly committed (violated boundary)"
                
        except Exception as e:
            return False, f"{adapter_name}: boundary check failed: {e}"
    
    return True, "Power boundary respected: no direct writes/commits"


def gate_r2_result_structure(adapter_configs: List[Dict[str, Any]], repo_path: Path) -> Tuple[bool, str]:
    """
    Gate R2-E: Result Structure - ToolResult 字段完整
    
    检查：
    - ToolResult 包含必需字段
    - tool / status / diff / files_touched / line_count / tool_run_id
    - Step 4 扩展：model_id / provider
    """
    os.environ["AGENTOS_GATE_MODE"] = "1"
    
    required_fields = [
        "tool", "status", "diff", "files_touched", "line_count", "tool_run_id",
        "model_id", "provider"  # Step 4 扩展
    ]
    
    for config in adapter_configs:
        adapter_name = config["name"]
        adapter = config["adapter"]
        
        health = adapter.health_check()
        if health.status != "connected":
            continue
        
        try:
            task = ToolTask(
                task_id=f"test_{adapter_name}",
                instruction="Test",
                repo_path=str(repo_path),
                allowed_paths=["README.md"],
                forbidden_paths=[],
                timeout_seconds=30
            )
            
            result = adapter.run(task, allow_mock=True)
            
            # 检查必需字段
            for field in required_fields:
                if not hasattr(result, field):
                    return False, f"{adapter_name}: ToolResult missing field '{field}'"
            
            # 检查 provider 是否合法
            if result.provider not in ["cloud", "local", None]:
                return False, f"{adapter_name}: invalid provider '{result.provider}'"
                
        except Exception as e:
            return False, f"{adapter_name}: structure check failed: {e}"
    
    return True, f"Result structure valid: all required fields present"


def run_connectivity_gate(repo_root: Path) -> Dict[str, Any]:
    """运行 Multi-Model Connectivity Gate"""
    
    print("🔒 TL-R2: Multi-Model Connectivity Gate")
    print("=" * 60)
    print(f"Repo: {repo_root}\n")
    
    # 准备 adapter 配置
    adapter_configs = [
        {
            "name": "claude_cli",
            "adapter": ClaudeCliAdapter()
        },
        {
            "name": "openai_chat",
            "adapter": OpenAIChatAdapter(model_id="gpt-4o")
        },
        {
            "name": "ollama",
            "adapter": OllamaAdapter(model_id="llama3")
        }
    ]
    
    gates = [
        ("R2-A: Health Check", lambda: gate_r2_health_check(adapter_configs)),
        ("R2-B: Minimal Run", lambda: gate_r2_minimal_run(adapter_configs, repo_root)),
        ("R2-C: Diff Valid", lambda: gate_r2_diff_valid(adapter_configs, repo_root)),
        ("R2-D: No Direct Write", lambda: gate_r2_no_direct_write(adapter_configs, repo_root)),
        ("R2-E: Result Structure", lambda: gate_r2_result_structure(adapter_configs, repo_root)),
    ]
    
    results = {}
    all_passed = True
    
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
    repo_root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    
    if not repo_root.exists():
        print(f"❌ Error: Repository not found: {repo_root}")
        sys.exit(1)
    
    results = run_connectivity_gate(repo_root)
    
    # 保存结果
    output_dir = repo_root / "artifacts" / "gates"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = output_dir / "tl_r2_connectivity.json"
    import json
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n📄 Results saved to: {output_file}")
    
    sys.exit(0 if results["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
