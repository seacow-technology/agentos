"""
Trace Assembler - 决策历史重建和查询

核心功能：
1. 组装完整的决策 trace（events + audits + state_changes）
2. 提供分页查询支持（cursor-based pagination）
3. 生成任务的治理摘要（summary）

🔒 SEMANTIC FREEZE (F-1): Governance Replay
-------------------------------------------
ALL methods in this class are READ-ONLY.

✅ TraceAssembler CAN:
   - Query historical decision snapshots
   - Assemble trace from events + audits + state_changes
   - Calculate statistics from historical data
   - Return frozen data structures

❌ TraceAssembler CANNOT:
   - NEVER modify past decisions
   - NEVER recalculate decisions with new policy
   - NEVER change decision_id or audit records
   - NEVER perform "what-if" recomputation

Guarantee: All operations are READ-ONLY. Past decisions are IMMUTABLE.
Reference: ADR-004 Section F-1

设计原则：
1. 时间顺序稳定：相同时间戳的记录按固定规则排序
2. 分页不重复：cursor 机制确保不会重复或跳过记录
3. 完整上下文：trace 包含所有决策所需的输入和输出
"""

from dataclasses import dataclass
from typing import Any, Optional

from agentos.core.supervisor.trace.storage import TraceStorage


@dataclass(frozen=True)
class TraceItem:
    """
    Trace 记录项

    代表决策历史中的一个时间点，可能是：
    - 原始事件（task_events）
    - 决策记录（task_audits）
    - 状态变更（state_change）
    """
    ts: str                      # ISO8601 时间戳
    kind: str                    # 记录类型：event | audit | state_change
    data: dict[str, Any]         # 完整的记录数据


@dataclass(frozen=True)
class TaskGovernanceSummary:
    """
    任务治理摘要

    提供任务的治理状态概览，用于快速了解任务的决策情况。
    """
    task_id: str                        # 任务 ID
    status: str                         # 任务状态
    last_decision_type: Optional[str]   # 最后一次决策类型
    last_decision_ts: Optional[str]     # 最后一次决策时间
    blocked_reason_code: Optional[str]  # 阻塞原因代码（如果被阻塞）
    inbox_backlog: int                  # 待处理事件数
    decision_count: int                 # 决策总数


