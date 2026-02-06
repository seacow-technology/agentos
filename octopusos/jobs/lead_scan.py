#!/usr/bin/env python3
"""
Lead Agent Scan Job

定期运行 Lead Agent 风险扫描，发现潜在问题并创建 follow-up tasks

Usage:
    python -m agentos.jobs.lead_scan --window 24h --dry-run
    python -m agentos.jobs.lead_scan --window 7d
    python -m agentos.jobs.lead_scan --window 24h --force
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.table import Table

# 导入跨平台文件锁工具
from agentos.core.utils.filelock import acquire_lock, release_lock, LockAcquisitionError

# 导入 Lead Agent 组件
from agentos.core.lead.adapters.storage import LeadStorage
from agentos.core.lead.adapters.task_creator import LeadTaskCreator
from agentos.core.lead.contract import ContractMapper
from agentos.core.lead.dedupe import LeadFindingStore
from agentos.core.lead.dedupe import LeadFinding as DedupeLeadFinding
from agentos.core.lead.miner import RiskMiner, MinerConfig
from agentos.core.lead.models import ScanWindow, WindowKind
from agentos.core.lead.models import LeadFinding as MinerLeadFinding

# 导入配置管理
from agentos.config import load_lead_config, LeadConfig

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

console = Console()

# 锁文件路径 (跨平台临时目录)
LOCK_FILE_PATH = Path(tempfile.gettempdir()) / "agentos_lead_scan.lock"


class LeadScanJob:
    """
    Lead Agent 扫描作业

    负责：
    1. 从数据库查询 Supervisor 决策历史
    2. 运行 Risk Miner 规则检测
    3. 去重存储 findings
    4. 创建 follow-up tasks（仅 dry_run=False）
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        config_path: Optional[Path] = None,
        config: Optional[MinerConfig] = None,
        alert_thresholds: Optional[dict] = None
    ):
        """
        初始化扫描作业

        Args:
            db_path: 数据库路径（默认使用环境变量 AGENTOS_LEAD_SCAN_DB 或 ~/.agentos/store.db）
            config_path: 配置文件路径（可选，用于 override 默认配置）
            config: Miner 配置（可选，向后兼容，优先级低于 config_path）
            alert_thresholds: 告警阈值配置（可选，向后兼容，优先级低于 config_path）
        """
        if db_path is None:
            # Use environment variable with fallback
            db_path_str = os.getenv("AGENTOS_LEAD_SCAN_DB")
            if db_path_str:
                db_path = Path(db_path_str)
            else:
                from agentos.core.storage.paths import component_db_path
                db_path = component_db_path("agentos")

        self.db_path = db_path
        self._config_path_override = config_path  # 保存用于 config_info

        # 加载配置（优先使用配置文件）
        self.lead_config = load_lead_config(config_path)

        # 向后兼容：如果提供了 config 参数，则覆盖配置文件中的值
        if config is not None:
            miner_config = config
        else:
            # 从配置文件构建 MinerConfig
            miner_config = MinerConfig(
                spike_threshold=self.lead_config.rule_thresholds.spike_threshold,
                pause_count_threshold=self.lead_config.rule_thresholds.pause_count_threshold,
                decision_lag_p95_ms=float(self.lead_config.rule_thresholds.decision_lag_threshold_ms),
                redline_ratio_increase=self.lead_config.rule_thresholds.redline_ratio_increase_threshold,
                redline_baseline_ratio=self.lead_config.rule_thresholds.redline_ratio_min_baseline
            )

        # 初始化各组件
        self.storage = LeadStorage(db_path=db_path)
        self.miner = RiskMiner(config=miner_config)
        self.mapper = ContractMapper()
        self.finding_store = LeadFindingStore(db_path=db_path)
        self.task_creator = LeadTaskCreator(db_path=db_path)

        # 告警阈值配置（向后兼容）
        if alert_thresholds is not None:
            self.alert_thresholds = alert_thresholds
        else:
            self.alert_thresholds = {
                "min_blocked_for_alert": self.lead_config.alert_thresholds.min_blocked_for_alert,
                "min_high_risk_for_alert": self.lead_config.alert_thresholds.min_high_risk_for_alert
            }

        # 统计信息
        self.stats = {
            "started_at": None,
            "completed_at": None,
            "window_kind": None,
            "raw_findings": 0,
            "new_findings": 0,
            "duplicate_findings": 0,
            "tasks_created": 0,
            "tasks_skipped": 0,
            "dry_run": False,
            "error": None,
        }

    def _get_config_info(self) -> dict:
        """
        收集配置信息用于 WebUI 显示

        Returns:
            {
                "source": "file" | "env" | "cli" | "default",
                "config_path": "/path/to/config.yaml" or None,
                "config_version": "1.0.0",
                "config_hash": "abc123...",  # SHA256前8位
                "thresholds_summary": {
                    "spike_threshold": 5,
                    "pause_count_threshold": 2,
                    ...
                }
            }
        """
        import hashlib
        import os

        # 确定配置来源
        env_config = os.getenv("LEAD_CONFIG")
        if env_config:
            source = "env"
            config_path = env_config
        elif self._config_path_override:
            source = "cli"
            config_path = str(self._config_path_override)
        else:
            # 检查默认路径是否存在
            default_path = Path(__file__).parent.parent / "config" / "lead_rules.yaml"
            if default_path.exists():
                source = "file"
                config_path = str(default_path)
            else:
                source = "default"
                config_path = None

        # 计算配置 hash（用于检测变更）
        config_hash = None
        if config_path and Path(config_path).exists():
            try:
                with open(config_path, 'rb') as f:
                    config_hash = hashlib.sha256(f.read()).hexdigest()[:8]
            except Exception:
                config_hash = None

        return {
            "source": source,
            "config_path": config_path,
            "config_version": self.lead_config.version,
            "config_hash": config_hash,
            "thresholds_summary": {
                "spike_threshold": self.lead_config.rule_thresholds.spike_threshold,
                "pause_count_threshold": self.lead_config.rule_thresholds.pause_count_threshold,
                "retry_threshold": self.lead_config.rule_thresholds.retry_threshold,
                "decision_lag_threshold_ms": self.lead_config.rule_thresholds.decision_lag_threshold_ms,
                "redline_ratio_increase_threshold": self.lead_config.rule_thresholds.redline_ratio_increase_threshold,
                "high_risk_allow_threshold": self.lead_config.rule_thresholds.high_risk_allow_threshold
            }
        }

    def _check_contract_versions(self, dry_run: bool = True) -> dict:
        """
        检查 Storage 和 Miner 的契约版本是否兼容

        Args:
            dry_run: 如果为 True，版本不匹配时只输出 WARNING；
                    如果为 False，版本不匹配时抛出异常

        Returns:
            {
                "storage_version": str,
                "miner_version": str,
                "compatible": bool
            }

        Raises:
            RuntimeError: 非 dry-run 且版本不匹配时
        """
        from agentos.core.lead.adapters.storage import LeadStorage
        from agentos.core.lead.miner import RiskMiner

        storage_version = LeadStorage.CONTRACT_VERSION
        miner_version = RiskMiner.CONTRACT_VERSION

        # 记录版本到日志
        console.print(f"[dim]Contract versions: storage={storage_version}, miner={miner_version}[/dim]")

        # 检查版本兼容性（当前简单比较，未来Available语义化版本）
        compatible = storage_version == miner_version

        if not compatible:
            error_msg = (
                f"CONTRACT_MISMATCH: Storage version ({storage_version}) "
                f"!= Miner version ({miner_version}). "
                f"This may cause silent failures where findings=0."
            )

            if dry_run:
                # dry-run 模式：输出 WARNING 但允许继续
                console.print(f"[bold yellow]⚠️  WARNING: {error_msg}[/bold yellow]")
            else:
                # 非 dry-run 模式：直接失败
                raise RuntimeError(error_msg)

        return {
            "storage_version": storage_version,
            "miner_version": miner_version,
            "compatible": compatible
        }

    def _self_check_findings(
        self,
        storage_data: dict,
        miner_data: dict,
        findings: list,
        window_kind: str
    ) -> dict:
        """
        自检：如果有数据但 findings=0，触发告警

        Args:
            storage_data: Storage 返回的聚合数据
            miner_data: 转换后的 Miner 输入数据
            findings: Miner 输出的 findings
            window_kind: 扫描窗口类型

        Returns:
            {
                "has_data": bool,          # 是否有输入数据
                "findings_count": int,     # findings 数量
                "alert_triggered": bool,   # 是否触发告警
                "alert_reason": str        # 告警原因
            }
        """
        findings_count = len(findings)
        alert_triggered = False
        alert_reason = None

        # 统计输入数据量
        blocked_count = len(storage_data.get("blocked_reasons", []))
        pause_block_count = len(storage_data.get("pause_block_churn", []))
        retry_fail_count = len(storage_data.get("retry_then_fail", []))
        high_risk_allow_count = len(storage_data.get("high_risk_allow", []))

        total_storage_items = (
            blocked_count +
            pause_block_count +
            retry_fail_count +
            high_risk_allow_count
        )

        miner_findings_count = len(miner_data.get("findings", []))
        miner_decisions_count = len(miner_data.get("decisions", []))

        has_data = total_storage_items > 0 or miner_findings_count > 0 or miner_decisions_count > 0

        # 检查 1：高优先级信号（high_risk_allow 或大量 blocked）但 findings=0
        # 这个检查优先级最高，因为更严重
        min_blocked = self.alert_thresholds["min_blocked_for_alert"]
        min_high_risk = self.alert_thresholds["min_high_risk_for_alert"]

        if (high_risk_allow_count >= min_high_risk or blocked_count >= min_blocked) and findings_count == 0:
            alert_triggered = True
            alert_reason = (
                f"High-priority signals detected "
                f"(high_risk_allow={high_risk_allow_count}, blocked={blocked_count}) "
                f"but Miner produced 0 findings. This is abnormal."
            )

        # 检查 2：有 storage 数据但 findings=0（通用检查）
        if not alert_triggered and total_storage_items > 0 and findings_count == 0:
            alert_triggered = True
            alert_reason = (
                f"Storage returned {total_storage_items} items "
                f"(blocked={blocked_count}, pause_block={pause_block_count}, "
                f"retry_fail={retry_fail_count}, high_risk_allow={high_risk_allow_count}) "
                f"but Miner produced 0 findings. Possible causes: "
                f"1) Contract mismatch, 2) All rules filtered out, 3) Thresholds too high."
            )

        # 检查 3：24h 窗口但数据量为 0（可能数据管道断了）
        if window_kind == "24h" and not has_data:
            # 这个可能是正常的（系统确实没问题），但在新部署时可能是管道问题
            # 设置为 INFO 级别，不是严重告警
            console.print(
                f"[dim yellow]ℹ️  INFO: 24h scan found no data. "
                f"This is normal if system is healthy, but verify if this is a new deployment.[/dim yellow]"
            )

        # 输出告警
        if alert_triggered:
            console.print(f"\n[bold red]🚨 ALERT: POTENTIAL SILENT FAILURE[/bold red]")
            console.print(f"[bold red]{alert_reason}[/bold red]\n")

            # 记录到日志
            logger.error(f"SILENT FAILURE ALERT: {alert_reason}")

        return {
            "has_data": has_data,
            "findings_count": findings_count,
            "storage_items_count": total_storage_items,
            "miner_findings_input_count": miner_findings_count,
            "miner_decisions_input_count": miner_decisions_count,
            "alert_triggered": alert_triggered,
            "alert_reason": alert_reason
        }

    def run_scan(self, window_kind: str, dry_run: bool = True) -> dict:
        """
        运行风险扫描

        Args:
            window_kind: "24h" | "7d" 扫描窗口类型
            dry_run: True 时不创建 follow-up tasks，只返回发现结果

        Returns:
            {
                "timestamp": "2025-01-28T10:00:00Z",
                "window_kind": "24h",
                "findings_count": 5,
                "tasks_created": 3,
                "dry_run": True,
                "stats": {...},
                "contract_versions": {...},
                "config_info": {...}
            }
        """
        self.stats["started_at"] = datetime.now(timezone.utc).isoformat()
        self.stats["window_kind"] = window_kind
        self.stats["dry_run"] = dry_run

        try:
            console.print(f"[cyan]Starting Lead Agent scan (window={window_kind}, dry_run={dry_run})...[/cyan]")

            # 0a. 打印阈值摘要（如果配置启用）
            if self.lead_config.print_summary:
                self._print_threshold_summary()

            # 0b. 版本检查（必须在任何操作前）
            version_check = self._check_contract_versions(dry_run=dry_run)

            # 1. 构建扫描窗口
            scan_window = self._build_scan_window(window_kind)
            console.print(f"[dim]Scan window: {scan_window.start_ts} to {scan_window.end_ts}[/dim]")

            # 2. 从数据库查询 Supervisor 决策数据
            storage_data = self._load_storage_data(scan_window)
            console.print(f"[dim]Loaded storage data from database[/dim]")

            # 3. 转换数据格式（Storage 聚合数据 -> Miner 期望格式）- 使用独立 mapper 模块
            miner_data = self.mapper.convert_storage_to_miner(storage_data)
            console.print(f"[dim]Converted to miner format: {len(miner_data['findings'])} findings, {len(miner_data['decisions'])} decisions[/dim]")

            # 4. 运行 Risk Miner 规则检测
            raw_findings = self.miner.mine_risks(miner_data, scan_window)
            self.stats["raw_findings"] = len(raw_findings)
            console.print(f"[green]✓ Miner found {len(raw_findings)} raw findings[/green]")

            # 4.5 自检：如果有数据但 findings=0，触发告警
            self_check_result = self._self_check_findings(
                storage_data=storage_data,
                miner_data=miner_data,
                findings=raw_findings,
                window_kind=window_kind
            )

            # 5. 去重存储（基于 fingerprint 幂等）
            new_findings = self._deduplicate_and_store(raw_findings, dry_run=dry_run)
            self.stats["new_findings"] = len(new_findings)
            self.stats["duplicate_findings"] = len(raw_findings) - len(new_findings)

            if dry_run:
                console.print(f"[yellow]○ Would store {len(new_findings)} new findings ({self.stats['duplicate_findings']} duplicates) (dry_run mode)[/yellow]")
            else:
                console.print(f"[green]✓ Stored {len(new_findings)} new findings ({self.stats['duplicate_findings']} duplicates)[/green]")

            # 6. 创建 follow-up tasks（仅 dry_run=False）
            if not dry_run:
                task_result = self.task_creator.create_batch(new_findings, dry_run=False)
                self.stats["tasks_created"] = task_result["created"]
                self.stats["tasks_skipped"] = task_result["skipped"]
                console.print(f"[green]✓ Created {task_result['created']} follow-up tasks ({task_result['skipped']} skipped)[/green]")
            else:
                # dry_run: 只模拟创建
                mock_result = self.task_creator.create_batch(new_findings, dry_run=True)
                self.stats["tasks_created"] = 0
                self.stats["tasks_skipped"] = len(new_findings)
                console.print(f"[yellow]○ Would create {mock_result['created']} tasks (dry_run mode)[/yellow]")

            # 7. 完成统计
            self.stats["completed_at"] = datetime.now(timezone.utc).isoformat()

            # 打印摘要
            self._print_summary()

            # 8. 返回结果（包含配置信息）
            return {
                "timestamp": self.stats["completed_at"],
                "window_kind": window_kind,
                "findings_count": self.stats["new_findings"],
                "tasks_created": self.stats["tasks_created"],
                "dry_run": dry_run,
                "stats": self.stats,
                "self_check": self_check_result,
                "contract_versions": version_check,
                "config_info": self._get_config_info(),
            }

        except Exception as e:
            self.stats["error"] = str(e)
            self.stats["completed_at"] = datetime.now(timezone.utc).isoformat()
            logger.error(f"Lead scan failed: {e}", exc_info=True)
            console.print(f"[red]✗ Lead scan failed: {e}[/red]")
            raise

    def _build_scan_window(self, window_kind: str) -> ScanWindow:
        """构建扫描窗口"""
        from datetime import timedelta

        valid_kinds = ["24h", "7d"]
        if window_kind not in valid_kinds:
            raise ValueError(f"Invalid window_kind: {window_kind}. Must be one of: {valid_kinds}")

        end_time = datetime.now(timezone.utc)
        if window_kind == "24h":
            start_time = end_time - timedelta(hours=24)
            kind_enum = WindowKind.HOUR_24
        elif window_kind == "7d":
            start_time = end_time - timedelta(days=7)
            kind_enum = WindowKind.DAY_7
        else:
            raise ValueError(f"Unsupported window_kind: {window_kind}")

        return ScanWindow(
            kind=kind_enum,
            start_ts=start_time.isoformat(),
            end_ts=end_time.isoformat(),
        )

    def _load_storage_data(self, window: ScanWindow) -> dict:
        """
        从 LeadStorage 加载所有规则所需的数据

        Returns:
            {
                "blocked_reasons": [...],
                "pause_block_churn": [...],
                "retry_then_fail": [...],
                "decision_lag": {...},
                "redline_ratio": {...},
                "high_risk_allow": [...]
            }
        """
        return {
            "blocked_reasons": self.storage.get_blocked_reasons(window),
            "pause_block_churn": self.storage.get_pause_block_churn(window),
            "retry_then_fail": self.storage.get_retry_then_fail(window),
            "decision_lag": self.storage.get_decision_lag(window),
            "redline_ratio": self.storage.get_redline_ratio(window),
            "high_risk_allow": self.storage.get_high_risk_allow(window),
        }


    def _deduplicate_and_store(self, findings: list, dry_run: bool = False) -> list:
        """
        去重并存储 findings

        将 Miner 返回的 models.LeadFinding 转换为 dedupe.LeadFinding 并存储。

        Args:
            findings: List[MinerLeadFinding] - Miner 返回的 findings
            dry_run: 如果为 True，不写入数据库，只返回去重后的 findings

        Returns:
            新发现的 dedupe findings 列表（排除已存在的）- List[DedupeLeadFinding]
        """
        new_findings = []

        for miner_finding in findings:
            # 转换 models.LeadFinding -> dedupe.LeadFinding - 使用独立 mapper 模块
            dedupe_finding = self.mapper.convert_miner_to_dedupe(miner_finding)

            if dry_run:
                # dry-run: 不实际写库，直接返回（不去重）
                # 注意：这里不去重是因为 dry-run 时数据库中没有历史数据Available于去重判断
                # 返回所有转换后的 findings
                new_findings.append(dedupe_finding)
            else:
                # 真实执行: 尝试 upsert（幂等）
                is_new = self.finding_store.upsert_finding(dedupe_finding)

                if is_new:
                    # 返回 dedupe finding（包含 linked_task_id 等字段）
                    new_findings.append(dedupe_finding)

        return new_findings


    def _print_threshold_summary(self):
        """打印当前使用的阈值摘要"""
        table = Table(title=f"Lead Agent 规则阈值 (v{self.lead_config.version})")
        table.add_column("规则", style="cyan")
        table.add_column("阈值", style="yellow")
        table.add_column("说明", style="dim")

        table.add_row(
            "blocked_reason_spike",
            str(self.lead_config.rule_thresholds.spike_threshold),
            "相同错误码激增"
        )
        table.add_row(
            "pause_block_churn",
            str(self.lead_config.rule_thresholds.pause_count_threshold),
            "PAUSE 次数阈值"
        )
        table.add_row(
            "retry_then_fail",
            str(self.lead_config.rule_thresholds.retry_threshold),
            "RETRY 后失败"
        )
        table.add_row(
            "decision_lag",
            f"{self.lead_config.rule_thresholds.decision_lag_threshold_ms}ms",
            "决策延迟 p95"
        )
        table.add_row(
            "redline_ratio",
            f"{self.lead_config.rule_thresholds.redline_ratio_increase_threshold:.0%}",
            "占比增幅阈值"
        )
        table.add_row(
            "high_risk_allow",
            str(self.lead_config.rule_thresholds.high_risk_allow_threshold),
            "高危放行"
        )

        console.print(table)
        console.print()  # 空行分隔

    def _print_summary(self):
        """打印扫描摘要"""
        console.print("\n[bold green]Lead Scan Complete![/bold green]")
        console.print(f"  Window: {self.stats['window_kind']}")
        console.print(f"  Raw Findings: {self.stats['raw_findings']}")
        console.print(f"  New Findings: {self.stats['new_findings']}")
        console.print(f"  Duplicate Findings: {self.stats['duplicate_findings']}")
        console.print(f"  Tasks Created: {self.stats['tasks_created']}")
        console.print(f"  Tasks Skipped: {self.stats['tasks_skipped']}")

        if self.stats["dry_run"]:
            console.print("\n[yellow]DRY RUN - No tasks were created[/yellow]")

        # 计算执行时间
        if self.stats["started_at"] and self.stats["completed_at"]:
            start_dt = datetime.fromisoformat(self.stats["started_at"])
            end_dt = datetime.fromisoformat(self.stats["completed_at"])
            duration = (end_dt - start_dt).total_seconds()
            console.print(f"\n[dim]Execution time: {duration:.2f}s[/dim]")


