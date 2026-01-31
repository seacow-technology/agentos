"""
BrainOS Governance API - P4

提供决策记录、治理规则、审计和责任追溯的 REST API。

Endpoints:
- GET /api/brain/governance/decisions - 列出决策记录
- GET /api/brain/governance/decisions/{decision_id} - 获取单个决策记录
- GET /api/brain/governance/decisions/{decision_id}/replay - 重放决策
- POST /api/brain/governance/decisions/{decision_id}/signoff - 签字决策
- GET /api/brain/governance/rules - 列出所有治理规则
"""

import logging
import json
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from agentos.webui.api.time_format import iso_z
from agentos.core.time import utc_now


logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# Request/Response Models
# ============================================================================

class SignoffRequest(BaseModel):
    """签字请求"""
    signed_by: str
    note: str


# ============================================================================
# Helper Functions
# ============================================================================

def get_brainos_db_path() -> Path:
    """
    获取 BrainOS 数据库路径

    从环境变量 BRAINOS_DB_PATH 读取，或使用默认路径。
    Uses environment variable for configurability (consistent with registry_db pattern).
    """
    db_path_str = os.environ.get('BRAINOS_DB_PATH')
    if db_path_str:
        return Path(db_path_str)

    # 默认路径：使用component_db_path
    from agentos.core.storage.paths import component_db_path
    return component_db_path("brainos")


# ============================================================================
# API Endpoints
# ============================================================================

@router.get("/api/brain/governance/decisions")
async def list_decision_records(
    seed: Optional[str] = Query(None, description="Filter by seed"),
    decision_type: Optional[str] = Query(None, description="Filter by type (NAVIGATION/COMPARE/HEALTH)"),
    limit: int = Query(50, description="Max records to return", ge=1, le=500)
):
    """
    列出决策记录

    Args:
        seed: 过滤种子（可选）
        decision_type: 过滤类型（可选）
        limit: 最大返回数量

    Returns:
        决策记录列表
    """
    try:
        from agentos.core.brain.store import SQLiteStore
        from agentos.core.brain.governance.decision_recorder import list_decision_records
        import os

        db_path = get_brainos_db_path()

        if not db_path.exists():
            return JSONResponse(
                status_code=404,
                content={
                    "ok": False,
                    "data": None,
                    "error": f"BrainOS database not found at {db_path}. Please run 'agentos brain build' first."
                }
            )

        store = SQLiteStore(str(db_path), auto_init=True)
        store.connect()

        try:
            records = list_decision_records(store, seed=seed, decision_type=decision_type, limit=limit)
        finally:
            store.close()

        return {
            "ok": True,
            "data": {"records": records, "count": len(records)},
            "error": None
        }

    except Exception as e:
        logger.exception("Error in list_decision_records")
        return JSONResponse(
            status_code=500,
            content={"ok": False, "data": None, "error": str(e)}
        )


@router.get("/api/brain/governance/decisions/{decision_id}")
async def get_decision_record(decision_id: str):
    """
    获取单个决策记录

    Args:
        decision_id: 决策 ID

    Returns:
        决策记录详情
    """
    try:
        from agentos.core.brain.store import SQLiteStore
        from agentos.core.brain.governance.decision_recorder import load_decision_record
        import os

        db_path = get_brainos_db_path()

        if not db_path.exists():
            return JSONResponse(
                status_code=404,
                content={
                    "ok": False,
                    "data": None,
                    "error": f"BrainOS database not found at {db_path}"
                }
            )

        store = SQLiteStore(str(db_path), auto_init=True)
        store.connect()

        try:
            record = load_decision_record(store, decision_id)

            if not record:
                return JSONResponse(
                    status_code=404,
                    content={
                        "ok": False,
                        "data": None,
                        "error": f"Decision record not found: {decision_id}"
                    }
                )

            # 验证完整性
            integrity_ok = record.verify_integrity()

            result = record.to_dict()
            result["integrity_verified"] = integrity_ok

        finally:
            store.close()

        return {
            "ok": True,
            "data": result,
            "error": None
        }

    except Exception as e:
        logger.exception("Error in get_decision_record")
        return JSONResponse(
            status_code=500,
            content={"ok": False, "data": None, "error": str(e)}
        )


