"""
数据契约转换器

负责在 Storage、Miner、Dedupe 三层之间转换数据格式。
这是数据契约的核心实现，确保各层之间的数据格式匹配。

版本化策略：
- 每个 Mapper 都有独立的 VERSION 常量
- 转换逻辑变更时需要增加版本号
- 保持向后兼容性，避免破坏性变更
"""

from typing import Dict, List, Any
from datetime import datetime, timezone

from agentos.core.lead.models import LeadFinding as MinerLeadFinding, ScanWindow
from agentos.core.lead.dedupe import LeadFinding as DedupeLeadFinding


class StorageToMinerMapper:
    """
    Storage 聚合数据 -> Miner 输入格式

    输入格式（Storage）:
    {
        "blocked_reasons": [{code, count, task_ids}],
        "pause_block_churn": [{task_id, pause_count, final_status}],
        "retry_then_fail": [{error_code, count, task_ids}],
        "decision_lag": {p95_ms, samples},
        "redline_ratio": {current_ratio, previous_ratio, ...},
        "high_risk_allow": [{decision_id, task_id, risk_level}]
    }

    输出格式（Miner）:
    {
        "findings": [{code, kind, severity, decision_id, message}],
        "decisions": [{task_id, decision_id, decision_type, timestamp}],
        "metrics": {decision_latencies, decision_lag_p95}
    }
    """

    VERSION = "1.0.0"

    @staticmethod
    def convert(storage_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        转换 Storage 数据到 Miner 格式

        此方法实现了 lead_scan.py 中的 _convert_storage_to_miner_format 逻辑，
        保持完全相同的行为以确保向后兼容。

        Args:
            storage_data: LeadStorage 返回的聚合数据

        Returns:
            miner_data: RiskMiner 期望的输入格式
        """
        findings = []

        # 1. 从 blocked_reasons 构造 findings
        # 每个 blocked_reasons 记录包含: {code, count, task_ids}
        # 需要展开为多个 finding 记录
        for item in storage_data.get("blocked_reasons", []):
            code = item.get("code", "")
            task_ids = item.get("task_ids", [])
            count = item.get("count", 0)

            # 为每个 task_id 创建一个 finding 记录
            for i, task_id in enumerate(task_ids[:count]):  # 限制数量防止过大
                findings.append({
                    "code": code,
                    "kind": "BLOCKED",
                    "severity": "HIGH",
                    "decision_id": f"dec_blocked_{code}_{i}",
                    "message": f"Task blocked with code {code}"
                })

        # 2. 从 retry_then_fail 构造 findings
        # retry_then_fail 记录: {error_code, count, task_ids}
        for item in storage_data.get("retry_then_fail", []):
            error_code = item.get("error_code", "")
            task_ids = item.get("task_ids", [])
            count = item.get("count", 0)

            for i, task_id in enumerate(task_ids[:count]):
                findings.append({
                    "code": error_code,
                    "kind": "RETRY_FAILED",
                    "severity": "HIGH",
                    "decision_id": f"dec_retry_{error_code}_{i}",
                    "message": f"Task failed after retry with error {error_code}"
                })

        # 3. 从 high_risk_allow 构造 findings
        # high_risk_allow 记录: {decision_id, task_id, risk_level, findings}
        for item in storage_data.get("high_risk_allow", []):
            decision_id = item.get("decision_id", "")
            # 如果有 findings 字段，直接使用
            item_findings = item.get("findings", [])
            for finding in item_findings:
                finding["decision_id"] = decision_id
                findings.append(finding)

        decisions = []

        # 4. 从 pause_block_churn 构造 decisions
        # pause_block_churn 记录: {task_id, pause_count, final_status, decision_ids}
        for item in storage_data.get("pause_block_churn", []):
            task_id = item.get("task_id", "")
            pause_count = item.get("pause_count", 0)
            final_status = item.get("final_status", "BLOCKED")

            # 添加 PAUSE 决策（模拟多次 PAUSE）
            for i in range(pause_count):
                decisions.append({
                    "task_id": task_id,
                    "decision_id": f"pause_{task_id}_{i}",
                    "decision_type": "PAUSE",
                    "timestamp": f"2025-01-28T{10+i:02d}:00:00Z"  # 模拟时间戳
                })

            # 添加最终 BLOCK 决策
            decisions.append({
                "task_id": task_id,
                "decision_id": f"block_{task_id}",
                "decision_type": "BLOCK",
                "timestamp": f"2025-01-28T{10+pause_count:02d}:00:00Z"
            })

        # 5. 从 retry_then_fail 构造 RETRY 和 BLOCK 决策
        # retry_then_fail 记录: {error_code, count, task_ids}
        for item in storage_data.get("retry_then_fail", []):
            task_ids = item.get("task_ids", [])

            for task_id in task_ids:
                # 添加 RETRY 决策
                decisions.append({
                    "task_id": task_id,
                    "decision_id": f"retry_{task_id}",
                    "decision_type": "RETRY",
                    "timestamp": "2025-01-28T09:00:00Z"  # 模拟时间戳
                })

                # 添加后续 BLOCK 决策
                decisions.append({
                    "task_id": task_id,
                    "decision_id": f"block_after_retry_{task_id}",
                    "decision_type": "BLOCK",
                    "timestamp": "2025-01-28T10:00:00Z"  # 模拟时间戳
                })

        # 6. 从 high_risk_allow 构造 ALLOW 决策
        for item in storage_data.get("high_risk_allow", []):
            decisions.append({
                "task_id": item.get("task_id", ""),
                "decision_id": item.get("decision_id", ""),
                "decision_type": "ALLOW",
                "timestamp": item.get("timestamp", "")
            })

        # 7. 构造 metrics
        decision_lag = storage_data.get("decision_lag", {})
        metrics = {
            "decision_latencies": decision_lag.get("samples", []),
            "decision_lag_p95": decision_lag.get("p95_ms", 0)
        }

        # 8. 构造 Miner 期望的数据格式
        miner_data = {
            "findings": findings,
            "decisions": decisions,
            "metrics": metrics
        }

        return miner_data


class MinerToDedupeMapper:
    """
    Miner 输出格式 -> Dedupe 存储格式

    输入格式（Miner）:
    models.LeadFinding(
        fingerprint, rule_code, severity, title, description,
        evidence, window (ScanWindow), detected_at
    )

    输出格式（Dedupe）:
    dedupe.LeadFinding(
        fingerprint, code, severity, title, description, window_kind,
        evidence, first_seen_at, last_seen_at, count, linked_task_id
    )
    """

    VERSION = "1.0.0"

    @staticmethod
    def convert(miner_finding: MinerLeadFinding) -> DedupeLeadFinding:
        """
        转换 Miner LeadFinding 到 Dedupe LeadFinding

        此方法实现了 lead_scan.py 中的 _convert_miner_to_dedupe_finding 逻辑，
        保持完全相同的行为以确保向后兼容。

        Args:
            miner_finding: RiskMiner 输出的 LeadFinding

        Returns:
            dedupe_finding: LeadFindingStore 接受的 LeadFinding
        """
        return DedupeLeadFinding(
            fingerprint=miner_finding.fingerprint,
            code=miner_finding.rule_code,  # rule_code -> code
            severity=miner_finding.severity.upper(),  # 确保大写
            title=miner_finding.title,
            description=miner_finding.description,
            window_kind=miner_finding.window.kind.value,  # WindowKind enum -> string
            evidence=miner_finding.evidence,
            first_seen_at=None,  # 由 dedupe store 设置
            last_seen_at=None,  # 由 dedupe store 设置
            count=1,
            linked_task_id=None,
        )


class ContractMapper:
    """
    统一的转换器入口，组合 Storage->Miner 和 Miner->Dedupe 转换

    这个类提供了一个统一的接口来访问所有转换功能，
    便于依赖注入和测试。
    """

    def __init__(self):
        self.storage_to_miner = StorageToMinerMapper()
        self.miner_to_dedupe = MinerToDedupeMapper()

    def convert_storage_to_miner(self, storage_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Storage -> Miner 转换

        Args:
            storage_data: LeadStorage 返回的聚合数据

        Returns:
            miner_data: RiskMiner 期望的输入格式
        """
        return self.storage_to_miner.convert(storage_data)

    def convert_miner_to_dedupe(self, miner_finding: MinerLeadFinding) -> DedupeLeadFinding:
        """
        Miner -> Dedupe 转换

        Args:
            miner_finding: RiskMiner 输出的 LeadFinding

        Returns:
            dedupe_finding: LeadFindingStore 接受的 LeadFinding
        """
        return self.miner_to_dedupe.convert(miner_finding)

    @property
    def version(self) -> Dict[str, str]:
        """返回所有 mapper 的版本信息"""
        return {
            "storage_to_miner": StorageToMinerMapper.VERSION,
            "miner_to_dedupe": MinerToDedupeMapper.VERSION
        }