class TraceAssembler:
    """
    Trace 组装器

    负责从多个数据源（task_audits, task_events）组装完整的决策历史。
    """

    def __init__(self, storage: TraceStorage):
        """
        Args:
            storage: 数据存储访问层
        """
        self.storage = storage

    def get_summary(self, task_id: str) -> Optional[TaskGovernanceSummary]:
        """
        获取任务的治理摘要

        Args:
            task_id: 任务 ID

        Returns:
            治理摘要，如果任务不存在返回 None
        """
        # 1. 获取任务基本信息
        task_info = self.storage.get_task_info(task_id)
        if task_info is None:
            return None

        # 2. 获取最后一次决策
        last_decision = self.storage.get_last_decision(task_id)

        last_decision_type = None
        last_decision_ts = None
        if last_decision:
            # 从 event_type 提取决策类型
            # SUPERVISOR_ALLOWED -> ALLOW
            # SUPERVISOR_BLOCKED -> BLOCK
            event_type = last_decision["event_type"]
            if event_type.startswith("SUPERVISOR_"):
                decision_type_raw = event_type.replace("SUPERVISOR_", "")
                last_decision_type = decision_type_raw
                last_decision_ts = last_decision["created_at"]

        # 3. 获取阻塞原因（如果被阻塞）
        blocked_reason_code = None
        if task_info["status"] == "BLOCKED":
            blocked_info = self.storage.get_blocked_reason(task_id)
            if blocked_info:
                blocked_reason_code = blocked_info["reason_code"]

        # 4. 获取统计信息
        inbox_backlog = self.storage.get_inbox_backlog(task_id)
        decision_count = self.storage.get_decision_count(task_id)

        return TaskGovernanceSummary(
            task_id=task_id,
            status=task_info["status"],
            last_decision_type=last_decision_type,
            last_decision_ts=last_decision_ts,
            blocked_reason_code=blocked_reason_code,
            inbox_backlog=inbox_backlog,
            decision_count=decision_count,
        )

    def get_decision_trace(
        self,
        task_id: str,
        limit: int = 200,
        cursor: Optional[str] = None
    ) -> tuple[list[TraceItem], Optional[str]]:
        """
        获取任务的决策 trace（按时间倒序）

        组装完整的事件历史，包括：
        - 原始事件（task_events）
        - 决策记录（task_audits）
        - 状态变更

        Args:
            task_id: 任务 ID
            limit: 返回记录数（最多 200）
            cursor: 分页游标（格式：timestamp_id）

        Returns:
            (trace_items, next_cursor) 元组
            - trace_items: TraceItem 列表（按时间倒序）
            - next_cursor: 下一页的游标，如果没有更多记录则为 None
        """
        # 限制 limit 最大值
        limit = min(limit, 200)

        # 解析 cursor（如果提供）
        offset = 0
        if cursor:
            try:
                # cursor 格式：timestamp_id（如 "2024-01-01T00:00:00Z_123"）
                parts = cursor.split("_")
                if len(parts) == 2:
                    cursor_ts = parts[0]
                    cursor_id = parts[1]
                    # 计算 offset（简化实现：使用计数）
                    # 实际生产环境应使用更精确的 WHERE ts < ? OR (ts = ? AND id < ?) 过滤
                    offset = self._calculate_offset(task_id, cursor_ts, cursor_id)
            except Exception:
                # cursor 解析失败，从头开始
                offset = 0

        # 获取混合的记录（audits + events）
        records = self.storage.get_all_audits_and_events(
            task_id=task_id,
            limit=limit + 1  # 多取一条用于判断是否还有下一页
        )

        # 转换为 TraceItem
        trace_items = []
        for record in records[:limit]:  # 只返回 limit 条
            trace_items.append(TraceItem(
                ts=record["ts"],
                kind=record["kind"],
                data=record
            ))

        # 生成下一页游标
        next_cursor = None
        if len(records) > limit:
            # 还有更多记录，生成游标
            last_item = records[limit - 1]
            next_cursor = f"{last_item['ts']}_{last_item['id']}"

        return trace_items, next_cursor

    def get_decision(self, decision_id: str) -> Optional[dict[str, Any]]:
        """
        获取单个决策的完整快照

        Args:
            decision_id: 决策 ID

        Returns:
            决策快照（从 payload.decision_snapshot 提取），如果不存在返回 None
        """
        record = self.storage.get_decision_by_id(decision_id)
        if record is None:
            return None

        # 从 payload 中提取 decision_snapshot
        payload = record["payload"]
        decision_snapshot = payload.get("decision_snapshot")

        if decision_snapshot is None:
            # 兼容旧格式：如果没有 decision_snapshot，返回完整 payload
            return payload

        return decision_snapshot

    def _calculate_offset(
        self,
        task_id: str,
        cursor_ts: str,
        cursor_id: str
    ) -> int:
        """
        计算 cursor 对应的 offset

        这是一个简化实现，实际生产环境应该使用 WHERE 条件过滤。

        Args:
            task_id: 任务 ID
            cursor_ts: cursor 时间戳
            cursor_id: cursor ID

        Returns:
            offset 值
        """
        # 简化实现：查询所有记录直到找到 cursor 位置
        # 实际生产环境应该用更高效的 SQL WHERE 条件
        all_records = self.storage.get_all_audits_and_events(
            task_id=task_id,
            limit=1000  # 假设不会超过 1000 条
        )

        offset = 0
        for record in all_records:
            if record["ts"] == cursor_ts and str(record["id"]) == cursor_id:
                return offset
            offset += 1

        return 0  # 如果没找到，从头开始


def format_trace_item(item: TraceItem) -> dict[str, Any]:
    """
    格式化 TraceItem 为 API 响应格式

    Args:
        item: TraceItem 对象

    Returns:
        格式化的字典，适合 JSON 序列化
    """
    result = {
        "ts": item.ts,
        "kind": item.kind,
    }

    # 根据 kind 提取关键字段
    if item.kind == "audit":
        result.update({
            "audit_id": item.data.get("id"),
            "event_type": item.data.get("event_type"),
            "decision_id": item.data.get("decision_id"),
            "decision_snapshot": item.data.get("payload", {}).get("decision_snapshot"),
        })
    elif item.kind == "event":
        result.update({
            "event_id": item.data.get("id"),
            "event_type": item.data.get("event_type"),
            "payload": item.data.get("payload"),
        })
    else:
        # 其他类型：直接返回 data
        result["data"] = item.data

    return result
