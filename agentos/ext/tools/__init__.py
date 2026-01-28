"""
External Tools - 工具适配器

提供外部工具集成能力

Step 3 Runtime 核心：
- types: 运行时数据结构
- diff_verifier: Diff 验证器

Step 4 Multi-Model 核心：
- cloud_chat_adapter: 云端聊天模型基类
- openai_chat_adapter: OpenAI API 适配器
- ollama_adapter: 本地 Ollama 适配器

Step 4 扩展：LM Studio + llama.cpp
- lmstudio_adapter: LM Studio 适配器（OpenAI-compatible）
- llamacpp_adapter: llama.cpp server 适配器
- generic_local_http_adapter: 通用本地 HTTP 基类
"""

from .base_adapter import BaseToolAdapter
from .claude_cli_adapter import ClaudeCliAdapter
from .opencode_adapter import OpenCodeAdapter
from .codex_adapter import CodexAdapter
from .cloud_chat_adapter import CloudChatAdapter
from .openai_chat_adapter import OpenAIChatAdapter
from .ollama_adapter import OllamaAdapter
from .lmstudio_adapter import LMStudioAdapter
from .llamacpp_adapter import LlamaCppAdapter
from .generic_local_http_adapter import GenericLocalHTTPAdapter
from .types import (
    ToolHealth,
    ToolTask,
    ToolResult,
    ToolCapabilities,
    DiffValidationResult
)
from .diff_verifier import DiffVerifier
# 🔩 H2：evidence 系统级规范
from .evidence import (
    normalize_endpoint,
    finalize_tool_result,
    finalize_health,
    write_tool_event,
    assert_h2_evidence,
    assert_h3_output_kind,  # 🔩 H3：output_kind ↔ diff 绑定
    create_diff_validation_summary,  # 🔩 H3-1：diff_validation 证据链
)

__all__ = [
    "BaseToolAdapter",
    "ClaudeCliAdapter",
    "OpenCodeAdapter",
    "CodexAdapter",
    # Step 4: Multi-model adapters
    "CloudChatAdapter",
    "OpenAIChatAdapter",
    "OllamaAdapter",
    # Step 4 扩展：LM Studio + llama.cpp
    "LMStudioAdapter",
    "LlamaCppAdapter",
    "GenericLocalHTTPAdapter",
    # Runtime types
    "ToolHealth",
    "ToolTask",
    "ToolResult",
    "ToolCapabilities",
    "DiffValidationResult",
    "DiffVerifier",
    # 🔩 H2：evidence 系统级规范
    "normalize_endpoint",
    "finalize_tool_result",
    "finalize_health",
    "write_tool_event",
    "assert_h2_evidence",
    "assert_h3_output_kind",  # 🔩 H3
    "create_diff_validation_summary",  # 🔩 H3-1
]
