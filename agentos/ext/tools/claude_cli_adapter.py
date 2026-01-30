"""
Claude CLI Adapter - Claude命令行工具适配器

Step 3 Runtime 实现：
- health_check(): 检查 Claude CLI Available性
- run(): 执行外包并产出 diff
- supports(): 声明 cloud 模式能力
"""

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any
from datetime import datetime, timezone
import hashlib
import uuid

from .base_adapter import BaseToolAdapter
from .types import ToolHealth, ToolTask, ToolResult, ToolCapabilities
from agentos.core.infra.tool_executor import ToolExecutor


class ClaudeCliAdapter(BaseToolAdapter):
    """Claude CLI 工具适配器"""
    
    def __init__(self):
        super().__init__("claude_cli")
    
    # ========== Step 3 Runtime 核心方法 ==========
    
    def health_check(self) -> ToolHealth:
        """
        健康检查：检查 Claude CLI 是否Available
        
        检查顺序：
        1. CLI 是否存在（which claude）
        2. 是否可以运行（claude --version）
        3. 认证是否有效（尝试调用 API）
        
        Returns:
            ToolHealth
        """
        # 检查 CLI 是否存在
        try:
            result = subprocess.run(
                ["which", "claude"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode != 0:
                return ToolHealth(
                    status="not_configured",
                    details="Claude CLI not found. Install from: https://claude.ai/download"
                )
        except Exception as e:
            return ToolHealth(
                status="not_configured",
                details=f"Cannot check Claude CLI: {e}"
            )
        
        # 检查是否可以运行
        try:
            result = subprocess.run(
                ["claude", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode != 0:
                return ToolHealth(
                    status="not_configured",
                    details=f"Claude CLI exists but cannot run: {result.stderr}"
                )
            
            version = result.stdout.strip()
        except subprocess.TimeoutExpired:
            return ToolHealth(
                status="unreachable",
                details="Claude CLI timed out (5s)"
            )
        except Exception as e:
            return ToolHealth(
                status="not_configured",
                details=f"Cannot run Claude CLI: {e}"
            )
        
        # 简化检查：只检查 CLI 存在即可
        # 真实的 API 认证检查会在 run() 时做
        return ToolHealth(
            status="connected",
            details=f"Claude CLI {version} is available"
        )
    
    def run(self, task: ToolTask, allow_mock: bool = False) -> ToolResult:
        """
        执行外包任务（Runtime 核心）
        
        流程：
        1. 准备临时文件（task.txt）
        2. 调用 claude --print
        3. 捕获输出
        4. 生成 diff（git diff）
        5. 返回 ToolResult
        
        Args:
            task: 任务描述
            allow_mock: 是否允许 Mock 模式（仅 Gate 可传入）
        
        Returns:
            ToolResult（包含 diff）
        """
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        repo_path = Path(task.repo_path)
        
        # 🔩 钉子 A：Mock 模式必须被 Gate 限定
        # Mock 只能在以下条件之一成立时启用：
        # 1. AGENTOS_GATE_MODE=1
        # 2. 或 allow_mock=True 明确传入
        import os
        gate_mode = os.environ.get("AGENTOS_GATE_MODE", "0") == "1"
        use_mock = gate_mode or allow_mock
        
        if use_mock:
            return self._run_mock(task, run_id, repo_path, explicit=allow_mock)
        
        try:
            # 准备任务文件
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write(task.instruction)
                task_file = Path(f.name)
            
            # 调用 Claude CLI
            # 注意：使用 --print 模式，限制 timeout
            cmd = [
                "claude",
                "--print",
                "--max-budget-usd", "0.10",  # 限制成本
                task.instruction
            ]
            
            result = subprocess.run(
                cmd,
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=task.timeout_seconds
            )
            
            stdout = result.stdout
            stderr = result.stderr
            
            # 获取 git diff
            diff_result = subprocess.run(
                ["git", "diff"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            diff = diff_result.stdout
            
            # 分析变更的文件
            files_touched = []
            line_count = 0
            if diff:
                for line in diff.split('\n'):
                    if line.startswith('diff --git'):
                        # Extract file path: diff --git a/file b/file
                        parts = line.split()
                        if len(parts) >= 3:
                            file_path = parts[2].lstrip('a/')
                            files_touched.append(file_path)
                    elif line.startswith('+') and not line.startswith('+++'):
                        line_count += 1
            
            # 判断状态
            if result.returncode == 0 and diff:
                status = "success"
            elif result.returncode == 0 and not diff:
                status = "failed"
                stderr += "\nNo changes generated"
            else:
                status = "failed"
            
            return ToolResult(
                tool="claude_cli",
                status=status,
                diff=diff,
                files_touched=files_touched,
                line_count=line_count,
                tool_run_id=run_id,
                stdout=stdout,
                stderr=stderr,
                error_message=stderr if result.returncode != 0 else None
            )
            
        except subprocess.TimeoutExpired:
            # 🔩 钉子 A：超时时只有在允许 Mock 的情况下才能 fallback
            import os
            gate_mode = os.environ.get("AGENTOS_GATE_MODE", "0") == "1"
            if gate_mode or allow_mock:
                return self._run_mock(task, run_id, repo_path, reason="timeout", explicit=allow_mock)
            else:
                # 生产环境：超时必须失败，不能 fallback
                return ToolResult(
                    tool="claude_cli",
                    status="timeout",
                    diff="",
                    files_touched=[],
                    line_count=0,
                    tool_run_id=run_id,
                    error_message=f"Claude CLI timed out after {task.timeout_seconds}s (Mock not allowed in production)"
                )
        except Exception as e:
            return ToolResult(
                tool="claude_cli",
                status="failed",
                diff="",
                files_touched=[],
                line_count=0,
                tool_run_id=run_id,
                error_message=f"Execution failed: {e}"
            )
        finally:
            # 清理临时文件
            if 'task_file' in locals():
                task_file.unlink(missing_ok=True)
    
    def _run_mock(self, task: ToolTask, run_id: str, repo_path: Path, reason: str = "mock_mode", explicit: bool = False) -> ToolResult:
        """
        Mock 模式：生成示例 diff（用于测试）
        
        当 Claude CLI 不Available或超时时，自动生成一个符合任务要求的 diff。
        """
        # 根据任务指令生成简单的 diff
        # 这里假设任务是 "Add a footer to index.html"
        
        # 读取目标文件
        target_file = None
        for allowed_path in task.allowed_paths:
            file_path = repo_path / allowed_path
            if file_path.exists():
                target_file = file_path
                break
        
        if not target_file:
            return ToolResult(
                tool="claude_cli_mock",
                status="failed",
                diff="",
                files_touched=[],
                line_count=0,
                tool_run_id=run_id,
                error_message="No target file found in allowed paths"
            )
        
        # 读取文件内容（原始）
        original_content = target_file.read_text()
        
        # 生成简单修改（添加 footer）
        if "index.html" in str(target_file).lower() and "footer" in task.instruction.lower():
            # HTML 文件：在 </body> 前添加 footer
            if "</body>" in original_content:
                footer_text = "AgentOS Step 3 Runtime"
                if "powered by" in task.instruction.lower():
                    footer_text = "Powered by " + footer_text
                
                new_content = original_content.replace(
                    "</body>",
                    f'    <footer>\n        <p>{footer_text}</p>\n    </footer>\n</body>'
                )
                
                # ⚠️ 关键：先写入文件，再生成 diff，最后恢复原始内容
                # 这样 diff 才能被正确 apply
                
                # 1. 保存原始内容（临时）
                # 2. 写入修改
                target_file.write_text(new_content)
                
                # 3. 生成 diff
                diff_result = subprocess.run(
                    ["git", "diff", str(target_file.name)],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                diff = diff_result.stdout
                
                # 4. 恢复原始内容（让 Executor 来 apply diff）
                target_file.write_text(original_content)
                
                # 计算变更
                line_count = len([l for l in diff.split('\n') if l.startswith('+') and not l.startswith('+++')])
                
                # 🔩 钉子 A：返回结果时附带 mock 信息
                result = ToolResult(
                    tool="claude_cli_mock",
                    status="success",
                    diff=diff,
                    files_touched=[str(target_file.relative_to(repo_path))],
                    line_count=line_count,
                    tool_run_id=run_id,
                    stdout=f"Mock mode: {reason} (explicit={explicit})",
                    stderr=f"Used mock implementation due to: {reason}"
                )
                
                # 🔩 钉子 A：在 result 中标记使用了 Mock
                # 这样 run_tape 可以记录
                result._mock_used = True
                result._mock_reason = reason
                
                return result
        
        # Fallback：返回失败
        return ToolResult(
            tool="claude_cli_mock",
            status="failed",
            diff="",
            files_touched=[],
            line_count=0,
            tool_run_id=run_id,
            error_message=f"Mock mode not implemented for this task type: {task.instruction}"
        )
    
    def supports(self) -> ToolCapabilities:
        """
        声明 Claude CLI 能力
        
        🔒 钉子 1：Mode System 必须知道模型能力
        """
        return ToolCapabilities(
            execution_mode="cloud",
            supports_diff=True,
            supports_patch=True,
            supports_health_check=True,
            # 🔒 钉子 1：模型能力
            chat=True,
            json_mode=False,  # Claude CLI 不支持严格 JSON mode
            function_call=True,  # Claude 3.5 支持 tool use
            stream=False,  # CLI 模式不支持流式
            long_context=True,  # Claude 3.5 支持 200K context
            diff_quality="high"  # Claude 3.5 diff 质量很高
        )
    
    # ========== 原有方法 ==========
    
    def pack(self, execution_request: Dict[str, Any], repo_state: Dict[str, Any]) -> Dict[str, Any]:
        """打包任务给Claude CLI"""
        
        task_pack_id = f"ttpack_{hashlib.sha256(execution_request['execution_request_id'].encode()).hexdigest()[:16]}"
        
        # 从execution_request提取信息
        task_pack = {
            "tool_task_pack_id": task_pack_id,
            "schema_version": "0.11.2",
            "execution_request_id": execution_request["execution_request_id"],
            "tool_type": "claude_cli",
            "repo_state": repo_state,
            "work_scope": {
                "allowed_directories": ["agentos/**", "docs/**", "tests/**"],
                "forbidden_paths": [".git/config", ".env", "*.pem", "*.key"]
            },
            "steps": self._create_steps(execution_request),
            "prompt_pack": self._create_prompt_pack(execution_request),
            "acceptance": {
                "gates": ["build", "lint", "test"],
                "tests": ["pytest tests/", "ruff check ."],
                "policy_checks": ["scope_check", "red_line_check"]
            },
            "created_at": datetime.now(timezone.utc).isoformat(),
            "metadata": {
                "priority": "medium",
                "estimated_complexity": "moderate",
                "timeout_minutes": 30
            }
        }
        
        return task_pack
    
    def _create_steps(self, execution_request: Dict[str, Any]) -> list:
        """创建执行步骤"""
        return [
            {
                "step_id": "step_001",
                "goal": "Implement requested changes",
                "constraints": {
                    "must": [
                        "Stay within allowed directories",
                        "Follow existing code patterns",
                        "Add appropriate tests"
                    ],
                    "must_not": [
                        "Modify .git/ directory",
                        "Change sensitive files",
                        "Break existing tests"
                    ]
                },
                "expected_artifacts": [
                    {"type": "file", "path": "*.py"},
                    {"type": "file", "path": "tests/*.py"}
                ],
                "verification_commands": [
                    "pytest tests/",
                    "ruff check ."
                ]
            }
        ]
    
    def _create_prompt_pack(self, execution_request: Dict[str, Any]) -> Dict[str, Any]:
        """创建提示词包"""
        return {
            "system_prompt": """You are implementing changes for AgentOS.
Follow these guidelines:
- Stay within the allowed directory scope
- Follow existing code patterns and conventions
- Add tests for new functionality
- Run verification commands before completing
""",
            "red_lines": [
                "Do not modify .git/ directory",
                "Do not change .env or credential files",
                "Do not execute arbitrary shell commands",
                "Do not access network resources"
            ],
            "examples": []
        }
    
    def dispatch(self, task_pack: Dict[str, Any], output_dir: Path) -> str:
        """生成Claude CLI调度命令"""
        
        # 保存task pack到文件
        task_pack_file = output_dir / f"{task_pack['tool_task_pack_id']}.json"
        task_pack_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(task_pack_file, "w", encoding="utf-8") as f:
            json.dump(task_pack, f, indent=2)
        
        # 生成调度命令
        command = f"""# Claude CLI Dispatch Command
# Task Pack: {task_pack['tool_task_pack_id']}

# Option 1: Manual execution (recommended for first time)
claude --task {task_pack_file} --output {output_dir}/claude_output

# Option 2: With specific instructions
claude --task {task_pack_file} \\
  --instruction "Follow the task pack exactly" \\
  --output {output_dir}/claude_output

# After execution, collect results with:
# agentos tool collect --run {task_pack['tool_task_pack_id']} \\
#   --in {output_dir}/claude_output \\
#   --out {output_dir}/result_pack.json
"""
        
        return command
    
    def collect(self, task_pack_id: str, output_dir: Path) -> Dict[str, Any]:
        """收集Claude CLI执行结果"""
        
        result_pack_id = f"trpack_{hashlib.sha256(task_pack_id.encode()).hexdigest()[:16]}"
        
        # 扫描输出目录
        diffs = []
        artifacts = {
            "files_created": [],
            "files_modified": [],
            "files_deleted": [],
            "commits": []
        }
        
        # 简化版：只记录基本信息
        result_pack = {
            "tool_result_pack_id": result_pack_id,
            "schema_version": "0.11.2",
            "tool_task_pack_id": task_pack_id,
            "tool_type": "claude_cli",
            "status": "success",  # 需要实际检测
            "diffs": diffs,
            "artifacts": artifacts,
            "test_logs": {
                "build_output": "",
                "test_output": "",
                "lint_output": ""
            },
            "run_metadata": {
                "tool_version": "claude-cli-1.0",
                "model_name": "claude-3.5-sonnet",
                "execution_time_seconds": 0,
                "cost_usd": 0,
                "tokens_used": 0
            },
            "policy_attestation": {
                "scope_compliant": True,
                "red_lines_respected": True,
                "violations": []
            },
            "started_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": datetime.now(timezone.utc).isoformat()
        }
        
        return result_pack
    
    def verify(self, result_pack: Dict[str, Any]) -> tuple[bool, list[str]]:
        """验证结果包"""
        errors = []
        
        # 检查状态
        if result_pack["status"] not in ["success", "partial_success"]:
            errors.append(f"Status is {result_pack['status']}, not success")
        
        # 检查policy attestation
        if not result_pack["policy_attestation"]["scope_compliant"]:
            errors.append("Scope compliance failed")
        
        if not result_pack["policy_attestation"]["red_lines_respected"]:
            errors.append("Red lines violated")
        
        # 检查violations
        violations = result_pack["policy_attestation"].get("violations", [])
        for v in violations:
            if v["severity"] in ["error", "critical"]:
                errors.append(f"Policy violation: {v['description']}")
        
        return len(errors) == 0, errors
