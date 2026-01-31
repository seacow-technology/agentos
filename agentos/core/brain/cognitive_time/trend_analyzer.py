"""
Trend Analyzer - 趋势分析引擎

核心功能：
1. 从快照中提取时间点
2. 计算趋势线（斜率、方向）
3. 识别认知债务
4. 生成健康报告

设计原则：
- 不是"回放"，而是"监控"
- 关注健康度趋势
- 识别退化区域
- 预警认知债务
"""

from typing import List, Dict
from datetime import datetime, timedelta
from .models import (
    TimePoint,
    TrendLine,
    TrendDirection,
    HealthLevel,
    CognitiveDebt,
    HealthReport
)
from ..compare.snapshot import list_snapshots, load_snapshot, SnapshotSummary


def analyze_trends(
    store,  # SQLiteStore
    window_days: int = 30,
    granularity: str = "day"  # "day" or "week"
) -> HealthReport:
    """
    分析认知健康趋势

    Args:
        store: BrainOS 数据库
        window_days: 时间窗口（天）
        granularity: 粒度（day/week）

    Returns:
        HealthReport: 健康报告
    """
    # 1. 获取时间窗口内的快照
    snapshots = list_snapshots(store, limit=100)  # 最多 100 个快照

    window_start = datetime.now() - timedelta(days=window_days)

    # 过滤时间窗口内的快照（处理时区）
    filtered_snapshots = []
    for s in snapshots:
        try:
            # 尝试解析 ISO 格式时间戳
            ts_str = s.timestamp.replace('Z', '+00:00')
            ts = datetime.fromisoformat(ts_str)

            # 如果 ts 是 aware，window_start 也要是 aware
            if ts.tzinfo is not None and window_start.tzinfo is None:
                from datetime import timezone
                window_start = window_start.replace(tzinfo=timezone.utc)
            elif ts.tzinfo is None and window_start.tzinfo is not None:
                # ts 是 naive，移除 window_start 的 tzinfo
                window_start = window_start.replace(tzinfo=None)

            if ts >= window_start:
                filtered_snapshots.append(s)
        except (ValueError, AttributeError):
            # 无法解析时间戳，跳过
            continue

    if len(filtered_snapshots) < 2:
        # 数据不足，返回空报告
        return create_insufficient_data_report(window_days)

    # 2. 转换为时间点
    time_points = [snapshot_to_time_point(store, s) for s in filtered_snapshots]
    time_points.sort(key=lambda p: p.timestamp)

    # 3. 计算趋势线
    coverage_trend = compute_trend_line("coverage_percentage", time_points)
    blind_spot_trend = compute_trend_line("blind_spot_ratio", time_points)
    evidence_density_trend = compute_trend_line("evidence_density", time_points)

    # 4. 分析来源迁移
    source_migration = analyze_source_migration(time_points)

    # 5. 识别认知债务
    cognitive_debts = identify_cognitive_debts(store, time_points)

    # 6. 计算当前健康评分
    current_point = time_points[-1]
    current_health_score = current_point.health_score
    current_health_level = score_to_level(current_health_score)

    # 7. 生成预警和建议
    warnings = generate_warnings(coverage_trend, blind_spot_trend, cognitive_debts)
    recommendations = generate_recommendations(coverage_trend, blind_spot_trend, cognitive_debts)

    report = HealthReport(
        window_start=time_points[0].timestamp,
        window_end=time_points[-1].timestamp,
        window_days=window_days,
        current_health_level=current_health_level,
        current_health_score=current_health_score,
        coverage_trend=coverage_trend,
        blind_spot_trend=blind_spot_trend,
        evidence_density_trend=evidence_density_trend,
        source_migration=source_migration,
        cognitive_debts=cognitive_debts,
        total_debt_count=len(cognitive_debts),
        warnings=warnings,
        recommendations=recommendations,
        computed_at=datetime.now().isoformat()
    )

    # P4-A Hook: 生成决策记录
    try:
        from ..governance.decision_recorder import record_health_decision
        record_health_decision(store, window_days, granularity, report)
    except Exception as e:
        # 不影响主流程
        import logging
        logging.getLogger(__name__).warning(f"Failed to record health decision: {e}")

    return report


