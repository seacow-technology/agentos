"""
Decision Snapshot Schema - 不可变的审计数据契约

这个模块定义了 Decision Replay 系统的核心数据结构。
所有字段都是 frozen dataclass，确保审计记录的不可变性。

🔒 SEMANTIC FREEZE (F-1): Governance Replay
-------------------------------------------
Replay = 解释"为什么发生" (Explain "Why it happened")

✅ Replay IS:
   - Explains WHY decisions were made
   - Provides audit trail for compliance
   - Generates statistics from historical data

❌ Replay IS NOT:
   - NOT a debugging tool for runtime issues
   - NOT a decision recomputation engine
   - NOT retroactive judgment ("事后改判")
   - NOT what-if scenario simulator

Guarantee: Past decisions are IMMUTABLE. Same query always returns same historical truth.
Reference: ADR-004 Section F-1

设计原则：
1. 完整性：捕获决策的所有输入、输出、上下文
2. 不可变性：使用 frozen dataclass，防止事后篡改
3. 可追溯性：包含完整的事件链和时间戳
4. 可验证性：提供严格的 schema 校验
"""

from dataclasses import dataclass
from typing import Any, Literal, Optional

# 类型定义
DecisionType = Literal["ALLOW", "PAUSE", "BLOCK", "RETRY"]
FindingKind = Literal["REDLINE", "CONFLICT", "RISK", "RUNTIME"]
Severity = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
ActionStatus = Literal["OK", "FAILED"]


@dataclass(frozen=True)
class EventRef:
    """
    事件引用 - 记录触发决策的原始事件

    包含完整的事件溯源信息，用于 replay 时重建上下文。
    """
    event_id: str      # 事件唯一 ID
    event_type: str    # 事件类型（TASK_CREATED, TASK_STEP_COMPLETED 等）
    source: str        # 事件来源："eventbus" | "polling"
    ts: str            # ISO8601 时间戳


@dataclass(frozen=True)
class FindingSnapshot:
    """
    发现快照 - 记录策略评估发现的问题

    每个 finding 代表一个具体的风险点、冲突或违规。
    """
    kind: FindingKind               # 发现类型
    severity: Severity              # 严重程度
    code: str                       # 问题代码（如 "REDLINE_001", "CONFLICT_API_LIMIT"）
    message: str                    # 人类可读的描述
    evidence: dict[str, Any]        # 证据数据（工具调用、上下文片段等）


@dataclass(frozen=True)
class DecisionSnapshot:
    """
    决策快照 - 完整的决策记录

    这是 Decision Replay 的核心数据结构，包含：
    - 输入：触发事件、策略上下文
    - 处理：评估发现的所有问题
    - 输出：最终决策和执行的动作
    - 性能：决策耗时等指标

    所有字段都是必需的（除非明确标记为 Optional），
    确保审计记录的完整性。
    """
    decision_id: str                      # 决策唯一 ID
    policy: str                           # 应用的策略名称
    event: EventRef                       # 触发决策的事件
    inputs: dict[str, Any]                # 策略输入（task state, context 等）
    findings: list[FindingSnapshot]       # 评估发现的所有问题
    decision: dict[str, Any]              # 最终决策结果
    actions: list[dict[str, Any]]         # 执行的动作列表
    metrics: dict[str, Any]               # 性能指标（耗时、资源使用等）


