"""
Decision Recorder - 决策记录器

负责将 Navigation/Compare/Time 的结果转换为 DecisionRecord
"""

from typing import Optional
import uuid
from datetime import datetime, timezone
import json
import logging

from agentos.core.time import utc_now_iso
from .decision_record import (
    DecisionRecord,
    DecisionType,
    DecisionStatus,
    GovernanceAction
)
from .rule_engine import apply_governance_rules
from ..store import SQLiteStore

logger = logging.getLogger(__name__)


def record_navigation_decision(
    store: SQLiteStore,
    seed: str,
    goal: Optional[str],
    max_hops: int,
    result
):
    """
    记录 Navigation 决策

    Args:
        store: BrainOS 数据库
        seed: 种子实体
        goal: 目标实体（可选）
        max_hops: 最大跳数
        result: NavigationResult
    """
    decision_id = str(uuid.uuid4())

    # 构建输入
    inputs = {
        "seed": seed,
        "goal": goal,
        "max_hops": max_hops
    }

    # 构建输出（需要从 result 中提取）
    paths_count = len(result.paths)

    # 计算统计数据
    max_risk_level = "LOW"
    total_blind_spots = 0
    avg_confidence = 0.0

    if result.paths:
        # 找到最高风险等级
        for path in result.paths:
            if path.risk_level.value == "HIGH":
                max_risk_level = "HIGH"
            elif path.risk_level.value == "MEDIUM" and max_risk_level == "LOW":
                max_risk_level = "MEDIUM"

            total_blind_spots += path.blind_spot_count

        # 计算平均置信度
        avg_confidence = sum(p.confidence for p in result.paths) / len(result.paths)

    outputs = {
        "current_zone": result.current_zone.value,
        "paths_count": paths_count,
        "max_risk_level": max_risk_level,
        "total_blind_spots": total_blind_spots,
        "avg_confidence": avg_confidence,
        "no_path_reason": result.no_path_reason
    }

    # 运行治理规则
    rules_triggered, final_verdict = apply_governance_rules(
        DecisionType.NAVIGATION,
        inputs,
        outputs
    )

    # 计算置信度（使用平均路径置信度）
    confidence_score = avg_confidence if result.paths else 0.0

    # 创建记录
    record = DecisionRecord(
        decision_id=decision_id,
        decision_type=DecisionType.NAVIGATION,
        seed=seed,
        inputs=inputs,
        outputs=outputs,
        rules_triggered=rules_triggered,
        final_verdict=final_verdict,
        confidence_score=confidence_score,
        timestamp=utc_now_iso(),
        snapshot_ref=None,
        status=DecisionStatus.PENDING
    )

    # 计算 hash
    record.record_hash = record.compute_hash()

    # 保存到数据库
    save_decision_record(store, record)

    logger.info(f"Recorded navigation decision: {decision_id}, verdict={final_verdict.value}, rules={len(rules_triggered)}")


def record_compare_decision(
    store: SQLiteStore,
    from_snapshot_id: str,
    to_snapshot_id: str,
    result
):
    """
    记录 Compare 决策

    Args:
        store: BrainOS 数据库
        from_snapshot_id: 起始快照 ID
        to_snapshot_id: 目标快照 ID
        result: CompareResult
    """
    decision_id = str(uuid.uuid4())

    inputs = {
        "from_snapshot_id": from_snapshot_id,
        "to_snapshot_id": to_snapshot_id
    }

    outputs = {
        "overall_assessment": result.overall_assessment,
        "health_score_change": result.health_score_change,
        "entities_added": result.entities_added,
        "entities_removed": result.entities_removed,
        "entities_weakened": result.entities_weakened
    }

    # 运行治理规则
    rules_triggered, final_verdict = apply_governance_rules(
        DecisionType.COMPARE,
        inputs,
        outputs
    )

    # 置信度（简化：基于健康分数变化）
    confidence_score = max(0.0, 1.0 - abs(result.health_score_change))

    record = DecisionRecord(
        decision_id=decision_id,
        decision_type=DecisionType.COMPARE,
        seed=from_snapshot_id,
        inputs=inputs,
        outputs=outputs,
        rules_triggered=rules_triggered,
        final_verdict=final_verdict,
        confidence_score=confidence_score,
        timestamp=utc_now_iso(),
        snapshot_ref=from_snapshot_id,
        status=DecisionStatus.PENDING
    )

    record.record_hash = record.compute_hash()
    save_decision_record(store, record)

    logger.info(f"Recorded compare decision: {decision_id}, verdict={final_verdict.value}")


