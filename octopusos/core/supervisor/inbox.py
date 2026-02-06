"""
Supervisor Inbox 管理

负责事件的去重、持久化和状态管理。
"""

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

from agentos.core.db.registry_db import get_db
from .models import SupervisorEvent, EventSource
from agentos.core.time import utc_now, utc_now_iso


logger = logging.getLogger(__name__)


class InboxManager:
    """
    Inbox 管理器

    职责：
    1. 接收来自 EventBus 或 Polling 的事件
    2. 去重（基于 event_id UNIQUE 约束）
    3. 持久化到 supervisor_inbox 表
    """

    def __init__(self, db_path: Path):
        """
        初始化 Inbox 管理器

        Args:
            db_path: 数据库路径
        """
        self.db_path = db_path
        logger.info("InboxManager initialized")

    def insert_event(
        self, event: SupervisorEvent, cursor: Optional[sqlite3.Cursor] = None
    ) -> bool:
        """
        插入事件到 inbox（带去重）

        Args:
            event: Supervisor 事件
            cursor: 可选的数据库游标（用于事务）

        Returns:
            True 如果成功插入，False 如果事件已存在（重复）
        """
        own_connection = cursor is None
        if own_connection:
            # 使用 get_db() 获取线程本地连接
            conn = get_db()
            cursor = conn.cursor()

        try:
            # 序列化 payload
            payload_json = json.dumps(event.payload, ensure_ascii=False)

            # 插入事件
            cursor.execute(
                """
                INSERT INTO supervisor_inbox (
                    event_id, task_id, event_type, source, payload, received_at, status
                ) VALUES (?, ?, ?, ?, ?, ?, 'pending')
                """,
                (
                    event.event_id,
                    event.task_id,
                    event.event_type,
                    event.source.value,
                    payload_json,
                    utc_now_iso(),
                ),
            )

            if own_connection:
                conn.commit()

            logger.debug(
                f"Event inserted: {event.event_id} ({event.event_type}, task={event.task_id})"
            )
            return True

        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint failed" in str(e):
                logger.debug(f"Event already exists (deduped): {event.event_id}")
                return False
            else:
                logger.error(f"Database integrity error: {e}")
                raise

        except Exception as e:
            logger.error(f"Failed to insert event: {e}", exc_info=True)
            raise
        # 注意：不需要 finally 块来关闭连接，因为 get_db() 返回的是线程本地连接

    def get_pending_count(self) -> int:
        """
        获取待处理事件数量

        Returns:
            待处理事件数量
        """
        # 使用 get_db() 获取线程本地连接，不需要关闭
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT COUNT(*) FROM supervisor_inbox
            WHERE status = 'pending'
            """
        )
        count = cursor.fetchone()[0]
        return count

    def get_backlog_metrics(self) -> Dict[str, any]:
        """
        获取 inbox backlog 指标

        Returns:
            指标字典：
            {
                "pending_count": int,
                "processing_count": int,
                "failed_count": int,
                "oldest_pending_age_seconds": Optional[float]
            }
        """
        # 使用 get_db() 获取线程本地连接，不需要关闭
        conn = get_db()
        cursor = conn.cursor()

        # 统计各状态事件数量
        cursor.execute(
            """
            SELECT status, COUNT(*) as count
            FROM supervisor_inbox
            GROUP BY status
            """
        )
        counts = {row["status"]: row["count"] for row in cursor.fetchall()}

        # 获取最老的待处理事件年龄
        cursor.execute(
            """
            SELECT MIN(received_at) as oldest
            FROM supervisor_inbox
            WHERE status = 'pending'
            """
        )
        oldest_row = cursor.fetchone()
        oldest_age_seconds = None

        if oldest_row and oldest_row["oldest"]:
            try:
                oldest_ts = datetime.fromisoformat(oldest_row["oldest"])
                now_ts = utc_now()
                oldest_age_seconds = (now_ts - oldest_ts).total_seconds()
            except Exception as e:
                logger.warning(f"Failed to parse oldest timestamp: {e}")

        return {
            "pending_count": counts.get("pending", 0),
            "processing_count": counts.get("processing", 0),
            "failed_count": counts.get("failed", 0),
            "completed_count": counts.get("completed", 0),
            "oldest_pending_age_seconds": oldest_age_seconds,
        }

    def cleanup_old_events(self, days: int = 7) -> int:
        """
        清理旧的已完成事件

        Args:
            days: 保留天数

        Returns:
            删除的事件数量
        """
        # 使用 get_db() 获取线程本地连接，不需要关闭
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            """
            DELETE FROM supervisor_inbox
            WHERE status = 'completed'
              AND processed_at < datetime('now', '-' || ? || ' days')
            """,
            (days,),
        )

        deleted_count = cursor.rowcount
        conn.commit()

        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} old events (>{days} days)")

        return deleted_count
