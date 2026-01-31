"""
Quota Manager

管理能力配额的检查、更新和重置。
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional
from pathlib import Path

from agentos.core.capabilities.governance_models.quota import (
    CapabilityQuota,
    QuotaState,
    QuotaCheckResult,
)

logger = logging.getLogger(__name__)


class QuotaManager:
    """配额管理器"""

    def __init__(self, db_path: Optional[Path] = None):
        """
        初始化配额管理器

        Args:
            db_path: 数据库路径(用于持久化配额状态)
        """
        self.db_path = db_path
        self.quotas: Dict[str, CapabilityQuota] = {}
        self.states: Dict[str, QuotaState] = {}

    def register_quota(self, quota: CapabilityQuota):
        """注册配额配置"""
        self.quotas[quota.quota_id] = quota
        logger.info(f"Registered quota: {quota.quota_id}")

    def check_quota(
        self,
        quota_id: str,
        estimated_runtime_ms: Optional[int] = None,
        estimated_cost: Optional[float] = None
    ) -> QuotaCheckResult:
        """
        检查配额是否允许执行

        Args:
            quota_id: 配额 ID
            estimated_runtime_ms: 预估运行时间
            estimated_cost: 预估成本

        Returns:
            QuotaCheckResult: 检查结果
        """
        quota = self.quotas.get(quota_id)
        if not quota or not quota.enabled:
            # 无配额或未启用,默认允许
            return QuotaCheckResult(
                allowed=True,
                state=self._get_or_create_state(quota_id)
            )

        state = self._get_or_create_state(quota_id)

        # 检查窗口是否需要重置
        if self._should_reset_window(quota, state):
            self._reset_window(state)

        # 检查各项限制
        reasons = []
        warning = False

        # 1. 每分钟调用次数
        if quota.limit.calls_per_minute:
            if state.used_calls >= quota.limit.calls_per_minute:
                reasons.append(
                    f"Calls per minute limit reached: "
                    f"{state.used_calls}/{quota.limit.calls_per_minute}"
                )
            elif state.used_calls >= quota.limit.calls_per_minute * 0.8:
                warning = True

        # 2. 并发数
        if quota.limit.max_concurrent:
            if state.current_concurrent >= quota.limit.max_concurrent:
                reasons.append(
                    f"Max concurrent limit reached: "
                    f"{state.current_concurrent}/{quota.limit.max_concurrent}"
                )

        # 3. 运行时间
        if quota.limit.max_runtime_ms and estimated_runtime_ms:
            if state.used_runtime_ms + estimated_runtime_ms > quota.limit.max_runtime_ms:
                reasons.append(
                    f"Max runtime limit would be exceeded: "
                    f"{state.used_runtime_ms + estimated_runtime_ms}/{quota.limit.max_runtime_ms} ms"
                )

        # 4. 成本
        if quota.limit.max_cost_units and estimated_cost:
            if state.used_cost_units + estimated_cost > quota.limit.max_cost_units:
                reasons.append(
                    f"Max cost limit would be exceeded: "
                    f"{state.used_cost_units + estimated_cost}/{quota.limit.max_cost_units} units"
                )

        allowed = len(reasons) == 0
        reason = "; ".join(reasons) if reasons else None

        return QuotaCheckResult(
            allowed=allowed,
            reason=reason,
            state=state,
            warning=warning
        )

    def update_quota(
        self,
        quota_id: str,
        runtime_ms: int,
        cost_units: float = 0.0,
        increment_concurrent: int = 0
    ):
        """
        更新配额使用状态

        Args:
            quota_id: 配额 ID
            runtime_ms: 本次运行时间
            cost_units: 本次成本
            increment_concurrent: 并发数增量(+1 开始,-1 结束)
        """
        state = self._get_or_create_state(quota_id)

        if increment_concurrent > 0:
            state.used_calls += 1

        state.used_runtime_ms += runtime_ms
        state.used_cost_units += cost_units
        state.current_concurrent += increment_concurrent

        # 确保并发数不为负
        if state.current_concurrent < 0:
            logger.warning(f"Concurrent count went negative for {quota_id}")
            state.current_concurrent = 0

        self.states[quota_id] = state

        # 持久化(如果有数据库)
        self._persist_state(state)

    def _get_or_create_state(self, quota_id: str) -> QuotaState:
        """获取或创建配额状态"""
        if quota_id not in self.states:
            self.states[quota_id] = QuotaState(
                quota_id=quota_id,
                window_start=datetime.now()
            )
        return self.states[quota_id]

    def _should_reset_window(self, quota: CapabilityQuota, state: QuotaState) -> bool:
        """判断是否应该重置窗口"""
        if quota.window == "fixed":
            # 固定窗口:每分钟重置
            return (datetime.now() - state.window_start) > timedelta(minutes=1)
        else:
            # 滑动窗口:不自动重置
            return False

    def _reset_window(self, state: QuotaState):
        """重置窗口"""
        state.used_calls = 0
        state.used_runtime_ms = 0
        state.used_cost_units = 0.0
        state.window_start = datetime.now()
        state.last_reset = datetime.now()
        logger.info(f"Reset quota window for {state.quota_id}")

    def _persist_state(self, state: QuotaState):
        """持久化状态(可选,如果有数据库)"""
        # TODO: 实现数据库持久化
        pass
