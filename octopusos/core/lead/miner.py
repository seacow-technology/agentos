"""
Risk Miner - 风险规则挖掘引擎

实现6条MVP风险规则，从 Supervisor 决策历史中自动挖掘系统性风险和异常模式。

🔒 SEMANTIC FREEZE (F-3): Lead Agent Behavior
----------------------------------------------
Lead Agent is read-only risk miner

✅ Lead Agent CAN:
   - Read historical governance data (task_audits, events)
   - Detect risk patterns
   - Produce LeadFinding records
   - Create follow-up tasks for human review

❌ Lead Agent CANNOT:
   - NEVER modify business data (tasks, sessions, etc.)
   - NEVER auto-fix detected issues
   - NEVER apply remediation actions
   - NEVER change system configuration

Guarantee: All Lead Agent operations are READ-ONLY. All remediation requires human approval.
Reference: ADR-004 Section F-3

规则列表：
1. blocked_reason_spike: 某 finding.code 在24h内激增
2. pause_block_churn: 同一任务多次 PAUSE 后最终 BLOCK
3. retry_recommended_but_fails: RETRY 建议后仍然失败
4. decision_lag_anomaly: 决策延迟 p95 超阈值
5. redline_ratio_increase: REDLINE 类型 finding 占比显著上升
6. high_risk_allow: HIGH/CRITICAL 严重度问题仍被 ALLOW
"""

from dataclasses import dataclass
from typing import Any, Dict, List
import uuid
from collections import defaultdict, Counter

from agentos.core.lead.models import LeadFinding, ScanWindow


@dataclass
class MinerConfig:
    """
    Miner 配置

    所有规则的阈值都可配置，方便调优和测试。
    """
    # 规则1: blocked_reason_spike
    spike_threshold: int = 5                    # 激增阈值（count）

    # 规则2: pause_block_churn
    pause_count_threshold: int = 2              # PAUSE 次数阈值

    # 规则3: retry_recommended_but_fails
    # （无额外阈值，检测 RETRY 后是否有 BLOCK/FAILED）

    # 规则4: decision_lag_anomaly
    decision_lag_p95_ms: float = 5000.0         # P95 延迟阈值（毫秒）

    # 规则5: redline_ratio_increase
    redline_ratio_increase: float = 0.10        # 占比增幅阈值（如 0.10 = 10%）
    redline_baseline_ratio: float = 0.05        # 基准占比（用于判断是否显著）

    # 规则6: high_risk_allow
    # （无阈值，直接检测 HIGH/CRITICAL + ALLOW 组合）


