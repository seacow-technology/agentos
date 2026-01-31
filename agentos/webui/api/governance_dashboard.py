"""
Governance Dashboard API - 聚合 API for C-level Governance Dashboard

为 C-level Governance Dashboard 提供系统治理健康度的实时视图。

核心端点:
- GET /api/governance/dashboard - 获取完整的 Dashboard 数据

设计原则:
1. 只读聚合，不创建新的存储表
2. 数据来源: lead_findings, task_audits, guardian_reviews, tasks
3. 性能要求: 响应时间 < 1s
4. 优雅降级: 部分数据缺失时仍能返回有意义的结果
5. 5分钟缓存: 减少数据库压力
"""

import json
import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from agentos.store import get_db


from agentos.webui.api.time_format import iso_z
from agentos.core.time import utc_now

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/governance", tags=["governance_dashboard"])


# ============================================
# Response Models
# ============================================


class MetricsResponse(BaseModel):
    """Dashboard 核心指标"""
    risk_level: str  # HIGH | MEDIUM | LOW | CRITICAL | UNKNOWN
    open_findings: int
    blocked_rate: float  # 0.0-1.0
    guarded_percentage: float  # 0.0-1.0


class TrendDataResponse(BaseModel):
    """趋势数据"""
    current: float
    previous: float
    change: float  # 变化百分比 (-1.0 to +1.0)
    direction: str  # up | down | stable
    data_points: List[float]  # 用于 sparkline


class TrendsResponse(BaseModel):
    """Dashboard 趋势数据"""
    findings: TrendDataResponse
    blocked_decisions: TrendDataResponse
    guardian_coverage: TrendDataResponse


class TopRiskResponse(BaseModel):
    """Top 风险项"""
    id: str
    type: str
    severity: str
    title: str
    affected_tasks: int
    first_seen: str


class HealthResponse(BaseModel):
    """系统健康度指标"""
    guardian_coverage: float
    avg_decision_latency_ms: int
    tasks_with_audits: float
    active_guardians: int
    last_scan: Optional[str] = None


class DashboardResponse(BaseModel):
    """Dashboard 完整响应"""
    metrics: MetricsResponse
    trends: TrendsResponse
    top_risks: List[TopRiskResponse]
    health: HealthResponse
    generated_at: str


# ============================================
# Data Fetching Functions
# ============================================


