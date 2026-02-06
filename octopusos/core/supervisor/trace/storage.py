"""
Trace Storage - 数据访问层

提供统一的数据访问接口，封装所有 SQL 查询逻辑。

设计原则：
1. 单一职责：只负责数据读取，不做业务逻辑
2. 类型安全：返回类型明确的字典或列表
3. 性能优化：使用索引友好的查询模式
"""

import json
import sqlite3
from typing import Any, Optional


class TraceStorage:
    """
    Trace 数据存储访问层

    封装所有与 Decision Replay 相关的数据库查询。
    """

    def __init__(self, conn: sqlite3.Connection):
        """
        Args:
            conn: SQLite 数据库连接（必须设置 row_factory）
        """
        self.conn = conn

    def get_task_info(self, task_id: str) -> Optional[dict[str, Any]]:
        """
        获取任务基本信息

        Args:
            task_id: 任务 ID

        Returns:
            任务信息字典，如果不存在返回 None
        """
        cursor = self.conn.execute(
            """
            SELECT task_id, status, created_at, updated_at
            FROM tasks
            WHERE task_id = ?
            """,
            (task_id,)
        )
        row = cursor.fetchone()
        if row is None:
            return None

        return {
            "task_id": row["task_id"],
            "status": row["status"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def get_last_decision(self, task_id: str) -> Optional[dict[str, Any]]:
        """
        获取任务的最后一次决策

        Args:
            task_id: 任务 ID

        Returns:
            最后一次决策的审计记录，如果不存在返回 None
        """
        cursor = self.conn.execute(
            """
            SELECT audit_id, decision_id, event_type, payload, created_at
            FROM task_audits
            WHERE task_id = ?
              AND event_type LIKE 'SUPERVISOR_%'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (task_id,)
        )
        row = cursor.fetchone()
        if row is None:
            return None

        payload = json.loads(row["payload"]) if row["payload"] else {}

        return {
            "audit_id": row["audit_id"],
            "decision_id": row["decision_id"],
            "event_type": row["event_type"],
            "payload": payload,
            "created_at": row["created_at"],
        }

    def get_inbox_backlog(self, task_id: str) -> int:
        """
        获取任务的 inbox backlog（未处理事件数）

        Args:
            task_id: 任务 ID

        Returns:
            未处理事件数量
        """
        cursor = self.conn.execute(
            """
            SELECT COUNT(*) as count
            FROM supervisor_inbox
            WHERE task_id = ?
              AND status = 'pending'
            """,
            (task_id,)
        )
        row = cursor.fetchone()
        return row["count"] if row else 0

    def get_decision_count(self, task_id: str) -> int:
        """
        获取任务的决策总数

        Args:
            task_id: 任务 ID

        Returns:
            决策总数
        """
        cursor = self.conn.execute(
            """
            SELECT COUNT(*) as count
            FROM task_audits
            WHERE task_id = ?
              AND event_type LIKE 'SUPERVISOR_%'
            """,
            (task_id,)
        )
        row = cursor.fetchone()
        return row["count"] if row else 0

    def get_audit_records(
        self,
        task_id: str,
        limit: int = 200,
        offset: int = 0
    ) -> list[dict[str, Any]]:
        """
        获取任务的审计记录（按时间倒序）

        Args:
            task_id: 任务 ID
            limit: 返回记录数
            offset: 偏移量

        Returns:
            审计记录列表
        """
        cursor = self.conn.execute(
            """
            SELECT audit_id, decision_id, event_type, payload, created_at,
                   source_event_ts, supervisor_processed_at
            FROM task_audits
            WHERE task_id = ?
              AND event_type LIKE 'SUPERVISOR_%'
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            (task_id, limit, offset)
        )

        records = []
        for row in cursor:
            payload = json.loads(row["payload"]) if row["payload"] else {}
            records.append({
                "audit_id": row["audit_id"],
                "decision_id": row["decision_id"],
                "event_type": row["event_type"],
                "payload": payload,
                "created_at": row["created_at"],
                "source_event_ts": row["source_event_ts"],
                "supervisor_processed_at": row["supervisor_processed_at"],
            })

        return records

    def get_task_events(
        self,
        task_id: str,
        limit: int = 200,
        offset: int = 0
    ) -> list[dict[str, Any]]:
        """
        获取任务的事件记录（按时间倒序）

        Args:
            task_id: 任务 ID
            limit: 返回记录数
            offset: 偏移量

        Returns:
            事件记录列表
        """
        cursor = self.conn.execute(
            """
            SELECT event_id, event_type, payload, created_at
            FROM task_events
            WHERE task_id = ?
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            (task_id, limit, offset)
        )

        records = []
        for row in cursor:
            payload = json.loads(row["payload"]) if row["payload"] else {}
            records.append({
                "event_id": row["event_id"],
                "event_type": row["event_type"],
                "payload": payload,
                "created_at": row["created_at"],
            })

        return records

    def get_decision_by_id(self, decision_id: str) -> Optional[dict[str, Any]]:
        """
        通过 decision_id 获取决策快照

        Args:
            decision_id: 决策 ID

        Returns:
            决策快照，如果不存在返回 None
        """
        cursor = self.conn.execute(
            """
            SELECT audit_id, task_id, decision_id, event_type, payload, created_at,
                   source_event_ts, supervisor_processed_at
            FROM task_audits
            WHERE decision_id = ?
            LIMIT 1
            """,
            (decision_id,)
        )
        row = cursor.fetchone()
        if row is None:
            return None

        payload = json.loads(row["payload"]) if row["payload"] else {}

        return {
            "audit_id": row["audit_id"],
            "task_id": row["task_id"],
            "decision_id": row["decision_id"],
            "event_type": row["event_type"],
            "payload": payload,
            "created_at": row["created_at"],
            "source_event_ts": row["source_event_ts"],
            "supervisor_processed_at": row["supervisor_processed_at"],
        }

    def get_blocked_reason(self, task_id: str) -> Optional[dict[str, Any]]:
        """
        获取任务被阻塞的原因（最近一次 BLOCK 决策）

        Args:
            task_id: 任务 ID

        Returns:
            阻塞原因信息，如果不存在返回 None
        """
        cursor = self.conn.execute(
            """
            SELECT audit_id, decision_id, payload, created_at
            FROM task_audits
            WHERE task_id = ?
              AND event_type = 'SUPERVISOR_BLOCKED'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (task_id,)
        )
        row = cursor.fetchone()
        if row is None:
            return None

        payload = json.loads(row["payload"]) if row["payload"] else {}

        # 从 decision_snapshot 中提取 reason code
        decision_snapshot = payload.get("decision_snapshot", {})
        findings = decision_snapshot.get("findings", [])
        reason_code = findings[0]["code"] if findings else None

        return {
            "audit_id": row["audit_id"],
            "decision_id": row["decision_id"],
            "reason_code": reason_code,
            "created_at": row["created_at"],
        }

    def get_all_audits_and_events(
        self,
        task_id: str,
        limit: int = 200
    ) -> list[dict[str, Any]]:
        """
        获取任务的所有审计记录和事件（按时间倒序，混合排序）

        用于组装完整的 trace，包括：
        - task_audits 中的决策记录
        - task_events 中的原始事件
        - 其他状态变更记录

        Args:
            task_id: 任务 ID
            limit: 返回记录数

        Returns:
            混合的记录列表，每条记录包含 kind 字段标识类型
        """
        # 使用 UNION ALL 合并多个来源的记录，统一按时间排序
        cursor = self.conn.execute(
            """
            SELECT
                'audit' as kind,
                created_at as ts,
                audit_id as id,
                event_type,
                payload,
                decision_id,
                source_event_ts,
                supervisor_processed_at
            FROM task_audits
            WHERE task_id = ?

            UNION ALL

            SELECT
                'event' as kind,
                created_at as ts,
                CAST(event_id as TEXT) as id,
                event_type,
                payload,
                NULL as decision_id,
                NULL as source_event_ts,
                NULL as supervisor_processed_at
            FROM task_events
            WHERE task_id = ?

            ORDER BY ts DESC
            LIMIT ?
            """,
            (task_id, task_id, limit)
        )

        records = []
        for row in cursor:
            payload = json.loads(row["payload"]) if row["payload"] else {}
            records.append({
                "kind": row["kind"],
                "ts": row["ts"],
                "id": row["id"],
                "event_type": row["event_type"],
                "payload": payload,
                "decision_id": row["decision_id"],
                "source_event_ts": row["source_event_ts"],
                "supervisor_processed_at": row["supervisor_processed_at"],
            })

        return records