def snapshot_to_time_point(store, summary: SnapshotSummary) -> TimePoint:
    """
    将快照摘要转换为时间点

    Args:
        store: BrainOS 数据库
        summary: 快照摘要

    Returns:
        TimePoint: 时间点（含健康指标）
    """
    # 计算证据密度
    evidence_density = summary.evidence_count / summary.entity_count if summary.entity_count > 0 else 0.0

    # 计算盲区比例
    blind_spot_ratio = summary.blind_spot_count / summary.entity_count if summary.entity_count > 0 else 0.0

    # 计算健康评分
    health_score = compute_health_score_from_metrics(
        summary.coverage_percentage / 100.0,  # 转换为 0-1
        evidence_density,
        blind_spot_ratio
    )

    # TODO: 从 snapshot 加载来源覆盖率
    # 暂时使用简化值
    git_coverage = 0.0
    doc_coverage = 0.0
    code_coverage = 0.0

    return TimePoint(
        snapshot_id=summary.snapshot_id,
        timestamp=summary.timestamp,
        coverage_percentage=summary.coverage_percentage / 100.0,  # 转换为 0-1
        evidence_density=evidence_density,
        blind_spot_ratio=blind_spot_ratio,
        git_coverage=git_coverage,
        doc_coverage=doc_coverage,
        code_coverage=code_coverage,
        entity_count=summary.entity_count,
        edge_count=summary.edge_count,
        evidence_count=summary.evidence_count,
        health_score=health_score
    )


def compute_trend_line(metric_name: str, time_points: List[TimePoint]) -> TrendLine:
    """
    计算趋势线

    使用线性回归拟合斜率

    Args:
        metric_name: 指标名称
        time_points: 时间点列表

    Returns:
        TrendLine: 趋势线
    """
    if len(time_points) < 2:
        return TrendLine(
            metric_name=metric_name,
            time_points=[],
            direction=TrendDirection.INSUFFICIENT_DATA,
            slope=0.0,
            avg_value=0.0,
            max_value=0.0,
            min_value=0.0,
            predicted_next_value=None
        )

    # 提取指标值
    values = [getattr(p, metric_name) for p in time_points]

    # 计算统计量
    avg_value = sum(values) / len(values)
    max_value = max(values)
    min_value = min(values)

    # 简单线性回归（最小二乘法）
    n = len(values)
    x = list(range(n))  # 时间索引
    y = values

    x_mean = sum(x) / n
    y_mean = avg_value

    numerator = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(n))
    denominator = sum((x[i] - x_mean) ** 2 for i in range(n))

    slope = numerator / denominator if denominator != 0 else 0.0

    # 判断趋势方向
    # 注意：blind_spot_ratio 增加是退化，其他指标增加是改善
    threshold = 0.001  # 斜率阈值
    if abs(slope) < threshold:
        direction = TrendDirection.STABLE
    elif slope > 0:
        if metric_name == "blind_spot_ratio":
            direction = TrendDirection.DEGRADING  # 盲区增加 = 退化
        else:
            direction = TrendDirection.IMPROVING  # 覆盖率增加 = 改善
    else:
        if metric_name == "blind_spot_ratio":
            direction = TrendDirection.IMPROVING  # 盲区减少 = 改善
        else:
            direction = TrendDirection.DEGRADING  # 覆盖率减少 = 退化

    # 预测下一个值
    intercept = y_mean - slope * x_mean
    predicted_next_value = slope * n + intercept

    return TrendLine(
        metric_name=metric_name,
        time_points=time_points,
        direction=direction,
        slope=slope,
        avg_value=avg_value,
        max_value=max_value,
        min_value=min_value,
        predicted_next_value=predicted_next_value
    )


