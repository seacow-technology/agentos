"""
EventBus 订阅器

负责订阅 EventBus 事件并唤醒 Supervisor。
"""

import logging
from pathlib import Path
from typing import Any

from ..events.bus import EventBus, get_event_bus
from .inbox import InboxManager
from .models import SupervisorEvent
from .supervisor import SupervisorService

logger = logging.getLogger(__name__)


class SupervisorSubscriber:
    """
    Supervisor 的 EventBus 订阅器

    职责：
    1. 订阅 EventBus 事件
    2. 将事件写入 inbox（去重）
    3. 唤醒 Supervisor 主循环

    设计原则：
    - 不处理业务逻辑
    - 不阻塞 EventBus
    - 仅做"通知"和"持久化"
    """

    def __init__(
        self,
        supervisor_service: SupervisorService,
        inbox_manager: InboxManager,
        event_bus: EventBus = None,
    ):
        """
        初始化订阅器

        Args:
            supervisor_service: Supervisor 服务
            inbox_manager: Inbox 管理器
            event_bus: EventBus 实例（默认使用全局实例）
        """
        self.supervisor_service = supervisor_service
        self.inbox_manager = inbox_manager
        self.event_bus = event_bus or get_event_bus()

        logger.info("SupervisorSubscriber initialized")

    def subscribe(self) -> None:
        """订阅 EventBus 事件"""
        self.event_bus.subscribe(self.on_event)
        logger.info("✅ Subscribed to EventBus")

    def unsubscribe(self) -> None:
        """取消订阅"""
        self.event_bus.unsubscribe(self.on_event)
        logger.info("Unsubscribed from EventBus")

    def on_event(self, event: Any) -> None:
        """
        EventBus 事件回调

        注意：
        - 此方法在 EventBus 的线程中调用
        - 不能阻塞或抛出异常
        - 只做最小必要工作：写 inbox + 唤醒

        Args:
            event: EventBus 事件对象
        """
        try:
            # 转换为 SupervisorEvent
            supervisor_event = SupervisorEvent.from_eventbus(event)

            # 写入 inbox（去重在这里发生）
            inserted = self.inbox_manager.insert_event(supervisor_event)

            if inserted:
                logger.debug(
                    f"Event received from EventBus: {supervisor_event.event_type} "
                    f"(task={supervisor_event.task_id})"
                )
                # 唤醒 Supervisor
                self.supervisor_service.wake(reason="eventbus")
            else:
                # 事件已存在（重复）
                logger.debug(
                    f"Duplicate event from EventBus (deduped): {supervisor_event.event_id}"
                )

        except Exception as e:
            # 永远不要让异常传播到 EventBus
            logger.error(f"Error in SupervisorSubscriber.on_event: {e}", exc_info=True)


def setup_supervisor_subscription(
    supervisor_service: SupervisorService,
    db_path: Path,
) -> SupervisorSubscriber:
    """
    便捷函数：设置 Supervisor 订阅

    Args:
        supervisor_service: Supervisor 服务
        db_path: 数据库路径

    Returns:
        已订阅的 SupervisorSubscriber
    """
    inbox_manager = InboxManager(db_path)
    subscriber = SupervisorSubscriber(supervisor_service, inbox_manager)
    subscriber.subscribe()

    logger.info("✅ Supervisor subscription setup complete")
    return subscriber