# 并发保护：文件锁状态管理
class LockManager:
    """管理文件锁状态"""
    def __init__(self):
        self.lock_file = None

    def acquire(self) -> bool:
        """
        获取并发锁（文件锁 - 跨平台兼容）

        Returns:
            True: 获取成功
            False: 已有其他实例运行
        """
        try:
            # 确保锁文件存在
            LOCK_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
            LOCK_FILE_PATH.touch(exist_ok=True)

            # 打开锁文件
            self.lock_file = open(LOCK_FILE_PATH, 'w', encoding='utf-8')

            # 尝试获取非阻塞排他锁 (跨平台)
            acquire_lock(self.lock_file, non_blocking=True)

            # 写入 PID（可选，用于调试）
            import os
            self.lock_file.write(f"{os.getpid()}\n")
            self.lock_file.flush()

            logger.info(f"Acquired lock: {LOCK_FILE_PATH}")
            return True

        except LockAcquisitionError:
            # 锁被其他进程持有
            logger.warning(f"Failed to acquire lock: {LOCK_FILE_PATH} (another instance is running)")
            if self.lock_file:
                self.lock_file.close()
                self.lock_file = None
            return False
        except Exception as e:
            logger.error(f"Error acquiring lock: {e}")
            if self.lock_file:
                self.lock_file.close()
                self.lock_file = None
            return False

    def release(self):
        """释放并发锁 (跨平台兼容)"""
        if self.lock_file:
            try:
                release_lock(self.lock_file)
                self.lock_file.close()
                logger.info(f"Released lock: {LOCK_FILE_PATH}")
            except Exception as e:
                logger.warning(f"Error releasing lock: {e}")
            finally:
                self.lock_file = None


