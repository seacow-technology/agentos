"""
Supervisor 核心服务

SupervisorService：主服务类，管理事件摄入和处理
SupervisorProcessor：事件处理器，路由到不同的 policy
"""

import asyncio
import logging
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .models import SupervisorEvent, Decision, DecisionType
from agentos.core.time import utc_now_iso


logger = logging.getLogger(__name__)


class SupervisorService:
    """
    Supervisor 主服务

    职责：
    1. 管理 wake 信号（来自 EventBus 或定时器）
    2. 协调 EventBus 订阅器和 Polling 机制
    3. 运行主处理循环
    """

    def __init__(
        self,
        db_path: Path,
        processor: "SupervisorProcessor",
        poll_interval: int = 10,  # 秒
    ):
        """
        初始化 Supervisor 服务

        Args:
            db_path: 数据库路径
            processor: 事件处理器
            poll_interval: Polling 间隔（秒）
        """
        self.db_path = db_path
        self.processor = processor
        self.poll_interval = poll_interval

        # Wake 信号
        self._wakeup_flag = threading.Event()
        self._running = False
        self._thread: Optional[threading.Thread] = None

        logger.info(f"SupervisorService initialized (poll_interval={poll_interval}s)")

    def start(self) -> None:
        """启动 Supervisor 服务"""
        if self._running:
            logger.warning("SupervisorService already running")
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="SupervisorService")
        self._thread.start()
        logger.info("✅ SupervisorService started")

    def stop(self) -> None:
        """停止 Supervisor 服务"""
        if not self._running:
            return

        logger.info("Stopping SupervisorService...")
        self._running = False
        self._wakeup_flag.set()  # 唤醒线程以便退出

        if self._thread:
            self._thread.join(timeout=5)
            if self._thread.is_alive():
                logger.warning("SupervisorService thread did not stop gracefully")
            else:
                logger.info("✅ SupervisorService stopped")

    def wake(self, reason: str = "unknown") -> None:
        """
        唤醒 Supervisor（由 EventBus 订阅器或外部触发）

        Args:
            reason: 唤醒原因（用于日志）
        """
        logger.debug(f"Supervisor woken up: {reason}")
        self._wakeup_flag.set()

    def _run_loop(self) -> None:
        """主处理循环（运行在独立线程）"""
        logger.info("Supervisor main loop started")

        while self._running:
            # 等待唤醒或超时
            woken = self._wakeup_flag.wait(timeout=self.poll_interval)
            self._wakeup_flag.clear()

            if not self._running:
                break

            reason = "eventbus" if woken else "polling_timeout"
            logger.debug(f"Processing events (reason: {reason})")

            try:
                # 处理待处理事件
                self.processor.process_pending_events()
            except Exception as e:
                logger.error(f"Error in supervisor processing: {e}", exc_info=True)

        logger.info("Supervisor main loop exited")


