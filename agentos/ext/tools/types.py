"""
Tool Runtime Types - Step 3 Runtime 核心类型定义

定义 Tool Outsourcing Runtime 的标准数据结构。
"""

from typing import Literal, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class ToolHealth:
    """
    Tool 健康检查结果
    
    六态模型（Step 4 扩展 + LM Studio/llama.cpp）：
    - connected: 工具Available，认证成功
    - not_configured: 工具 CLI 不存在 / API token 缺失
    - invalid_token: 工具存在但认证失败
    - unreachable: 工具Available但 API 超时/不可达
    - model_missing: 本地模型不存在（仅 local adapter）
    - schema_mismatch: 本地模型返回格式不匹配（仅 local adapter）
    
    🔒 钉子 2：错误必须分类（运维排查必需）
    """
    status: Literal["connected", "not_configured", "invalid_token", "unreachable", "model_missing", "schema_mismatch"]
    details: str
    checked_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    # 🔒 钉子 2：错误分类（运维排查必需）
    error_category: Optional[Literal["config", "auth", "network", "model", "schema", "runtime"]] = None
    
    def is_healthy(self) -> bool:
        """是否健康（Available于外包）"""
        return self.status == "connected"
    
    def categorize_error(self) -> str:
        """
        自动分类错误（🔒 钉子 2）
        
        Returns:
            错误类别
        """
        if self.error_category:
            return self.error_category
        
        # 自动推断
        if self.status == "not_configured":
            return "config"
        elif self.status == "invalid_token":
            return "auth"
        elif self.status == "unreachable":
            return "network"
        elif self.status == "model_missing":
            return "model"
        elif self.status == "schema_mismatch":
            return "schema"
        else:
            return "runtime"


@dataclass
class ToolTask:
    """
    Tool 任务描述
    
    Runtime 层传给 Adapter 的最小任务单元。
    """
    task_id: str
    instruction: str
    repo_path: str
    allowed_paths: List[str] = field(default_factory=list)
    forbidden_paths: List[str] = field(default_factory=list)
    timeout_seconds: int = 300
    
    def to_dict(self):
        return {
            "task_id": self.task_id,
            "instruction": self.instruction,
            "repo_path": self.repo_path,
            "allowed_paths": self.allowed_paths,
            "forbidden_paths": self.forbidden_paths,
            "timeout_seconds": self.timeout_seconds
        }


@dataclass
class ToolResult:
    """
    Tool 执行结果
    
    Runtime 必须字段（Step 3 核心数据结构）。
    Tool 只能产出 diff，不能直接写 repo / commit。
    
    Step 4 扩展：添加 model_id / provider 字段
    
    🔒 钉子 3：输出语义类型（Mode System 支点）
    """
    tool: str
    status: Literal["success", "partial_success", "failed", "timeout"]
    diff: str  # unified diff format
    files_touched: List[str]
    line_count: int
    tool_run_id: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    # Step 4: 多模型标识
    model_id: Optional[str] = None  # e.g., "gpt-4.1", "claude-3.5-sonnet", "llama3"
    provider: Optional[Literal["cloud", "local"]] = None
    
    # 🔒 钉子 3：输出语义类型（Mode System 必需）
    output_kind: Literal["diff", "plan", "analysis", "explanation", "diagnosis"] = "diff"
    
    # 🔩 H2：error_category 进入 evidence chain（运维审计必需）
    error_category: Optional[Literal["config", "auth", "network", "model", "schema", "runtime"]] = None
    endpoint: Optional[str] = None  # 脱敏端点（只保留 host，如 "http://localhost:1234"）
    
    # Optional
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    error_message: Optional[str] = None
    
    # 🔩 H3-1：diff_validation 证据链（运维审计必需）
    # 存储 DiffValidationResult 的序列化形式
    diff_validation: Optional[dict] = None
    
    # 🔩 钉子 A：Mock 标记（内部字段，不序列化到 JSON）
    _mock_used: bool = field(default=False, repr=False, compare=False)
    _mock_reason: Optional[str] = field(default=None, repr=False, compare=False)
    
    # 🔩 钉子 C：权力断点标记（断言用）
    wrote_files: bool = False  # Tool 是否直接写了文件（必须 False）
    committed: bool = False    # Tool 是否直接 commit（必须 False）
    
    def to_dict(self):
        return {
            "tool": self.tool,
            "status": self.status,
            "diff": self.diff,
            "files_touched": self.files_touched,
            "line_count": self.line_count,
            "tool_run_id": self.tool_run_id,
            "timestamp": self.timestamp,
            # Step 4: 多模型字段
            "model_id": self.model_id,
            "provider": self.provider,
            # 🔒 钉子 3：输出语义类型
            "output_kind": self.output_kind,
            # 🔩 H2：运维审计字段
            "error_category": self.error_category,
            "endpoint": self.endpoint,
            # Optional
            "stdout": self.stdout,
            "stderr": self.stderr,
            "error_message": self.error_message,
            # 🔩 H3-1：diff_validation 证据链
            "diff_validation": self.diff_validation,
            # 🔩 钉子 C：显式声明权力断点
            "wrote_files": self.wrote_files,
            "committed": self.committed
        }


@dataclass
class ToolCapabilities:
    """
    Tool 能力声明
    
    支持 Local / Cloud 的 Adapter 模型。
    
    🔒 钉子 1：Mode System 必须知道模型能力
    """
    execution_mode: Literal["cloud", "local"]
    supports_diff: bool
    supports_patch: bool
    supports_health_check: bool
    
    # 🔒 钉子 1：模型能力声明（Mode System 必需）
    chat: bool = True  # 是否支持对话
    json_mode: bool = False  # 是否支持 JSON 严格输出
    function_call: bool = False  # 是否支持函数调用
    stream: bool = False  # 是否支持流式输出
    long_context: bool = False  # 是否支持长上下文（>8K tokens）
    diff_quality: Literal["low", "medium", "high"] = "medium"  # Diff 生成质量
    
    def to_dict(self):
        return {
            "execution_mode": self.execution_mode,
            "supports_diff": self.supports_diff,
            "supports_patch": self.supports_patch,
            "supports_health_check": self.supports_health_check,
            # Mode System 能力
            "chat": self.chat,
            "json_mode": self.json_mode,
            "function_call": self.function_call,
            "stream": self.stream,
            "long_context": self.long_context,
            "diff_quality": self.diff_quality
        }


@dataclass
class DiffValidationResult:
    """
    Diff 验证结果
    
    🔩 补强1：记录 format-patch 标准化证据
    """
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    normalized_from_format_patch: bool = False  # 🔩 补强1：是否经过 format-patch 标准化
    normalized_start_line: Optional[int] = None  # 🔩 补强1改进：diff 从第几行开始（0-based，排查用）
    
    def to_dict(self):
        return {
            "is_valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "normalized_from_format_patch": self.normalized_from_format_patch,  # 🔩 补强1
            "normalized_start_line": self.normalized_start_line  # 🔩 补强1改进
        }
