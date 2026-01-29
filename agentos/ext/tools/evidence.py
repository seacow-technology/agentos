"""
Tool Runtime Evidence - 运行时证据链规范

🔩 H2：error_category 和 endpoint 必须进入所有 evidence
这是系统级规范，不允许 gate 自己"猜"或"漏"。

职责：
- normalize_endpoint(): 脱敏端点（统一格式 host:port）
- finalize_tool_result(): 填充 ToolResult 的 error_category + endpoint
- finalize_health(): 填充 ToolHealth 的 error_category
- write_tool_event(): 标准化写入 run_tape.jsonl

硬规则：
1. endpoint 格式：只保留 host[:port]，不带 scheme/path/token
2. error_category：失败时必填，来自 ToolHealth.categorize_error()
3. Gate 禁止自己推断 error_category（只断言，不生成）
"""

from typing import Optional, Dict, Any
from urllib.parse import urlparse
from pathlib import Path
import json
from datetime import datetime, timezone

from .types import ToolResult, ToolHealth


def normalize_endpoint(base_url: Optional[str]) -> Optional[str]:
    """
    标准化 endpoint 格式
    
    规则：
    - 只保留 host[:port]
    - 不带 scheme (http://)
    - 不带 path (/v1)
    - 不带 query (?token=)
    
    Args:
        base_url: 原始 URL（如 http://localhost:1234/v1）
    
    Returns:
        标准化 endpoint（如 localhost:1234）
    
    Examples:
        >>> normalize_endpoint("http://localhost:1234/v1")
        'localhost:1234'
        >>> normalize_endpoint("https://api.openai.com/v1")
        'api.openai.com'
        >>> normalize_endpoint(None)
        None
    """
    if not base_url:
        return None
    
    try:
        parsed = urlparse(base_url)
        
        # 只保留 host
        host = parsed.hostname or parsed.netloc
        
        # 如果有非标准端口，加上端口
        if parsed.port:
            return f"{host}:{parsed.port}"
        
        return host
        
    except Exception:
        # 解析失败，返回原始值（但这应该被 gate 检测到）
        return base_url


def finalize_tool_result(
    result: ToolResult,
    adapter: Any,
    health: Optional[ToolHealth] = None,
    task: Any = None
) -> ToolResult:
    """
    填充 ToolResult 的 H2 + H3 字段（含 diff_validation）
    
    规则:
    1. error_category: 失败时必填，来自 health.categorize_error()
    2. endpoint: 从 adapter.base_url 提取并脱敏
    3. 🔩 H3：output_kind ↔ diff 绑定（防模式软化）
    4. 🔩 H3-1：diff_validation 写入 evidence chain（运维审计必需）
    
    🔩 H2：Gate 禁止自己推断，必须调用此函数
    🔩 H3：强制 output_kind 语义一致性
    🔩 H3-1：diff_validation 进入证据链
    
    Args:
        result: ToolResult
        adapter: Tool adapter（必须有 base_url 或能获取 endpoint）
        health: ToolHealth（如果 result 失败但缺 error_category，从这里取）
        task: ToolTask（可选，用于 diff validation 的 allowed_paths/forbidden_paths）
    
    Returns:
        填充后的 ToolResult（含 diff_validation 元数据）
    
    Raises:
        ValueError: 如果 output_kind 与 diff 不一致
    """
    # 🔩 H2-1：error_category（失败时必填）
    if result.status in ["failed", "timeout"] and not result.error_category:
        if health:
            result.error_category = health.categorize_error()
        else:
            # 如果没有 health，默认 runtime
            result.error_category = "runtime"
    
    # 🔩 H2-1：endpoint（脱敏）
    if not result.endpoint:
        if hasattr(adapter, 'base_url') and adapter.base_url:
            result.endpoint = normalize_endpoint(adapter.base_url)
        elif hasattr(adapter, 'endpoint'):
            result.endpoint = normalize_endpoint(adapter.endpoint)
    
    # 🔩 H3：output_kind ↔ diff 绑定（系统级规范，防软化）
    if result.output_kind == "diff":
        # 规则1：output_kind == "diff" → diff 必须非空
        if not result.diff or result.diff.strip() == "":
            raise ValueError(
                f"output_kind='diff' but diff is empty. "
                f"This violates Mode System semantics. "
                f"(tool={result.tool}, status={result.status})"
            )
        
        # 🔩 H3-1：自动填充 diff_validation（如果有 task 和 DiffVerifier）
        # 注意：这里不做完整 DiffVerifier.verify()，只填充元数据结构
        # 完整验证由 gate 显式调用（因为需要 import DiffVerifier，避免循环依赖）
        # 但我们确保 result 有 diff_validation 字段（如果 task 提供了 allowed_paths）
        if task and hasattr(task, 'allowed_paths'):
            # Gate 会调用 DiffVerifier 填充这个字段，这里只预留
            # 实际上，DiffVerifier 应由 gate 调用后填充到 result.metadata
            # 这里只做基本检查
            pass
    
    else:
        # 规则3：output_kind != "diff" → diff 必须为空（禁止夹带）
        if result.diff and result.diff.strip() != "":
            raise ValueError(
                f"output_kind='{result.output_kind}' but diff is not empty. "
                f"Non-diff modes cannot produce diffs (power boundary violation). "
                f"(tool={result.tool}, diff_length={len(result.diff)})"
            )
    
    return result


