"""
Lead Task Creator Adapter

负责将 LeadFinding 转换为 follow-up tasks，通过 TaskService 创建任务。

设计原则：
1. 支持 dry_run 模式（不落库，返回模拟 task_id）
2. 检查重复（finding.linked_task_id 不为空时跳过）
3. 任务描述包含完整的 evidence 和 fingerprint
4. 根据 severity 决定初始状态（APPROVED vs DRAFT）
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from agentos.core.time import utc_now


try:
    from ulid import ULID
except ImportError:
    import uuid
    class ULID:
        @staticmethod
        def from_datetime(dt):
            return str(uuid.uuid4())

from agentos.core.lead.dedupe import LeadFinding, LeadFindingStore
from agentos.core.task.service import TaskService
from agentos.core.task.states import TaskState

logger = logging.getLogger(__name__)


# Severity to priority mapping
SEVERITY_TO_PRIORITY = {
    "CRITICAL": 1,
    "HIGH": 2,
    "MEDIUM": 3,
    "LOW": 4
}


class LeadTaskCreator:
    """
    Lead Task Creator Adapter

    将 LeadFinding 转换为 follow-up tasks。
    """

    def __init__(self, db_path: Path):
        """
        初始化 Task Creator

        Args:
            db_path: 数据库路径（用于 TaskService 和 LeadFindingStore）
        """
        self.db_path = db_path
        self.task_service = TaskService(db_path=db_path)
        self.finding_store = LeadFindingStore(db_path=db_path)
        logger.info(f"LeadTaskCreator initialized with db_path={db_path}")

    def create_follow_up_task(
        self,
        finding: LeadFinding,
        dry_run: bool = True
    ) -> Optional[str]:
        """
        为单个 finding 创建 follow-up task

        Args:
            finding: 风险线索
            dry_run: True 时不落库，只返回模拟的 task_id

        Returns:
            task_id: 创建的任务 ID（dry_run 时返回 "DRY_RUN_task-xxx"）
            None: finding 已有 linked_task_id 时跳过
        """
        # 1. 检查重复：如果已有 linked_task_id，跳过
        if finding.linked_task_id:
            logger.debug(f"Skipping finding {finding.fingerprint}: already linked to task {finding.linked_task_id}")
            return None

        # 2. 生成任务标题和描述
        title = self._generate_task_title(finding)
        description = self._generate_task_description(finding)

        # 3. 构建 metadata
        metadata = {
            "lead_agent": {
                "fingerprint": finding.fingerprint,
                "rule_code": finding.code,
                "severity": finding.severity,
                "window_kind": finding.window_kind,
                "first_seen_at": finding.first_seen_at.isoformat(),
                "last_seen_at": finding.last_seen_at.isoformat(),
                "count": finding.count,
            },
            "priority": SEVERITY_TO_PRIORITY.get(finding.severity.upper(), 3),
        }

        # 4. 根据 severity 决定初始状态
        # CRITICAL/HIGH: 直接创建为 APPROVED 状态
        # MEDIUM/LOW: 创建为 DRAFT 状态
        initial_state = self._get_initial_state(finding.severity)

        # 5. dry_run: 模拟创建
        if dry_run:
            task_id = f"DRY_RUN_{ULID.from_datetime(utc_now())}"
            logger.info(
                f"[DRY_RUN] Would create task for finding {finding.fingerprint}: "
                f"title='{title}', state={initial_state}"
            )
            return task_id

        # 6. 实际创建任务
        try:
            # 创建 DRAFT 任务
            task = self.task_service.create_draft_task(
                title=title,
                created_by="lead_agent",
                metadata=metadata
            )

            # 如果是 CRITICAL/HIGH，立即 approve
            if initial_state == TaskState.APPROVED.value:
                task = self.task_service.approve_task(
                    task_id=task.task_id,
                    actor="lead_agent",
                    reason=f"Auto-approved due to {finding.severity} severity"
                )

            # 添加任务描述（通过 task_audits 或 lineage）
            self.task_service.add_audit(
                task_id=task.task_id,
                event_type="LEAD_FINDING_LINKED",
                level="info",
                payload={
                    "fingerprint": finding.fingerprint,
                    "description": description,
                }
            )

            # 7. 更新 finding.linked_task_id
            self.finding_store.link_task(
                fingerprint=finding.fingerprint,
                task_id=task.task_id
            )

            logger.info(
                f"Created follow-up task {task.task_id} for finding {finding.fingerprint} "
                f"(state={task.status}, severity={finding.severity})"
            )

            return task.task_id

        except Exception as e:
            logger.error(f"Failed to create follow-up task for finding {finding.fingerprint}: {e}", exc_info=True)
            raise

    def create_batch(
        self,
        findings: List[LeadFinding],
        dry_run: bool = True
    ) -> dict:
        """
        批量创建 follow-up tasks

        Args:
            findings: 风险线索列表
            dry_run: True 时不落库，只返回模拟的 task_id

        Returns: {
            "created": int,      # 实际创建数
            "skipped": int,      # 已有 linked_task 跳过数
            "task_ids": [...]    # 创建的 task_id 列表
        }
        """
        created_count = 0
        skipped_count = 0
        task_ids = []

        for finding in findings:
            task_id = self.create_follow_up_task(finding, dry_run=dry_run)

            if task_id is None:
                skipped_count += 1
            else:
                created_count += 1
                task_ids.append(task_id)

        logger.info(
            f"Batch task creation completed: created={created_count}, "
            f"skipped={skipped_count}, dry_run={dry_run}"
        )

        return {
            "created": created_count,
            "skipped": skipped_count,
            "task_ids": task_ids,
        }

    def _generate_task_title(self, finding: LeadFinding) -> str:
        """
        生成任务标题

        格式: [LEAD][{window_kind}] {code} - {title}
        """
        return f"[LEAD][{finding.window_kind}] {finding.code} - {finding.title}"

    def _generate_task_description(self, finding: LeadFinding) -> str:
        """
        生成任务描述（Markdown 格式）

        包含：
        - 规则信息
        - 问题描述
        - 证据
        - 建议行动
        - 元数据（fingerprint）
        """
        # 格式化 evidence
        evidence_str = self._format_evidence(finding.evidence)

        # 生成建议行动
        recommendation = self._generate_recommendation(finding)

        description = f"""## Lead Agent 风险线索

