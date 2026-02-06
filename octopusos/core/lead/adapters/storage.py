"""
Lead Storage Adapter

只读查询适配器，从 AgentOS 数据库（task_audits, tasks 等表）提取 Supervisor 决策和指标数据。

数据源：
- task_audits: 审计日志（包含 decision_snapshot）
- tasks: 任务表（状态、优先级等）

设计原则：
1. 只读查询，不修改数据
2. 使用索引优化（按 task_id/created_at 的 where + order）
3. 样例限制：所有返回的 task_ids/samples 最多 5 个
4. 边界条件：窗口为空时返回空列表/零值
"""

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any, Dict, List

from agentos.core.lead.models import ScanWindow

logger = logging.getLogger(__name__)

# Supervisor 审计事件类型常量
SUPERVISOR_ALLOWED = "SUPERVISOR_ALLOWED"
SUPERVISOR_PAUSED = "SUPERVISOR_PAUSED"
SUPERVISOR_BLOCKED = "SUPERVISOR_BLOCKED"
SUPERVISOR_RETRY_RECOMMENDED = "SUPERVISOR_RETRY_RECOMMENDED"
SUPERVISOR_DECISION = "SUPERVISOR_DECISION"


class LeadStorage:
    """
    Lead Storage Adapter

    从 task_audits 表查询 Supervisor 决策历史，提供给 Risk Miner 分析。
    """

    # 契约版本：定义 LeadStorage 返回的数据格式
    CONTRACT_VERSION = "1.0.0"

    # 契约说明：
    # v1.0.0: 初始版本
    # - 返回聚合数据：blocked_reasons, pause_block_churn, retry_then_fail,
    #   decision_lag, redline_ratio, high_risk_allow
    # - blocked_reasons 格式：[{code, count, task_ids}]
    # - high_risk_allow 格式：[{decision_id, task_id, risk_level}]

    def __init__(self, db_path: Path):
        """
        初始化 Storage Adapter

        Args:
            db_path: 数据库路径
        """
        self.db_path = db_path
        logger.info(f"LeadStorage initialized with db_path={db_path}")

    def get_blocked_reasons(self, window: ScanWindow) -> List[Dict[str, Any]]:
        """
        规则1: blocked_reason_spike

        返回窗口内所有 BLOCKED 决策的原因统计。

        查询逻辑：
        1. 从 task_audits 中查询 SUPERVISOR_BLOCKED 事件
        2. 从 payload JSON 中提取 findings[].code
        3. 统计每个 code 的出现次数

        Args:
            window: 扫描窗口

        Returns:
            格式: [
                {
                    "code": "ERROR_CODE_XYZ",
                    "count": 5,
                    "task_ids": ["task-1", "task-2", ...]  # 最多5个样例
                },
                ...
            ]
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            # 查询窗口内所有 BLOCKED 事件
            cursor.execute(
                """
                SELECT task_id, payload
                FROM task_audits
                WHERE event_type = ?
                  AND created_at >= ?
                  AND created_at <= ?
                ORDER BY created_at DESC
                """,
                (SUPERVISOR_BLOCKED, window.start_ts, window.end_ts)
            )

            rows = cursor.fetchall()

            # 统计每个 finding.code 的出现次数
            code_stats: Dict[str, Dict[str, Any]] = {}

            for row in rows:
                task_id = row["task_id"]
                payload_json = row["payload"]

                if not payload_json:
                    continue

                try:
                    payload = json.loads(payload_json)
                    findings = payload.get("findings", [])

                    for finding in findings:
                        code = finding.get("code", "")
                        if not code:
                            continue

                        if code not in code_stats:
                            code_stats[code] = {
                                "code": code,
                                "count": 0,
                                "task_ids": []
                            }

                        code_stats[code]["count"] += 1
                        if task_id not in code_stats[code]["task_ids"]:
                            code_stats[code]["task_ids"].append(task_id)

                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse payload JSON for task_id={task_id}")
                    continue

            # 限制样例数量（最多5个）
            result = []
            for stats in code_stats.values():
                stats["task_ids"] = stats["task_ids"][:5]
                result.append(stats)

            return result

        finally:
            conn.close()

    def get_pause_block_churn(self, window: ScanWindow) -> List[Dict[str, Any]]:
        """
        规则2: pause_block_churn

        返回窗口内 PAUSE 多次后最终 BLOCK 的任务。

        查询逻辑：
        1. 查询窗口内所有 PAUSE 和 BLOCK 事件
        2. 按 task_id 分组
        3. 统计每个 task 的 PAUSE 次数
        4. 检查最后一个事件是否为 BLOCK

        Args:
            window: 扫描窗口

        Returns:
            格式: [
                {
                    "task_id": "task-abc",
                    "pause_count": 3,
                    "final_status": "BLOCKED"
                },
                ...
            ]
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            # 查询窗口内所有 PAUSE 和 BLOCK 事件
            cursor.execute(
                """
                SELECT task_id, event_type, created_at
                FROM task_audits
                WHERE event_type IN (?, ?)
                  AND created_at >= ?
                  AND created_at <= ?
                ORDER BY task_id, created_at ASC
                """,
                (SUPERVISOR_PAUSED, SUPERVISOR_BLOCKED, window.start_ts, window.end_ts)
            )

            rows = cursor.fetchall()

            # 按 task_id 分组统计
            task_events: Dict[str, List[Dict[str, Any]]] = {}

            for row in rows:
                task_id = row["task_id"]
                event_type = row["event_type"]
                created_at = row["created_at"]

                if task_id not in task_events:
                    task_events[task_id] = []

                task_events[task_id].append({
                    "event_type": event_type,
                    "created_at": created_at
                })

            # 检测 PAUSE -> BLOCK 模式
            result = []
            for task_id, events in task_events.items():
                pause_count = sum(1 for e in events if e["event_type"] == SUPERVISOR_PAUSED)

                # 检查最后一个事件是否为 BLOCK
                if events and events[-1]["event_type"] == SUPERVISOR_BLOCKED:
                    result.append({
                        "task_id": task_id,
                        "pause_count": pause_count,
                        "final_status": "BLOCKED"
                    })

            return result

        finally:
            conn.close()

    def get_retry_then_fail(self, window: ScanWindow) -> List[Dict[str, Any]]:
        """
        规则3: retry_recommended_but_fails

        返回窗口内建议 RETRY 但仍失败的任务。

        查询逻辑：
        1. 查询 RETRY_RECOMMENDED 事件
        2. 查询这些任务后续是否有 BLOCKED 事件
        3. 提取失败原因（从 findings[].code）

        Args:
            window: 扫描窗口

        Returns:
            格式: [
                {
                    "error_code": "TIMEOUT",
                    "count": 3,
                    "task_ids": ["task-x", "task-y", ...]
                },
                ...
            ]
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            # 第一步：查询所有 RETRY 事件
            cursor.execute(
                """
                SELECT task_id, created_at
                FROM task_audits
                WHERE event_type = ?
                  AND created_at >= ?
                  AND created_at <= ?
                ORDER BY created_at ASC
                """,
                (SUPERVISOR_RETRY_RECOMMENDED, window.start_ts, window.end_ts)
            )

            retry_tasks = cursor.fetchall()

            # 第二步：对每个 RETRY 任务，检查后续是否有 BLOCK 事件
            error_stats: Dict[str, Dict[str, Any]] = {}

            for retry_row in retry_tasks:
                task_id = retry_row["task_id"]
                retry_ts = retry_row["created_at"]

                # 查询该任务在 RETRY 之后的 BLOCK 事件
                cursor.execute(
                    """
                    SELECT payload
                    FROM task_audits
                    WHERE task_id = ?
                      AND event_type = ?
                      AND created_at > ?
                      AND created_at <= ?
                    ORDER BY created_at ASC
                    LIMIT 1
                    """,
                    (task_id, SUPERVISOR_BLOCKED, retry_ts, window.end_ts)
                )

                block_row = cursor.fetchone()
                if not block_row:
                    continue

                payload_json = block_row["payload"]
                if not payload_json:
                    continue

                try:
                    payload = json.loads(payload_json)
                    findings = payload.get("findings", [])

                    for finding in findings:
                        code = finding.get("code", "UNKNOWN")

                        if code not in error_stats:
                            error_stats[code] = {
                                "error_code": code,
                                "count": 0,
                                "task_ids": []
                            }

                        error_stats[code]["count"] += 1
                        if task_id not in error_stats[code]["task_ids"]:
                            error_stats[code]["task_ids"].append(task_id)

                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse payload JSON for task_id={task_id}")
                    continue

            # 限制样例数量（最多5个）
            result = []
            for stats in error_stats.values():
                stats["task_ids"] = stats["task_ids"][:5]
                result.append(stats)

            return result

        finally:
            conn.close()

    def get_decision_lag(self, window: ScanWindow) -> Dict[str, Any]:
        """
        规则4: decision_lag_anomaly

        返回窗口内决策延迟统计。

        查询逻辑（v21+ 优化）：
        1. 优先使用冗余列（source_event_ts, supervisor_processed_at）进行查询
        2. 如果冗余列不存在或为 NULL，fallback 到 payload JSON 提取（向后兼容）
        3. 计算延迟：lag_ms = supervisor_processed_at - source_event_ts
        4. 计算 p95

        Args:
            window: 扫描窗口

        Returns:
            格式: {
                "p95_ms": 5500,
                "samples": [
                    {"decision_id": "dec-1", "lag_ms": 6000},
                    {"decision_id": "dec-2", "lag_ms": 5800},
                    ...  # 最多5个样例
                ]
            }
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            # 检查是否有冗余列（v21+）
            cursor.execute("PRAGMA table_info(task_audits)")
            columns = {row[1] for row in cursor.fetchall()}
            has_redundant_columns = 'source_event_ts' in columns and 'supervisor_processed_at' in columns

            lags = []

            if has_redundant_columns:
                # v21+ 路径：使用冗余列（性能优化）
                cursor.execute(
                    """
                    SELECT
                        decision_id,
                        source_event_ts,
                        supervisor_processed_at,
                        created_at,
                        payload
                    FROM task_audits
                    WHERE event_type LIKE 'SUPERVISOR_%'
                      AND created_at >= ?
                      AND created_at <= ?
                    ORDER BY created_at DESC
                    """,
                    (window.start_ts, window.end_ts)
                )

                rows = cursor.fetchall()

                for row in rows:
                    decision_id = row["decision_id"]
                    source_event_ts_str = row["source_event_ts"]
                    supervisor_processed_at_str = row["supervisor_processed_at"]
                    created_at = row["created_at"]
                    payload_json = row["payload"]

                    # 优先使用冗余列
                    if source_event_ts_str and supervisor_processed_at_str:
                        try:
                            from datetime import datetime
                            source_ts = datetime.fromisoformat(source_event_ts_str.replace('Z', '+00:00'))
                            processed_ts = datetime.fromisoformat(supervisor_processed_at_str.replace('Z', '+00:00'))
                            lag_ms = int((processed_ts - source_ts).total_seconds() * 1000)

                            if lag_ms >= 0:  # 过滤负值（时钟不同步）
                                lags.append({
                                    "decision_id": decision_id or "unknown",
                                    "lag_ms": lag_ms
                                })
                                continue
                        except (ValueError, AttributeError) as e:
                            logger.warning(f"Failed to parse timestamps from columns for decision {decision_id}: {e}")
                            # Fallthrough to payload extraction

                    # Fallback: 从 payload JSON 提取（向后兼容）
                    if payload_json:
                        try:
                            payload = json.loads(payload_json)
                            decision_id_fb = decision_id or payload.get("decision_id", "unknown")
                            source_ts_str = payload.get("source_event_ts")
                            decision_ts_str = payload.get("supervisor_processed_at") or payload.get("timestamp")

                            if source_ts_str and decision_ts_str:
                                from datetime import datetime
                                source_ts = datetime.fromisoformat(source_ts_str.replace('Z', '+00:00'))
                                decision_ts = datetime.fromisoformat(decision_ts_str.replace('Z', '+00:00'))
                                lag_ms = int((decision_ts - source_ts).total_seconds() * 1000)

                                if lag_ms >= 0:
                                    lags.append({
                                        "decision_id": decision_id_fb,
                                        "lag_ms": lag_ms
                                    })
                        except (json.JSONDecodeError, ValueError, TypeError) as e:
                            logger.warning(f"Failed to parse lag data from payload: {e}")
                            continue

            else:
                # v20 及以前路径：从 payload JSON 提取（向后兼容）
                cursor.execute(
                    """
                    SELECT decision_id, payload, created_at
                    FROM task_audits
                    WHERE event_type LIKE 'SUPERVISOR_%'
                      AND created_at >= ?
                      AND created_at <= ?
                    ORDER BY created_at DESC
                    """,
                    (window.start_ts, window.end_ts)
                )

                rows = cursor.fetchall()

                for row in rows:
                    decision_id = row["decision_id"]
                    payload_json = row["payload"]
                    created_at = row["created_at"]

                    if not payload_json:
                        continue

                    try:
                        payload = json.loads(payload_json)
                        decision_id = decision_id or payload.get("decision_id", "unknown")

                        # 尝试从 payload 提取时间戳
                        source_ts_str = payload.get("source_event_ts")
                        decision_ts_str = payload.get("supervisor_processed_at") or payload.get("timestamp")

                        if not source_ts_str or not decision_ts_str:
                            continue

                        from datetime import datetime
                        source_ts = datetime.fromisoformat(source_ts_str.replace('Z', '+00:00'))
                        decision_ts = datetime.fromisoformat(decision_ts_str.replace('Z', '+00:00'))
                        lag_ms = int((decision_ts - source_ts).total_seconds() * 1000)

                        if lag_ms >= 0:
                            lags.append({
                                "decision_id": decision_id,
                                "lag_ms": lag_ms
                            })

                    except (json.JSONDecodeError, ValueError, TypeError) as e:
                        logger.warning(f"Failed to parse lag data from payload: {e}")
                        continue

            if not lags:
                return {
                    "p95_ms": 0,
                    "samples": []
                }

            # 计算 p95
            sorted_lags = sorted(lags, key=lambda x: x["lag_ms"], reverse=True)
            p95_index = int(len(sorted_lags) * 0.05)  # top 5%
            p95_ms = sorted_lags[p95_index]["lag_ms"] if p95_index < len(sorted_lags) else sorted_lags[0]["lag_ms"]

            # 取样例（最多5个高延迟样本）
            samples = sorted_lags[:5]

            return {
                "p95_ms": p95_ms,
                "samples": samples
            }

        finally:
            conn.close()

    def get_redline_ratio(self, window: ScanWindow) -> Dict[str, Any]:
        """
        规则5: redline_ratio_increase

        返回窗口内和前一窗口的 REDLINE 占比。

        查询逻辑：
        1. 查询当前窗口内所有决策事件
        2. 统计 findings 中 kind="REDLINE" 的数量
        3. 查询前一窗口的占比（用于比较）

        Args:
            window: 扫描窗口

        Returns:
            格式: {
                "current_ratio": 0.25,  # 当前窗口 25%
                "previous_ratio": 0.10,  # 前一窗口 10%
                "current_count": 25,
                "total_count": 100
            }
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            # 计算当前窗口统计
            current_stats = self._calculate_redline_ratio(cursor, window.start_ts, window.end_ts)

            # 计算前一窗口统计（窗口长度相同）
            from datetime import datetime, timedelta
            start_dt = datetime.fromisoformat(window.start_ts.replace('Z', '+00:00'))
            end_dt = datetime.fromisoformat(window.end_ts.replace('Z', '+00:00'))
            duration = end_dt - start_dt

            prev_end_ts = start_dt.isoformat()
            prev_start_ts = (start_dt - duration).isoformat()

            previous_stats = self._calculate_redline_ratio(cursor, prev_start_ts, prev_end_ts)

            return {
                "current_ratio": current_stats["ratio"],
                "previous_ratio": previous_stats["ratio"],
                "current_count": current_stats["redline_count"],
                "total_count": current_stats["total_count"]
            }

        finally:
            conn.close()

    def _calculate_redline_ratio(self, cursor: sqlite3.Cursor, start_ts: str, end_ts: str) -> Dict[str, Any]:
        """
        计算指定窗口内的 REDLINE 占比

        Args:
            cursor: 数据库游标
            start_ts: 开始时间
            end_ts: 结束时间

        Returns:
            {
                "redline_count": int,
                "total_count": int,
                "ratio": float
            }
        """
        # 查询窗口内所有 Supervisor 决策事件
        cursor.execute(
            """
            SELECT payload
            FROM task_audits
            WHERE event_type LIKE 'SUPERVISOR_%'
              AND created_at >= ?
              AND created_at <= ?
            """,
            (start_ts, end_ts)
        )

        rows = cursor.fetchall()

        redline_count = 0
        total_count = 0

        for row in rows:
            payload_json = row["payload"]
            if not payload_json:
                continue

            try:
                payload = json.loads(payload_json)
                findings = payload.get("findings", [])

                for finding in findings:
                    total_count += 1
                    if finding.get("kind") == "REDLINE":
                        redline_count += 1

            except json.JSONDecodeError:
                continue

        ratio = redline_count / total_count if total_count > 0 else 0.0

        return {
            "redline_count": redline_count,
            "total_count": total_count,
            "ratio": ratio
        }

    def get_high_risk_allow(self, window: ScanWindow) -> List[Dict[str, Any]]:
        """
        规则6: high_risk_allow

        返回窗口内高风险但仍被 ALLOW 的决策。

        查询逻辑：
        1. 查询 SUPERVISOR_ALLOWED 事件
        2. 从 payload JSON 提取 decision_id 和 findings
        3. 检查是否有 severity="HIGH" 或 "CRITICAL"
        4. 返回这些决策的详情

        Args:
            window: 扫描窗口

        Returns:
            格式: [
                {
                    "decision_id": "dec-xyz",
                    "task_id": "task-123",
                    "risk_level": "HIGH"
                },
                ...
            ]
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            # 查询窗口内所有 ALLOW 事件
            cursor.execute(
                """
                SELECT task_id, payload
                FROM task_audits
                WHERE event_type = ?
                  AND created_at >= ?
                  AND created_at <= ?
                ORDER BY created_at DESC
                """,
                (SUPERVISOR_ALLOWED, window.start_ts, window.end_ts)
            )

            rows = cursor.fetchall()

            result = []

            for row in rows:
                task_id = row["task_id"]
                payload_json = row["payload"]

                if not payload_json:
                    continue

                try:
                    payload = json.loads(payload_json)
                    decision_id = payload.get("decision_id", "unknown")
                    findings = payload.get("findings", [])

                    # 检查是否有高风险 finding
                    for finding in findings:
                        severity = finding.get("severity", "").upper()
                        if severity in ["HIGH", "CRITICAL"]:
                            result.append({
                                "decision_id": decision_id,
                                "task_id": task_id,
                                "risk_level": severity
                            })
                            break  # 每个决策只记录一次

                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse payload JSON for task_id={task_id}")
                    continue

            # 限制样例数量（最多5个）
            return result[:5]

        finally:
            conn.close()
