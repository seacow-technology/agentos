"""
Audit Adapter

封装审计事件的写入。
"""

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..models import Decision, Finding
from agentos.core.time import utc_now_iso


logger = logging.getLogger(__name__)


# Supervisor 专用审计事件类型
SUPERVISOR_ALLOWED = "SUPERVISOR_ALLOWED"
SUPERVISOR_PAUSED = "SUPERVISOR_PAUSED"
SUPERVISOR_BLOCKED = "SUPERVISOR_BLOCKED"
SUPERVISOR_RETRY_RECOMMENDED = "SUPERVISOR_RETRY_RECOMMENDED"
SUPERVISOR_DECISION = "SUPERVISOR_DECISION"
SUPERVISOR_ERROR = "SUPERVISOR_ERROR"


class AuditAdapter:
    """
    Audit Adapter

    职责：
    - 封装审计事件写入
    - 提供语义化的接口
    - 确保审计记录完整可追溯
    """

    def __init__(self, db_path: Path):
        """
        初始化 Audit Adapter

        Args:
            db_path: 数据库路径
        """
        self.db_path = db_path
        logger.info("AuditAdapter initialized")

    def write_decision(
        self,
        task_id: str,
        decision: Decision,
        cursor: Optional[sqlite3.Cursor] = None,
    ) -> int:
        """
        写入决策审计事件

        Args:
            task_id: 任务 ID
            decision: 决策对象
            cursor: 数据库游标

        Returns:
            audit_id
        """
        # 根据决策类型选择事件类型
        event_type_map = {
            "allow": SUPERVISOR_ALLOWED,
            "pause": SUPERVISOR_PAUSED,
            "block": SUPERVISOR_BLOCKED,
            "retry": SUPERVISOR_RETRY_RECOMMENDED,
            "require_review": SUPERVISOR_DECISION,
        }

        event_type = event_type_map.get(decision.decision_type.value, SUPERVISOR_DECISION)

        # 构造 payload
        payload = {
            "decision_id": decision.decision_id,
            "decision_type": decision.decision_type.value,
            "reason": decision.reason,
            "findings": [f.to_dict() for f in decision.findings],
            "actions": [a.to_dict() for a in decision.actions],
            "timestamp": decision.timestamp,
        }

        # 根据严重程度确定 level
        level = self._determine_level(decision)

        return self.write_audit_event(
            task_id=task_id,
            event_type=event_type,
            level=level,
            payload=payload,
            cursor=cursor,
        )

    def write_error(
        self,
        task_id: str,
        error_message: str,
        context: Optional[Dict[str, Any]] = None,
        cursor: Optional[sqlite3.Cursor] = None,
    ) -> int:
        """
        写入错误审计事件

        Args:
            task_id: 任务 ID
            error_message: 错误信息
            context: 错误上下文
            cursor: 数据库游标

        Returns:
            audit_id
        """
        payload = {
            "error": error_message,
            "context": context or {},
            "timestamp": utc_now_iso(),
        }

        return self.write_audit_event(
            task_id=task_id,
            event_type=SUPERVISOR_ERROR,
            level="error",
            payload=payload,
            cursor=cursor,
        )

    def write_audit_event(
        self,
        task_id: str,
        event_type: str,
        level: str = "info",
        payload: Optional[Dict[str, Any]] = None,
        cursor: Optional[sqlite3.Cursor] = None,
    ) -> int:
        """
        写入通用审计事件

        Args:
            task_id: 任务 ID
            event_type: 事件类型
            level: 日志级别（info/warn/error）
            payload: 事件载荷
            cursor: 数据库游标

        Returns:
            audit_id
        """
        own_connection = cursor is None
        if own_connection:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

        try:
            # 序列化 payload
            payload_json = json.dumps(payload or {}, ensure_ascii=False)

            # 插入审计事件
            cursor.execute(
                """
                INSERT INTO task_audits (
                    task_id, level, event_type, payload, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    level,
                    event_type,
                    payload_json,
                    utc_now_iso(),
                ),
            )

            audit_id = cursor.lastrowid

            if own_connection:
                conn.commit()

            logger.debug(
                f"Audit event written: {event_type} (task={task_id}, audit_id={audit_id})"
            )
            return audit_id

        finally:
            if own_connection:
                conn.close()

    def get_audit_trail(
        self,
        task_id: str,
        event_type_prefix: Optional[str] = "SUPERVISOR_",
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        获取任务的审计轨迹

        Args:
            task_id: 任务 ID
            event_type_prefix: 事件类型前缀（默认只获取 Supervisor 事件）
            limit: 最大返回数量

        Returns:
            审计事件列表
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            if event_type_prefix:
                cursor.execute(
                    """
                    SELECT audit_id, task_id, level, event_type, payload, created_at
                    FROM task_audits
                    WHERE task_id = ?
                      AND event_type LIKE ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (task_id, f"{event_type_prefix}%", limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT audit_id, task_id, level, event_type, payload, created_at
                    FROM task_audits
                    WHERE task_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (task_id, limit),
                )

            rows = cursor.fetchall()

            # 转换为字典列表
            events = []
            for row in rows:
                event = dict(row)
                # 解析 payload
                if event.get("payload"):
                    try:
                        event["payload"] = json.loads(event["payload"])
                    except json.JSONDecodeError:
                        pass
                events.append(event)

            return events

        finally:
            conn.close()

    def _determine_level(self, decision: Decision) -> str:
        """
        根据决策确定日志级别

        Args:
            decision: 决策对象

        Returns:
            日志级别（info/warn/error）
        """
        if decision.decision_type.value in ["block", "pause"]:
            return "warn"
        elif decision.decision_type.value == "allow":
            return "info"
        elif decision.decision_type.value == "require_review":
            return "warn"
        else:
            return "info"
