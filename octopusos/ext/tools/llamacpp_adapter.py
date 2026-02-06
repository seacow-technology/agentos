"""
llama.cpp Adapter - llama.cpp server 适配器

Step 4 扩展：
- 继承 GenericLocalHTTPAdapter
- 支持 /completion 接口（llama.cpp server 标准接口）
- health_check(): 优先 /health，备选 /completion probe
- run(): 通过 /completion 调用

llama.cpp server 启动方式：
- ./llama-server -m model.gguf --port 8080
- 或：./main -m model.gguf --server --port 8080

配置：
- Base URL: http://localhost:8080
- Endpoint: /completion

🔒 钉子 1：声明模型能力（Mode System 必需）
"""

import os
from pathlib import Path
from typing import Dict, Any

from .generic_local_http_adapter import GenericLocalHTTPAdapter
from .types import ToolCapabilities


class LlamaCppAdapter(GenericLocalHTTPAdapter):
    """llama.cpp server 适配器"""
    
    def __init__(self, model_id: str = "llama-local", base_url: str = "http://localhost:8080"):
        """
        初始化 llama.cpp 适配器
        
        Args:
            model_id: 模型 ID（默认 llama-local）
            base_url: llama.cpp server base URL（默认 http://localhost:8080）
        """
        super().__init__(
            tool_name="llamacpp",
            model_id=model_id,
            base_url=base_url,
            mode="llamacpp_completion"
        )
    
    def _get_endpoint(self) -> str:
        """
        获取 API endpoint
        
        Returns:
            /completion
        """
        return "/completion"
    
    def _build_request(self, prompt: str, timeout: int) -> Dict[str, Any]:
        """
        构建 llama.cpp /completion 请求
        
        Args:
            prompt: 任务提示词
            timeout: 超时时间（秒）
        
        Returns:
            请求 payload
        """
        return {
            "prompt": f"""You are a code modification assistant for AgentOS.

Task: {prompt}

Rules:
1. Make direct modifications to the repository files
2. Follow existing code patterns and conventions
3. Do NOT use git commands
4. Return a brief summary of changes made
""",
            "temperature": 0.2,
            "max_tokens": 256,
            "stop": ["</s>", "User:", "Assistant:"],
            "stream": False
        }
    
    def _parse_response(self, response_data: Dict[str, Any]) -> str:
        """
        解析 llama.cpp /completion 响应
        
        Args:
            response_data: API 响应数据
        
        Returns:
            模型输出文本
        
        Raises:
            KeyError: 如果响应格式不匹配
        """
        # llama.cpp /completion 响应格式：
        # {"content": "...", "stop": true, ...}
        if "content" not in response_data:
            raise KeyError("Response missing 'content' field (schema mismatch)")
        
        return response_data["content"]
    
    def supports(self) -> ToolCapabilities:
        """
        声明 llama.cpp 能力
        
        🔒 钉子 1：Mode System 必须知道模型能力
        """
        return ToolCapabilities(
            execution_mode="local",
            supports_diff=True,
            supports_patch=True,
            supports_health_check=True,
            # 🔒 钉子 1：模型能力（Mode System 必需）
            chat=True,
            json_mode=False,  # llama.cpp 基本版本不支持
            function_call=False,
            stream=True,  # llama.cpp 支持流式
            long_context=False,  # 取决于加载的模型
            diff_quality="low"  # 纯 llama.cpp 通常质量较低
        )
