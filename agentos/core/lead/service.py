"""
Lead Agent Service

LeadService 是 Lead Agent 的核心服务层，负责：
1. 协调扫描流程（run_scan）
2. 调用 RiskMiner 执行规则检测
3. 调用 DedupeStore 去重存储
4. 调用 FollowUpTaskCreator 创建后续任务

设计原则：
- 零外部依赖：不直接依赖 DB/jobs/TaskService
- 纯领域逻辑：只处理扫描流程，存储/调度由外部注入
- 接口冻结：run_scan() 签名不可变
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
import logging

from agentos.core.time import utc_now, utc_now_iso
from agentos.core.lead.models import (
    LeadFinding,
    ScanWindow,
    WindowKind,
    ScanResult,
    FollowUpTaskSpec,
)

logger = logging.getLogger(__name__)


@dataclass
class LeadServiceConfig:
    """
    LeadService 配置

    阈值可配置，用于调整风险检测的敏感度。
    """
    # 扫描窗口配置
    default_window_kind: str = "24h"

    # 规则阈值（TODO: 后续与 RiskMiner 集成时使用）
    timeout_threshold: int = 3  # 超时任务阈值
    blocked_threshold: int = 5  # 阻塞任务阈值
    redline_threshold: int = 1  # 红线违规阈值（0 容忍）

    # Follow-up 任务配置
    create_followup_tasks: bool = True  # 是否创建后续任务

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "default_window_kind": self.default_window_kind,
            "timeout_threshold": self.timeout_threshold,
            "blocked_threshold": self.blocked_threshold,
            "redline_threshold": self.redline_threshold,
            "create_followup_tasks": self.create_followup_tasks,
        }


class LeadService:
    """
    Lead Agent 主服务

    核心职责：
    1. 协调扫描流程（扫描窗口 -> 规则检测 -> 去重 -> 后续任务）
    2. 返回扫描结果（findings + 统计信息）

    不做的事：
    1. 不直接访问 DB（由 StorageAdapter 提供数据）
    2. 不直接创建任务（由 FollowUpTaskCreator 负责）
    3. 不处理调度/Cron（由 Jobs 层负责）
    """

    def __init__(self, config: Optional[LeadServiceConfig] = None):
        """
        初始化 LeadService

        Args:
            config: 配置对象（可选，默认使用默认配置）
        """
        self.config = config or LeadServiceConfig()

        # Components (injected externally)
        self.storage = None
        self.miner = None
        self.dedupe_store = None
        self.task_creator = None

    def run_scan(
        self,
        window_kind: str,
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """
        运行风险扫描

        这是 Lead Agent 的核心接口（接口冻结）。
        扫描流程：
        1. 构建扫描窗口
        2. 调用 RiskMiner 执行规则检测（TODO）
        3. 调用 DedupeStore 去重存储（TODO）
        4. 调用 FollowUpTaskCreator 创建后续任务（TODO，仅 dry_run=False）
        5. 返回扫描结果

        Args:
            window_kind: "24h" | "7d" 扫描窗口类型
            dry_run: True 时不创建 follow-up tasks，只返回发现结果

        Returns:
            {
                "findings": [LeadFinding.to_dict(), ...],
                "window": ScanWindow.to_dict(),
                "tasks_created": int,
                "metadata": {
                    "scan_id": str,
                    "dry_run": bool,
                    "rule_stats": {...},  # TODO: 规则统计
                    ...
                }
            }

        Raises:
            ValueError: 如果 window_kind 无效
        """
        # 1. 验证并构建扫描窗口
        scan_window = self._build_scan_window(window_kind)

        # 2. 执行风险挖掘（TODO: 调用 RiskMiner）
        findings = self._mine_risks(scan_window)

        # 3. 去重存储（TODO: 调用 DedupeStore）
        deduplicated_findings = self._deduplicate_findings(findings)

        # 4. 创建后续任务（TODO: 调用 FollowUpTaskCreator，仅 dry_run=False）
        tasks_created = 0
        if not dry_run and self.config.create_followup_tasks:
            tasks_created = self._create_followup_tasks(deduplicated_findings)

        # 5. 构建并返回结果
        result = ScanResult(
            findings=deduplicated_findings,
            window=scan_window,
            tasks_created=tasks_created,
            metadata={
                "scan_id": self._generate_scan_id(),
                "dry_run": dry_run,
                "total_findings": len(findings),
                "deduplicated_findings": len(deduplicated_findings),
                "rule_stats": {},  # TODO: 从 RiskMiner 获取统计
            }
        )

        return result.to_dict()

    def _build_scan_window(self, window_kind: str) -> ScanWindow:
        """
        构建扫描窗口

        Args:
            window_kind: "24h" | "7d"

        Returns:
            ScanWindow 对象

        Raises:
            ValueError: 如果 window_kind 无效
        """
        # 验证 window_kind
        valid_kinds = ["24h", "7d"]
        if window_kind not in valid_kinds:
            raise ValueError(
                f"Invalid window_kind: {window_kind}. Must be one of: {valid_kinds}"
            )

        # 计算时间范围
        end_time = utc_now()
        if window_kind == "24h":
            start_time = end_time - timedelta(hours=24)
        elif window_kind == "7d":
            start_time = end_time - timedelta(days=7)
        else:
            raise ValueError(f"Unsupported window_kind: {window_kind}")

        # 转换为 WindowKind 枚举
        kind_enum = WindowKind.HOUR_24 if window_kind == "24h" else WindowKind.DAY_7

        return ScanWindow(
            kind=kind_enum,
            start_ts=start_time.isoformat(),
            end_ts=end_time.isoformat(),
        )

    def _mine_risks(self, scan_window: ScanWindow) -> list[LeadFinding]:
        """
        执行风险挖掘

        调用 RiskMiner 执行 6 条规则检测：
        - Rule 1: blocked_reason_spike
        - Rule 2: pause_block_churn
        - Rule 3: retry_recommended_but_fails
        - Rule 4: decision_lag_anomaly
        - Rule 5: redline_ratio_increase
        - Rule 6: high_risk_allow

        Args:
            scan_window: 扫描时间窗口

        Returns:
            LeadFinding 列表
        """
        if not self.storage or not self.miner:
            logger.warning("Storage or Miner not injected, returning empty findings")
            return []

        try:
            # Collect storage data from multiple queries
            storage_data = {
                "decisions": [],
                "findings": [],
                "metrics": {}
            }

            # Query 1: Blocked reasons (for rule 1)
            blocked_reasons = self.storage.get_blocked_reasons(scan_window)
            for reason in blocked_reasons:
                for task_id in reason.get("task_ids", []):
                    storage_data["findings"].append({
                        "code": reason["code"],
                        "decision_id": f"dec_{task_id}",
                        "kind": "BLOCK",
                        "severity": "HIGH"
                    })

            # Query 2: Pause-block churn (for rule 2)
            pause_block_tasks = self.storage.get_pause_block_churn(scan_window)
            for task in pause_block_tasks:
                storage_data["decisions"].append({
                    "task_id": task["task_id"],
                    "decision_type": "BLOCK",
                    "timestamp": utc_now_iso()
                })

            # Query 3: Retry then fail (for rule 3)
            retry_fails = self.storage.get_retry_then_fail(scan_window)
            for fail in retry_fails:
                for task_id in fail.get("task_ids", []):
                    storage_data["decisions"].append({
                        "task_id": task_id,
                        "decision_type": "RETRY",
                        "decision_id": f"retry_{task_id}",
                        "timestamp": utc_now_iso()
                    })
                    storage_data["decisions"].append({
                        "task_id": task_id,
                        "decision_type": "BLOCK",
                        "decision_id": f"block_{task_id}",
                        "timestamp": utc_now_iso()
                    })

            # Query 4: Decision lag (for rule 4)
            lag_data = self.storage.get_decision_lag(scan_window)
            storage_data["metrics"]["decision_latencies"] = [
                sample["lag_ms"] for sample in lag_data.get("samples", [])
            ]

            # Query 5: Redline ratio (for rule 5)
            redline_data = self.storage.get_redline_ratio(scan_window)
            for _ in range(redline_data.get("current_count", 0)):
                storage_data["findings"].append({
                    "code": "REDLINE",
                    "kind": "REDLINE",
                    "severity": "HIGH"
                })

            # Query 6: High risk allow (for rule 6)
            high_risk_allows = self.storage.get_high_risk_allow(scan_window)
            for allow in high_risk_allows:
                storage_data["decisions"].append({
                    "task_id": allow["task_id"],
                    "decision_type": "ALLOW",
                    "decision_id": allow["decision_id"]
                })
                storage_data["findings"].append({
                    "code": "HIGH_RISK",
                    "decision_id": allow["decision_id"],
                    "severity": allow["risk_level"],
                    "kind": "HIGH_RISK"
                })

            # Run miner
            findings = self.miner.mine_risks(storage_data, scan_window)

            logger.info(f"Mined {len(findings)} findings from window {scan_window.kind}")
            return findings

        except Exception as e:
            logger.error(f"Failed to mine risks: {e}", exc_info=True)
            return []

    def _deduplicate_findings(self, findings: list[LeadFinding]) -> list[LeadFinding]:
        """
        去重 findings

        调用 DedupeStore 基于 fingerprint 去重：
        - 查询 lead_findings 表，检查 fingerprint 是否已存在
        - 过滤掉已存在的 findings
        - 插入新的 findings

        Args:
            findings: 原始 findings 列表

        Returns:
            去重后的 findings 列表（只包含新 findings）
        """
        if not self.dedupe_store:
            logger.warning("DedupeStore not injected, skipping deduplication")
            return findings

        try:
            new_findings = []

            for finding in findings:
                # Convert LeadFinding (from models.py) to LeadFinding (from dedupe.py)
                from agentos.core.lead.dedupe import LeadFinding as DedupeLeadFinding

                dedupe_finding = DedupeLeadFinding(
                    fingerprint=finding.fingerprint,
                    code=finding.rule_code,
                    severity=finding.severity.upper(),
                    title=finding.title,
                    description=finding.description,
                    window_kind=finding.window.kind.value,
                    first_seen_at=datetime.fromisoformat(finding.detected_at.replace('Z', '+00:00')),
                    last_seen_at=datetime.fromisoformat(finding.detected_at.replace('Z', '+00:00')),
                    count=1,
                    evidence=finding.evidence,
                    linked_task_id=None
                )

                # Upsert: returns True if new, False if updated
                is_new = self.dedupe_store.upsert_finding(dedupe_finding)

                if is_new:
                    new_findings.append(finding)

            logger.info(f"Deduplicated {len(findings)} findings -> {len(new_findings)} new findings")
            return new_findings

        except Exception as e:
            logger.error(f"Failed to deduplicate findings: {e}", exc_info=True)
            return findings

    def _create_followup_tasks(self, findings: list[LeadFinding]) -> int:
        """
        创建后续任务

        调用 FollowUpTaskCreator 为高优先级 findings 创建任务：
        - 根据 severity 决定是否创建任务
        - 生成 FollowUpTaskSpec
        - 调用 TaskService 创建任务

        Args:
            findings: 去重后的 findings 列表

        Returns:
            创建的任务数量
        """
        if not self.task_creator:
            logger.warning("TaskCreator not injected, skipping task creation")
            return 0

        try:
            # Convert LeadFinding (from models.py) to LeadFinding (from dedupe.py)
            from agentos.core.lead.dedupe import LeadFinding as DedupeLeadFinding

            dedupe_findings = []
            for finding in findings:
                dedupe_finding = DedupeLeadFinding(
                    fingerprint=finding.fingerprint,
                    code=finding.rule_code,
                    severity=finding.severity.upper(),
                    title=finding.title,
                    description=finding.description,
                    window_kind=finding.window.kind.value,
                    first_seen_at=datetime.fromisoformat(finding.detected_at.replace('Z', '+00:00')),
                    last_seen_at=datetime.fromisoformat(finding.detected_at.replace('Z', '+00:00')),
                    count=1,
                    evidence=finding.evidence,
                    linked_task_id=None
                )
                dedupe_findings.append(dedupe_finding)

            # Create tasks (dry_run=False)
            result = self.task_creator.create_batch(dedupe_findings, dry_run=False)

            tasks_created = result["created"]
            logger.info(f"Created {tasks_created} follow-up tasks from {len(findings)} findings")

            return tasks_created

        except Exception as e:
            logger.error(f"Failed to create follow-up tasks: {e}", exc_info=True)
            return 0

    def _generate_scan_id(self) -> str:
        """
        生成扫描 ID

        Returns:
            扫描 ID（格式: scan_<timestamp>）
        """
        timestamp = utc_now().strftime("%Y%m%d_%H%M%S")
        return f"scan_{timestamp}"

    def get_config(self) -> Dict[str, Any]:
        """
        获取当前配置

        Returns:
            配置字典
        """
        return self.config.to_dict()

    def update_config(self, updates: Dict[str, Any]) -> None:
        """
        更新配置

        Args:
            updates: 配置更新字典
        """
        for key, value in updates.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
            else:
                raise ValueError(f"Invalid config key: {key}")