**规则代码**: {finding.code}
**严重等级**: {finding.severity}
**检测窗口**: {finding.window_kind}
**首次发现**: {finding.first_seen_at.isoformat()}
**最近发现**: {finding.last_seen_at.isoformat()}
**重复次数**: {finding.count}

## 问题描述
{finding.description or "（无详细描述）"}

## 证据
{evidence_str}

## 建议行动
{recommendation}

---
*由 Lead Agent 自动生成 | fingerprint: {finding.fingerprint}*
"""
        return description

    def _format_evidence(self, evidence: Dict) -> str:
        """
        格式化证据为 Markdown

        支持：
        - count: 数量统计
        - samples: 任务样例（task_ids）
        - decision_ids: 决策 ID 引用
        - task_ids: 任务 ID 引用
        - 其他字段：JSON 格式
        """
        lines = []

        # 处理 count
        if "count" in evidence:
            lines.append(f"- **发现次数**: {evidence['count']}")

        # 处理 samples（task_ids）
        if "samples" in evidence:
            task_ids = evidence["samples"]
            if isinstance(task_ids, list) and task_ids:
                lines.append(f"- **样例任务** ({len(task_ids)} 个):")
                for task_id in task_ids[:5]:  # 最多显示 5 个
                    lines.append(f"  - `{task_id}`")

        # 处理 task_ids
        if "task_ids" in evidence:
            task_ids = evidence["task_ids"]
            if isinstance(task_ids, list) and task_ids:
                lines.append(f"- **相关任务** ({len(task_ids)} 个):")
                for task_id in task_ids[:5]:
                    lines.append(f"  - `{task_id}`")

        # 处理 decision_ids
        if "decision_ids" in evidence:
            decision_ids = evidence["decision_ids"]
            if isinstance(decision_ids, list) and decision_ids:
                lines.append(f"- **相关决策** ({len(decision_ids)} 个):")
                for decision_id in decision_ids[:5]:
                    lines.append(f"  - `{decision_id}`")

        # 处理其他字段
        other_fields = {k: v for k, v in evidence.items()
                       if k not in ["count", "samples", "task_ids", "decision_ids"]}
        if other_fields:
            lines.append("- **其他证据**:")
            for key, value in other_fields.items():
                if isinstance(value, (dict, list)):
                    value_str = json.dumps(value, indent=2, ensure_ascii=False)
                    lines.append(f"  - `{key}`: ```json\n{value_str}\n```")
                else:
                    lines.append(f"  - `{key}`: {value}")

        return "\n".join(lines) if lines else "（无证据）"

    def _generate_recommendation(self, finding: LeadFinding) -> str:
        """
        根据规则代码和严重级别生成建议行动
        """
        severity = finding.severity.upper()
        code = finding.code

        # 根据严重级别生成通用建议
        if severity == "CRITICAL":
            urgency = "**立即处理**"
        elif severity == "HIGH":
            urgency = "**优先处理**"
        elif severity == "MEDIUM":
            urgency = "**近期处理**"
        else:
            urgency = "**考虑处理**"

        # 根据规则代码生成具体建议
        recommendations = {
            "blocked_reason_spike": [
                "检查相关任务的 blocked 原因",
                "评估是否需要调整 Guardian 规则",
                "如果是系统性问题，考虑修复根因",
            ],
            "pause_block_churn": [
                "分析任务为何多次 PAUSE 后仍 BLOCK",
                "检查 retry 逻辑是否合理",
                "评估任务执行环境的稳定性",
            ],
            "retry_recommended_but_fails": [
                "分析 retry 推荐后仍失败的原因",
                "检查错误码是否需要特殊处理",
                "评估 retry 策略的有效性",
            ],
            "decision_lag_anomaly": [
                "检查 Supervisor 处理延迟的原因",
                "评估系统负载和性能瓶颈",
                "考虑优化决策流程",
            ],
            "redline_ratio_increase": [
                "分析 REDLINE 违规增多的原因",
                "检查是否有新的风险行为模式",
                "评估 Guardian 策略的有效性",
            ],
            "high_risk_allow": [
                "检查为何高风险任务被 ALLOW",
                "评估 Guardian 策略是否过于宽松",
                "考虑加强风险审查机制",
            ],
        }

        specific_recommendations = recommendations.get(code, [
            "分析问题根因",
            "评估影响范围",
            "制定解决方案",
        ])

        rec_lines = [urgency, ""]
        rec_lines.extend(f"{i+1}. {rec}" for i, rec in enumerate(specific_recommendations))

        return "\n".join(rec_lines)

    def _get_initial_state(self, severity: str) -> str:
        """
        根据严重级别决定初始状态

        Args:
            severity: LOW | MEDIUM | HIGH | CRITICAL

        Returns:
            TaskState.DRAFT.value 或 TaskState.APPROVED.value
        """
        severity_upper = severity.upper()

        if severity_upper in ["CRITICAL", "HIGH"]:
            return TaskState.APPROVED.value
        else:
            return TaskState.DRAFT.value