class RiskMiner:
    """
    风险规则挖掘引擎

    从 storage_data 中应用多条规则，输出 LeadFinding 列表。
    """

    # 契约版本：定义 RiskMiner 期望的输入数据格式
    CONTRACT_VERSION = "1.0.0"

    # 契约说明：
    # v1.0.0: 初始版本
    # - 期望输入格式：{findings: [...], decisions: [...], metrics: {...}}
    # - findings 格式：[{code, kind, task_ids, count}]
    # - decisions 格式：[{task_id, decision_id, status, risk_level, action}]

    def __init__(self, config: MinerConfig = None):
        """
        初始化 Miner

        Args:
            config: Miner 配置，如果为 None 则使用默认配置
        """
        self.config = config or MinerConfig()

    def mine_risks(
        self,
        storage_data: Dict[str, Any],
        window: ScanWindow
    ) -> List[LeadFinding]:
        """
        执行风险挖掘

        Args:
            storage_data: 从 LeadStorage 返回的数据字典，包含：
                - decisions: List[Dict] - 决策记录列表
                - findings: List[Dict] - 发现记录列表
                - metrics: Dict - 性能指标
            window: 扫描时间窗口

        Returns:
            LeadFinding 列表
        """
        findings = []

        # 规则1: blocked_reason_spike
        findings.extend(self._rule_blocked_reason_spike(storage_data, window))

        # 规则2: pause_block_churn
        findings.extend(self._rule_pause_block_churn(storage_data, window))

        # 规则3: retry_recommended_but_fails
        findings.extend(self._rule_retry_recommended_but_fails(storage_data, window))

        # 规则4: decision_lag_anomaly
        findings.extend(self._rule_decision_lag_anomaly(storage_data, window))

        # 规则5: redline_ratio_increase
        findings.extend(self._rule_redline_ratio_increase(storage_data, window))

        # 规则6: high_risk_allow
        findings.extend(self._rule_high_risk_allow(storage_data, window))

        return findings

    def _rule_blocked_reason_spike(
        self,
        storage_data: Dict[str, Any],
        window: ScanWindow
    ) -> List[LeadFinding]:
        """
        规则1: blocked_reason_spike

        检测24h内某 finding.code 激增（count > threshold）。

        逻辑：
        1. 统计每个 finding.code 的出现次数
        2. 对于 count > threshold 的 code，生成 finding

        Evidence:
        - count: 出现次数
        - samples: 样例 decision_id 列表（最多5个）
        """
        findings_list = storage_data.get("findings", [])
        decisions = storage_data.get("decisions", [])

        # 统计每个 code 的出现次数和关联的 decision_id
        code_stats = defaultdict(lambda: {"count": 0, "decision_ids": []})

        for finding in findings_list:
            code = finding.get("code", "")
            decision_id = finding.get("decision_id", "")

            if code:
                code_stats[code]["count"] += 1
                if decision_id:
                    code_stats[code]["decision_ids"].append(decision_id)

        # 检测激增
        result = []
        for code, stats in code_stats.items():
            if stats["count"] > self.config.spike_threshold:
                # 生成 fingerprint
                fingerprint = LeadFinding.generate_fingerprint(
                    rule_code="blocked_reason_spike",
                    window=window,
                    dimensions={"finding_code": code}
                )

                # 取样例（最多5个）
                samples = stats["decision_ids"][:5]

                finding = LeadFinding(
                    finding_id=f"lead_{uuid.uuid4().hex[:12]}",
                    fingerprint=fingerprint,
                    rule_code="blocked_reason_spike",
                    severity="high",
                    title=f"Finding code '{code}' spiked",
                    description=(
                        f"Finding code '{code}' appeared {stats['count']} times "
                        f"in the last 24h, exceeding threshold of {self.config.spike_threshold}"
                    ),
                    evidence={
                        "count": stats["count"],
                        "finding_code": code,
                        "sample_decision_ids": samples
                    },
                    window=window
                )
                result.append(finding)

        return result

    def _rule_pause_block_churn(
        self,
        storage_data: Dict[str, Any],
        window: ScanWindow
    ) -> List[LeadFinding]:
        """
        规则2: pause_block_churn

        检测同一任务多次 PAUSE 后最终 BLOCK。

        逻辑：
        1. 按 task_id 分组决策
        2. 统计每个 task 的 PAUSE 次数
        3. 检查最终决策是否为 BLOCK
        4. 如果 PAUSE >= threshold 且最终 BLOCK，生成 finding

        Evidence:
        - task_id: 任务 ID
        - pause_count: PAUSE 次数
        - final_decision: 最终决策类型
        - sample_decision_ids: 样例 decision_id（包含 PAUSE 和 BLOCK）
        """
        decisions = storage_data.get("decisions", [])

        # 按 task_id 分组
        task_decisions = defaultdict(list)
        for decision in decisions:
            task_id = decision.get("task_id")
            if task_id:
                task_decisions[task_id].append(decision)

        # 检测 pause-block 模式
        result = []
        for task_id, task_dec_list in task_decisions.items():
            # 按时间排序（假设 decision_id 或 timestamp 可排序）
            sorted_decs = sorted(
                task_dec_list,
                key=lambda d: d.get("timestamp", d.get("decision_id", ""))
            )

            # 统计 PAUSE 次数
            pause_count = sum(
                1 for d in sorted_decs
                if d.get("decision_type") == "PAUSE"
            )

            # 检查最终决策
            if sorted_decs:
                final_decision = sorted_decs[-1].get("decision_type")

                if pause_count >= self.config.pause_count_threshold and final_decision == "BLOCK":
                    # 生成 fingerprint
                    fingerprint = LeadFinding.generate_fingerprint(
                        rule_code="pause_block_churn",
                        window=window,
                        dimensions={"task_id": task_id}
                    )

                    # 取样例（PAUSE 和 BLOCK 决策）
                    pause_samples = [
                        d["decision_id"] for d in sorted_decs
                        if d.get("decision_type") == "PAUSE"
                    ][:3]
                    block_sample = [sorted_decs[-1]["decision_id"]]
                    samples = pause_samples + block_sample

                    finding = LeadFinding(
                        finding_id=f"lead_{uuid.uuid4().hex[:12]}",
                        fingerprint=fingerprint,
                        rule_code="pause_block_churn",
                        severity="medium",
                        title=f"Task {task_id} churned through PAUSE then BLOCK",
                        description=(
                            f"Task {task_id} was PAUSED {pause_count} times "
                            f"before being BLOCKED"
                        ),
                        evidence={
                            "task_id": task_id,
                            "pause_count": pause_count,
                            "final_decision": final_decision,
                            "sample_decision_ids": samples
                        },
                        window=window
                    )
                    result.append(finding)

        return result

    def _rule_retry_recommended_but_fails(
        self,
        storage_data: Dict[str, Any],
        window: ScanWindow
    ) -> List[LeadFinding]:
        """
        规则3: retry_recommended_but_fails

        检测 RETRY 建议后仍然失败（BLOCK 或系统失败）。

        逻辑：
        1. 找到所有 decision_type = RETRY 的决策
        2. 对于每个 RETRY 决策，检查同一 task 后续是否有 BLOCK 或失败
        3. 如果有，生成 finding

        Evidence:
        - task_id: 任务 ID
        - retry_decision_id: RETRY 决策 ID
        - failed_decision_id: 失败决策 ID
        - failed_decision_type: 失败决策类型
        """
        decisions = storage_data.get("decisions", [])

        # 按 task_id 分组
        task_decisions = defaultdict(list)
        for decision in decisions:
            task_id = decision.get("task_id")
            if task_id:
                task_decisions[task_id].append(decision)

        # 检测 RETRY 后失败
        result = []
        for task_id, task_dec_list in task_decisions.items():
            # 按时间排序
            sorted_decs = sorted(
                task_dec_list,
                key=lambda d: d.get("timestamp", d.get("decision_id", ""))
            )

            # 找到所有 RETRY 决策
            for i, decision in enumerate(sorted_decs):
                if decision.get("decision_type") == "RETRY":
                    retry_decision_id = decision.get("decision_id")

                    # 检查后续是否有 BLOCK
                    for j in range(i + 1, len(sorted_decs)):
                        subsequent = sorted_decs[j]
                        if subsequent.get("decision_type") == "BLOCK":
                            # 生成 fingerprint
                            fingerprint = LeadFinding.generate_fingerprint(
                                rule_code="retry_recommended_but_fails",
                                window=window,
                                dimensions={
                                    "task_id": task_id,
                                    "retry_decision_id": retry_decision_id
                                }
                            )

                            finding = LeadFinding(
                                finding_id=f"lead_{uuid.uuid4().hex[:12]}",
                                fingerprint=fingerprint,
                                rule_code="retry_recommended_but_fails",
                                severity="medium",
                                title=f"Task {task_id} failed after RETRY recommendation",
                                description=(
                                    f"Task {task_id} was recommended to RETRY "
                                    f"but subsequently got BLOCKED"
                                ),
                                evidence={
                                    "task_id": task_id,
                                    "retry_decision_id": retry_decision_id,
                                    "failed_decision_id": subsequent.get("decision_id"),
                                    "failed_decision_type": "BLOCK"
                                },
                                window=window
                            )
                            result.append(finding)
                            break  # 只报告第一次失败

        return result

    def _rule_decision_lag_anomaly(
        self,
        storage_data: Dict[str, Any],
        window: ScanWindow
    ) -> List[LeadFinding]:
        """
        规则4: decision_lag_anomaly

        检测决策延迟 p95 超过阈值。

        逻辑：
        1. 从 metrics 中提取所有决策延迟
        2. 计算 p95
        3. 如果 p95 > threshold，生成 finding

        Evidence:
        - p95_latency_ms: P95 延迟（毫秒）
        - sample_count: 样本数量
        - threshold_ms: 阈值
        """
        metrics = storage_data.get("metrics", {})

        # 提取延迟数据（假设 metrics 包含 decision_latencies）
        latencies = metrics.get("decision_latencies", [])

        if not latencies:
            return []

        # 计算 p95
        sorted_latencies = sorted(latencies)
        p95_index = int(len(sorted_latencies) * 0.95)
        p95_latency = sorted_latencies[p95_index] if p95_index < len(sorted_latencies) else sorted_latencies[-1]

        # 检查是否超阈值
        if p95_latency > self.config.decision_lag_p95_ms:
            # 生成 fingerprint（全局，不按维度细分）
            fingerprint = LeadFinding.generate_fingerprint(
                rule_code="decision_lag_anomaly",
                window=window,
                dimensions={}
            )

            finding = LeadFinding(
                finding_id=f"lead_{uuid.uuid4().hex[:12]}",
                fingerprint=fingerprint,
                rule_code="decision_lag_anomaly",
                severity="high",
                title="Decision latency p95 exceeded threshold",
                description=(
                    f"Decision latency p95 is {p95_latency:.1f}ms, "
                    f"exceeding threshold of {self.config.decision_lag_p95_ms}ms"
                ),
                evidence={
                    "p95_latency_ms": p95_latency,
                    "sample_count": len(latencies),
                    "threshold_ms": self.config.decision_lag_p95_ms
                },
                window=window
            )
            return [finding]

        return []

    def _rule_redline_ratio_increase(
        self,
        storage_data: Dict[str, Any],
        window: ScanWindow
    ) -> List[LeadFinding]:
        """
        规则5: redline_ratio_increase

        检测 REDLINE 类型 finding 占比显著上升。

        逻辑：
        1. 统计 REDLINE 类型 finding 的数量
        2. 计算 REDLINE 占比（REDLINE / total findings）
        3. 如果占比显著高于基准（如从 5% 涨到 20%），生成 finding

        Evidence:
        - redline_count: REDLINE 类型数量
        - total_count: 总 finding 数量
        - redline_ratio: REDLINE 占比
        - baseline_ratio: 基准占比
        """
        findings_list = storage_data.get("findings", [])

        if not findings_list:
            return []

        # 统计 REDLINE 数量
        redline_count = sum(
            1 for f in findings_list
            if f.get("kind") == "REDLINE"
        )
        total_count = len(findings_list)

        # 计算占比
        redline_ratio = redline_count / total_count if total_count > 0 else 0.0

        # 检查占比是否显著上升
        baseline = self.config.redline_baseline_ratio
        increase = redline_ratio - baseline

        if increase > self.config.redline_ratio_increase:
            # 生成 fingerprint
            fingerprint = LeadFinding.generate_fingerprint(
                rule_code="redline_ratio_increase",
                window=window,
                dimensions={}
            )

            finding = LeadFinding(
                finding_id=f"lead_{uuid.uuid4().hex[:12]}",
                fingerprint=fingerprint,
                rule_code="redline_ratio_increase",
                severity="high",
                title="REDLINE findings ratio increased significantly",
                description=(
                    f"REDLINE findings ratio is {redline_ratio:.2%}, "
                    f"increased by {increase:.2%} from baseline {baseline:.2%}"
                ),
                evidence={
                    "redline_count": redline_count,
                    "total_count": total_count,
                    "redline_ratio": redline_ratio,
                    "baseline_ratio": baseline,
                    "increase": increase
                },
                window=window
            )
            return [finding]

        return []

    def _rule_high_risk_allow(
        self,
        storage_data: Dict[str, Any],
        window: ScanWindow
    ) -> List[LeadFinding]:
        """
        规则6: high_risk_allow

        检测 HIGH/CRITICAL 严重度的 finding 仍被 ALLOW。

        逻辑：
        1. 找到所有 decision_type = ALLOW 的决策
        2. 检查这些决策中是否有 HIGH 或 CRITICAL 的 findings
        3. 如果有，生成 finding

        Evidence:
        - count: 违规决策数量
        - sample_decision_ids: 样例决策 ID（最多5个）
        """
        decisions = storage_data.get("decisions", [])
        findings_list = storage_data.get("findings", [])

        # 构建 decision_id -> findings 的映射
        decision_findings = defaultdict(list)
        for finding in findings_list:
            decision_id = finding.get("decision_id")
            if decision_id:
                decision_findings[decision_id].append(finding)

        # 检测 HIGH/CRITICAL + ALLOW 组合
        violation_decision_ids = []

        for decision in decisions:
            if decision.get("decision_type") == "ALLOW":
                decision_id = decision.get("decision_id")
                related_findings = decision_findings.get(decision_id, [])

                # 检查是否有 HIGH 或 CRITICAL 的 findings
                has_high_risk = any(
                    f.get("severity") in ["HIGH", "CRITICAL"]
                    for f in related_findings
                )

                if has_high_risk:
                    violation_decision_ids.append(decision_id)

        # 生成 finding
        if violation_decision_ids:
            # 生成 fingerprint
            fingerprint = LeadFinding.generate_fingerprint(
                rule_code="high_risk_allow",
                window=window,
                dimensions={}
            )

            # 取样例（最多5个）
            samples = violation_decision_ids[:5]

            finding = LeadFinding(
                finding_id=f"lead_{uuid.uuid4().hex[:12]}",
                fingerprint=fingerprint,
                rule_code="high_risk_allow",
                severity="critical",
                title="HIGH/CRITICAL findings allowed to proceed",
                description=(
                    f"Found {len(violation_decision_ids)} decisions that ALLOWED "
                    f"tasks despite HIGH or CRITICAL severity findings"
                ),
                evidence={
                    "count": len(violation_decision_ids),
                    "sample_decision_ids": samples
                },
                window=window
            )
            return [finding]

        return []