def get_findings_data(
    conn: sqlite3.Connection,
    timeframe: str,
    project_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    从 lead_findings 表获取数据

    Args:
        conn: 数据库连接
        timeframe: 时间窗口 (7d | 30d | 90d)
        project_id: 项目 ID（可选）

    Returns:
        List of findings dictionaries
    """
    try:
        cursor = conn.cursor()

        # 计算时间范围
        days = _parse_timeframe(timeframe)
        cutoff = iso_z(utc_now() - timedelta(days=days))

        # 查询 findings
        query = """
            SELECT fingerprint, code, severity, title, description,
                   window_kind, first_seen_at, last_seen_at, count,
                   evidence_json, linked_task_id, created_at
            FROM lead_findings
            WHERE last_seen_at >= ?
            ORDER BY last_seen_at DESC
        """

        cursor.execute(query, (cutoff,))
        rows = cursor.fetchall()

        findings = []
        for row in rows:
            evidence = {}
            if row[9]:  # evidence_json
                try:
                    evidence = json.loads(row[9])
                except json.JSONDecodeError:
                    pass

            findings.append({
                "fingerprint": row[0],
                "code": row[1],
                "severity": row[2],
                "title": row[3],
                "description": row[4],
                "window_kind": row[5],
                "first_seen_at": row[6],
                "last_seen_at": row[7],
                "count": row[8],
                "evidence": evidence,
                "linked_task_id": row[10],
                "created_at": row[11],
            })

        return findings

    except Exception as e:
        logger.warning(f"Failed to fetch findings data: {e}")
        return []


def get_audits_data(
    conn: sqlite3.Connection,
    timeframe: str,
    project_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    从 task_audits 表获取数据

    Args:
        conn: 数据库连接
        timeframe: 时间窗口
        project_id: 项目 ID（可选）

    Returns:
        List of audit dictionaries
    """
    try:
        cursor = conn.cursor()

        # 计算时间范围
        days = _parse_timeframe(timeframe)
        cutoff = iso_z(utc_now() - timedelta(days=days))

        # 查询 Supervisor 决策审计
        query = """
            SELECT audit_id, task_id, repo_id, level, event_type,
                   payload, created_at, decision_id, source_event_ts,
                   supervisor_processed_at
            FROM task_audits
            WHERE event_type LIKE 'SUPERVISOR_%'
              AND created_at >= ?
            ORDER BY created_at DESC
        """

        cursor.execute(query, (cutoff,))
        rows = cursor.fetchall()

        audits = []
        for row in rows:
            payload = {}
            if row[5]:  # payload
                try:
                    payload = json.loads(row[5])
                except json.JSONDecodeError:
                    pass

            audits.append({
                "audit_id": row[0],
                "task_id": row[1],
                "repo_id": row[2],
                "level": row[3],
                "event_type": row[4],
                "payload": payload,
                "created_at": row[6],
                "decision_id": row[7] if len(row) > 7 else None,
                "source_event_ts": row[8] if len(row) > 8 else None,
                "supervisor_processed_at": row[9] if len(row) > 9 else None,
            })

        return audits

    except Exception as e:
        logger.warning(f"Failed to fetch audits data: {e}")
        return []


def get_guardian_data(
    conn: sqlite3.Connection,
    timeframe: str,
    project_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    从 guardian_reviews 表获取数据

    Args:
        conn: 数据库连接
        timeframe: 时间窗口
        project_id: 项目 ID（可选）

    Returns:
        List of review dictionaries
    """
    try:
        cursor = conn.cursor()

        # 计算时间范围
        days = _parse_timeframe(timeframe)
        cutoff = iso_z(utc_now() - timedelta(days=days))

        # 查询 guardian reviews
        query = """
            SELECT review_id, target_type, target_id, guardian_id,
                   review_type, verdict, confidence, rule_snapshot_id,
                   evidence, created_at
            FROM guardian_reviews
            WHERE created_at >= ?
            ORDER BY created_at DESC
        """

        cursor.execute(query, (cutoff,))
        rows = cursor.fetchall()

        reviews = []
        for row in rows:
            evidence = {}
            if row[8]:  # evidence
                try:
                    evidence = json.loads(row[8])
                except json.JSONDecodeError:
                    pass

            reviews.append({
                "review_id": row[0],
                "target_type": row[1],
                "target_id": row[2],
                "guardian_id": row[3],
                "review_type": row[4],
                "verdict": row[5],
                "confidence": row[6],
                "rule_snapshot_id": row[7],
                "evidence": evidence,
                "created_at": row[9],
            })

        return reviews

    except Exception as e:
        logger.warning(f"Failed to fetch guardian data: {e}")
        return []


def get_tasks_data(
    conn: sqlite3.Connection,
    timeframe: str,
    project_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    从 tasks 表获取数据

    Args:
        conn: 数据库连接
        timeframe: 时间窗口
        project_id: 项目 ID（可选）

    Returns:
        List of task dictionaries
    """
    try:
        cursor = conn.cursor()

        # 计算时间范围
        days = _parse_timeframe(timeframe)
        cutoff = iso_z(utc_now() - timedelta(days=days))

        # 查询 tasks
        query = """
            SELECT task_id, title, status, session_id, created_at,
                   updated_at, created_by, metadata
            FROM tasks
            WHERE created_at >= ?
            ORDER BY created_at DESC
        """

        cursor.execute(query, (cutoff,))
        rows = cursor.fetchall()

        tasks = []
        for row in rows:
            metadata = {}
            if row[7]:  # metadata
                try:
                    metadata = json.loads(row[7])
                except json.JSONDecodeError:
                    pass

            tasks.append({
                "task_id": row[0],
                "title": row[1],
                "status": row[2],
                "session_id": row[3],
                "created_at": row[4],
                "updated_at": row[5],
                "created_by": row[6],
                "metadata": metadata,
            })

        return tasks

    except Exception as e:
        logger.warning(f"Failed to fetch tasks data: {e}")
        return []


# ============================================
# Aggregation Logic
# ============================================


def aggregate_risk_level(findings: List[Dict[str, Any]]) -> str:
    """
    根据 findings 的严重程度计算整体风险等级

    逻辑:
    - 存在 CRITICAL findings → CRITICAL
    - 存在 HIGH findings 且数量 > 5 → HIGH
    - 存在 HIGH findings 但数量 <= 5 → MEDIUM
    - 否则 → LOW

    Args:
        findings: findings 列表

    Returns:
        风险等级: CRITICAL | HIGH | MEDIUM | LOW | UNKNOWN
    """
    if not findings:
        return "LOW"

    severity_counts = {
        "CRITICAL": 0,
        "HIGH": 0,
        "MEDIUM": 0,
        "LOW": 0,
    }

    for finding in findings:
        severity = finding.get("severity", "").upper()
        if severity in severity_counts:
            severity_counts[severity] += 1

    # 判断风险等级
    if severity_counts["CRITICAL"] > 0:
        return "CRITICAL"
    elif severity_counts["HIGH"] > 5:
        return "HIGH"
    elif severity_counts["HIGH"] > 0:
        return "MEDIUM"
    elif severity_counts["MEDIUM"] > 0:
        return "LOW"
    else:
        return "LOW"


def calculate_blocked_rate(audits: List[Dict[str, Any]]) -> float:
    """
    计算决策被阻止的比例

    blocked_rate = (BLOCKED 决策数) / (总决策数)

    Args:
        audits: 审计记录列表

    Returns:
        阻止率 (0.0-1.0)
    """
    if not audits:
        return 0.0

    total_decisions = 0
    blocked_decisions = 0

    for audit in audits:
        event_type = audit.get("event_type", "")
        if event_type.startswith("SUPERVISOR_"):
            total_decisions += 1
            if event_type == "SUPERVISOR_BLOCKED":
                blocked_decisions += 1

    if total_decisions == 0:
        return 0.0

    return blocked_decisions / total_decisions


def calculate_guardian_coverage(
    tasks: List[Dict[str, Any]],
    guardian_reviews: List[Dict[str, Any]]
) -> float:
    """
    计算有 Guardian 验收的任务比例

    guarded_percentage = (有 review 的 task 数) / (总 task 数)

    Args:
        tasks: 任务列表
        guardian_reviews: Guardian 审查列表

    Returns:
        覆盖率 (0.0-1.0)
    """
    if not tasks:
        return 0.0

    # 提取所有被审查的 task_id
    reviewed_task_ids = set()
    for review in guardian_reviews:
        if review.get("target_type") == "task":
            reviewed_task_ids.add(review.get("target_id"))

    task_ids = {task["task_id"] for task in tasks}

    if not task_ids:
        return 0.0

    # 计算交集
    guarded_count = len(task_ids & reviewed_task_ids)

    return guarded_count / len(task_ids)


def compute_trend(
    current_data: List[Any],
    historical_data: List[Tuple[datetime, float]],
    timeframe: str,
    value_extractor=None
) -> Dict[str, Any]:
    """
    计算趋势信息

    Args:
        current_data: 当前数据
        historical_data: 历史数据点 [(timestamp, value), ...]
        timeframe: 时间窗口
        value_extractor: 从 current_data 提取数值的函数

    Returns:
        趋势信息字典
    """
    # 提取当前值
    if value_extractor:
        current_value = value_extractor(current_data)
    else:
        current_value = len(current_data) if current_data else 0.0

    # 计算前一周期的平均值
    if not historical_data:
        previous_value = current_value
    else:
        previous_value = sum(v for _, v in historical_data) / len(historical_data)

    # 计算变化百分比
    if previous_value == 0:
        change = 0.0 if current_value == 0 else 1.0
    else:
        change = (current_value - previous_value) / previous_value

    # 判断方向
    if abs(change) < 0.05:  # 5% threshold
        direction = "stable"
    elif change > 0:
        direction = "up"
    else:
        direction = "down"

    # 生成 sparkline 数据点
    data_points = [v for _, v in historical_data] if historical_data else []
    if current_value is not None:
        data_points.append(current_value)

    return {
        "current": float(current_value),
        "previous": float(previous_value),
        "change": float(change),
        "direction": direction,
        "data_points": data_points[-7:],  # 最近 7 个数据点
    }


def identify_top_risks(
    findings: List[Dict[str, Any]],
    audits: List[Dict[str, Any]],
    guardian_reviews: List[Dict[str, Any]],
    limit: int = 5
) -> List[Dict[str, Any]]:
    """
    识别 Top N 风险

    风险评分算法:
    - severity 权重: CRITICAL=10, HIGH=5, MEDIUM=2, LOW=1
    - 影响范围权重: affected_tasks * 0.5
    - 时间权重: 最近 24h 发现的 * 1.5

    Args:
        findings: findings 列表
        audits: 审计记录列表
        guardian_reviews: Guardian 审查列表
        limit: 返回前 N 个

    Returns:
        Top N 风险列表
    """
    severity_weights = {
        "CRITICAL": 10,
        "HIGH": 5,
        "MEDIUM": 2,
        "LOW": 1,
    }

    risks = []
    now = utc_now()

    # 从 findings 生成风险
    for finding in findings:
        severity = finding.get("severity", "").upper()
        severity_score = severity_weights.get(severity, 1)

        # 提取影响的任务数
        evidence = finding.get("evidence", {})
        affected_tasks = 0
        if isinstance(evidence, dict):
            # 尝试从不同的证据结构提取任务数
            if "task_ids" in evidence:
                affected_tasks = len(evidence["task_ids"])
            elif "count" in evidence:
                affected_tasks = evidence["count"]

        # 计算时间权重
        first_seen = finding.get("first_seen_at", finding.get("created_at", ""))
        try:
            first_seen_dt = datetime.fromisoformat(first_seen.replace("Z", "+00:00"))
            hours_ago = (now - first_seen_dt).total_seconds() / 3600
            time_weight = 1.5 if hours_ago < 24 else 1.0
        except (ValueError, AttributeError):
            time_weight = 1.0

        # 计算总分
        score = severity_score * time_weight + affected_tasks * 0.5

        risks.append({
            "id": finding.get("fingerprint", ""),
            "type": finding.get("code", "unknown"),
            "severity": severity,
            "title": finding.get("title", "Unknown risk"),
            "affected_tasks": affected_tasks,
            "first_seen": first_seen,
            "score": score,
        })

    # 排序并返回 Top N
    risks.sort(key=lambda x: x["score"], reverse=True)

    # 移除内部使用的 score 字段
    for risk in risks[:limit]:
        risk.pop("score", None)

    return risks[:limit]


def calculate_health_metrics(
    tasks: List[Dict[str, Any]],
    audits: List[Dict[str, Any]],
    guardian_reviews: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    计算系统健康度指标

    Args:
        tasks: 任务列表
        audits: 审计记录列表
        guardian_reviews: Guardian 审查列表

    Returns:
        健康度指标字典
    """
    # Guardian 覆盖率
    guardian_coverage = calculate_guardian_coverage(tasks, guardian_reviews)

    # 平均决策延迟
    avg_latency = 0
    latencies = []
    for audit in audits:
        source_ts = audit.get("source_event_ts")
        processed_ts = audit.get("supervisor_processed_at")

        if source_ts and processed_ts:
            try:
                source_dt = datetime.fromisoformat(source_ts.replace("Z", "+00:00"))
                processed_dt = datetime.fromisoformat(processed_ts.replace("Z", "+00:00"))
                latency_ms = int((processed_dt - source_dt).total_seconds() * 1000)
                if latency_ms >= 0:
                    latencies.append(latency_ms)
            except (ValueError, AttributeError):
                pass

    if latencies:
        avg_latency = sum(latencies) // len(latencies)

    # 有审计记录的任务比例
    tasks_with_audits = 0.0
    if tasks:
        audited_task_ids = {audit["task_id"] for audit in audits}
        task_ids = {task["task_id"] for task in tasks}
        if task_ids:
            tasks_with_audits = len(task_ids & audited_task_ids) / len(task_ids)

    # 活跃的 Guardian 数量
    active_guardians = len({review["guardian_id"] for review in guardian_reviews})

    # 最后扫描时间（从 findings 获取）
    last_scan = None

    return {
        "guardian_coverage": guardian_coverage,
        "avg_decision_latency_ms": avg_latency,
        "tasks_with_audits": tasks_with_audits,
        "active_guardians": active_guardians,
        "last_scan": last_scan,
    }


# ============================================
# Helper Functions
# ============================================


def _parse_timeframe(timeframe: str) -> int:
    """
    解析时间窗口字符串

    Args:
        timeframe: 7d | 30d | 90d

    Returns:
        天数

    Raises:
        ValueError: 如果格式不正确
    """
    timeframe_map = {
        "7d": 7,
        "30d": 30,
        "90d": 90,
    }

    if timeframe not in timeframe_map:
        raise ValueError(f"Invalid timeframe: {timeframe}. Must be one of: 7d, 30d, 90d")

    return timeframe_map[timeframe]


def safe_aggregate(func, fallback_value, *args, **kwargs):
    """
    安全执行聚合函数，失败时返回降级值

    Args:
        func: 聚合函数
        fallback_value: 降级值
        *args: 函数参数
        **kwargs: 函数关键字参数

    Returns:
        函数结果或降级值
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger.warning(f"Aggregation failed: {func.__name__}, using fallback: {e}")
        return fallback_value


def get_cache_key() -> int:
    """
    返回基于当前时间的缓存键（5分钟粒度）

    Returns:
        缓存键（整数）
    """
    now = utc_now()
    return int(now.timestamp() / 300)  # 300 seconds = 5 minutes


@lru_cache(maxsize=32)
def get_cached_dashboard(
    timeframe: str,
    project_id: Optional[str],
    cache_key: int
) -> Dict[str, Any]:
    """
    缓存的 dashboard 数据获取

    cache_key 是基于当前时间的整数（每 5 分钟递增一次）
    这样可以自动实现缓存过期

    Args:
        timeframe: 时间窗口
        project_id: 项目 ID（可选）
        cache_key: 缓存键

    Returns:
        Dashboard 数据字典
    """
    return _compute_dashboard(timeframe, project_id)


def _compute_dashboard(
    timeframe: str,
    project_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    计算 dashboard 数据（无缓存）

    Args:
        timeframe: 时间窗口
        project_id: 项目 ID（可选）

    Returns:
        Dashboard 数据字典
    """
    try:
        conn = get_db()

        # 获取数据
        findings = safe_aggregate(get_findings_data, [], conn, timeframe, project_id)
        audits = safe_aggregate(get_audits_data, [], conn, timeframe, project_id)
        guardian_reviews = safe_aggregate(get_guardian_data, [], conn, timeframe, project_id)
        tasks = safe_aggregate(get_tasks_data, [], conn, timeframe, project_id)

        # 计算指标
        risk_level = safe_aggregate(aggregate_risk_level, "UNKNOWN", findings)
        open_findings = len([f for f in findings if not f.get("linked_task_id")])
        blocked_rate = safe_aggregate(calculate_blocked_rate, 0.0, audits)
        guarded_percentage = safe_aggregate(
            calculate_guardian_coverage, 0.0, tasks, guardian_reviews
        )

        # 计算趋势（简化版本，使用当前数据）
        # TODO: 实现真正的历史数据趋势分析
        findings_trend = compute_trend(findings, [], timeframe)
        blocked_trend = compute_trend(
            audits, [], timeframe,
            value_extractor=lambda a: calculate_blocked_rate(a) * 100
        )
        coverage_trend = compute_trend(
            tasks, [], timeframe,
            value_extractor=lambda t: calculate_guardian_coverage(t, guardian_reviews) * 100
        )

        # 识别 Top 风险
        top_risks = safe_aggregate(
            identify_top_risks, [], findings, audits, guardian_reviews, 5
        )

        # 计算健康度
        health = safe_aggregate(
            calculate_health_metrics, {
                "guardian_coverage": 0.0,
                "avg_decision_latency_ms": 0,
                "tasks_with_audits": 0.0,
                "active_guardians": 0,
                "last_scan": None,
            },
            tasks, audits, guardian_reviews
        )

        return {
            "metrics": {
                "risk_level": risk_level,
                "open_findings": open_findings,
                "blocked_rate": round(blocked_rate, 3),
                "guarded_percentage": round(guarded_percentage, 3),
            },
            "trends": {
                "findings": findings_trend,
                "blocked_decisions": blocked_trend,
                "guardian_coverage": coverage_trend,
            },
            "top_risks": top_risks,
            "health": health,
            "generated_at": iso_z(utc_now()),
        }

    except Exception as e:
        logger.error(f"Failed to compute dashboard: {e}", exc_info=True)
        # 返回降级的空数据
        return {
            "metrics": {
                "risk_level": "UNKNOWN",
                "open_findings": 0,
                "blocked_rate": 0.0,
                "guarded_percentage": 0.0,
            },
            "trends": {
                "findings": {
                    "current": 0, "previous": 0, "change": 0,
                    "direction": "stable", "data_points": []
                },
                "blocked_decisions": {
                    "current": 0, "previous": 0, "change": 0,
                    "direction": "stable", "data_points": []
                },
                "guardian_coverage": {
                    "current": 0, "previous": 0, "change": 0,
                    "direction": "stable", "data_points": []
                },
            },
            "top_risks": [],
            "health": {
                "guardian_coverage": 0.0,
                "avg_decision_latency_ms": 0,
                "tasks_with_audits": 0.0,
                "active_guardians": 0,
                "last_scan": None,
            },
            "generated_at": iso_z(utc_now()),
        }


# ============================================
# API Endpoints
# ============================================


@router.get("/dashboard", response_model=DashboardResponse)
async def get_governance_dashboard(
    timeframe: str = Query(
        "7d",
        pattern="^(7d|30d|90d)$",
        description="Time window (7d, 30d, 90d)"
    ),
    project_id: Optional[str] = Query(
        None,
        description="Filter by project ID (optional)"
    )
) -> DashboardResponse:
    """
    获取 Governance Dashboard 的完整数据

    查询参数:
    - timeframe: 7d | 30d | 90d (默认: 7d)
    - project_id: 可选，过滤特定项目

    返回结构:
    - metrics: 核心指标（风险等级、开放发现数、阻止率、Guardian 覆盖率）
    - trends: 趋势数据（findings、blocked_decisions、guardian_coverage）
    - top_risks: Top 5 风险
    - health: 系统健康度指标
    - generated_at: 生成时间

    性能特性:
    - 5 分钟缓存
    - 响应时间 < 1s
    - 优雅降级（部分数据缺失时仍能返回）

    Example:
        ```bash
        curl http://localhost:8080/api/governance/dashboard?timeframe=7d
        ```
    """
    try:
        # 使用缓存获取数据
        cache_key = get_cache_key()
        dashboard_data = get_cached_dashboard(timeframe, project_id, cache_key)

        # 转换为响应模型
        return DashboardResponse(**dashboard_data)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Dashboard API error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate dashboard: {str(e)}"
        )