def analyze_source_migration(time_points: List[TimePoint]) -> Dict[str, TrendDirection]:
    """
    分析来源迁移

    检查 Git/Doc/Code 覆盖是上升还是下降

    Args:
        time_points: 时间点列表

    Returns:
        来源迁移分析结果
    """
    if len(time_points) < 2:
        return {
            "git": TrendDirection.INSUFFICIENT_DATA,
            "doc": TrendDirection.INSUFFICIENT_DATA,
            "code": TrendDirection.INSUFFICIENT_DATA
        }

    first = time_points[0]
    last = time_points[-1]

    def detect_direction(first_val: float, last_val: float) -> TrendDirection:
        if abs(last_val - first_val) < 0.05:
            return TrendDirection.STABLE
        elif last_val > first_val:
            return TrendDirection.IMPROVING
        else:
            return TrendDirection.DEGRADING

    return {
        "git": detect_direction(first.git_coverage, last.git_coverage),
        "doc": detect_direction(first.doc_coverage, last.doc_coverage),
        "code": detect_direction(first.code_coverage, last.code_coverage)
    }


def identify_cognitive_debts(store, time_points: List[TimePoint]) -> List[CognitiveDebt]:
    """
    识别认知债务

    定义：
    - UNCOVERED: 长期无覆盖（>= 14 天）
    - DEGRADING: 证据持续减少（>= 7 天）
    - ORPHANED: 长期孤立（无边连接，>= 14 天）

    Args:
        store: BrainOS 数据库
        time_points: 时间点列表

    Returns:
        认知债务列表
    """
    if len(time_points) < 2:
        return []

    debts = []

    # 简化实现：检查当前快照中的低覆盖实体
    latest_snapshot = load_snapshot(store, time_points[-1].snapshot_id)

    for entity in latest_snapshot.entities:
        if entity.evidence_count == 0:
            debts.append(CognitiveDebt(
                entity_id=entity.entity_id,
                entity_type=entity.entity_type,
                entity_key=entity.entity_key,
                entity_name=entity.entity_name,
                debt_type="UNCOVERED",
                duration_days=14,  # 简化：假设 14 天
                severity=1.0,
                description=f"Entity has no evidence for extended period",
                recommendation="Add documentation or code references"
            ))

        elif len(entity.coverage_sources) == 0:
            debts.append(CognitiveDebt(
                entity_id=entity.entity_id,
                entity_type=entity.entity_type,
                entity_key=entity.entity_key,
                entity_name=entity.entity_name,
                debt_type="UNCOVERED",
                duration_days=7,
                severity=0.7,
                description=f"Entity has no coverage sources",
                recommendation="Link to Git commits, docs, or code"
            ))

    # 排序：按严重度降序
    debts.sort(key=lambda d: d.severity, reverse=True)

    return debts[:10]  # 最多返回 10 个


def compute_health_score(point: TimePoint) -> float:
    """
    计算健康评分（0-100）

    公式：
    health_score = (
        0.4 * coverage_percentage * 100 +
        0.3 * min(evidence_density * 10, 100) +
        0.3 * (100 - blind_spot_ratio * 100)
    )

    Args:
        point: 时间点

    Returns:
        健康评分（0-100）
    """
    return compute_health_score_from_metrics(
        point.coverage_percentage,
        point.evidence_density,
        point.blind_spot_ratio
    )


def compute_health_score_from_metrics(
    coverage_pct: float,
    evidence_density: float,
    blind_spot_ratio: float
) -> float:
    """
    从指标计算健康评分

    Args:
        coverage_pct: 覆盖率（0-1）
        evidence_density: 证据密度
        blind_spot_ratio: 盲区比例（0-1）

    Returns:
        健康评分（0-100）
    """
    score = (
        0.4 * coverage_pct * 100 +
        0.3 * min(evidence_density * 10, 100) +
        0.3 * (100 - blind_spot_ratio * 100)
    )

    return max(0.0, min(100.0, score))


def score_to_level(score: float) -> HealthLevel:
    """
    评分转健康等级

    Args:
        score: 健康评分（0-100）

    Returns:
        健康等级
    """
    if score >= 80:
        return HealthLevel.EXCELLENT
    elif score >= 60:
        return HealthLevel.GOOD
    elif score >= 40:
        return HealthLevel.FAIR
    elif score >= 20:
        return HealthLevel.POOR
    else:
        return HealthLevel.CRITICAL


