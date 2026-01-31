"""
Base Policy

所有 Supervisor Policies 的基类。
"""

import logging
import sqlite3
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from ..models import SupervisorEvent, Decision
from ..adapters import GateAdapter, EvaluatorAdapter, AuditAdapter
from agentos.core.time import utc_now_iso


logger = logging.getLogger(__name__)


class BasePolicy(ABC):
    """
    Policy 基类

    提供通用的 adapter 访问和工具方法。
    """

    def __init__(self, db_path: Path):
        """
        初始化 Policy

        Args:
            db_path: 数据库路径
        """
        self.db_path = db_path
        self.gate_adapter = GateAdapter(db_path)
        self.evaluator_adapter = EvaluatorAdapter()
        self.audit_adapter = AuditAdapter(db_path)

        logger.debug(f"{self.__class__.__name__} initialized")

    @abstractmethod
    def evaluate(
        self, event: SupervisorEvent, cursor: sqlite3.Cursor
    ) -> Optional[Decision]:
        """
        评估事件并做出决策

        Args:
            event: Supervisor 事件
            cursor: 数据库游标

        Returns:
            Decision 对象或 None（如果不需要决策）
        """
        pass

    def __call__(
        self, event: SupervisorEvent, cursor: sqlite3.Cursor
    ) -> Optional[Decision]:
        """
        使 Policy 可以直接被调用

        Args:
            event: Supervisor 事件
            cursor: 数据库游标

        Returns:
            Decision 对象或 None
        """
        try:
            decision = self.evaluate(event, cursor)

            # 如果有决策，写入审计
            if decision:
                self.audit_adapter.write_decision(event.task_id, decision, cursor)

            return decision

        except Exception as e:
            logger.error(
                f"{self.__class__.__name__} evaluation failed: {e}", exc_info=True
            )
            # 写入错误审计
            self.audit_adapter.write_error(
                event.task_id,
                str(e),
                {"policy": self.__class__.__name__, "event_type": event.event_type},
                cursor,
            )
            raise

    def get_task_metadata(self, task_id: str, cursor: sqlite3.Cursor) -> dict:
        """
        获取任务元数据

        Args:
            task_id: 任务 ID
            cursor: 数据库游标

        Returns:
            任务元数据字典
        """
        cursor.execute(
            """
            SELECT metadata
            FROM tasks
            WHERE task_id = ?
            """,
            (task_id,),
        )

        row = cursor.fetchone()
        if not row or not row[0]:
            return {}

        import json
        try:
            return json.loads(row[0])
        except json.JSONDecodeError:
            return {}

    def get_task_status(self, task_id: str, cursor: sqlite3.Cursor) -> str:
        """
        获取任务状态

        Args:
            task_id: 任务 ID
            cursor: 数据库游标

        Returns:
            任务状态
        """
        cursor.execute(
            """
            SELECT status
            FROM tasks
            WHERE task_id = ?
            """,
            (task_id,),
        )

        row = cursor.fetchone()
        return row[0] if row else "unknown"

    def update_task_status(
        self, task_id: str, new_status: str, cursor: sqlite3.Cursor
    ) -> None:
        """
        更新任务状态

        Args:
            task_id: 任务 ID
            new_status: 新状态
            cursor: 数据库游标
        """
        from datetime import datetime, timezone

        cursor.execute(
            """
            UPDATE tasks
            SET status = ?, updated_at = ?
            WHERE task_id = ?
            """,
            (new_status, utc_now_iso(), task_id),
        )

        logger.info(f"Task {task_id} status updated: {new_status}")
