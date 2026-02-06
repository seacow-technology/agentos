"""
Event Poller

负责从数据库增量拉取事件并写入 inbox（兜底机制）。
"""

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from .inbox import InboxManager
from .models import SupervisorEvent, EventSource
from agentos.core.time import utc_now_iso


logger = logging.getLogger(__name__)


class EventPoller:
    """
    事件 Poller（兜底慢路径）

    职责：
    1. 从 task_audits 等表增量拉取事件
    2. 写入 supervisor_inbox（去重）
    3. 维护 checkpoint（游标）

    设计原则：
    - DB 为真相源
    - Checkpoint 保证不丢事件
    - 与 EventBus 的重复由 inbox 去重
    """

    def __init__(
        self,
        db_path: Path,
        inbox_manager: InboxManager,
        source_table: str = "task_audits",
        batch_size: int = 100,
    ):
        """
        初始化 Poller

        Args:
            db_path: 数据库路径
            inbox_manager: Inbox 管理器
            source_table: 源表名（默认 "task_audits"）
            batch_size: 批处理大小
        """
        self.db_path = db_path
        self.inbox_manager = inbox_manager
        self.source_table = source_table
        self.batch_size = batch_size

        logger.info(
            f"EventPoller initialized (source_table={source_table}, batch_size={batch_size})"
        )

    def scan(self, conn: Optional[sqlite3.Connection] = None) -> int:
        """
        扫描并拉取新事件

        Args:
            conn: 可选的数据库连接（用于共享事务）

        Returns:
            拉取的事件数量
        """
        own_connection = conn is None
        if own_connection:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            # 获取 checkpoint
            last_seen_id = self._get_checkpoint(cursor)
            logger.debug(f"Checkpoint: last_seen_id={last_seen_id}")

            # 拉取新事件
            events = self._fetch_new_events(cursor, last_seen_id)

            if not events:
                logger.debug("No new events to poll")
                return 0

            logger.info(f"Polling {len(events)} new events from {self.source_table}")

            # 写入 inbox
            inserted_count = 0
            max_id = last_seen_id

            for event_row in events:
                try:
                    # 转换为 SupervisorEvent
                    supervisor_event = self._convert_to_supervisor_event(event_row)

                    # 写入 inbox（去重）
                    inserted = self.inbox_manager.insert_event(supervisor_event, cursor)

                    if inserted:
                        inserted_count += 1

                    # 更新 max_id
                    event_id = event_row.get("audit_id") or event_row.get("id")
                    if event_id and event_id > max_id:
                        max_id = event_id

                except Exception as e:
                    logger.error(
                        f"Error processing polled event {event_row.get('audit_id', 'unknown')}: {e}",
                        exc_info=True,
                    )
                    # 继续处理其他事件

            # 更新 checkpoint
            if max_id > last_seen_id:
                self._update_checkpoint(cursor, max_id)

            if own_connection:
                conn.commit()

            logger.info(
                f"✅ Polled {inserted_count}/{len(events)} new events "
                f"(checkpoint: {last_seen_id} -> {max_id})"
            )
            return inserted_count

        finally:
            if own_connection:
                conn.close()

    def _get_checkpoint(self, cursor: sqlite3.Cursor) -> int:
        """
        获取当前 checkpoint

        Args:
            cursor: 数据库游标

        Returns:
            last_seen_id（如果不存在则返回 0）
        """
        cursor.execute(
            """
            SELECT last_seen_id
            FROM supervisor_checkpoint
            WHERE source_table = ?
            """,
            (self.source_table,),
        )

        row = cursor.fetchone()
        return row["last_seen_id"] if row else 0

    def _update_checkpoint(self, cursor: sqlite3.Cursor, last_seen_id: int) -> None:
        """
        更新 checkpoint

        Args:
            cursor: 数据库游标
            last_seen_id: 新的 last_seen_id
        """
        cursor.execute(
            """
            INSERT OR REPLACE INTO supervisor_checkpoint (
                source_table, last_seen_id, updated_at
            ) VALUES (?, ?, ?)
            """,
            (self.source_table, last_seen_id, utc_now_iso()),
        )

    def _fetch_new_events(
        self, cursor: sqlite3.Cursor, last_seen_id: int
    ) -> List[sqlite3.Row]:
        """
        从源表拉取新事件

        Args:
            cursor: 数据库游标
            last_seen_id: 上次处理的最大 ID

        Returns:
            事件行列表
        """
        if self.source_table == "task_audits":
            cursor.execute(
                """
                SELECT audit_id, task_id, event_type, payload, created_at, level
                FROM task_audits
                WHERE audit_id > ?
                ORDER BY audit_id ASC
                LIMIT ?
                """,
                (last_seen_id, self.batch_size),
            )
        else:
            # 其他源表可以在这里扩展
            logger.warning(f"Unsupported source_table: {self.source_table}")
            return []

        return cursor.fetchall()

    def _convert_to_supervisor_event(self, row: sqlite3.Row) -> SupervisorEvent:
        """
        将数据库行转换为 SupervisorEvent

        Args:
            row: 数据库行

        Returns:
            SupervisorEvent 对象
        """
        # 解析 payload
        payload = {}
        if row.get("payload"):
            try:
                payload = json.loads(row["payload"])
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse payload JSON: {e}")

        # 生成事件 ID（使用 audit_id 作为唯一标识）
        event_id = f"polling_{self.source_table}_{row['audit_id']}"

        return SupervisorEvent(
            event_id=event_id,
            source=EventSource.POLLING,
            task_id=row["task_id"],
            event_type=row["event_type"],
            ts=row.get("created_at", utc_now_iso()),
            payload=payload,
        )

    def get_checkpoint_status(self, conn: Optional[sqlite3.Connection] = None) -> Dict[str, any]:
        """
        获取 checkpoint 状态

        Args:
            conn: 可选的数据库连接（用于共享事务）

        Returns:
            Checkpoint 状态字典
        """
        own_connection = conn is None
        if own_connection:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT last_seen_id, updated_at, metadata
                FROM supervisor_checkpoint
                WHERE source_table = ?
                """,
                (self.source_table,),
            )

            row = cursor.fetchone()

            if not row:
                return {
                    "source_table": self.source_table,
                    "last_seen_id": 0,
                    "updated_at": None,
                    "metadata": None,
                }

            return {
                "source_table": self.source_table,
                "last_seen_id": row["last_seen_id"],
                "updated_at": row["updated_at"],
                "metadata": json.loads(row["metadata"]) if row["metadata"] else None,
            }

        finally:
            if own_connection:
                conn.close()