# 全局锁管理器
_lock_manager = LockManager()


def acquire_lock() -> bool:
    """获取并发锁（向后兼容接口）"""
    return _lock_manager.acquire()


def release_lock():
    """释放并发锁（向后兼容接口）"""
    _lock_manager.release()


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description="Lead Agent Scan Job - 自动风险扫描与任务创建",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 预览模式（不创建任务）
  python -m agentos.jobs.lead_scan --window 24h --dry-run

  # 实际运行（创建任务）
  python -m agentos.jobs.lead_scan --window 7d

  # 强制运行（跳过并发检查）
  python -m agentos.jobs.lead_scan --window 24h --force
"""
    )

    parser.add_argument(
        "--window",
        choices=["24h", "7d"],
        default="24h",
        help="扫描时间窗口（默认: 24h）"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="预览模式，不创建 follow-up tasks"
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="强制运行，跳过并发检查"
    )

    parser.add_argument(
        "--db-path",
        type=Path,
        help="数据库路径（默认: ~/.agentos/store/agentos/db.sqlite）"
    )

    parser.add_argument(
        "--config",
        type=Path,
        help="配置文件路径（用于 override 默认阈值）"
    )

    args = parser.parse_args()

    # 1. 并发保护
    if not args.force:
        if not acquire_lock():
            console.print("[yellow]另一个 lead_scan 实例正在运行，跳过本次执行[/yellow]")
            console.print("[dim]提示: 使用 --force 参数可强制运行[/dim]")
            sys.exit(0)
    else:
        console.print("[yellow]警告: 跳过并发检查（--force 模式）[/yellow]")

    try:
        # 2. 运行扫描
        job = LeadScanJob(
            db_path=args.db_path,
            config_path=args.config
        )
        result = job.run_scan(
            window_kind=args.window,
            dry_run=args.dry_run
        )

        # 3. 输出结构化日志（JSON，方便解析）
        logger.info(f"Lead scan result: {json.dumps(result, indent=2, ensure_ascii=False)}")

        sys.exit(0)

    except KeyboardInterrupt:
        console.print("\n[yellow]扫描被用户中断[/yellow]")
        sys.exit(1)

    except Exception as e:
        console.print(f"[red]Lead scan 失败: {e}[/red]")
        logger.error(f"Lead scan failed: {e}", exc_info=True)
        sys.exit(1)

    finally:
        # 4. 释放锁
        if not args.force:
            release_lock()


if __name__ == "__main__":
    main()