@router.get("/api/brain/governance/decisions/{decision_id}/replay")
async def replay_decision(decision_id: str):
    """
    重放决策（P4-C：完整性验证和审计追踪）

    返回：
    - 原始输入和输出
    - 触发的规则列表
    - 完整性验证结果（hash 验证）
    - 快照引用（如果有）
    - 签字信息（如果已签字）
    - 审计追踪

    Red Line 3 验证：
    - 计算并验证记录 hash
    - 检测篡改

    Args:
        decision_id: 决策 ID

    Returns:
        完整的重放结果
    """
    try:
        from agentos.core.brain.store import SQLiteStore
        from agentos.core.brain.governance.decision_recorder import load_decision_record
        from agentos.core.brain.compare.snapshot import load_snapshot
        import os

        db_path = get_brainos_db_path()

        if not db_path.exists():
            return JSONResponse(
                status_code=404,
                content={
                    "ok": False,
                    "data": None,
                    "error": f"BrainOS database not found at {db_path}"
                }
            )

        store = SQLiteStore(str(db_path), auto_init=True)
        store.connect()

        try:
            record = load_decision_record(store, decision_id)

            if not record:
                return JSONResponse(
                    status_code=404,
                    content={
                        "ok": False,
                        "data": None,
                        "error": f"Decision record not found: {decision_id}"
                    }
                )

            # P4-C: 完整性验证（Red Line 3）
            computed_hash = record.compute_hash()
            stored_hash = record.record_hash
            integrity_ok = (computed_hash == stored_hash)

            replay_result = {
                "decision": record.to_dict(),
                "integrity_check": {
                    "passed": integrity_ok,
                    "computed_hash": computed_hash,
                    "stored_hash": stored_hash,
                    "algorithm": "SHA256"
                },
                "replay_timestamp": iso_z(utc_now()),
                "warnings": [],
                "audit_trail": {
                    "created_at": record.timestamp,
                    "decision_type": record.decision_type.value,
                    "rules_evaluated": len(record.rules_triggered),
                    "final_verdict": record.final_verdict.value,
                    "status": record.status.value
                }
            }

            # Red Line 3: 篡改检测
            if not integrity_ok:
                replay_result["warnings"].append({
                    "level": "CRITICAL",
                    "message": "Integrity verification FAILED - record may have been tampered",
                    "details": f"Hash mismatch: expected {stored_hash}, got {computed_hash}"
                })

            # P4-C: 签字信息
            if record.signed_by:
                replay_result["signoff"] = {
                    "signed_by": record.signed_by,
                    "sign_timestamp": record.sign_timestamp,
                    "sign_note": record.sign_note
                }
                replay_result["audit_trail"]["signed_at"] = record.sign_timestamp
                replay_result["audit_trail"]["signer"] = record.signed_by

            # P4-C: 快照加载（如果有引用）
            snapshot_data = None
            if record.snapshot_ref:
                try:
                    snapshot = load_snapshot(store, record.snapshot_ref)
                    if snapshot:
                        snapshot_data = {
                            "snapshot_id": snapshot.summary.snapshot_id,
                            "timestamp": snapshot.summary.timestamp,
                            "entity_count": snapshot.summary.entity_count,
                            "edge_count": snapshot.summary.edge_count,
                            "source": snapshot.summary.source
                        }
                    else:
                        replay_result["warnings"].append({
                            "level": "WARNING",
                            "message": f"Snapshot not found: {record.snapshot_ref}"
                        })
                except Exception as e:
                    replay_result["warnings"].append({
                        "level": "ERROR",
                        "message": f"Failed to load snapshot: {str(e)}"
                    })

            if snapshot_data:
                replay_result["snapshot"] = snapshot_data

            # P4-C: 规则详情
            replay_result["rules_triggered"] = [
                {
                    "rule_id": trigger.rule_id,
                    "rule_name": trigger.rule_name,
                    "action": trigger.action.value,
                    "rationale": trigger.rationale
                }
                for trigger in record.rules_triggered
            ]

        finally:
            store.close()

        return {
            "ok": True,
            "data": replay_result,
            "error": None
        }

    except Exception as e:
        logger.exception("Error in replay_decision")
        return JSONResponse(
            status_code=500,
            content={"ok": False, "data": None, "error": str(e)}
        )


