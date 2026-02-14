"""Action log API.

Goal: Make /action-log page a real read-path backed by existing audit/event store.

Data source (minimal + stable):
- compat_state.ensure_schema() creates compat_audit_events in the unified OCTOPUSOS_DB_PATH SQLite.
- many existing endpoints already write audit_event(...) into that table.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple, List

from fastapi import APIRouter, Query

from octopusos.webui.api.compat_state import db_connect, ensure_schema
from octopusos.webui.api._audit_allowlists import ACTION_EVENT_TYPES


router = APIRouter(prefix="/api", tags=["action-log"])

def _iso_to_epoch_ms(value: str) -> int:
    raw = (value or "").strip()
    if not raw:
        return 0
    try:
        # compat_state.now_iso() uses timezone-aware isoformat, but normalize just in case.
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    except Exception:
        return 0


def _safe_json_load(text: Optional[str]) -> Dict[str, Any]:
    if not text:
        return {}
    try:
        out = json.loads(text)
        return out if isinstance(out, dict) else {}
    except Exception:
        return {}


def _derive_risk_level(event_type: str, payload: Dict[str, Any], result: Dict[str, Any]) -> str:
    for src in (payload, result):
        v = (src.get("risk_level") or src.get("risk") or "").strip()
        if isinstance(v, str) and v:
            return v.upper()
    et = (event_type or "").lower()
    if any(k in et for k in ["block", "reject", "deny", "forbid", "critical"]):
        return "HIGH"
    if any(k in et for k in ["confirm", "override", "warn"]):
        return "MEDIUM"
    return "LOW"


def _derive_verdict(event_type: str, payload: Dict[str, Any], result: Dict[str, Any]) -> str:
    for src in (result, payload):
        v = (src.get("verdict") or src.get("decision") or "").strip()
        if isinstance(v, str) and v:
            return v
    et = (event_type or "").lower()
    if any(k in et for k in ["block", "reject", "deny"]):
        return "blocked"
    if "confirm" in et:
        return "confirmed"
    return "allowed"

def _build_where_clause(
    *,
    include_noise: bool,
    apply_allowlist: bool,
    session_id: Optional[str],
    capability: Optional[str],
    level: Optional[str],
    verdict: Optional[str],
    q: Optional[str],
) -> Tuple[str, List[Any]]:
    clauses: List[str] = []
    params: List[Any] = []

    if (not include_noise) and apply_allowlist:
        placeholders = ",".join(["?"] * len(ACTION_EVENT_TYPES))
        clauses.append(f"(event_type IN ({placeholders}))")
        params.extend(list(ACTION_EVENT_TYPES))

    if session_id:
        sid = session_id.strip()
        if sid:
            clauses.append(
                "("
                + " OR ".join(
                    [
                        "payload_json LIKE ?",
                        "result_json LIKE ?",
                        "payload_json LIKE ?",
                        "result_json LIKE ?",
                    ]
                )
                + ")"
            )
            params.extend(
                [
                    f'%\"session_id\":\"{sid}\"%',
                    f'%\"session_id\":\"{sid}\"%',
                    f'%\"session\":\"{sid}\"%',
                    f'%\"session\":\"{sid}\"%',
                ]
            )

    if capability:
        cap = capability.strip()
        if cap:
            clauses.append(
                "("
                + " OR ".join(
                    [
                        "payload_json LIKE ?",
                        "payload_json LIKE ?",
                        "payload_json LIKE ?",
                        "payload_json LIKE ?",
                    ]
                )
                + ")"
            )
            params.extend(
                [
                    f'%\"capability\":\"{cap}\"%',
                    f'%\"capability_id\":\"{cap}\"%',
                    f'%\"provider\":\"{cap}\"%',
                    f'%\"channel_id\":\"{cap}\"%',
                ]
            )

    if level:
        lvl = level.strip().upper()
        if lvl:
            clauses.append(
                "("
                + " OR ".join(
                    [
                        "payload_json LIKE ?",
                        "result_json LIKE ?",
                        "payload_json LIKE ?",
                        "result_json LIKE ?",
                    ]
                )
                + ")"
            )
            params.extend(
                [
                    f'%\"risk_level\":\"{lvl}\"%',
                    f'%\"risk_level\":\"{lvl}\"%',
                    f'%\"risk\":\"{lvl}\"%',
                    f'%\"risk\":\"{lvl}\"%',
                ]
            )

    if verdict:
        v = verdict.strip()
        if v:
            clauses.append(
                "("
                + " OR ".join(
                    [
                        "payload_json LIKE ?",
                        "result_json LIKE ?",
                        "payload_json LIKE ?",
                        "result_json LIKE ?",
                    ]
                )
                + ")"
            )
            params.extend(
                [
                    f'%\"verdict\":\"{v}\"%',
                    f'%\"verdict\":\"{v}\"%',
                    f'%\"decision\":\"{v}\"%',
                    f'%\"decision\":\"{v}\"%',
                ]
            )

    if q:
        needle = q.strip()
        if needle:
            clauses.append(
                "("
                + " OR ".join(
                    [
                        "event_type LIKE ?",
                        "endpoint LIKE ?",
                        "actor LIKE ?",
                        "payload_json LIKE ?",
                    ]
                )
                + ")"
            )
            pat = f"%{needle}%"
            params.extend([pat, pat, pat, pat])

    where_sql = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where_sql, params


@router.get("/action-log")
def list_action_log(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session_id: Optional[str] = Query(default=None),
    capability: Optional[str] = Query(default=None),
    level: Optional[str] = Query(default=None),
    verdict: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None),
    include_noise: int = Query(default=0),
) -> Dict[str, Any]:
    conn = db_connect()
    try:
        ensure_schema(conn)

        where_sql, where_params = _build_where_clause(
            include_noise=bool(include_noise),
            apply_allowlist=True,
            session_id=session_id,
            capability=capability,
            level=level,
            verdict=verdict,
            q=q,
        )

        total_row = conn.execute(
            f"SELECT COUNT(*) AS c FROM compat_audit_events{where_sql}",
            where_params,
        ).fetchone()
        total = int(total_row["c"] or 0) if total_row else 0

        dropped_total: Optional[int] = None
        unknown_event_types: Optional[list[dict[str, Any]]] = None
        if not include_noise:
            base_where_sql, base_where_params = _build_where_clause(
                include_noise=False,
                apply_allowlist=False,
                session_id=session_id,
                capability=capability,
                level=level,
                verdict=verdict,
                q=q,
            )
            base_total_row = conn.execute(
                f"SELECT COUNT(*) AS c FROM compat_audit_events{base_where_sql}",
                base_where_params,
            ).fetchone()
            base_total = int(base_total_row["c"] or 0) if base_total_row else 0
            dropped_total = max(0, base_total - total)

            placeholders = ",".join(["?"] * len(ACTION_EVENT_TYPES))
            unknown_where = base_where_sql + (" AND " if base_where_sql else " WHERE ") + f"(event_type NOT IN ({placeholders}))"
            unknown_rows = conn.execute(
                f"""
                SELECT event_type, COUNT(*) AS c
                FROM compat_audit_events
                {unknown_where}
                GROUP BY event_type
                ORDER BY c DESC
                LIMIT 10
                """,
                [*base_where_params, *list(ACTION_EVENT_TYPES)],
            ).fetchall()
            unknown_event_types = [{"event_type": str(r["event_type"]), "count": int(r["c"] or 0)} for r in unknown_rows]

        rows = conn.execute(
            """
            SELECT event_id, event_type, endpoint, actor, payload_json, result_json, created_at
            FROM compat_audit_events
            """
            + where_sql
            + """
            ORDER BY event_id DESC
            LIMIT ? OFFSET ?
            """,
            [*where_params, limit, offset],
        ).fetchall()

        items = []
        for r in rows:
            payload = _safe_json_load(r["payload_json"])
            result = _safe_json_load(r["result_json"])

            derived_session = (
                payload.get("session_id")
                or payload.get("session")
                or result.get("session_id")
                or result.get("session")
                or ""
            )
            derived_capability = (
                payload.get("capability")
                or payload.get("capability_id")
                or payload.get("provider")
                or payload.get("channel_id")
                or ""
            )

            risk_level = _derive_risk_level(r["event_type"], payload, result)
            derived_verdict = _derive_verdict(r["event_type"], payload, result)

            ts_ms = _iso_to_epoch_ms(r["created_at"])
            trace_id = (
                payload.get("trace_id")
                or payload.get("run_id")
                or result.get("trace_id")
                or result.get("run_id")
                or ""
            )
            action = payload.get("action") or payload.get("operation") or r["event_type"] or ""

            items.append(
                {
                    "id": f"evt_{r['event_id']}",
                    "ts": ts_ms,
                    "actor": r["actor"],
                    "event_type": str(r["event_type"] or ""),
                    "endpoint": str(r["endpoint"] or ""),
                    "capability": derived_capability or "octopusos",
                    "action": action,
                    "risk_level": risk_level,
                    "verdict": derived_verdict,
                    "session_id": derived_session or "",
                    "trace_id": trace_id,
                    "summary": payload.get("summary") or f"{r['event_type']} {r['endpoint']}",
                }
            )

        out: Dict[str, Any] = {"items": items, "total": total, "source": "octopusos"}
        if dropped_total is not None:
            out["dropped_total"] = dropped_total
        if unknown_event_types is not None:
            out["unknown_event_types"] = unknown_event_types
        if total == 0:
            out["hint"] = (
                "No audit events matched in compat_audit_events. "
                "Run a task to generate events or check OCTOPUSOS_DB_PATH / filters / include_noise."
            )
        return out
    finally:
        conn.close()
