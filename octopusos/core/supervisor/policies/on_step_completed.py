"""
OnStepCompletedPolicy

步骤完成后的风险再评估。
"""

import logging
import sqlite3
from typing import Optional

from ..models import SupervisorEvent, Decision, DecisionType, Finding, Action, ActionType
from .base import BasePolicy

logger = logging.getLogger(__name__)


class OnStepCompletedPolicy(BasePolicy):
    """
    步骤完成时的 Policy

    职责：
    1. 风险再评估（与 baseline 比较）
    2. 检测风险趋势上升
    3. 触发 runtime enforcer（如有必要）
    4. 决策：ALLOW / PAUSE
    """

    def evaluate(
        self, event: SupervisorEvent, cursor: sqlite3.Cursor
    ) -> Optional[Decision]:
        """
        评估步骤完成事件

        Args:
            event: Supervisor 事件
            cursor: 数据库游标

        Returns:
            Decision 对象
        """
        logger.info(f"Evaluating STEP_COMPLETED for task {event.task_id}")

        findings = []
        decision_type = DecisionType.ALLOW
        reason = "Step completed - no issues detected"

        # 1. 获取步骤信息
        step_id = event.payload.get("step_id")
        step_result = event.payload.get("result", {})
        risk_indicators = event.payload.get("risk_indicators", {})

        logger.debug(
            f"Step {step_id} completed with risk_indicators: {risk_indicators}"
        )

        # 2. 检查风险指标
        if risk_indicators:
            # 检查是否有风险上升
            risk_spike_detected = False
            risk_details = []

            # 示例风险指标：
            # - error_rate: 错误率
            # - resource_usage: 资源使用率
            # - security_score: 安全评分

            error_rate = risk_indicators.get("error_rate", 0)
            if error_rate > 0.3:  # 错误率超过 30%
                risk_spike_detected = True
                risk_details.append(f"High error rate: {error_rate:.1%}")

            resource_usage = risk_indicators.get("resource_usage", 0)
            if resource_usage > 0.8:  # 资源使用率超过 80%
                risk_spike_detected = True
                risk_details.append(f"High resource usage: {resource_usage:.1%}")

            security_score = risk_indicators.get("security_score", 100)
            if security_score < 50:  # 安全评分低于 50
                risk_spike_detected = True
                risk_details.append(f"Low security score: {security_score}")

            if risk_spike_detected:
                findings.append(
                    Finding(
                        category="risk",
                        severity="medium",
                        description=f"Risk spike detected: {'; '.join(risk_details)}",
                        evidence=risk_details,
                        source="on_step_completed_policy",
                    )
                )

        # 3. 检查是否有异常输出
        warnings = step_result.get("warnings", [])
        if warnings:
            findings.append(
                Finding(
                    category="risk",
                    severity="low",
                    description=f"Step produced {len(warnings)} warnings",
                    evidence=warnings,
                    source="on_step_completed_policy",
                )
            )

        # 4. 检查 runtime enforcer（如果有 run_id）
        run_id = event.payload.get("run_id")
        if run_id:
            # 获取任务元数据
            metadata = self.get_task_metadata(event.task_id, cursor)
            execution_mode = metadata.get("run_mode", "assisted")

            # 执行 runtime gates 检查
            passed, violation_reason = self.gate_adapter.enforce_runtime_gates(
                run_id=run_id,
                execution_mode=execution_mode,
                cursor=cursor,
            )

            if not passed:
                findings.append(
                    Finding(
                        category="constraint",
                        severity="high",
                        description=f"Runtime gate violation: {violation_reason}",
                        evidence=[violation_reason],
                        source="gate_adapter",
                    )
                )

        # 5. 根据 findings 做出决策
        if findings:
            # 检查是否有高严重度的 finding
            high_severity_count = sum(
                1 for f in findings if f.severity in ["high", "critical"]
            )

            if high_severity_count > 0:
                decision_type = DecisionType.PAUSE
                reason = f"Step paused for review - {high_severity_count} high severity issues"

                # 创建 PAUSE 动作
                actions = [
                    Action(
                        action_type=ActionType.PAUSE_GATE,
                        target=event.task_id,
                        params={
                            "checkpoint": "open_plan",
                            "reason": reason,
                        },
                    )
                ]

                # 触发 pause gate
                self.gate_adapter.trigger_pause(
                    event.task_id, "open_plan", reason, cursor
                )

            else:
                # 低/中严重度，允许继续但记录
                decision_type = DecisionType.ALLOW
                reason = f"Step completed with {len(findings)} warnings - continuing"
                actions = []

        else:
            # 没有问题，允许继续
            actions = []

        # 6. 构造并返回决策
        decision = Decision(
            decision_type=decision_type,
            reason=reason,
            findings=findings,
            actions=actions,
        )

        logger.info(
            f"STEP_COMPLETED decision: {decision_type.value} (findings={len(findings)})"
        )
        return decision