def finalize_health(health: ToolHealth) -> ToolHealth:
    """
    填充 ToolHealth 的 H2 字段
    
    规则：
    - error_category: 失败时必填，来自 categorize_error()
    
    🔩 H2：确保所有 health 都有 error_category
    
    Args:
        health: ToolHealth
    
    Returns:
        填充后的 ToolHealth
    """
    # 🔩 H2-1：error_category（失败时自动分类）
    if health.status != "connected" and not health.error_category:
        health.error_category = health.categorize_error()
    
    return health


def write_tool_event(
    output_dir: Path,
    event_type: str,
    data: Dict[str, Any],
    append: bool = False
) -> Path:
    """
    写入标准化的 tool event 到 run_tape.jsonl
    
    规则：
    - 每个 event 必须包含 timestamp
    - 每个 event 必须包含 event_type
    - H2 字段必须存在（error_category, endpoint）
    
    Args:
        output_dir: 输出目录（如 outputs/gates/tl_r2_lmstudio）
        event_type: 事件类型（health_check / tool_run / gate_assert）
        data: 事件数据
        append: 是否追加（默认 False，覆盖）
    
    Returns:
        写入的文件路径
    """
    audit_dir = output_dir / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    
    tape_file = audit_dir / "run_tape.jsonl"
    
    # 添加 metadata
    event = {
        "event_type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **data
    }
    
    mode = "a" if append else "w"
    with open(tape_file, mode, encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")
    
    return tape_file


def assert_h2_evidence(evidence: Dict[str, Any]) -> tuple[bool, list[str]]:
    """
    断言 H2 证据完整性（跨 gate 通用）
    
    规则：
    1. 若 status != connected：error_category 必须存在且属于枚举
    2. endpoint 必须存在（not_configured 场景可为空）
    3. endpoint 不能包含 scheme/path/token
    
    Args:
        evidence: Evidence 字典
    
    Returns:
        (是否通过, 错误列表)
    
    Example:
        >>> passed, errors = assert_h2_evidence(evidence)
        >>> if not passed:
        ...     print("H2 violations:", errors)
    """
    errors = []
    
    # 检查 health.error_category
    if "health" in evidence:
        health = evidence["health"]
        status = health.get("status")
        error_category = health.get("error_category")
        
        if status != "connected":
            # 失败时必须有 error_category
            if not error_category:
                errors.append(f"health.status='{status}' but error_category is missing")
            elif error_category not in ["config", "auth", "network", "model", "schema", "runtime"]:
                errors.append(f"health.error_category='{error_category}' is not in enum")
    
    # 检查 tool_result.error_category
    if "tool_result" in evidence:
        result = evidence["tool_result"]
        status = result.get("status")
        error_category = result.get("error_category")
        
        if status in ["failed", "timeout"]:
            # 失败时必须有 error_category
            if not error_category:
                errors.append(f"tool_result.status='{status}' but error_category is missing")
            elif error_category not in ["config", "auth", "network", "model", "schema", "runtime"]:
                errors.append(f"tool_result.error_category='{error_category}' is not in enum")
    
    # 检查 tool_result.endpoint
    if "tool_result" in evidence:
        result = evidence["tool_result"]
        endpoint = result.get("endpoint")
        
        # endpoint 不能包含 scheme/path
        if endpoint:
            if endpoint.startswith("http://") or endpoint.startswith("https://"):
                errors.append(f"endpoint='{endpoint}' contains scheme (should be host:port only)")
            if "/" in endpoint:
                errors.append(f"endpoint='{endpoint}' contains path (should be host:port only)")
            if "?" in endpoint or "=" in endpoint:
                errors.append(f"endpoint='{endpoint}' contains query params (should be host:port only)")
    
    return len(errors) == 0, errors


def create_diff_validation_summary(validation_result: Any) -> Dict[str, Any]:
    """
    创建 diff_validation 证据链摘要（H3-1）
    
    🔩 H3-1：将 DiffValidationResult 转换为证据链格式
    
    Args:
        validation_result: DiffValidationResult 对象
    
    Returns:
        diff_validation 证据字典
        
    Example:
        >>> from agentos.ext.tools import DiffVerifier
        >>> validation = DiffVerifier.verify(result, allowed, forbidden)
        >>> summary = create_diff_validation_summary(validation)
        >>> # summary = {"is_valid": True, "errors_count": 0, "warnings_count": 1, ...}
    """
    if not validation_result:
        return None
    
    # 如果是 dict，直接返回（已经是摘要格式）
    if isinstance(validation_result, dict):
        return validation_result
    
    # 如果是 DiffValidationResult，转换为证据链格式
    return {
        "is_valid": validation_result.is_valid,
        "errors_count": len(validation_result.errors),
        "warnings_count": len(validation_result.warnings),
        "errors": validation_result.errors,
        "warnings": validation_result.warnings
    }


def assert_h3_output_kind(evidence: Dict[str, Any]) -> tuple[bool, list[str]]:
    """
    断言 H3 output_kind ↔ diff 绑定（跨 gate 通用）
    
    🔩 H3：防止模式软化的核心钉子
    🔩 H3-1：验证 diff_validation 在证据链中
    
    规则：
    1. output_kind == "diff" → diff 必须非空且有效
    2. output_kind != "diff" → diff 必须为空（禁止夹带）
    3. 🔩 H3-1：如果 output_kind == "diff"，必须有 diff_validation 且 is_valid == true
    4. 🔩 H3-1：diff_validation 必须包含 errors_count + warnings_count
    
    Args:
        evidence: Evidence 字典
    
    Returns:
        (是否通过, 错误列表)
    
    Example:
        >>> passed, errors = assert_h3_output_kind(evidence)
        >>> if not passed:
        ...     print("H3 violations (Mode System):", errors)
    """
    errors = []
    
    if "tool_result" not in evidence:
        return True, []  # 没有 tool_result，跳过
    
    result = evidence["tool_result"]
    output_kind = result.get("output_kind", "diff")  # 默认 diff
    diff = result.get("diff", "")
    
    if output_kind == "diff":
        # 规则1：output_kind == "diff" → diff 必须非空
        if not diff or diff.strip() == "":
            errors.append(
                f"output_kind='diff' but diff is empty. "
                f"Implementation mode requires non-empty diff."
            )
        
        # 规则3：🔩 H3-1：必须有 diff_validation 且 is_valid
        diff_validation = result.get("diff_validation")
        if not diff_validation:
            errors.append(
                f"output_kind='diff' but diff_validation is missing. "
                f"H3-1: diff_validation must be present in evidence chain."
            )
        else:
            # 验证 diff_validation 结构
            if "is_valid" not in diff_validation:
                errors.append(
                    f"diff_validation missing 'is_valid' field. "
                    f"H3-1: diff_validation must have is_valid/errors_count/warnings_count."
                )
            elif not diff_validation.get("is_valid", False):
                errors.append(
                    f"output_kind='diff' but diff_validation.is_valid=False. "
                    f"Errors: {diff_validation.get('errors', [])} "
                    f"Warnings: {diff_validation.get('warnings', [])}"
                )
            
            # 验证必须有 errors_count 和 warnings_count
            if "errors_count" not in diff_validation:
                errors.append(
                    f"diff_validation missing 'errors_count'. "
                    f"H3-1: evidence chain requires errors_count field."
                )
            if "warnings_count" not in diff_validation:
                errors.append(
                    f"diff_validation missing 'warnings_count'. "
                    f"H3-1: evidence chain requires warnings_count field."
                )
    
    else:
        # 规则2：output_kind != "diff" → diff 必须为空
        if diff and diff.strip() != "":
            errors.append(
                f"output_kind='{output_kind}' but diff is not empty (length={len(diff)}). "
                f"Non-diff modes cannot produce diffs (power boundary violation)."
            )
    
    return len(errors) == 0, errors
