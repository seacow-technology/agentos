"""Decision timeline API (frozen contract + real read-path).

Backed by the unified audit/event store:
- compat_state.ensure_schema() creates compat_audit_events in OCTOPUSOS_DB_PATH SQLite.
- many existing endpoints already write audit_event(...) into that table.

Governance bridging (Phase 1.7+):
- Also synthesizes stable, auditable timeline items from Dispatch proposals
  (registry_db/dispatch_proposals), so Governance pages can be cross-linked
  by proposal_id with stable event_id/event_type semantics.

This endpoint is used by:
- /decision-timeline (apps/webui/src/pages/DecisionTimelinePage.tsx)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple, List

from fastapi import APIRouter, Query

from octopusos.core.dispatch import DispatchRepo
from octopusos.store.timestamp_utils import from_epoch_ms
from octopusos.webui.api.compat_state import db_connect, ensure_schema
from octopusos.webui.api._audit_allowlists import DECISION_EVENT_TYPES


router = APIRouter(prefix="/api", tags=["decision-timeline"])


def _iso_to_epoch_ms(value: str) -> int:
    raw = (value or "").strip()
    if not raw:
        return 0
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    except Exception:
        return 0


def _iso_from_ms(ms: int) -> str:
    dt = from_epoch_ms(ms)
    if dt is None:
        return ""
    return dt.isoformat().replace("+00:00", "Z")


def _safe_json_load(text: Optional[str]) -> Dict[str, Any]:
    if not text:
        return {}
    try:
        out = json.loads(text)
        return out if isinstance(out, dict) else {}
    except Exception:
        return {}


def _derive_decision(event_type: str, payload: Dict[str, Any], result: Dict[str, Any]) -> str:
    for src in (payload, result):
        v = (src.get("decision") or src.get("verdict") or "").strip()
        if isinstance(v, str) and v:
            return v
    et = (event_type or "").lower()
    if any(k in et for k in ["block", "reject", "deny"]):
        return "block"
    if "confirm" in et or "override" in et:
        return "confirm"
    return "allow"


def _derive_risk_level(event_type: str, payload: Dict[str, Any], result: Dict[str, Any]) -> str:
    for src in (payload, result):
        v = (src.get("risk_level") or src.get("risk") or "").strip()
        if isinstance(v, str) and v:
            return v.upper()
    et = (event_type or "").lower()
    if any(k in et for k in ["block", "reject", "deny", "critical"]):
        return "HIGH"
    if any(k in et for k in ["confirm", "override", "warn"]):
        return "MEDIUM"
    return "LOW"


def _build_where_clause(
    *,
    include_noise: bool,
    apply_allowlist: bool,
    q: Optional[str],
    status: Optional[str],
    session_id: Optional[str],
    risk_level: Optional[str],
) -> Tuple[str, List[Any]]:
    clauses: List[str] = []
    params: List[Any] = []

    if (not include_noise) and apply_allowlist:
        placeholders = ",".join(["?"] * len(DECISION_EVENT_TYPES))
        clauses.append(f"(event_type IN ({placeholders}))")
        params.extend(list(DECISION_EVENT_TYPES))

    if status:
        st = status.strip()
        if st:
            clauses.append("(payload_json LIKE ? OR result_json LIKE ?)")
            params.extend([f'%\"status\":\"{st}\"%', f'%\"status\":\"{st}\"%'])

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

    if risk_level:
        lvl = risk_level.strip().upper()
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


def _dispatch_snapshot_items(*, status: Optional[str], limit: int) -> List[Dict[str, Any]]:
    """Synthesize stable decision-timeline items from Dispatch proposals.

    Goal: enable cross-page linkage by proposal_id with stable event_id/event_type,
    without requiring a dedicated timeline table.
    """
    repo = DispatchRepo()
    repo.ensure_tables()

    proposals = repo.list_proposals(status=status, limit=min(max(limit, 1), 200))
    items: List[Dict[str, Any]] = []
    for p in proposals:
        event_type = "proposal_status_snapshot"
        event_id = f"dt_{p.proposal_id}_{event_type}"
        occurred_at = _iso_from_ms(p.updated_at or p.created_at)
        created_at = _iso_from_ms(p.created_at)

        items.append(
            {
                # Audit fields (used by Governance audit strong tier).
                "event_id": event_id,
                "event_type": event_type,
                "proposal_id": p.proposal_id,
                # Snapshot fields.
                "status": p.status,
                "risk_level": (p.risk_level or "").upper(),
                "occurred_at": occurred_at,
                # UI-friendly mapping (DecisionTimelinePage normalizes best-effort).
                "id": f"dp_{p.proposal_id}",
                "ts": int((p.updated_at or p.created_at) or 0),
                "decision": "allow",
                "reason_code": "dispatch_proposal",
                "summary": f"Dispatch proposal {p.proposal_id} status={p.status}",
                "session_id": "",
                "trace_id": "",
                "source": "dispatch",
                "timestamp": occurred_at or created_at,
                "context": p.proposal_type,
                "confidence": 1.0,
                "actor": p.requested_by,
            }
        )

    return items


@router.get("/decision-timeline")
def list_decision_timeline(
    q: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session_id: Optional[str] = Query(default=None),
    risk_level: Optional[str] = Query(default=None),
    include_noise: int = Query(default=0),
) -> Dict[str, Any]:
    conn = db_connect()
    try:
        ensure_schema(conn)
        where_sql, where_params = _build_where_clause(
            include_noise=bool(include_noise),
            apply_allowlist=True,
            q=q,
            status=status,
            session_id=session_id,
            risk_level=risk_level,
        )

        total_row = conn.execute(
            f"SELECT COUNT(*) AS c FROM compat_audit_events{where_sql}",
            where_params,
        ).fetchone()
        allow_total = int(total_row["c"] or 0) if total_row else 0

        dropped_total: Optional[int] = None
        unknown_event_types: Optional[list[dict[str, Any]]] = None
        base_total = allow_total
        if not include_noise:
            base_where_sql, base_where_params = _build_where_clause(
                include_noise=False,
                apply_allowlist=False,
                q=q,
                status=status,
                session_id=session_id,
                risk_level=risk_level,
            )
            base_total_row = conn.execute(
                f"SELECT COUNT(*) AS c FROM compat_audit_events{base_where_sql}",
                base_where_params,
            ).fetchone()
            base_total = int(base_total_row["c"] or 0) if base_total_row else 0
            dropped_total = max(0, base_total - allow_total)

            placeholders = ",".join(["?"] * len(DECISION_EVENT_TYPES))
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
                [*base_where_params, *list(DECISION_EVENT_TYPES)],
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

        items: list[Dict[str, Any]] = []
        for r in rows:
            event_type = str(r["event_type"] or "")
            payload = _safe_json_load(r["payload_json"])
            result = _safe_json_load(r["result_json"])

            derived_session = (
                payload.get("session_id")
                or payload.get("session")
                or result.get("session_id")
                or result.get("session")
                or ""
            )
            derived_risk = _derive_risk_level(event_type, payload, result)
            decision = _derive_decision(event_type, payload, result)
            ts_ms = _iso_to_epoch_ms(r["created_at"])
            trace_id = (
                payload.get("trace_id")
                or payload.get("run_id")
                or result.get("trace_id")
                or result.get("run_id")
                or ""
            )
            summary = payload.get("summary") or f"{event_type} {r['endpoint']}"

            # Frozen-contract fields + UI-friendly mapping.
            items.append(
                {
                    # Audit-friendly stable identifiers.
                    "event_id": str(r["event_id"] or ""),
                    "event_type": event_type,
                    "proposal_id": payload.get("proposal_id") or result.get("proposal_id") or "",
                    "id": f"dec_{r['event_id']}",
                    "ts": ts_ms,
                    "decision": decision,
                    "risk_level": derived_risk,
                    "reason_code": event_type,
                    "summary": summary,
                    "session_id": derived_session or "",
                    "trace_id": trace_id,
                    "source": "octopusos",
                    # DecisionTimelinePage mapping helpers
                    "timestamp": r["created_at"],
                    "context": str(r["endpoint"] or ""),
                    "confidence": 1.0,
                    "status": "recorded",
                    "actor": r["actor"],
                }
            )

        dispatch_items = _dispatch_snapshot_items(status=status, limit=limit)
        # Only include dispatch snapshots in noise/debug mode. The default view should be strictly allowlisted.
        dispatch_items = dispatch_items if include_noise else []
        merged_items = [*dispatch_items, *items]
        out: Dict[str, Any] = {
            "items": merged_items,
            "total": int(allow_total) + len(dispatch_items),
            "source": "octopusos",
        }
        if dropped_total is not None:
            out["dropped_total"] = dropped_total
        if unknown_event_types is not None:
            out["unknown_event_types"] = unknown_event_types

        if base_total == 0 and len(dispatch_items) == 0:
            out["hint"] = (
                "No decision-like audit events matched in compat_audit_events. "
                "Run a task to generate events or check OCTOPUSOS_DB_PATH / filters / include_noise."
            )
        return out
    finally:
        conn.close()