class SupervisorProcessor:
    """
    Supervisor 事件处理器

    职责：
    1. 从 DB 拉取未处理事件
    2. 路由到对应的 policy
    3. 执行决策（通过 adapters）
    4. 写入审计
    5. 处理 Guardian verdict（路由到 VerdictConsumer）
    """

    def __init__(
        self,
        db_path: Path,
        policy_router: Optional["PolicyRouter"] = None,
        verdict_consumer: Optional[Any] = None,
        batch_size: int = 50,
    ):
        """
        初始化事件处理器

        Args:
            db_path: 数据库路径
            policy_router: Policy 路由器
            verdict_consumer: VerdictConsumer 实例（处理 Guardian verdicts）
            batch_size: 批处理大小
        """
        self.db_path = db_path
        self.policy_router = policy_router
        self.verdict_consumer = verdict_consumer
        self.batch_size = batch_size

        logger.info(f"SupervisorProcessor initialized (batch_size={batch_size})")

    def process_pending_events(self) -> int:
        """
        处理所有待处理的事件

        Returns:
            处理的事件数量
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            # 拉取待处理事件
            events = self._fetch_pending_events(cursor)

            if not events:
                logger.debug("No pending events to process")
                return 0

            logger.info(f"Processing {len(events)} pending events")

            processed_count = 0
            for event_row in events:
                try:
                    # 标记为处理中
                    self._mark_event_processing(cursor, event_row["event_id"])
                    conn.commit()

                    # 处理事件
                    event = SupervisorEvent.from_db_row(dict(event_row))
                    self.process_event(event, cursor)

                    # 标记为已完成
                    self._mark_event_completed(cursor, event_row["event_id"])
                    conn.commit()

                    processed_count += 1

                except Exception as e:
                    logger.error(
                        f"Error processing event {event_row['event_id']}: {e}",
                        exc_info=True,
                    )
                    # 标记为失败
                    self._mark_event_failed(cursor, event_row["event_id"], str(e))
                    conn.commit()

            logger.info(f"✅ Processed {processed_count}/{len(events)} events")
            return processed_count

        finally:
            conn.close()

    def process_event(self, event: SupervisorEvent, cursor: sqlite3.Cursor) -> None:
        """
        处理单个事件

        Args:
            event: Supervisor 事件
            cursor: 数据库游标
        """
        logger.info(
            f"Processing event: {event.event_type} for task {event.task_id}"
        )

        # Route Guardian events to VerdictConsumer
        if event.event_type.startswith("GUARDIAN_"):
            if self.verdict_consumer is None:
                logger.warning("No verdict_consumer configured, skipping Guardian event")
                return

            try:
                # Guardian events are handled by VerdictConsumer
                # For now, we log and skip - actual integration happens in policies
                logger.debug(f"Guardian event detected: {event.event_type}")
                # The verdict_consumer.apply_verdict() is called by policies, not here
            except Exception as e:
                logger.error(f"Error processing Guardian event: {e}", exc_info=True)
                raise
            return

        # 路由到 policy
        if self.policy_router is None:
            logger.warning("No policy_router configured, skipping event processing")
            return

        try:
            decision = self.policy_router.route(event, cursor)

            if decision:
                logger.info(
                    f"Decision: {decision.decision_type.value} for task {event.task_id}"
                )
                # 执行决策（由 policy 内部完成，或通过 adapters）
                # 这里只记录日志，实际执行在 policy 中
            else:
                logger.debug(f"No decision made for event {event.event_type}")

        except Exception as e:
            logger.error(f"Error routing event to policy: {e}", exc_info=True)
            raise

    def _fetch_pending_events(self, cursor: sqlite3.Cursor) -> List[sqlite3.Row]:
        """
        从 supervisor_inbox 拉取待处理事件

        Args:
            cursor: 数据库游标

        Returns:
            待处理事件列表
        """
        cursor.execute(
            """
            SELECT event_id, task_id, event_type, source, payload, received_at
            FROM supervisor_inbox
            WHERE status = 'pending'
            ORDER BY received_at ASC
            LIMIT ?
            """,
            (self.batch_size,),
        )
        return cursor.fetchall()

    def _mark_event_processing(self, cursor: sqlite3.Cursor, event_id: str) -> None:
        """标记事件为处理中"""
        cursor.execute(
            """
            UPDATE supervisor_inbox
            SET status = 'processing'
            WHERE event_id = ?
            """,
            (event_id,),
        )

    def _mark_event_completed(self, cursor: sqlite3.Cursor, event_id: str) -> None:
        """标记事件为已完成"""
        cursor.execute(
            """
            UPDATE supervisor_inbox
            SET status = 'completed',
                processed_at = ?
            WHERE event_id = ?
            """,
            (utc_now_iso(), event_id),
        )

    def _mark_event_failed(
        self, cursor: sqlite3.Cursor, event_id: str, error_message: str
    ) -> None:
        """标记事件为失败"""
        cursor.execute(
            """
            UPDATE supervisor_inbox
            SET status = 'failed',
                error_message = ?,
                retry_count = retry_count + 1,
                processed_at = ?
            WHERE event_id = ?
            """,
            (error_message, utc_now_iso(), event_id),
        )


class PolicyRouter:
    """
    Policy 路由器

    根据事件类型选择对应的 policy 并执行。
    """

    def __init__(self):
        self.policies: Dict[str, Callable] = {}
        logger.info("PolicyRouter initialized")

    def register(self, event_type: str, policy: Callable) -> None:
        """
        注册 policy

        Args:
            event_type: 事件类型（如 "TASK_CREATED"）
            policy: Policy 处理函数（签名：(event, cursor) -> Decision）
        """
        self.policies[event_type] = policy
        logger.debug(f"Registered policy for event_type: {event_type}")

    def route(
        self, event: SupervisorEvent, cursor: sqlite3.Cursor
    ) -> Optional[Decision]:
        """
        路由事件到对应的 policy

        Args:
            event: Supervisor 事件
            cursor: 数据库游标

        Returns:
            Decision 对象（如果 policy 返回）
        """
        policy = self.policies.get(event.event_type)

        if policy is None:
            logger.debug(f"No policy registered for event_type: {event.event_type}")
            return None

        try:
            decision = policy(event, cursor)
            return decision
        except Exception as e:
            logger.error(
                f"Policy execution failed for {event.event_type}: {e}", exc_info=True
            )
            raise
