"""
OpenAI Chat Adapter - OpenAI API 适配器

Step 4 Runtime 实现：
- health_check(): 检查 OPENAI_API_KEY
- run(): 通过 openai Python SDK 调用
- supports(): 声明 cloud 模式能力

支持的模型：
- gpt-4.1
- gpt-4o
- gpt-4o-mini
- o3-mini

🔒 钉子 1：声明 OpenAI 的高级能力
"""

import os
import json
from pathlib import Path
from typing import Optional

from .cloud_chat_adapter import CloudChatAdapter
from .types import ToolCapabilities


class OpenAIChatAdapter(CloudChatAdapter):
    """OpenAI Chat API 适配器"""
    
    def __init__(self, model_id: str = "gpt-4o", base_url: Optional[str] = None, api_key: Optional[str] = None):
        """
        初始化 OpenAI 适配器
        
        Args:
            model_id: 模型 ID（默认 gpt-4o）
            base_url: API base URL（可选，用于 OpenAI-compatible 服务如 LM Studio）
            api_key: API key（可选，优先使用此值）
        """
        super().__init__("openai_chat", model_id)
        self.base_url = base_url or os.environ.get("OPENAI_BASE_URL")
        self.api_key_override = api_key
    
    def _check_credentials(self) -> tuple[bool, str]:
        """
        检查 OPENAI_API_KEY 环境变量
        
        Returns:
            (is_valid, details)
        """
        api_key = self.api_key_override or os.environ.get("OPENAI_API_KEY")
        
        if not api_key:
            return False, "OPENAI_API_KEY not found in environment"
        
        # 本地模型（OpenAI-compatible）不强制 sk- 前缀
        if self.base_url and not self.base_url.startswith("https://api.openai.com"):
            return True, f"OpenAI-compatible endpoint configured: {self.base_url}"
        
        # 云端 OpenAI 必须 sk- 前缀
        if not api_key.startswith("sk-"):
            return False, "OPENAI_API_KEY format invalid (must start with 'sk-')"
        
        return True, f"OpenAI API key configured (model: {self.model_id})"
    
    def _call_api(self, prompt: str, repo_path: Path, timeout: int) -> tuple[str, str, int]:
        """
        调用 OpenAI API
        
        Args:
            prompt: 任务提示词
            repo_path: 仓库路径
            timeout: 超时时间（秒）
        
        Returns:
            (stdout, stderr, returncode)
        """
        try:
            # 检查是否安装了 openai
            try:
                import openai
            except ImportError:
                return (
                    "",
                    "openai package not installed. Install with: pip install openai",
                    1
                )
            
            # 配置 API key
            api_key = self.api_key_override or os.environ.get("OPENAI_API_KEY")
            if not api_key:
                return "", "OPENAI_API_KEY not configured", 1
            
            # 创建 client（支持自定义 base_url）
            client_kwargs = {"api_key": api_key, "timeout": timeout}
            if self.base_url:
                client_kwargs["base_url"] = self.base_url
            
            client = openai.OpenAI(**client_kwargs)
            
            # 构建系统提示词
            system_prompt = f"""You are a code modification assistant for OctopusOS.

Repository: {repo_path}
Task: {prompt}

Rules:
1. Make direct modifications to the repository files
2. Follow existing code patterns and conventions
3. Do NOT use git commands
4. Return a brief summary of changes made

Work directory: {repo_path}
"""
            
            # 调用 API
            response = client.chat.completions.create(
                model=self.model_id,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=2000
            )

            # Best-effort usage tracking
            try:
                from octopusos.core.llm.usage_events import LLMUsageEvent, record_llm_usage_event_best_effort
                usage = getattr(response, "usage", None)
                record_llm_usage_event_best_effort(
                    LLMUsageEvent(
                        provider="openai",
                        model=self.model_id,
                        operation="tool.openai_chat",
                        prompt_tokens=getattr(usage, "prompt_tokens", None),
                        completion_tokens=getattr(usage, "completion_tokens", None),
                        total_tokens=getattr(usage, "total_tokens", None),
                        confidence="HIGH" if usage is not None else "LOW",
                        metadata={
                            "tool_id": "openai_chat",
                            "repo_path": str(repo_path),
                        },
                    )
                )
            except Exception:
                pass
            
            # 提取响应
            assistant_message = response.choices[0].message.content
            
            return assistant_message, "", 0
            
        except Exception as e:
            return "", f"OpenAI API call failed: {e}", 1


    def supports(self) -> ToolCapabilities:
        """
        声明 OpenAI Chat API 能力
        
        🔒 钉子 1：Mode System 必须知道模型能力
        """
        return ToolCapabilities(
            execution_mode="cloud",
            supports_diff=True,
            supports_patch=True,
            supports_health_check=True,
            # 🔒 钉子 1：模型能力
            chat=True,
            json_mode=True,  # GPT-4 支持 JSON mode
            function_call=True,  # GPT-4 支持 function calling
            stream=True,  # 支持流式
            long_context=True,  # GPT-4 支持长上下文
            diff_quality="high"  # GPT-4 diff 质量高
        )