def generate_warnings(
    coverage_trend: TrendLine,
    blind_spot_trend: TrendLine,
    cognitive_debts: List[CognitiveDebt]
) -> List[str]:
    """
    生成预警

    Args:
        coverage_trend: 覆盖率趋势
        blind_spot_trend: 盲区趋势
        cognitive_debts: 认知债务列表

    Returns:
        预警列表
    """
    warnings = []

    if coverage_trend.direction == TrendDirection.DEGRADING:
        warnings.append(f"⚠️ Coverage is DEGRADING (slope: {coverage_trend.slope:.4f})")

    if blind_spot_trend.direction == TrendDirection.DEGRADING:  # blind_spot 增加 = 退化
        warnings.append(f"⚠️ Blind spots are INCREASING (slope: {blind_spot_trend.slope:.4f})")

    if len(cognitive_debts) > 5:
        warnings.append(f"⚠️ High cognitive debt: {len(cognitive_debts)} uncovered entities")

    return warnings


def generate_recommendations(
    coverage_trend: TrendLine,
    blind_spot_trend: TrendLine,
    cognitive_debts: List[CognitiveDebt]
) -> List[str]:
    """
    生成建议

    Args:
        coverage_trend: 覆盖率趋势
        blind_spot_trend: 盲区趋势
        cognitive_debts: 认知债务列表

    Returns:
        建议列表
    """
    recommendations = []

    if coverage_trend.direction == TrendDirection.DEGRADING:
        recommendations.append("📝 Rebuild BrainOS index to update coverage")
        recommendations.append("📄 Add more documentation mentions")

    if blind_spot_trend.direction == TrendDirection.DEGRADING:
        recommendations.append("🔍 Review and resolve blind spots")
        recommendations.append("🔗 Add missing evidence links")

    if len(cognitive_debts) > 0:
        recommendations.append(f"💳 Address top {min(5, len(cognitive_debts))} cognitive debts")
        for debt in cognitive_debts[:3]:
            recommendations.append(f"  - {debt.entity_name}: {debt.recommendation}")

    return recommendations


def create_insufficient_data_report(window_days: int) -> HealthReport:
    """
    数据不足时返回的空报告

    Args:
        window_days: 时间窗口（天）

    Returns:
        空健康报告
    """
    return HealthReport(
        window_start="",
        window_end="",
        window_days=window_days,
        current_health_level=HealthLevel.GOOD,  # 默认
        current_health_score=50.0,
        coverage_trend=TrendLine(
            metric_name="coverage_percentage",
            time_points=[],
            direction=TrendDirection.INSUFFICIENT_DATA,
            slope=0.0,
            avg_value=0.0,
            max_value=0.0,
            min_value=0.0,
            predicted_next_value=None
        ),
        blind_spot_trend=TrendLine(
            metric_name="blind_spot_ratio",
            time_points=[],
            direction=TrendDirection.INSUFFICIENT_DATA,
            slope=0.0,
            avg_value=0.0,
            max_value=0.0,
            min_value=0.0,
            predicted_next_value=None
        ),
        evidence_density_trend=TrendLine(
            metric_name="evidence_density",
            time_points=[],
            direction=TrendDirection.INSUFFICIENT_DATA,
            slope=0.0,
            avg_value=0.0,
            max_value=0.0,
            min_value=0.0,
            predicted_next_value=None
        ),
        source_migration={
            "git": TrendDirection.INSUFFICIENT_DATA,
            "doc": TrendDirection.INSUFFICIENT_DATA,
            "code": TrendDirection.INSUFFICIENT_DATA
        },
        cognitive_debts=[],
        total_debt_count=0,
        warnings=["⚠️ Insufficient data (need >= 2 snapshots)"],
        recommendations=["📸 Create snapshots regularly to enable trend analysis"],
        computed_at=datetime.now().isoformat()
    )