@router.post("/api/brain/governance/decisions/{decision_id}/signoff")
async def signoff_decision(decision_id: str, request: SignoffRequest):
    """
    签字决策（P4-D：状态机验证）

    流程：
    1. 检查决策存在
    2. 验证状态（必须是 PENDING）
    3. 验证 final_verdict（必须是 REQUIRE_SIGNOFF）
    4. 应用状态转换（PENDING → SIGNED）
    5. 创建签字记录
    6. Red Line 3: 不修改原记录 hash，只更新 status 和签字字段

    Args:
        decision_id: 决策 ID
        request: 签字请求（signed_by, note）

    Returns:
        签字结果
    """
    try:
        from agentos.core.brain.store import SQLiteStore
        from agentos.core.brain.governance.decision_recorder import load_decision_record
        from agentos.core.brain.governance.decision_record import DecisionStatus, GovernanceAction
        from agentos.core.brain.governance.state_machine import (
            validate_state_transition,
            StateTransition,
            apply_transition,
            StateTransitionError
        )
        from datetime import datetime, timezone
        import os
        import uuid

        # 验证 note 非空
        if not request.note or not request.note.strip():
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "data": None,
                    "error": "Signoff note is required and cannot be empty"
                }
            )

        db_path = get_brainos_db_path()

        if not db_path.exists():
            return JSONResponse(
                status_code=404,
                content={
                    "ok": False,
                    "data": None,
                    "error": f"BrainOS database not found at {db_path}"
                }
            )

        store = SQLiteStore(str(db_path), auto_init=True)
        store.connect()

        try:
            record = load_decision_record(store, decision_id)

            if not record:
                return JSONResponse(
                    status_code=404,
                    content={
                        "ok": False,
                        "data": None,
                        "error": f"Decision record not found: {decision_id}"
                    }
                )

            # P4-D: 状态机验证
            # 1. 检查是否需要签字
            if record.final_verdict != GovernanceAction.REQUIRE_SIGNOFF:
                return JSONResponse(
                    status_code=400,
                    content={
                        "ok": False,
                        "data": None,
                        "error": f"Decision does not require signoff (verdict: {record.final_verdict.value})"
                    }
                )

            # 2. 检查当前状态
            if record.status != DecisionStatus.PENDING:
                if record.status == DecisionStatus.SIGNED:
                    return JSONResponse(
                        status_code=400,
                        content={
                            "ok": False,
                            "data": None,
                            "error": f"Decision already signed by {record.signed_by} at {record.sign_timestamp}"
                        }
                    )
                else:
                    return JSONResponse(
                        status_code=400,
                        content={
                            "ok": False,
                            "data": None,
                            "error": f"Decision in unexpected state: {record.status.value}"
                        }
                    )

            # 3. 验证状态转换
            try:
                new_status = apply_transition(
                    record.status,
                    StateTransition.SIGNOFF,
                    record.final_verdict
                )
            except StateTransitionError as e:
                return JSONResponse(
                    status_code=400,
                    content={
                        "ok": False,
                        "data": None,
                        "error": f"Invalid state transition: {str(e)}"
                    }
                )

            # 4. 更新签字信息
            sign_timestamp = iso_z(utc_now())
            signoff_id = str(uuid.uuid4())

            cursor = store.conn.cursor()

            # Red Line 3: 不修改原记录 hash，只更新 status 和签字字段
            cursor.execute("""
                UPDATE decision_records
                SET signed_by = ?, sign_timestamp = ?, sign_note = ?, status = ?
                WHERE decision_id = ?
            """, (request.signed_by, sign_timestamp, request.note, new_status.value, decision_id))

            # 5. 插入签字记录（独立表）
            cursor.execute("""
                INSERT INTO decision_signoffs (signoff_id, decision_id, signed_by, timestamp, note)
                VALUES (?, ?, ?, ?, ?)
            """, (signoff_id, decision_id, request.signed_by, sign_timestamp, request.note))

            store.conn.commit()

        finally:
            store.close()

        return {
            "ok": True,
            "data": {
                "signoff_id": signoff_id,
                "decision_id": decision_id,
                "signed_by": request.signed_by,
                "timestamp": sign_timestamp,
                "note": request.note,
                "new_status": new_status.value
            },
            "error": None
        }

    except Exception as e:
        logger.exception("Error in signoff_decision")
        return JSONResponse(
            status_code=500,
            content={"ok": False, "data": None, "error": str(e)}
        )


