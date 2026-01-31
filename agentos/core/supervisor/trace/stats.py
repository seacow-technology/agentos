"""
Stats Calculator - 治理统计和指标计算

提供各种统计查询功能：
1. 决策类型分布（ALLOW / PAUSE / BLOCK / RETRY）
2. 被阻塞任务 Top N
3. 决策延迟分析（p50 / p95）

设计原则：
1. 性能优化：使用索引友好的查询
2. 增量计算：支持时间范围过滤
3. 类型安全：返回明确的数据结构
"""

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from agentos.core.time import utc_now



class StatsCalculator:
    """
    治理统计计算器

    提供各种统计指标的计算功能。
    """

    def __init__(self, conn: sqlite3.Connection):
        """
        Args:
            conn: SQLite 数据库连接
        """
        self.conn = conn

    def get_decision_type_stats(
        self,
        hours: int = 24
    ) -> dict[str, int]:
        """
        获取决策类型分布统计

        Args:
            hours: 统计最近 N 小时的数据（默认 24 小时）

        Returns:
            决策类型到数量的映射，如：
            {
                "ALLOW": 150,
                "PAUSE": 10,
                "BLOCK": 5,
                "RETRY": 3
            }
        """
        # 计算时间范围
        cutoff_time = utc_now() - timedelta(hours=hours)
        cutoff_str = cutoff_time.isoformat()

        cursor = self.conn.execute(
            """
            SELECT event_type, COUNT(*) as count
            FROM task_audits
            WHERE event_type LIKE 'SUPERVISOR_%'
              AND created_at >= ?
            GROUP BY event_type
            """,
            (cutoff_str,)
        )

        stats = {}
        for row in cursor:
            # 提取决策类型：SUPERVISOR_ALLOWED -> ALLOW
            event_type = row["event_type"]
            if event_type.startswith("SUPERVISOR_"):
                decision_type = event_type.replace("SUPERVISOR_", "")
                stats[decision_type] = row["count"]

        return stats

    def get_blocked_tasks_topn(
        self,
        limit: int = 10
    ) -> list[dict[str, Any]]:
        """
        获取被阻塞任务的 Top N（按阻塞次数排序）

        Args:
            limit: 返回前 N 个任务

        Returns:
            任务列表，每个任务包含：
            - task_id: 任务 ID
            - block_count: 阻塞次数
            - last_blocked_at: 最后一次阻塞时间
            - reason_code: 最后一次阻塞原因代码
        """
        cursor = self.conn.execute(
            """
            SELECT
                task_id,
                COUNT(*) as block_count,
                MAX(created_at) as last_blocked_at
            FROM task_audits
            WHERE event_type = 'SUPERVISOR_BLOCKED'
            GROUP BY task_id
            ORDER BY block_count DESC, last_blocked_at DESC
            LIMIT ?
            """,
            (limit,)
        )

        results = []
        for row in cursor:
            task_id = row["task_id"]

            # 获取最后一次阻塞的原因代码
            reason_code = self._get_last_blocked_reason(task_id)

            results.append({
                "task_id": task_id,
                "block_count": row["block_count"],
                "last_blocked_at": row["last_blocked_at"],
                "reason_code": reason_code,
            })

        return results

    def get_decision_lag_percentiles(
        self,
        hours: int = 24
    ) -> dict[str, Optional[float]]:
        """
        计算决策延迟的百分位数（p50, p95）

        决策延迟 = supervisor_processed_at - source_event_ts

        v21+ 优化：区分数据来源（冗余列 vs payload JSON）

        Args:
            hours: 统计最近 N 小时的数据

        Returns:
            百分位数字典，如：
            {
                "p50": 0.123,  # 中位数，单位：秒
                "p95": 0.456,  # 95 分位数
                "count": 100,  # 样本数量
                "samples": [   # 样例数据（p95 附近的高延迟样本）
                    {
                        "decision_id": "dec-1",
                        "lag_ms": 5500,
                        "source": "columns"  # 数据来源：columns（冗余列）或 payload（JSON）
                    },
                    ...
                ],
                "query_method": "columns",  # 查询方法：columns 或 payload_fallback
                "redundant_column_coverage": 0.95  # 冗余列覆盖率（0.0-1.0）
            }
        """
        # 计算时间范围
        cutoff_time = utc_now() - timedelta(hours=hours)
        cutoff_str = cutoff_time.isoformat()

        # 检查是否有冗余列（v21+）
        cursor = self.conn.execute("PRAGMA table_info(task_audits)")
        columns = {row[1] for row in cursor.fetchall()}
        has_redundant_columns = 'source_event_ts' in columns and 'supervisor_processed_at' in columns

        lags_data = []  # 存储 (lag_seconds, decision_id, source_type)

        if has_redundant_columns:
            # v21+ 路径：查询冗余列和 payload（行级检测）
            cursor = self.conn.execute(
                """
                SELECT
                    decision_id,
                    source_event_ts,
                    supervisor_processed_at,
                    payload,
                    created_at
                FROM task_audits
                WHERE event_type LIKE 'SUPERVISOR_%'
                  AND created_at >= ?
                ORDER BY supervisor_processed_at
                """,
                (cutoff_str,)
            )

            for row in cursor:
                decision_id = row["decision_id"] or "unknown"
                source_ts_col = row["source_event_ts"]
                processed_at_col = row["supervisor_processed_at"]
                payload_json = row["payload"]

                # 行级检测：优先使用冗余列
                if source_ts_col and processed_at_col:
                    try:
                        source_ts = datetime.fromisoformat(source_ts_col.replace("Z", "+00:00"))
                        processed_ts = datetime.fromisoformat(processed_at_col.replace("Z", "+00:00"))
                        lag_seconds = (processed_ts - source_ts).total_seconds()
                        if lag_seconds >= 0:
                            lags_data.append((lag_seconds, decision_id, "columns"))
                            continue
                    except (ValueError, AttributeError):
                        pass  # Fallthrough to payload extraction

                # Fallback: 从 payload JSON 提取
                if payload_json:
                    try:
                        payload = json.loads(payload_json)
                        source_ts_str = payload.get("source_event_ts")
                        processed_at_str = payload.get("supervisor_processed_at") or payload.get("timestamp")

                        if source_ts_str and processed_at_str:
                            source_ts = datetime.fromisoformat(source_ts_str.replace("Z", "+00:00"))
                            processed_ts = datetime.fromisoformat(processed_at_str.replace("Z", "+00:00"))
                            lag_seconds = (processed_ts - source_ts).total_seconds()
                            if lag_seconds >= 0:
                                lags_data.append((lag_seconds, decision_id, "payload"))
                    except (json.JSONDecodeError, ValueError, TypeError, AttributeError):
                        continue
        else:
            # v20 及以前路径：从 payload JSON 提取
            cursor = self.conn.execute(
                """
                SELECT decision_id, payload, created_at
                FROM task_audits
                WHERE event_type LIKE 'SUPERVISOR_%'
                  AND created_at >= ?
                ORDER BY created_at
                """,
                (cutoff_str,)
            )

            for row in cursor:
                decision_id = row["decision_id"] or "unknown"
                payload_json = row["payload"]

                if not payload_json:
                    continue

                try:
                    payload = json.loads(payload_json)
                    source_ts_str = payload.get("source_event_ts")
                    processed_at_str = payload.get("supervisor_processed_at") or payload.get("timestamp")

                    if source_ts_str and processed_at_str:
                        source_ts = datetime.fromisoformat(source_ts_str.replace("Z", "+00:00"))
                        processed_ts = datetime.fromisoformat(processed_at_str.replace("Z", "+00:00"))
                        lag_seconds = (processed_ts - source_ts).total_seconds()
                        if lag_seconds >= 0:
                            lags_data.append((lag_seconds, decision_id, "payload"))
                except (json.JSONDecodeError, ValueError, TypeError, AttributeError):
                    continue

        if not lags_data:
            return {
                "p50": None,
                "p95": None,
                "count": 0,
                "samples": [],
                "query_method": "columns" if has_redundant_columns else "payload_fallback",
                "redundant_column_coverage": 0.0
            }

        # 排序并计算百分位数
        lags_data.sort(key=lambda x: x[0])  # 按 lag_seconds 排序
        count = len(lags_data)

        p50_idx = int(count * 0.5)
        p95_idx = int(count * 0.95)

        p50 = lags_data[p50_idx][0] if p50_idx < count else lags_data[-1][0]
        p95 = lags_data[p95_idx][0] if p95_idx < count else lags_data[-1][0]

        # 取样例：p95 附近的高延迟样本（最多 5 个）
        samples = []
        for i in range(max(0, count - 5), count):
            lag_seconds, decision_id, source_type = lags_data[i]
            samples.append({
                "decision_id": decision_id,
                "lag_ms": int(lag_seconds * 1000),
                "source": source_type
            })

        # 计算冗余列覆盖率
        columns_count = sum(1 for _, _, src in lags_data if src == "columns")
        coverage = columns_count / count if count > 0 else 0.0

        return {
            "p50": p50,
            "p95": p95,
            "count": count,
            "samples": samples,
            "query_method": "columns" if has_redundant_columns else "payload_fallback",
            "redundant_column_coverage": coverage
        }

    def get_overall_stats(self) -> dict[str, Any]:
        """
        获取整体治理统计

        Returns:
            综合统计字典，包含：
            - total_decisions: 总决策数
            - total_tasks: 涉及的任务数
            - active_blocks: 当前被阻塞的任务数
            - decision_types: 决策类型分布（24h）
            - lag_percentiles: 延迟百分位数（24h）
        """
        # 1. 总决策数
        cursor = self.conn.execute(
            """
            SELECT COUNT(*) as count
            FROM task_audits
            WHERE event_type LIKE 'SUPERVISOR_%'
            """
        )
        total_decisions = cursor.fetchone()["count"]

        # 2. 涉及的任务数
        cursor = self.conn.execute(
            """
            SELECT COUNT(DISTINCT task_id) as count
            FROM task_audits
            WHERE event_type LIKE 'SUPERVISOR_%'
            """
        )
        total_tasks = cursor.fetchone()["count"]

        # 3. 当前被阻塞的任务数
        cursor = self.conn.execute(
            """
            SELECT COUNT(*) as count
            FROM tasks
            WHERE status = 'BLOCKED'
            """
        )
        active_blocks = cursor.fetchone()["count"]

        # 4. 决策类型分布（24h）
        decision_types = self.get_decision_type_stats(hours=24)

        # 5. 延迟百分位数（24h）
        lag_percentiles = self.get_decision_lag_percentiles(hours=24)

        return {
            "total_decisions": total_decisions,
            "total_tasks": total_tasks,
            "active_blocks": active_blocks,
            "decision_types": decision_types,
            "lag_percentiles": lag_percentiles,
        }

    def _get_last_blocked_reason(self, task_id: str) -> Optional[str]:
        """
        获取任务最后一次被阻塞的原因代码

        Args:
            task_id: 任务 ID

        Returns:
            原因代码，如果不存在返回 None
        """
        cursor = self.conn.execute(
            """
            SELECT payload
            FROM task_audits
            WHERE task_id = ?
              AND event_type = 'SUPERVISOR_BLOCKED'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (task_id,)
        )
        row = cursor.fetchone()
        if row is None:
            return None

        try:
            payload = json.loads(row["payload"]) if row["payload"] else {}
            decision_snapshot = payload.get("decision_snapshot", {})
            findings = decision_snapshot.get("findings", [])
            if findings:
                return findings[0].get("code")
        except (json.JSONDecodeError, KeyError, IndexError):
            pass

        return None
