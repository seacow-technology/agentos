"""
Policy Router

根据事件类型路由到对应的 policy 处理。
"""

import logging
import sqlite3
from typing import Callable, Dict, Optional

from .models import SupervisorEvent, Decision

logger = logging.getLogger(__name__)


class PolicyRouter:
    """
    Policy 路由器

    根据事件类型选择对应的 policy 并执行。
    支持：
    - 精确匹配（如 "TASK_CREATED"）
    - 前缀匹配（如 "TASK_*" 匹配所有 TASK_ 开头的事件）
    - 默认 policy（如果没有匹配的）
    """

    def __init__(self):
        self.policies: Dict[str, Callable] = {}
        self.default_policy: Optional[Callable] = None
        logger.info("PolicyRouter initialized")

    def register(self, event_type: str, policy: Callable) -> None:
        """
        注册 policy

        Args:
            event_type: 事件类型（支持通配符 "*"）
            policy: Policy 处理函数
                   签名：(event: SupervisorEvent, cursor: sqlite3.Cursor) -> Optional[Decision]
        """
        self.policies[event_type] = policy
        logger.debug(f"Registered policy for event_type: {event_type}")

    def register_default(self, policy: Callable) -> None:
        """
        注册默认 policy（当没有匹配时使用）

        Args:
            policy: 默认 policy 处理函数
        """
        self.default_policy = policy
        logger.debug("Registered default policy")

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
        # 1. 尝试精确匹配
        policy = self.policies.get(event.event_type)

        # 2. 尝试前缀匹配（如 TASK_*）
        if policy is None:
            for event_pattern, registered_policy in self.policies.items():
                if self._matches_pattern(event.event_type, event_pattern):
                    policy = registered_policy
                    logger.debug(
                        f"Event {event.event_type} matched pattern {event_pattern}"
                    )
                    break

        # 3. 使用默认 policy
        if policy is None:
            if self.default_policy:
                logger.debug(f"Using default policy for {event.event_type}")
                policy = self.default_policy
            else:
                logger.debug(
                    f"No policy registered for event_type: {event.event_type}"
                )
                return None

        # 执行 policy
        try:
            decision = policy(event, cursor)
            return decision
        except Exception as e:
            logger.error(
                f"Policy execution failed for {event.event_type}: {e}", exc_info=True
            )
            raise

    def _matches_pattern(self, event_type: str, pattern: str) -> bool:
        """
        检查事件类型是否匹配模式

        支持简单的通配符匹配：
        - "TASK_*" 匹配所有 "TASK_" 开头的事件
        - "*_COMPLETED" 匹配所有 "_COMPLETED" 结尾的事件

        Args:
            event_type: 事件类型
            pattern: 模式字符串

        Returns:
            是否匹配
        """
        if "*" not in pattern:
            return event_type == pattern

        # 简单通配符匹配
        if pattern.startswith("*"):
            # "*_COMPLETED" -> 匹配结尾
            return event_type.endswith(pattern[1:])
        elif pattern.endswith("*"):
            # "TASK_*" -> 匹配开头
            return event_type.startswith(pattern[:-1])
        else:
            # 中间通配符暂不支持
            return False

    def list_registered_policies(self) -> Dict[str, str]:
        """
        列出所有已注册的 policy

        Returns:
            {event_type: policy_name} 字典
        """
        result = {}
        for event_type, policy in self.policies.items():
            policy_name = getattr(policy, "__name__", str(policy))
            result[event_type] = policy_name

        if self.default_policy:
            policy_name = getattr(self.default_policy, "__name__", str(self.default_policy))
            result["__default__"] = policy_name

        return result

    def register_mode_policies(self, db_path) -> None:
        """
        注册 Mode 相关的 policies（Task 27 helper）

        Args:
            db_path: 数据库路径
        """
        from pathlib import Path
        from .policies.on_mode_violation import OnModeViolationPolicy

        db_path = Path(db_path) if not isinstance(db_path, Path) else db_path

        # 注册 MODE_VIOLATION 事件处理
        # 使用精确匹配 "mode.violation" (EventType.MODE_VIOLATION.value)
        self.register("mode.violation", OnModeViolationPolicy(db_path))
        logger.info("Mode policies registered (mode.violation)")

        # 也支持通配符匹配 "mode.*" 以匹配未来的 mode 事件
        # Note: 如果需要支持多种 mode 事件，可以使用 "mode.*" 模式
        # self.register("mode.*", OnModeViolationPolicy(db_path))