@router.get("/api/brain/governance/rules")
async def list_governance_rules():
    """
    列出所有治理规则（P4-B: 包含配置规则）

    Returns:
        治理规则列表
    """
    try:
        from agentos.core.brain.governance.rule_engine import list_all_rules

        rules = list_all_rules(use_config_rules=True)

        return {
            "ok": True,
            "data": {"rules": rules, "count": len(rules)},
            "error": None
        }

    except Exception as e:
        logger.exception("Error in list_governance_rules")
        return JSONResponse(
            status_code=500,
            content={"ok": False, "data": None, "error": str(e)}
        )


@router.get("/api/brain/governance/decisions/{decision_id}/can_proceed")
async def check_can_proceed(decision_id: str):
    """
    检查决策是否允许操作继续（P4-D: Red Line 4）

    用途：
    - Navigation/Compare/Health API 在返回结果前检查此端点
    - 如果不允许继续，返回 403 Forbidden

    Red Line 4 规则：
    - BLOCK: 总是阻止
    - REQUIRE_SIGNOFF + PENDING: 阻止（需要签字）
    - REQUIRE_SIGNOFF + SIGNED: 允许
    - WARN/ALLOW: 允许

    Args:
        decision_id: 决策 ID

    Returns:
        {
            "can_proceed": bool,
            "blocking_reason": str | null,
            "requires_signoff": bool,
            "signoff_url": str | null
        }
    """
    try:
        from agentos.core.brain.store import SQLiteStore
        from agentos.core.brain.governance.decision_recorder import load_decision_record
        from agentos.core.brain.governance.state_machine import can_proceed_with_verdict
        import os

        db_path = get_brainos_db_path()

        if not db_path.exists():
            return JSONResponse(
                status_code=404,
                content={
                    "ok": False,
                    "data": None,
                    "error": f"BrainOS database not found at {db_path}"
                }
            )

        store = SQLiteStore(str(db_path), auto_init=True)
        store.connect()

        try:
            record = load_decision_record(store, decision_id)

            if not record:
                return JSONResponse(
                    status_code=404,
                    content={
                        "ok": False,
                        "data": None,
                        "error": f"Decision record not found: {decision_id}"
                    }
                )

            # P4-D: Red Line 4 检查
            can_proceed, blocking_reason = can_proceed_with_verdict(
                record.status,
                record.final_verdict
            )

            from agentos.core.brain.governance.decision_record import GovernanceAction

            result = {
                "decision_id": decision_id,
                "can_proceed": can_proceed,
                "blocking_reason": blocking_reason,
                "requires_signoff": (record.final_verdict == GovernanceAction.REQUIRE_SIGNOFF),
                "signoff_url": f"/api/brain/governance/decisions/{decision_id}/signoff" if not can_proceed and record.final_verdict == GovernanceAction.REQUIRE_SIGNOFF else None,
                "status": record.status.value,
                "final_verdict": record.final_verdict.value
            }

        finally:
            store.close()

        return {
            "ok": True,
            "data": result,
            "error": None
        }

    except Exception as e:
        logger.exception("Error in check_can_proceed")
        return JSONResponse(
            status_code=500,
            content={"ok": False, "data": None, "error": str(e)}
        )


# 导入缺失的模块
import os
from datetime import datetime, timezone
