"""
OnTaskCreatedPolicy

任务创建时的红线预检和冲突预检。
"""

import logging
import sqlite3
from pathlib import Path
from typing import Optional

from ..models import SupervisorEvent, Decision, DecisionType, Finding, Action, ActionType
from .base import BasePolicy

logger = logging.getLogger(__name__)


class OnTaskCreatedPolicy(BasePolicy):
    """
    任务创建时的 Policy

    职责：
    1. 执行红线预检（agent/command/rule redlines）
    2. 检测意图冲突
    3. 评估初始风险
    4. 决策：ALLOW / PAUSE / BLOCK
    """

    def evaluate(
        self, event: SupervisorEvent, cursor: sqlite3.Cursor
    ) -> Optional[Decision]:
        """
        评估任务创建事件

        Args:
            event: Supervisor 事件
            cursor: 数据库游标

        Returns:
            Decision 对象
        """
        logger.info(f"Evaluating TASK_CREATED for task {event.task_id}")

        findings = []
        decision_type = DecisionType.ALLOW
        reason = "Task created - no issues detected"

        # 1. 检查 payload 中是否有需要验证的实体
        agent_spec = event.payload.get("agent_spec")
        command_spec = event.payload.get("command_spec")
        rule_spec = event.payload.get("rule_spec")

        # 2. 执行红线验证
        if agent_spec:
            is_violation, errors = self.gate_adapter.check_redline_violation(
                "agent", agent_spec
            )
            if is_violation:
                findings.append(
                    Finding(
                        category="redline",
                        severity="high",
                        description=f"Agent redline violation: {'; '.join(errors)}",
                        evidence=errors,
                        source="gate_adapter",
                    )
                )

        if command_spec:
            is_violation, errors = self.gate_adapter.check_redline_violation(
                "command", command_spec
            )
            if is_violation:
                findings.append(
                    Finding(
                        category="redline",
                        severity="high",
                        description=f"Command redline violation: {'; '.join(errors)}",
                        evidence=errors,
                        source="gate_adapter",
                    )
                )

        if rule_spec:
            is_violation, errors = self.gate_adapter.check_redline_violation(
                "rule", rule_spec
            )
            if is_violation:
                findings.append(
                    Finding(
                        category="redline",
                        severity="high",
                        description=f"Rule redline violation: {'; '.join(errors)}",
                        evidence=errors,
                        source="gate_adapter",
                    )
                )

        # 3. 检查是否有 intent_set 需要评估
        intent_set_path = event.payload.get("intent_set_path")
        if intent_set_path:
            try:
                # 评估 intent set
                eval_result = self.evaluator_adapter.evaluate_intent_set(
                    Path(intent_set_path)
                )

                # 检查冲突
                conflicts = eval_result.get("evaluation", {}).get("conflicts", [])
                if self.evaluator_adapter.has_critical_conflicts(conflicts):
                    findings.append(
                        Finding(
                            category="conflict",
                            severity="high",
                            description=f"Critical conflicts detected in intent set",
                            evidence=[c.get("conflict_id", "unknown") for c in conflicts],
                            source="evaluator_adapter",
                        )
                    )

                # 检查风险
                risk_matrix = eval_result.get("evaluation", {}).get("risk_comparison", {})
                highest_risk = self.evaluator_adapter.get_highest_risk(risk_matrix)
                if highest_risk in ["high", "critical"]:
                    findings.append(
                        Finding(
                            category="risk",
                            severity=highest_risk,
                            description=f"High risk detected: {highest_risk}",
                            evidence=[highest_risk],
                            source="evaluator_adapter",
                        )
                    )

            except Exception as e:
                logger.error(f"Intent set evaluation failed: {e}", exc_info=True)
                findings.append(
                    Finding(
                        category="risk",
                        severity="medium",
                        description=f"Failed to evaluate intent set: {str(e)}",
                        evidence=[str(e)],
                        source="evaluator_adapter",
                    )
                )

        # 4. 根据 findings 做出决策
        if findings:
            # 检查是否有高严重度的 finding
            high_severity_count = sum(
                1 for f in findings if f.severity in ["high", "critical"]
            )

            if high_severity_count > 0:
                decision_type = DecisionType.BLOCK
                reason = f"Task blocked due to {high_severity_count} critical/high severity issues"

                # 创建 BLOCK 动作
                actions = [
                    Action(
                        action_type=ActionType.MARK_BLOCKED,
                        target=event.task_id,
                        params={"reason": reason},
                    )
                ]

                # 更新任务状态
                self.update_task_status(event.task_id, "blocked", cursor)

            else:
                decision_type = DecisionType.PAUSE
                reason = f"Task paused for review - {len(findings)} issues detected"

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
            # 没有问题，允许继续
            actions = [
                Action(
                    action_type=ActionType.MARK_VERIFYING,
                    target=event.task_id,
                    params={},
                )
            ]

        # 5. 构造并返回决策
        decision = Decision(
            decision_type=decision_type,
            reason=reason,
            findings=findings,
            actions=actions,
        )

        logger.info(
            f"TASK_CREATED decision: {decision_type.value} (findings={len(findings)})"
        )
        return decision
