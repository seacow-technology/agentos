"""
OnTaskFailedPolicy

任务失败时的归因和重试建议。
"""

import logging
import sqlite3
from typing import Optional

from ..models import SupervisorEvent, Decision, DecisionType, Finding, Action, ActionType
from .base import BasePolicy

logger = logging.getLogger(__name__)


# 不可重试的错误类型
NON_RETRYABLE_ERRORS = [
    "redline_violation",
    "permission_denied",
    "invalid_config",
    "quota_exceeded",
    "auth_failed",
]

# 可重试的错误类型
RETRYABLE_ERRORS = [
    "network_timeout",
    "connection_refused",
    "rate_limited",
    "service_unavailable",
    "temporary_failure",
]


class OnTaskFailedPolicy(BasePolicy):
    """
    任务失败时的 Policy

    职责：
    1. 失败归因（分析错误原因）
    2. 判断是否可重试
    3. 检查历史重试次数
    4. 决策：RETRY / BLOCK
    """

    def evaluate(
        self, event: SupervisorEvent, cursor: sqlite3.Cursor
    ) -> Optional[Decision]:
        """
        评估任务失败事件

        Args:
            event: Supervisor 事件
            cursor: 数据库游标

        Returns:
            Decision 对象
        """
        logger.info(f"Evaluating TASK_FAILED for task {event.task_id}")

        findings = []
        decision_type = DecisionType.BLOCK
        reason = "Task failed - analyzing cause"

        # 1. 获取失败信息
        error_message = event.payload.get("error", "Unknown error")
        error_code = event.payload.get("error_code")
        error_type = event.payload.get("error_type")

        logger.debug(
            f"Task failed: error_type={error_type}, error_code={error_code}, "
            f"error_message={error_message}"
        )

        # 2. 失败归因
        findings.append(
            Finding(
                category="failure",
                severity="high",
                description=f"Task failed: {error_message}",
                evidence=[error_message, error_code or "no_code"],
                source="on_task_failed_policy",
            )
        )

        # 3. 判断是否可重试
        can_retry = self._can_retry(error_type, error_code, error_message)

        # 4. 检查历史重试次数
        metadata = self.get_task_metadata(event.task_id, cursor)
        retry_count = metadata.get("retry_count", 0)
        max_retries = metadata.get("max_retries", 3)

        logger.debug(f"Retry status: retry_count={retry_count}, max_retries={max_retries}")

        # 5. 做出决策
        if can_retry and retry_count < max_retries:
            decision_type = DecisionType.RETRY
            reason = (
                f"Task failed but can be retried "
                f"(attempt {retry_count + 1}/{max_retries})"
            )

            # 创建 RETRY 动作
            actions = [
                Action(
                    action_type=ActionType.WRITE_AUDIT,
                    target=event.task_id,
                    params={
                        "event_type": "SUPERVISOR_RETRY_RECOMMENDED",
                        "retry_count": retry_count + 1,
                        "reason": reason,
                    },
                )
            ]

            # 注意：Supervisor 不强制执行 retry，只建议
            # 实际的 retry 逻辑由 Task Lifecycle 负责

        else:
            if not can_retry:
                reason = f"Task failed with non-retryable error: {error_type or 'unknown'}"
            else:
                reason = f"Task failed and max retries exceeded ({retry_count}/{max_retries})"

            decision_type = DecisionType.BLOCK
            findings.append(
                Finding(
                    category="constraint",
                    severity="high",
                    description=reason,
                    evidence=[f"retry_count={retry_count}", f"max_retries={max_retries}"],
                    source="on_task_failed_policy",
                )
            )

            # 创建 BLOCK 动作
            actions = [
                Action(
                    action_type=ActionType.MARK_BLOCKED,
                    target=event.task_id,
                    params={"reason": reason},
                )
            ]

            # 更新任务状态为 BLOCKED
            self.update_task_status(event.task_id, "blocked", cursor)

        # 6. 构造并返回决策
        decision = Decision(
            decision_type=decision_type,
            reason=reason,
            findings=findings,
            actions=actions,
        )

        logger.info(
            f"TASK_FAILED decision: {decision_type.value} "
            f"(can_retry={can_retry}, retry_count={retry_count})"
        )
        return decision

    def _can_retry(
        self,
        error_type: Optional[str],
        error_code: Optional[str],
        error_message: str,
    ) -> bool:
        """
        判断错误是否可重试

        Args:
            error_type: 错误类型
            error_code: 错误代码
            error_message: 错误信息

        Returns:
            是否可重试
        """
        # 1. 检查明确的不可重试错误
        if error_type in NON_RETRYABLE_ERRORS:
            return False

        # 2. 检查明确的可重试错误
        if error_type in RETRYABLE_ERRORS:
            return True

        # 3. 基于错误信息的启发式判断
        error_message_lower = error_message.lower()

        # 不可重试的关键词
        non_retryable_keywords = [
            "permission denied",
            "access denied",
            "invalid",
            "forbidden",
            "unauthorized",
            "quota exceeded",
            "redline",
        ]

        for keyword in non_retryable_keywords:
            if keyword in error_message_lower:
                return False

        # 可重试的关键词
        retryable_keywords = [
            "timeout",
            "connection",
            "network",
            "rate limit",
            "unavailable",
            "temporary",
        ]

        for keyword in retryable_keywords:
            if keyword in error_message_lower:
                return True

        # 4. 默认：不可重试（保守策略）
        logger.debug(f"Unknown error type '{error_type}', defaulting to non-retryable")
        return False