def record_health_decision(
    store: SQLiteStore,
    window_days: int,
    granularity: str,
    report
):
    """
    记录 Time/Health 决策

    Args:
        store: BrainOS 数据库
        window_days: 时间窗口（天）
        granularity: 粒度
        report: HealthReport
    """
    decision_id = str(uuid.uuid4())

    inputs = {
        "window_days": window_days,
        "granularity": granularity
    }

    outputs = {
        "current_health_level": report.current_health_level.value,
        "current_health_score": report.current_health_score,
        "coverage_trend_direction": report.coverage_trend.direction.value,
        "blind_spot_trend_direction": report.blind_spot_trend.direction.value,
        "warnings_count": len(report.warnings),
        "cognitive_debt_count": report.total_debt_count
    }

    # 运行治理规则
    rules_triggered, final_verdict = apply_governance_rules(
        DecisionType.HEALTH,
        inputs,
        outputs
    )

    # 置信度（基于健康分数）
    confidence_score = report.current_health_score / 100.0

    record = DecisionRecord(
        decision_id=decision_id,
        decision_type=DecisionType.HEALTH,
        seed=f"health_window_{window_days}d",
        inputs=inputs,
        outputs=outputs,
        rules_triggered=rules_triggered,
        final_verdict=final_verdict,
        confidence_score=confidence_score,
        timestamp=utc_now_iso(),
        snapshot_ref=None,
        status=DecisionStatus.PENDING
    )

    record.record_hash = record.compute_hash()
    save_decision_record(store, record)

    logger.info(f"Recorded health decision: {decision_id}, verdict={final_verdict.value}")


def save_decision_record(store: SQLiteStore, record: DecisionRecord):
    """
    保存决策记录到数据库（append-only）

    Args:
        store: BrainOS 数据库
        record: 决策记录
    """
    cursor = store.conn.cursor()

    cursor.execute("""
        INSERT INTO decision_records (
            decision_id, decision_type, seed, inputs, outputs,
            rules_triggered, final_verdict, confidence_score, timestamp,
            snapshot_ref, signed_by, sign_timestamp, sign_note, status, record_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        record.decision_id,
        record.decision_type.value,
        record.seed,
        json.dumps(record.inputs),
        json.dumps(record.outputs),
        json.dumps([r.to_dict() for r in record.rules_triggered]),
        record.final_verdict.value,
        record.confidence_score,
        record.timestamp,
        record.snapshot_ref,
        record.signed_by,
        record.sign_timestamp,
        record.sign_note,
        record.status.value,
        record.record_hash
    ))

    store.conn.commit()


def load_decision_record(store: SQLiteStore, decision_id: str) -> Optional[DecisionRecord]:
    """
    从数据库加载决策记录

    Args:
        store: BrainOS 数据库
        decision_id: 决策 ID

    Returns:
        DecisionRecord 或 None
    """
    cursor = store.conn.cursor()

    cursor.execute("""
        SELECT
            decision_id, decision_type, seed, inputs, outputs,
            rules_triggered, final_verdict, confidence_score, timestamp,
            snapshot_ref, signed_by, sign_timestamp, sign_note, status, record_hash
        FROM decision_records
        WHERE decision_id = ?
    """, (decision_id,))

    row = cursor.fetchone()
    if not row:
        return None

    # 解析 JSON 字段
    inputs = json.loads(row[3])
    outputs = json.loads(row[4])
    rules_triggered_data = json.loads(row[5])

    # 重建 RuleTrigger 列表
    from .decision_record import RuleTrigger
    rules_triggered = [
        RuleTrigger(
            rule_id=r["rule_id"],
            rule_name=r["rule_name"],
            action=GovernanceAction(r["action"]),
            rationale=r["rationale"]
        )
        for r in rules_triggered_data
    ]

    return DecisionRecord(
        decision_id=row[0],
        decision_type=DecisionType(row[1]),
        seed=row[2],
        inputs=inputs,
        outputs=outputs,
        rules_triggered=rules_triggered,
        final_verdict=GovernanceAction(row[6]),
        confidence_score=row[7],
        timestamp=row[8],
        snapshot_ref=row[9],
        signed_by=row[10],
        sign_timestamp=row[11],
        sign_note=row[12],
        status=DecisionStatus(row[13]),
        record_hash=row[14]
    )


def list_decision_records(
    store: SQLiteStore,
    seed: Optional[str] = None,
    decision_type: Optional[str] = None,
    limit: int = 50
) -> list:
    """
    列出决策记录

    Args:
        store: BrainOS 数据库
        seed: 过滤种子（可选）
        decision_type: 过滤类型（可选）
        limit: 最大返回数量

    Returns:
        记录列表（字典格式）
    """
    cursor = store.conn.cursor()

    query = "SELECT * FROM decision_records WHERE 1=1"
    params = []

    if seed:
        query += " AND seed = ?"
        params.append(seed)

    if decision_type:
        query += " AND decision_type = ?"
        params.append(decision_type)

    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)

    cursor.execute(query, params)

    records = []
    for row in cursor.fetchall():
        records.append({
            "decision_id": row[0],
            "decision_type": row[1],
            "seed": row[2],
            "inputs": json.loads(row[3]),
            "outputs": json.loads(row[4]),
            "rules_triggered": json.loads(row[5]),
            "final_verdict": row[6],
            "confidence_score": row[7],
            "timestamp": row[8],
            "status": row[13],
            "record_hash": row[14]
        })

    return records
