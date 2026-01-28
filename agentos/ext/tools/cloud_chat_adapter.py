"""
Cloud Chat Adapter - 云端聊天模型基类

Step 4 Runtime 核心：
- 统一 HTTP API 接口（OpenAI / Anthropic / Gemini）
- health_check(): 检查 API token / endpoint
- run(): 通过 HTTP 调用云端模型
- supports(): 声明 cloud 模式能力

权力边界红线：
- Tool 只能产出 diff
- Tool 不能直接写 repo
- Tool 不能直接 commit
"""

from abc import abstractmethod
from pathlib import Path
from typing import Optional
import uuid
import subprocess

from .base_adapter import BaseToolAdapter
from .types import ToolHealth, ToolTask, ToolResult, ToolCapabilities


class CloudChatAdapter(BaseToolAdapter):
    """
    云端聊天模型适配器基类
    
    统一 OpenAI / Anthropic / Gemini 等 HTTP API 接口。
    """
    
    def __init__(self, tool_name: str, model_id: str):
        """
        初始化云端聊天适配器
        
        Args:
            tool_name: 工具名称（如 openai_chat）
            model_id: 模型 ID（如 gpt-4.1）
        """
        super().__init__(tool_name)
        self.model_id = model_id
    
    # ========== Step 4 Runtime 核心方法（子类必须实现）==========
    
    @abstractmethod
    def _check_credentials(self) -> tuple[bool, str]:
        """
        检查凭证（子类实现）
        
        Returns:
            (is_valid, details)
        """
        pass
    
    @abstractmethod
    def _call_api(self, prompt: str, repo_path: Path, timeout: int) -> tuple[str, str, int]:
        """
        调用云端 API（子类实现）
        
        Args:
            prompt: 任务提示词
            repo_path: 仓库路径
            timeout: 超时时间（秒）
        
        Returns:
            (stdout, stderr, returncode)
        """
        pass
    
    # ========== 统一实现（无需子类覆盖）==========
    
    def health_check(self) -> ToolHealth:
        """
        健康检查：检查 API token / endpoint
        
        检查顺序：
        1. 环境变量是否配置
        2. 是否可以访问 API（简单调用）
        
        Returns:
            ToolHealth
        """
        # 检查凭证
        is_valid, details = self._check_credentials()
        
        if not is_valid:
            return ToolHealth(
                status="not_configured",
                details=details
            )
        
        # 简化检查：只检查凭证存在即可
        # 真实的 API 连通性检查会在 run() 时做
        return ToolHealth(
            status="connected",
            details=f"{self.tool_name} ({self.model_id}) is configured"
        )
    
    def run(self, task: ToolTask, allow_mock: bool = False) -> ToolResult:
        """
        执行外包任务（Runtime 核心）
        
        流程：
        1. 检查凭证
        2. 调用云端 API
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
        import os
        gate_mode = os.environ.get("AGENTOS_GATE_MODE", "0") == "1"
        use_mock = gate_mode or allow_mock
        
        if use_mock:
            return self._run_mock(task, run_id, repo_path, explicit=allow_mock)
        
        try:
            # 调用 API
            stdout, stderr, returncode = self._call_api(
                task.instruction,
                repo_path,
                task.timeout_seconds
            )
            
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
            if returncode == 0 and diff:
                status = "success"
            elif returncode == 0 and not diff:
                status = "failed"
                stderr += "\nNo changes generated"
            else:
                status = "failed"
            
            return ToolResult(
                tool=self.tool_name,
                status=status,
                diff=diff,
                files_touched=files_touched,
                line_count=line_count,
                tool_run_id=run_id,
                model_id=self.model_id,
                provider="cloud",
                stdout=stdout,
                stderr=stderr,
                error_message=stderr if returncode != 0 else None
            )
            
        except subprocess.TimeoutExpired:
            # 🔩 钉子 A：超时时只有在允许 Mock 的情况下才能 fallback
            if gate_mode or allow_mock:
                return self._run_mock(task, run_id, repo_path, reason="timeout", explicit=allow_mock)
            else:
                # 生产环境：超时必须失败，不能 fallback
                return ToolResult(
                    tool=self.tool_name,
                    status="timeout",
                    diff="",
                    files_touched=[],
                    line_count=0,
                    tool_run_id=run_id,
                    model_id=self.model_id,
                    provider="cloud",
                    error_message=f"{self.tool_name} timed out after {task.timeout_seconds}s (Mock not allowed in production)"
                )
        except Exception as e:
            return ToolResult(
                tool=self.tool_name,
                status="failed",
                diff="",
                files_touched=[],
                line_count=0,
                tool_run_id=run_id,
                model_id=self.model_id,
                provider="cloud",
                error_message=f"Execution failed: {e}"
            )
    
    def _run_mock(self, task: ToolTask, run_id: str, repo_path: Path, reason: str = "mock_mode", explicit: bool = False) -> ToolResult:
        """
        Mock 模式：生成示例 diff（用于测试）
        
        Args:
            task: 任务描述
            run_id: 运行 ID
            repo_path: 仓库路径
            reason: Mock 原因
            explicit: 是否明确传入
        
        Returns:
            ToolResult（Mock）
        """
        # 简单实现：返回一个固定的 diff
        mock_diff = """diff --git a/README.md b/README.md
index 1234567..abcdefg 100644
--- a/README.md
+++ b/README.md
@@ -1,2 +1,3 @@
 # AgentOS
 Step 3 Runtime Implementation
+Mock change from cloud chat adapter
"""
        
        result = ToolResult(
            tool=f"{self.tool_name}_mock",
            status="success",
            diff=mock_diff,
            files_touched=["README.md"],
            line_count=1,
            tool_run_id=run_id,
            model_id=f"{self.model_id}_mock",
            provider="cloud",
            stdout=f"Mock mode: {reason} (explicit={explicit})",
            stderr=f"Used mock implementation due to: {reason}"
        )
        
        # 🔩 钉子 A：标记使用了 Mock
        result._mock_used = True
        result._mock_reason = reason
        
        return result
    
    def supports(self) -> ToolCapabilities:
        """
        声明云端聊天模型能力
        
        🔒 钉子 1：Mode System 必须知道模型能力
        子类应该覆盖此方法声明具体能力
        """
        return ToolCapabilities(
            execution_mode="cloud",
            supports_diff=True,
            supports_patch=True,
            supports_health_check=True,
            # 🔒 钉子 1：模型能力（默认值，子类应覆盖）
            chat=True,
            json_mode=False,
            function_call=False,
            stream=False,
            long_context=False,
            diff_quality="medium"
        )
    
    # ========== 原有方法（空实现，保持接口兼容）==========
    
    def pack(self, execution_request, repo_state):
        """Not implemented for cloud chat adapters"""
        raise NotImplementedError("CloudChatAdapter does not support pack()")
    
    def dispatch(self, task_pack, output_dir):
        """Not implemented for cloud chat adapters"""
        raise NotImplementedError("CloudChatAdapter does not support dispatch()")
    
    def collect(self, task_pack_id, output_dir):
        """Not implemented for cloud chat adapters"""
        raise NotImplementedError("CloudChatAdapter does not support collect()")
    
    def verify(self, result_pack):
        """Not implemented for cloud chat adapters"""
        raise NotImplementedError("CloudChatAdapter does not support verify()")
