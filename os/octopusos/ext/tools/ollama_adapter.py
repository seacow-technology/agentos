"""
Ollama Adapter - 本地 LLM 适配器

Step 4 Runtime 实现：
- health_check(): 检查 Ollama 服务 + 模型是否存在
- run(): 通过 HTTP API 调用本地模型
- supports(): 声明 local 模式能力

支持的模型：
- llama3
- llama3.1
- codellama
- mistral
- 其他 Ollama 支持的模型
"""

import os
import json
from pathlib import Path
from typing import Optional
import subprocess
import uuid

# requests 是可选依赖（用于 API 调用）
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    requests = None

from .base_adapter import BaseToolAdapter
from .types import ToolHealth, ToolTask, ToolResult, ToolCapabilities


class OllamaAdapter(BaseToolAdapter):
    """Ollama 本地 LLM 适配器"""
    
    def __init__(self, model_id: str = "llama3"):
        """
        初始化 Ollama 适配器
        
        Args:
            model_id: 模型 ID（如 llama3）
        """
        super().__init__("ollama")
        self.model_id = model_id
        self.host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    
    def health_check(self) -> ToolHealth:
        """
        健康检查：检查 Ollama 服务 + 模型是否存在
        
        检查顺序：
        1. Ollama 服务是否可达
        2. 指定模型是否存在
        
        Returns:
            ToolHealth（包含 model_missing 状态）
        """
        if not HAS_REQUESTS:
            return ToolHealth(
                status="unreachable",
                details="requests library not installed, cannot check Ollama service"
            )
        
        try:
            # 1. 检查 Ollama 服务
            response = requests.get(f"{self.host}/api/tags", timeout=5)
            
            if response.status_code != 200:
                return ToolHealth(
                    status="unreachable",
                    details=f"Ollama service returned {response.status_code}"
                )
            
            # 2. 检查模型是否存在
            models_data = response.json()
            available_models = [m["name"] for m in models_data.get("models", [])]
            
            # 检查精确匹配或前缀匹配
            model_exists = any(
                m == self.model_id or m.startswith(f"{self.model_id}:")
                for m in available_models
            )
            
            if not model_exists:
                return ToolHealth(
                    status="model_missing",
                    details=f"Model '{self.model_id}' not found. Available: {', '.join(available_models[:3])}..."
                )
            
            return ToolHealth(
                status="connected",
                details=f"Ollama service running at {self.host}, model '{self.model_id}' available"
            )
            
        except Exception as e:
            if HAS_REQUESTS and isinstance(e, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
                return ToolHealth(
                    status="unreachable",
                    details=f"Cannot connect to Ollama at {self.host}: {e}"
                )
            return ToolHealth(
                status="unreachable",
                details=f"Error checking Ollama: {e}"
            )
    
    def run(self, task: ToolTask, allow_mock: bool = False) -> ToolResult:
        """
        执行外包任务（Runtime 核心）
        
        流程：
        1. 检查 Ollama 健康状态
        2. 调用 Ollama API
        3. 生成 diff（git diff）
        4. 返回 ToolResult
        
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
        gate_mode = os.environ.get("OCTOPUSOS_GATE_MODE", "0") == "1"
        use_mock = gate_mode or allow_mock
        
        if use_mock:
            return self._run_mock(task, run_id, repo_path, explicit=allow_mock)
        
        if not HAS_REQUESTS:
            # 如果没有 requests，只能使用 mock 模式
            if allow_mock:
                return self._run_mock(task, run_id, repo_path, reason="no_requests", explicit=True)
            return ToolResult(
                tool="ollama",
                status="failed",
                diff="",
                files_touched=[],
                line_count=0,
                tool_run_id=run_id,
                model_id=self.model_id,
                provider="local",
                error_message="requests library not installed"
            )
        
        try:
            # 构建提示词
            system_prompt = f"""You are a code modification assistant for OctopusOS.

Repository: {repo_path}
Task: {task.instruction}

Rules:
1. Make direct modifications to the repository files
2. Follow existing code patterns and conventions
3. Do NOT use git commands
4. Return a brief summary of changes made

Work directory: {repo_path}
"""
            
            # 调用 Ollama API
            response = requests.post(
                f"{self.host}/api/generate",
                json={
                    "model": self.model_id,
                    "prompt": system_prompt,
                    "stream": False
                },
                timeout=task.timeout_seconds
            )
            
            if response.status_code != 200:
                return ToolResult(
                    tool="ollama",
                    status="failed",
                    diff="",
                    files_touched=[],
                    line_count=0,
                    tool_run_id=run_id,
                    model_id=self.model_id,
                    provider="local",
                    error_message=f"Ollama API returned {response.status_code}: {response.text}"
                )
            
            result_data = response.json()
            model_output = result_data.get("response", "")

            # Best-effort usage tracking (Ollama / local)
            try:
                from octopusos.core.llm.usage_events import LLMUsageEvent, record_llm_usage_event_best_effort
                prompt_tokens_est = max(len(system_prompt) // 4, 0)
                completion_tokens_est = max(len(model_output) // 4, 0)
                record_llm_usage_event_best_effort(
                    LLMUsageEvent(
                        provider="ollama",
                        model=self.model_id,
                        operation="tool.ollama_generate",
                        prompt_tokens=prompt_tokens_est,
                        completion_tokens=completion_tokens_est,
                        total_tokens=prompt_tokens_est + completion_tokens_est,
                        confidence="ESTIMATED",
                        metadata={
                            "tool_id": "ollama",
                            "repo_path": str(repo_path),
                        },
                    )
                )
            except Exception:
                pass
             
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
                        parts = line.split()
                        if len(parts) >= 3:
                            file_path = parts[2].lstrip('a/')
                            files_touched.append(file_path)
                    elif line.startswith('+') and not line.startswith('+++'):
                        line_count += 1
            
            # 判断状态
            if diff:
                status = "success"
            else:
                status = "failed"
                model_output += "\nNo changes generated"
            
            return ToolResult(
                tool="ollama",
                status=status,
                diff=diff,
                files_touched=files_touched,
                line_count=line_count,
                tool_run_id=run_id,
                model_id=self.model_id,
                provider="local",
                stdout=model_output,
                stderr="",
                error_message=None if status == "success" else "No changes generated"
            )
            
        except Exception as e:
            # 统一异常处理
            if HAS_REQUESTS and isinstance(e, requests.exceptions.Timeout):
                # 🔩 钉子 A：超时时只有在允许 Mock 的情况下才能 fallback
                if gate_mode or allow_mock:
                    return self._run_mock(task, run_id, repo_path, reason="timeout", explicit=allow_mock)
            else:
                return ToolResult(
                    tool="ollama",
                    status="timeout",
                    diff="",
                    files_touched=[],
                    line_count=0,
                    tool_run_id=run_id,
                    model_id=self.model_id,
                    provider="local",
                    error_message=f"Ollama timed out after {task.timeout_seconds}s (Mock not allowed in production)"
                )
        except Exception as e:
            return ToolResult(
                tool="ollama",
                status="failed",
                diff="",
                files_touched=[],
                line_count=0,
                tool_run_id=run_id,
                model_id=self.model_id,
                provider="local",
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
        mock_diff = """diff --git a/README.md b/README.md
index 1234567..abcdefg 100644
--- a/README.md
+++ b/README.md
@@ -1,2 +1,3 @@
 # OctopusOS
 Step 3 Runtime Implementation
+Mock change from Ollama local adapter
"""
        
        result = ToolResult(
            tool="ollama_mock",
            status="success",
            diff=mock_diff,
            files_touched=["README.md"],
            line_count=1,
            tool_run_id=run_id,
            model_id=f"{self.model_id}_mock",
            provider="local",
            stdout=f"Mock mode: {reason} (explicit={explicit})",
            stderr=f"Used mock implementation due to: {reason}"
        )
        
        # 🔩 钉子 A：标记使用了 Mock
        result._mock_used = True
        result._mock_reason = reason
        
        return result
    
    def supports(self) -> ToolCapabilities:
        """
        声明 Ollama 能力
        
        🔒 钉子 1：Mode System 必须知道模型能力
        """
        return ToolCapabilities(
            execution_mode="local",
            supports_diff=True,
            supports_patch=True,
            supports_health_check=True,
            # 🔒 钉子 1：模型能力
            chat=True,
            json_mode=False,  # Ollama 基本版本不支持严格 JSON
            function_call=False,
            stream=True,  # Ollama 支持流式
            long_context=False,  # 取决于加载的模型
            diff_quality="medium"  # 本地模型通常 medium
        )
    
    # ========== 原有方法（空实现，保持接口兼容）==========
    
    def pack(self, execution_request, repo_state):
        """Not implemented for Ollama adapter"""
        raise NotImplementedError("OllamaAdapter does not support pack()")
    
    def dispatch(self, task_pack, output_dir):
        """Not implemented for Ollama adapter"""
        raise NotImplementedError("OllamaAdapter does not support dispatch()")
    
    def collect(self, task_pack_id, output_dir):
        """Not implemented for Ollama adapter"""
        raise NotImplementedError("OllamaAdapter does not support collect()")
    
    def verify(self, result_pack):
        """Not implemented for Ollama adapter"""
        raise NotImplementedError("OllamaAdapter does not support verify()")
