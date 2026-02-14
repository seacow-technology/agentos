"""Runtime management API for execution alias mappings.

Execution aliases map WebUI "execution surfaces" (e.g. ssh.exec, sftp.transfer)
to OctopusOS v3 capability_ids (single SoT in core capability registry).

Phase 6 contract:
- Read endpoints always work (builtin/file/db resolution).
- Write endpoints require Admin Token + two-step confirm gate.
- If DB tables are not available, write endpoints must not 500; they return a
  policy gate: 409 gate_detail(error_code="ALIAS_DB_NOT_AVAILABLE").
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import base64
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from octopusos.core.capabilities.admin_token import validate_admin_token
from octopusos.core.capability.registry import get_capability_registry
from octopusos.core.time import utc_now_ms
from octopusos.webui.api import compat_state
from octopusos.webui.api._gate_errors import gate_detail
from octopusos.webui.api.shell import _audit_db_connect


router = APIRouter()

_ALIAS_RE = re.compile(r"^[a-z0-9_.-]{2,64}$")
_DB_INIT_CONFIRM_TTL_MS = 5 * 60 * 1000

# v3 capability SoT mapping for governance/audit metadata.
# - Writes: mutating runtime execution alias resolution (HIGH risk)
# - Reads: listing/exporting evidence about current alias mappings (LOW risk)
_CAP_WRITE = "action.file.write"
_CAP_READ = "evidence.query"
_RISK_WRITE = "HIGH"
_RISK_READ = "LOW"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _audit(event_type: str, *, endpoint: str, payload: Any, result: Any) -> None:
    conn: Optional[sqlite3.Connection] = None
    try:
        conn = _audit_db_connect()
        compat_state.ensure_schema(conn)
        compat_state.audit_event(
            conn,
            event_type=event_type,
            endpoint=endpoint,
            actor="webui",
            payload=payload,
            result=result,
        )
        conn.commit()
    finally:
        if conn is not None:
            conn.close()


def _require_admin_token(admin_token: Optional[str]) -> str:
    token = (admin_token or "").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Admin token required")
    if not validate_admin_token(token):
        raise HTTPException(status_code=403, detail="Invalid admin token")
    return token


def _token_fingerprint(admin_token: str) -> str:
    return hashlib.sha256(admin_token.encode("utf-8")).hexdigest()[:12]


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64url_decode(s: str) -> bytes:
    pad = "=" * ((4 - (len(s) % 4)) % 4)
    return base64.urlsafe_b64decode((s + pad).encode("ascii"))


def _make_confirm_token(*, admin_token: str, payload: Dict[str, object]) -> str:
    # Stateless token: payload + HMAC(admin_token, payload_json)
    # This avoids needing any DB table before db/init creates it.
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    sig = hmac.new(admin_token.encode("utf-8"), blob, hashlib.sha256).hexdigest()
    return f"{_b64url_encode(blob)}.{sig}"


def _verify_confirm_token(*, admin_token: str, confirm_token: str) -> Dict[str, object]:
    try:
        part, sig = confirm_token.split(".", 1)
        blob = _b64url_decode(part)
        expected = hmac.new(admin_token.encode("utf-8"), blob, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            raise ValueError("bad sig")
        obj = json.loads(blob.decode("utf-8"))
        if not isinstance(obj, dict):
            raise ValueError("bad payload")
        return obj
    except Exception as e:
        raise HTTPException(
            status_code=409,
            detail=gate_detail(
                error_code="INVALID_CONFIRM_TOKEN",
                gate="confirm",
                message="invalid confirm token",
                capability_id=_CAP_WRITE,
                risk_tier=_RISK_WRITE,
            ),
        ) from e


def _connect_registry_db() -> sqlite3.Connection:
    reg = get_capability_registry()
    conn = sqlite3.connect(str(reg.db_path), timeout=5)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 5000")
    except Exception:
        pass
    return conn


def _has_table(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _ensure_alias_db_available_or_gate(conn: sqlite3.Connection, *, endpoint: str) -> None:
    missing: List[str] = []
    if not _has_table(conn, "execution_aliases"):
        missing.append("execution_aliases")
    if not _has_table(conn, "execution_alias_change_requests"):
        missing.append("execution_alias_change_requests")
    if missing:
        raise HTTPException(
            status_code=409,
            detail=gate_detail(
                error_code="ALIAS_DB_NOT_AVAILABLE",
                gate="policy",
                message="Execution alias DB tables not available. Initialize schema before writes.",
                context={"missing_tables": missing},
                capability_id=_CAP_WRITE,
                risk_tier=_RISK_WRITE,
            ),
        )


class ExecutionAliasResolved(BaseModel):
    alias: str
    capability_id: str
    requires_trust: bool
    requires_confirm: bool
    source: str


class ExecutionAliasesListOut(BaseModel):
    ok: bool = True
    total: int
    items: List[ExecutionAliasResolved]


class ExecutionAliasUpsertIn(BaseModel):
    alias: str = Field(..., min_length=2, max_length=64)
    capability_id: str = Field(..., min_length=2, max_length=128)
    requires_trust: bool = False
    requires_confirm: bool = False
    confirm: bool = False
    confirm_token: Optional[str] = None
    reason: Optional[str] = None


class ExecutionAliasDeleteIn(BaseModel):
    confirm: bool = False
    confirm_token: Optional[str] = None
    reason: Optional[str] = None


class ExecutionAliasDbInitIn(BaseModel):
    confirm: bool = False
    confirm_token: Optional[str] = None
    reason: Optional[str] = None


def _validate_alias_inputs(*, alias: str, capability_id: str) -> None:
    if not _ALIAS_RE.fullmatch(alias):
        raise HTTPException(status_code=400, detail="invalid alias format")
    reg = get_capability_registry()
    if not reg.get_capability(capability_id):
        raise HTTPException(status_code=400, detail="unknown capability_id")


def _resolved_or_404(alias: str) -> Dict[str, object]:
    reg = get_capability_registry()
    reg.load_execution_aliases()
    resolved = reg.resolve_execution_alias(alias)
    if not resolved:
        raise HTTPException(status_code=404, detail="alias not found")
    return resolved


@router.get("/api/execution/aliases", response_model=ExecutionAliasesListOut)
def list_execution_aliases(source: Optional[str] = Query(default=None)) -> Dict[str, Any]:
    reg = get_capability_registry()
    reg.load_execution_aliases()
    items: List[Dict[str, object]] = []
    # registry doesn't expose a public iterator; keep it internal and stable by
    # using resolve() for each known alias.
    aliases = sorted(list(getattr(reg, "_execution_alias_index", {}).keys()))
    for a in aliases:
        r = reg.resolve_execution_alias(a)
        if not r:
            continue
        if source and str(r.get("source") or "") != source:
            continue
        items.append(r)
    return {"ok": True, "total": len(items), "items": items}

@router.post("/api/execution/aliases", response_model=ExecutionAliasResolved)
def upsert_execution_alias(
    payload: ExecutionAliasUpsertIn,
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> Dict[str, Any]:
    token = _require_admin_token(admin_token)
    alias = payload.alias.strip()
    cap_id = payload.capability_id.strip()
    _validate_alias_inputs(alias=alias, capability_id=cap_id)

    conn = _connect_registry_db()
    try:
        _ensure_alias_db_available_or_gate(conn, endpoint="/api/execution/aliases")

        if not payload.confirm:
            request_id = uuid4().hex
            now = _now_iso()
            conn.execute(
                """
                INSERT INTO execution_alias_change_requests (request_id, op, payload_json, status, reason, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    "UPSERT",
                    json.dumps(
                        {
                            "alias": alias,
                            "capability_id": cap_id,
                            "requires_trust": bool(payload.requires_trust),
                            "requires_confirm": bool(payload.requires_confirm),
                        },
                        sort_keys=True,
                    ),
                    "CONFIRM_REQUIRED",
                    None,
                    now,
                    now,
                ),
            )
            conn.commit()

            _audit(
                "execution_aliases.upsert.confirm_required",
                endpoint="/api/execution/aliases",
                payload={
                    "alias": alias,
                    "capability_id": cap_id,
                    "requires_trust": bool(payload.requires_trust),
                    "requires_confirm": bool(payload.requires_confirm),
                    "request_id": request_id,
                    "capability_id": _CAP_WRITE,
                    "risk_tier": _RISK_WRITE,
                },
                result={"ok": False, "error_code": "CONFIRM_REQUIRED"},
            )
            raise HTTPException(
                status_code=409,
                detail=gate_detail(
                    error_code="CONFIRM_REQUIRED",
                    gate="confirm",
                    confirm_token=request_id,
                    message="High-risk operation. Re-submit with confirm=true, confirm_token, and reason to proceed.",
                    context={
                        "request_id": request_id,
                        "op": "UPSERT",
                        "alias": alias,
                        "capability_id": cap_id,
                        "requires_trust": bool(payload.requires_trust),
                        "requires_confirm": bool(payload.requires_confirm),
                    },
                    capability_id=_CAP_WRITE,
                    risk_tier=_RISK_WRITE,
                ),
            )

        confirm_token = (payload.confirm_token or "").strip()
        if not confirm_token:
            raise HTTPException(status_code=400, detail="missing confirm_token")
        reason = (payload.reason or "").strip()
        if len(reason) < 10:
            raise HTTPException(status_code=400, detail="reason required (min 10 chars)")

        row = conn.execute(
            "SELECT request_id, op, payload_json, status FROM execution_alias_change_requests WHERE request_id = ?",
            (confirm_token,),
        ).fetchone()
        if not row or str(row["status"]) != "CONFIRM_REQUIRED" or str(row["op"]) != "UPSERT":
            raise HTTPException(
                status_code=409,
                detail=gate_detail(
                    error_code="INVALID_CONFIRM_TOKEN",
                    gate="confirm",
                    message="confirm token not found or already used",
                    context={"request_id": confirm_token, "op": "UPSERT", "alias": alias},
                    capability_id=_CAP_WRITE,
                    risk_tier=_RISK_WRITE,
                ),
            )

        try:
            stored = json.loads(str(row["payload_json"] or "{}"))
        except Exception:
            stored = {}
        if (
            str(stored.get("alias") or "") != alias
            or str(stored.get("capability_id") or "") != cap_id
            or bool(stored.get("requires_trust", False)) != bool(payload.requires_trust)
            or bool(stored.get("requires_confirm", False)) != bool(payload.requires_confirm)
        ):
            raise HTTPException(
                status_code=409,
                detail=gate_detail(
                    error_code="INVALID_CONFIRM_TOKEN",
                    gate="confirm",
                    message="payload mismatch",
                    context={"request_id": confirm_token, "op": "UPSERT", "alias": alias},
                    capability_id=_CAP_WRITE,
                    risk_tier=_RISK_WRITE,
                ),
            )

        now_ms = int(utc_now_ms())
        updated_by = f"admin:{_token_fingerprint(token)}"
        conn.execute(
            """
            INSERT INTO execution_aliases (alias, capability_id, requires_trust, requires_confirm, updated_at, updated_by, source)
            VALUES (?, ?, ?, ?, ?, ?, 'db')
            ON CONFLICT(alias) DO UPDATE SET
                capability_id=excluded.capability_id,
                requires_trust=excluded.requires_trust,
                requires_confirm=excluded.requires_confirm,
                updated_at=excluded.updated_at,
                updated_by=excluded.updated_by,
                source='db'
            """,
            (
                alias,
                cap_id,
                1 if payload.requires_trust else 0,
                1 if payload.requires_confirm else 0,
                now_ms,
                updated_by,
            ),
        )
        conn.execute(
            "UPDATE execution_alias_change_requests SET status = ?, reason = ?, updated_at = ? WHERE request_id = ?",
            ("COMPLETED", reason, _now_iso(), confirm_token),
        )
        conn.commit()
    finally:
        conn.close()

    reg = get_capability_registry()
    reg.load_execution_aliases()
    resolved = reg.resolve_execution_alias(alias) or {}

    _audit(
        "execution_aliases.upsert",
        endpoint="/api/execution/aliases",
        payload={
            "alias": alias,
            "capability_id": cap_id,
            "requires_trust": bool(payload.requires_trust),
            "requires_confirm": bool(payload.requires_confirm),
            "confirm_token": confirm_token,
            "reason": (payload.reason or "").strip(),
            "updated_by": f"admin:{_token_fingerprint(token)}",
            "capability_id": _CAP_WRITE,
            "risk_tier": _RISK_WRITE,
        },
        result={"ok": True, "source": str(resolved.get("source") or "unknown")},
    )
    return resolved