def validate_decision_snapshot(obj: dict[str, Any]) -> None:
    """
    验证 DecisionSnapshot 的完整性和正确性

    Args:
        obj: 待验证的字典对象

    Raises:
        ValueError: 如果验证失败，抛出详细的错误信息

    验证规则：
    1. 所有必需字段都存在
    2. 类型正确（字符串、字典、列表等）
    3. 枚举值在允许范围内
    4. 嵌套结构完整
    """

    # 1. 验证顶层必需字段
    required_fields = [
        "decision_id", "policy", "event", "inputs",
        "findings", "decision", "actions", "metrics"
    ]

    for field in required_fields:
        if field not in obj:
            raise ValueError(f"Missing required field: {field}")

    # 2. 验证字段类型
    if not isinstance(obj["decision_id"], str) or not obj["decision_id"]:
        raise ValueError("decision_id must be a non-empty string")

    if not isinstance(obj["policy"], str) or not obj["policy"]:
        raise ValueError("policy must be a non-empty string")

    if not isinstance(obj["inputs"], dict):
        raise ValueError("inputs must be a dict")

    if not isinstance(obj["findings"], list):
        raise ValueError("findings must be a list")

    if not isinstance(obj["decision"], dict):
        raise ValueError("decision must be a dict")

    if not isinstance(obj["actions"], list):
        raise ValueError("actions must be a list")

    if not isinstance(obj["metrics"], dict):
        raise ValueError("metrics must be a dict")

    # 3. 验证 EventRef 结构
    event = obj["event"]
    if not isinstance(event, dict):
        raise ValueError("event must be a dict")

    event_required = ["event_id", "event_type", "source", "ts"]
    for field in event_required:
        if field not in event:
            raise ValueError(f"event.{field} is required")
        if not isinstance(event[field], str) or not event[field]:
            raise ValueError(f"event.{field} must be a non-empty string")

    # 验证 source 枚举值
    if event["source"] not in ["eventbus", "polling"]:
        raise ValueError(f"event.source must be 'eventbus' or 'polling', got: {event['source']}")

    # 4. 验证 findings 列表
    for idx, finding in enumerate(obj["findings"]):
        if not isinstance(finding, dict):
            raise ValueError(f"findings[{idx}] must be a dict")

        finding_required = ["kind", "severity", "code", "message", "evidence"]
        for field in finding_required:
            if field not in finding:
                raise ValueError(f"findings[{idx}].{field} is required")

        # 验证 kind 枚举
        valid_kinds = ["REDLINE", "CONFLICT", "RISK", "RUNTIME"]
        if finding["kind"] not in valid_kinds:
            raise ValueError(
                f"findings[{idx}].kind must be one of {valid_kinds}, got: {finding['kind']}"
            )

        # 验证 severity 枚举
        valid_severities = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
        if finding["severity"] not in valid_severities:
            raise ValueError(
                f"findings[{idx}].severity must be one of {valid_severities}, "
                f"got: {finding['severity']}"
            )

        # 验证 code 非空
        if not isinstance(finding["code"], str) or not finding["code"]:
            raise ValueError(f"findings[{idx}].code must be a non-empty string")

        # 验证 message 非空
        if not isinstance(finding["message"], str) or not finding["message"]:
            raise ValueError(f"findings[{idx}].message must be a non-empty string")

        # 验证 evidence 是 dict
        if not isinstance(finding["evidence"], dict):
            raise ValueError(f"findings[{idx}].evidence must be a dict")

    # 5. 验证 decision 结构
    decision = obj["decision"]
    if "decision_type" not in decision:
        raise ValueError("decision.decision_type is required")

    valid_decision_types = ["ALLOW", "PAUSE", "BLOCK", "RETRY"]
    if decision["decision_type"] not in valid_decision_types:
        raise ValueError(
            f"decision.decision_type must be one of {valid_decision_types}, "
            f"got: {decision['decision_type']}"
        )

    # 6. 验证 actions 列表
    for idx, action in enumerate(obj["actions"]):
        if not isinstance(action, dict):
            raise ValueError(f"actions[{idx}] must be a dict")

        if "action_type" not in action:
            raise ValueError(f"actions[{idx}].action_type is required")

        if not isinstance(action["action_type"], str) or not action["action_type"]:
            raise ValueError(f"actions[{idx}].action_type must be a non-empty string")

        # status 是可选的，但如果存在必须是有效值
        if "status" in action:
            valid_statuses = ["OK", "FAILED"]
            if action["status"] not in valid_statuses:
                raise ValueError(
                    f"actions[{idx}].status must be one of {valid_statuses}, "
                    f"got: {action['status']}"
                )


def validate_event_ref(obj: dict[str, Any]) -> None:
    """
    验证 EventRef 结构

    Args:
        obj: 待验证的字典对象

    Raises:
        ValueError: 如果验证失败
    """
    required_fields = ["event_id", "event_type", "source", "ts"]

    for field in required_fields:
        if field not in obj:
            raise ValueError(f"EventRef.{field} is required")
        if not isinstance(obj[field], str) or not obj[field]:
            raise ValueError(f"EventRef.{field} must be a non-empty string")

    if obj["source"] not in ["eventbus", "polling"]:
        raise ValueError(f"EventRef.source must be 'eventbus' or 'polling', got: {obj['source']}")


def validate_finding_snapshot(obj: dict[str, Any]) -> None:
    """
    验证 FindingSnapshot 结构

    Args:
        obj: 待验证的字典对象

    Raises:
        ValueError: 如果验证失败
    """
    required_fields = ["kind", "severity", "code", "message", "evidence"]

    for field in required_fields:
        if field not in obj:
            raise ValueError(f"FindingSnapshot.{field} is required")

    # 验证 kind 枚举
    valid_kinds = ["REDLINE", "CONFLICT", "RISK", "RUNTIME"]
    if obj["kind"] not in valid_kinds:
        raise ValueError(f"FindingSnapshot.kind must be one of {valid_kinds}, got: {obj['kind']}")

    # 验证 severity 枚举
    valid_severities = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    if obj["severity"] not in valid_severities:
        raise ValueError(
            f"FindingSnapshot.severity must be one of {valid_severities}, got: {obj['severity']}"
        )

    # 验证 code 非空
    if not isinstance(obj["code"], str) or not obj["code"]:
        raise ValueError("FindingSnapshot.code must be a non-empty string")

    # 验证 message 非空
    if not isinstance(obj["message"], str) or not obj["message"]:
        raise ValueError("FindingSnapshot.message must be a non-empty string")

    # 验证 evidence 是 dict
    if not isinstance(obj["evidence"], dict):
        raise ValueError("FindingSnapshot.evidence must be a dict")
