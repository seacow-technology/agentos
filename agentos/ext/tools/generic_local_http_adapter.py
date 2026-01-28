"""
Generic Local HTTP Adapter - 通用本地 HTTP 模型适配器基类

Step 4 扩展：
- 支持多种 HTTP 协议（llamacpp_completion / openai_compatible）
- 可配置 request_builder / response_parser
- 统一的 health_check 逻辑

用于：
- llama.cpp server (/completion)
- 其他本地 HTTP 服务
"""

from abc import abstractmethod
from pathlib import Path
from typing import Optional, Dict, Any, Literal
import uuid
import subprocess

# requests 是可选依赖
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    requests = None

from .base_adapter import BaseToolAdapter
from .types import ToolHealth, ToolTask, ToolResult, ToolCapabilities


class GenericLocalHTTPAdapter(BaseToolAdapter):
    """
    通用本地 HTTP 模型适配器基类
    
    支持多种协议模式的本地 HTTP 服务。
    """
    
    def __init__(
        self, 
        tool_name: str, 
        model_id: str,
        base_url: str,
        mode: Literal["llamacpp_completion", "openai_compatible"] = "llamacpp_completion"
    ):
        """
        初始化通用本地 HTTP 适配器
        
        Args:
            tool_name: 工具名称（如 llamacpp）
            model_id: 模型 ID
            base_url: HTTP 服务 base URL
            mode: 协议模式（llamacpp_completion / openai_compatible）
        """
        super().__init__(tool_name)
        self.model_id = model_id
        self.base_url = base_url.rstrip('/')
        self.mode = mode
    
    # ========== Step 4 Runtime 核心方法 ==========
    
    @abstractmethod
    def _build_request(self, prompt: str, timeout: int) -> Dict[str, Any]:
        """
        构建请求（子类实现）
        
        Args:
            prompt: 任务提示词
            timeout: 超时时间（秒）
        
        Returns:
            请求 payload
        """
        pass
    
    @abstractmethod
    def _parse_response(self, response_data: Dict[str, Any]) -> str:
        """
        解析响应（子类实现）
        
        Args:
            response_data: API 响应数据
        
        Returns:
            模型输出文本
        """
        pass
    
    @abstractmethod
    def _get_endpoint(self) -> str:
        """
        获取 API endpoint（子类实现）
        
        Returns:
            endpoint 路径（如 /completion）
        """
        pass
    
    def health_check(self) -> ToolHealth:
        """
        健康检查（通用实现）
        
        检查顺序：
        1. 尝试 GET /health
        2. 尝试最小 probe 请求
        
        🔒 钉子 2：错误必须分类（运维排查必需）
        
        Returns:
            ToolHealth
        """
        if not HAS_REQUESTS:
            return ToolHealth(
                status="unreachable",
                details="requests library not installed",
                error_category="dependency"
            )
        
        # 1. 尝试 GET /health（如果存在）
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            if response.status_code == 200:
                return ToolHealth(
                    status="connected",
                    details=f"{self.tool_name} server healthy at {self.base_url}"
                )
        except:
            pass
        
        # 2. 尝试最小 probe 请求
        try:
            endpoint = self._get_endpoint()
            payload = self._build_request("ok", 5)
            
            response = requests.post(
                f"{self.base_url}{endpoint}",
                json=payload,
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # 尝试解析响应
                try:
                    content = self._parse_response(data)
                    if content:
                        return ToolHealth(
                            status="connected",
                            details=f"{self.tool_name} server responding at {self.base_url}"
                        )
                    else:
                        return ToolHealth(
                            status="schema_mismatch",
                            details=f"Server responded but content is empty",
                            error_category="schema"  # 🔒 钉子 2：开发者错误
                        )
                except Exception as e:
                    return ToolHealth(
                        status="schema_mismatch",
                        details=f"Response parsing failed: {e}",
                        error_category="schema"  # 🔒 钉子 2：开发者错误
                    )
            
            return ToolHealth(
                status="unreachable",
                details=f"Server returned {response.status_code}",
                error_category="network"
            )
            
        except Exception as e:
            if HAS_REQUESTS and hasattr(requests, 'exceptions'):
                if isinstance(e, requests.exceptions.ConnectionError):
                    return ToolHealth(
                        status="unreachable",
                        details=f"Cannot connect to {self.tool_name} at {self.base_url}",
                        error_category="network"
                    )
                elif isinstance(e, requests.exceptions.Timeout):
                    return ToolHealth(
                        status="unreachable",
                        details=f"{self.tool_name} connection timed out (5s)",
                        error_category="runtime"
                    )
            return ToolHealth(
                status="unreachable",
                details=f"Health check failed: {e}",
                error_category="runtime"
            )
    
    def run(self, task: ToolTask, allow_mock: bool = False) -> ToolResult:
        """
        执行外包任务（Runtime 核心）
        
        流程：
        1. 调用本地 HTTP API
        2. 解析响应
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
        gate_mode = os.environ.get("AGENTOS_GATE_MODE", "0") == "1"
        use_mock = gate_mode or allow_mock
        
        if use_mock:
            return self._run_mock(task, run_id, repo_path, explicit=allow_mock)
        
        if not HAS_REQUESTS:
            if allow_mock:
                return self._run_mock(task, run_id, repo_path, reason="no_requests", explicit=True)
            return ToolResult(
                tool=self.tool_name,
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
            # 构建请求
            endpoint = self._get_endpoint()
            payload = self._build_request(task.instruction, task.timeout_seconds)
            
            # 调用 API
            response = requests.post(
                f"{self.base_url}{endpoint}",
                json=payload,
                timeout=task.timeout_seconds
            )
            
            if response.status_code != 200:
                return ToolResult(
                    tool=self.tool_name,
                    status="failed",
                    diff="",
                    files_touched=[],
                    line_count=0,
                    tool_run_id=run_id,
                    model_id=self.model_id,
                    provider="local",
                    error_message=f"API returned {response.status_code}: {response.text}"
                )
            
            # 解析响应
            data = response.json()
            model_output = self._parse_response(data)
            
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
                tool=self.tool_name,
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
            if HAS_REQUESTS and hasattr(requests, 'exceptions') and isinstance(e, requests.exceptions.Timeout):
                # 🔩 钉子 A：超时时只有在允许 Mock 的情况下才能 fallback
                if gate_mode or allow_mock:
                    return self._run_mock(task, run_id, repo_path, reason="timeout", explicit=allow_mock)
            else:
                return ToolResult(
                    tool=self.tool_name,
                    status="timeout",
                    diff="",
                    files_touched=[],
                    line_count=0,
                    tool_run_id=run_id,
                    model_id=self.model_id,
                    provider="local",
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
 # AgentOS
 Step 3 Runtime Implementation
+Mock change from generic local HTTP adapter
"""
        
        result = ToolResult(
            tool=f"{self.tool_name}_mock",
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
        """声明通用本地 HTTP 能力"""
        return ToolCapabilities(
            execution_mode="local",
            supports_diff=True,
            supports_patch=True,
            supports_health_check=True
        )
    
    # ========== 原有方法（空实现，保持接口兼容）==========
    
    def pack(self, execution_request, repo_state):
        """Not implemented for generic local HTTP adapters"""
        raise NotImplementedError("GenericLocalHTTPAdapter does not support pack()")
    
    def dispatch(self, task_pack, output_dir):
        """Not implemented for generic local HTTP adapters"""
        raise NotImplementedError("GenericLocalHTTPAdapter does not support dispatch()")
    
    def collect(self, task_pack_id, output_dir):
        """Not implemented for generic local HTTP adapters"""
        raise NotImplementedError("GenericLocalHTTPAdapter does not support collect()")
    
    def verify(self, result_pack):
        """Not implemented for generic local HTTP adapters"""
        raise NotImplementedError("GenericLocalHTTPAdapter does not support verify()")