@router.post("/api/execution/aliases/reload")
def reload_execution_aliases(
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> Dict[str, Any]:
    _require_admin_token(admin_token)
    reg = get_capability_registry()
    reg.load_execution_aliases()
    items = []
    aliases = sorted(list(getattr(reg, "_execution_alias_index", {}).keys()))
    for a in aliases:
        r = reg.resolve_execution_alias(a)
        if r:
            items.append(r)
    sources: Dict[str, int] = {}
    for r in items:
        sources[str(r.get("source") or "unknown")] = sources.get(str(r.get("source") or "unknown"), 0) + 1

    _audit(
        "execution_aliases.reload",
        endpoint="/api/execution/aliases/reload",
        payload={"capability_id": _CAP_WRITE, "risk_tier": _RISK_WRITE},
        result={"ok": True, "total": len(items), "sources": sources},
    )
    return {"ok": True, "total": len(items), "sources": sources}


@router.get("/api/execution/aliases/export")
def export_execution_aliases(source: Optional[str] = Query(default=None)) -> Dict[str, Any]:
    reg = get_capability_registry()
    reg.load_execution_aliases()
    items: List[Dict[str, object]] = []
    aliases = sorted(list(getattr(reg, "_execution_alias_index", {}).keys()))
    for a in aliases:
        r = reg.resolve_execution_alias(a)
        if not r:
            continue
        if source and str(r.get("source") or "") != source:
            continue
        items.append(r)

    generated_at = _now_iso()
    blob = json.dumps(
        {"generated_at": generated_at, "filters": {"source": source}, "items": items, "total": len(items)},
        ensure_ascii=False,
        sort_keys=True,
    ).encode("utf-8")
    sha = hashlib.sha256(blob).hexdigest()
    export_id = sha[:16]
    out_dir = Path(os.getcwd()) / "output" / "execution_aliases_exports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{export_id}.json"
    out_path.write_bytes(blob)

    _audit(
        "execution_aliases.export",
        endpoint="/api/execution/aliases/export",
        payload={"source": source, "capability_id": _CAP_READ, "risk_tier": _RISK_READ},
        result={"ok": True, "sha256": sha, "export_id": export_id},
    )
    return {
        "ok": True,
        "export_id": export_id,
        "sha256": sha,
        "generated_at": generated_at,
        "download_url": f"/api/execution/aliases/exports/{export_id}",
    }


@router.get("/api/execution/aliases/exports/{export_id}")
def download_execution_aliases_export(export_id: str):
    out_path = Path(os.getcwd()) / "output" / "execution_aliases_exports" / f"{export_id}.json"
    if not out_path.exists():
        raise HTTPException(status_code=404, detail="export not found")
    return StreamingResponse(out_path.open("rb"), media_type="application/json")


@router.post("/api/execution/aliases/db/init")
def init_execution_aliases_db(
    payload: ExecutionAliasDbInitIn,
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> Dict[str, Any]:
    token = _require_admin_token(admin_token)

    tables = ["execution_aliases", "execution_alias_change_requests"]

    if not payload.confirm:
        now_ms = int(utc_now_ms())
        confirm_payload = {
            "op": "db.init",
            "ts_ms": now_ms,
            "exp_ms": now_ms + int(_DB_INIT_CONFIRM_TTL_MS),
            "tables": tables,
            "admin_fp": _token_fingerprint(token),
            "nonce": uuid4().hex,
        }
        confirm_token = _make_confirm_token(admin_token=token, payload=confirm_payload)

        _audit(
            "execution_aliases.db_init.confirm_required",
            endpoint="/api/execution/aliases/db/init",
            payload={"tables": tables, "capability_id": _CAP_WRITE, "risk_tier": _RISK_WRITE},
            result={"ok": False, "error_code": "CONFIRM_REQUIRED"},
        )
        raise HTTPException(
            status_code=409,
            detail=gate_detail(
                error_code="CONFIRM_REQUIRED",
                gate="confirm",
                confirm_token=confirm_token,
                message="High-risk operation. Re-submit with confirm=true, confirm_token, and reason to proceed.",
                context={"op": "db.init", "tables": tables},
                capability_id=_CAP_WRITE,
                risk_tier=_RISK_WRITE,
            ),
        )

    confirm_token = (payload.confirm_token or "").strip()
    if not confirm_token:
        raise HTTPException(status_code=400, detail="missing confirm_token")
    reason = (payload.reason or "").strip()
    if len(reason) < 10:
        raise HTTPException(status_code=400, detail="reason required (min 10 chars)")

    decoded = _verify_confirm_token(admin_token=token, confirm_token=confirm_token)
    if str(decoded.get("op") or "") != "db.init":
        raise HTTPException(
            status_code=409,
            detail=gate_detail(
                error_code="INVALID_CONFIRM_TOKEN",
                gate="confirm",
                message="payload mismatch",
                context={"op": decoded.get("op")},
                capability_id=_CAP_WRITE,
                risk_tier=_RISK_WRITE,
            ),
        )
    exp_ms = int(decoded.get("exp_ms") or 0)
    if exp_ms and int(utc_now_ms()) > exp_ms:
        raise HTTPException(
            status_code=409,
            detail=gate_detail(
                error_code="INVALID_CONFIRM_TOKEN",
                gate="confirm",
                message="token expired",
                capability_id=_CAP_WRITE,
                risk_tier=_RISK_WRITE,
            ),
        )

    conn = _connect_registry_db()
    try:
        existed_aliases = _has_table(conn, "execution_aliases")
        existed_reqs = _has_table(conn, "execution_alias_change_requests")
        already = existed_aliases and existed_reqs

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS execution_aliases (
                alias TEXT PRIMARY KEY,
                capability_id TEXT NOT NULL,
                requires_trust INTEGER NOT NULL,
                requires_confirm INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                updated_by TEXT NOT NULL,
                source TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS execution_alias_change_requests (
                request_id TEXT PRIMARY KEY,
                op TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                status TEXT NOT NULL,
                reason TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()

    reg = get_capability_registry()
    reg.load_execution_aliases()

    status = "ALREADY_INITIALIZED" if already else "INITIALIZED"
    _audit(
        "execution_aliases.db_init",
        endpoint="/api/execution/aliases/db/init",
        payload={"tables": tables, "status": status, "reason": reason, "capability_id": _CAP_WRITE, "risk_tier": _RISK_WRITE},
        result={"ok": True},
    )
    return {"ok": True, "status": status, "tables": tables, "db": "registry", "reloaded": True}


@router.get("/api/execution/aliases/{alias}", response_model=ExecutionAliasResolved)
def get_execution_alias(alias: str) -> Dict[str, Any]:
    return _resolved_or_404(alias)


@router.delete("/api/execution/aliases/{alias}")
def delete_execution_alias(
    alias: str,
    payload: ExecutionAliasDeleteIn,
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> Dict[str, Any]:
    token = _require_admin_token(admin_token)
    alias = alias.strip()
    if not _ALIAS_RE.fullmatch(alias):
        raise HTTPException(status_code=400, detail="invalid alias format")

    conn = _connect_registry_db()
    try:
        _ensure_alias_db_available_or_gate(conn, endpoint=f"/api/execution/aliases/{alias}")

        if not payload.confirm:
            request_id = uuid4().hex
            now = _now_iso()
            conn.execute(
                """
                INSERT INTO execution_alias_change_requests (request_id, op, payload_json, status, reason, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    "DELETE",
                    json.dumps({"alias": alias}, sort_keys=True),
                    "CONFIRM_REQUIRED",
                    None,
                    now,
                    now,
                ),
            )
            conn.commit()

            _audit(
                "execution_aliases.delete.confirm_required",
                endpoint=f"/api/execution/aliases/{alias}",
                payload={
                    "alias": alias,
                    "request_id": request_id,
                    "capability_id": _CAP_WRITE,
                    "risk_tier": _RISK_WRITE,
                },
                result={"ok": False, "error_code": "CONFIRM_REQUIRED"},
            )
            raise HTTPException(
                status_code=409,
                detail=gate_detail(
                    error_code="CONFIRM_REQUIRED",
                    gate="confirm",
                    confirm_token=request_id,
                    message="High-risk operation. Re-submit with confirm=true, confirm_token, and reason to proceed.",
                    context={"request_id": request_id, "op": "DELETE", "alias": alias},
                    capability_id=_CAP_WRITE,
                    risk_tier=_RISK_WRITE,
                ),
            )

        confirm_token = (payload.confirm_token or "").strip()
        if not confirm_token:
            raise HTTPException(status_code=400, detail="missing confirm_token")
        reason = (payload.reason or "").strip()
        if len(reason) < 10:
            raise HTTPException(status_code=400, detail="reason required (min 10 chars)")

        row = conn.execute(
            "SELECT request_id, op, payload_json, status FROM execution_alias_change_requests WHERE request_id = ?",
            (confirm_token,),
        ).fetchone()
        if not row or str(row["status"]) != "CONFIRM_REQUIRED" or str(row["op"]) != "DELETE":
            raise HTTPException(
                status_code=409,
                detail=gate_detail(
                    error_code="INVALID_CONFIRM_TOKEN",
                    gate="confirm",
                    message="confirm token not found or already used",
                    context={"request_id": confirm_token, "op": "DELETE", "alias": alias},
                    capability_id=_CAP_WRITE,
                    risk_tier=_RISK_WRITE,
                ),
            )

        try:
            stored = json.loads(str(row["payload_json"] or "{}"))
        except Exception:
            stored = {}
        if str(stored.get("alias") or "") != alias:
            raise HTTPException(
                status_code=409,
                detail=gate_detail(
                    error_code="INVALID_CONFIRM_TOKEN",
                    gate="confirm",
                    message="payload mismatch",
                    context={"request_id": confirm_token, "op": "DELETE", "alias": alias},
                    capability_id=_CAP_WRITE,
                    risk_tier=_RISK_WRITE,
                ),
            )

        conn.execute("DELETE FROM execution_aliases WHERE alias = ?", (alias,))
        conn.execute(
            "UPDATE execution_alias_change_requests SET status = ?, reason = ?, updated_at = ? WHERE request_id = ?",
            ("COMPLETED", reason, _now_iso(), confirm_token),
        )
        conn.commit()
    finally:
        conn.close()

    reg = get_capability_registry()
    reg.load_execution_aliases()

    _audit(
        "execution_aliases.delete",
        endpoint=f"/api/execution/aliases/{alias}",
        payload={
            "alias": alias,
            "confirm_token": confirm_token,
            "reason": (payload.reason or "").strip(),
            "updated_by": f"admin:{_token_fingerprint(token)}",
            "capability_id": _CAP_WRITE,
            "risk_tier": _RISK_WRITE,
        },
        result={"ok": True},
    )
    return {"ok": True, "alias": alias}
