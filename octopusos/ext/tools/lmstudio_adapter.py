"""
LM Studio Adapter - LM Studio 本地模型适配器

Step 4 扩展：
- 继承 OpenAIChatAdapter（复用 OpenAI-compatible 接口）
- health_check(): 检查 LM Studio 服务 + 模型是否加载
- run(): 通过 OpenAI-compatible API 调用
- supports(): 声明 local 模式能力

LM Studio 配置：
- Base URL: http://localhost:1234/v1
- Models endpoint: /models
- 不强制 API key（使用占位符 "lm-studio"）
"""

import os
from pathlib import Path
from typing import Optional

# requests 是可选依赖
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    requests = None

from .openai_chat_adapter import OpenAIChatAdapter
from .types import ToolHealth, ToolCapabilities


class LMStudioAdapter(OpenAIChatAdapter):
    """LM Studio 本地模型适配器"""
    
    def __init__(self, model_id: str = "local-model", base_url: str = "http://localhost:1234/v1"):
        """
        初始化 LM Studio 适配器
        
        Args:
            model_id: 模型 ID（默认 local-model）
            base_url: LM Studio API base URL（默认 http://localhost:1234/v1）
        """
        super().__init__(
            model_id=model_id,
            base_url=base_url,
            api_key="lm-studio"  # 占位符，LM Studio 不需要真实 API key
        )
        self.tool_name = "lmstudio"
    
    def health_check(self) -> ToolHealth:
        """
        健康检查：检查 LM Studio 服务 + 模型是否加载
        
        检查顺序:
        1. GET /models - 检查服务是否可达
        2. 解析模型列表 - 检查是否有模型加载
        
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
        
        try:
            # 1. 检查服务可达性
            response = requests.get(f"{self.base_url}/models", timeout=5)
            
            if response.status_code != 200:
                return ToolHealth(
                    status="unreachable",
                    details=f"LM Studio returned {response.status_code}. Is the server running?",
                    error_category="network"
                )
            
            # 2. 检查模型是否加载
            models_data = response.json()
            models = models_data.get("data", [])
            
            if not models:
                return ToolHealth(
                    status="model_missing",
                    details="No model loaded in LM Studio. Please load a model in the UI.",
                    error_category="model"  # 🔒 钉子 2：操作性错误
                )
            
            # 提取模型 ID
            model_ids = [m.get("id", "") for m in models]
            model_list = ', '.join(model_ids[:3])
            if len(model_ids) > 3:
                model_list += f" (+{len(model_ids) - 3} more)"
            
            return ToolHealth(
                status="connected",
                details=f"LM Studio connected, models: {model_list}"
            )
            
        except Exception as e:
            if HAS_REQUESTS and hasattr(requests, 'exceptions'):
                if isinstance(e, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
                    return ToolHealth(
                        status="unreachable",
                        details=f"Cannot connect to LM Studio: {e}",
                        error_category="network"
                    )
            return ToolHealth(
                status="unreachable",
                details=f"Health check failed: {e}",
                error_category="runtime"
            )
    
    def supports(self) -> ToolCapabilities:
        """
        声明 LM Studio 能力
        
        🔒 钉子 1：Mode System 必须知道模型能力
        """
        return ToolCapabilities(
            execution_mode="local",
            supports_diff=True,
            supports_patch=True,
            supports_health_check=True,
            # 🔒 钉子 1：模型能力（Mode System 必需）
            chat=True,
            json_mode=False,  # LM Studio 取决于加载的模型
            function_call=False,
            stream=True,  # LM Studio 支持流式
            long_context=False,  # 取决于加载的模型
            diff_quality="medium"  # 本地模型通常是 medium
        )
