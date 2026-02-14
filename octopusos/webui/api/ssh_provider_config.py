"""SSH provider selection governance API.

This module exposes a governable config surface for choosing the SSH/SFTP
provider implementation (probe/system/mcp) using a resolver with sources:
builtin < file < db < env.

Contract:
- Reads always work (even when DB tables are missing).
- Writes require Admin Token + two-step confirm gate + reason(minLen=10).
- DB init is a HIGH-risk two-step confirm using a stateless HMAC token (so it
  works before tables exist).
- Evidence export produces a sha256-addressed JSON artifact with download_url.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from octopusos.core.capabilities.admin_token import validate_admin_token
from octopusos.core.capability.registry import get_capability_registry
from octopusos.core.providers.ssh_provider_registry import (
    get_ssh_provider_sources,
    reload_ssh_provider_config,
    resolve_ssh_provider,
)
from octopusos.core.time import utc_now_ms
from octopusos.webui.api import compat_state
from octopusos.webui.api._gate_errors import gate_detail
from octopusos.webui.api.shell import _audit_db_connect


router = APIRouter()

_CAP_WRITE = "action.file.write"
_CAP_READ = "evidence.query"
_RISK_WRITE = "HIGH"
_RISK_READ = "LOW"

_CONFIRM_TTL_MS = 5 * 60 * 1000

_ALLOWED = {"probe", "system", "mcp"}


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
    return conn


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _ensure_db_available_or_gate(conn: sqlite3.Connection) -> None:
    if not _table_exists(conn, "ssh_provider_config"):
        raise HTTPException(
            status_code=409,
            detail=gate_detail(
                error_code="SSH_PROVIDER_DB_NOT_AVAILABLE",
                gate="policy",
                message="SSH provider config table not available. Initialize schema before writes.",
                context={"missing_tables": ["ssh_provider_config"]},
                capability_id=_CAP_WRITE,
                risk_tier=_RISK_WRITE,
            ),
        )


class SshProviderOut(BaseModel):
    provider: str
    source: str
    allow_real: bool = False
    mcp_profile: Optional[str] = None
    effective_at: int
    requires_restart: bool = False


class SshProviderSourcesOut(BaseModel):
    ok: bool = True
    sources: Dict[str, Any]


class SshProviderUpsertIn(BaseModel):
    provider: str = Field(..., min_length=2, max_length=32)
    allow_real: bool = False
    mcp_profile: Optional[str] = Field(default=None, max_length=128)
    confirm: bool = False
    confirm_token: Optional[str] = None
    reason: Optional[str] = None


class DbInitIn(BaseModel):
    confirm: bool = False
    confirm_token: Optional[str] = None
    reason: Optional[str] = None


def _normalize_provider(v: str) -> str:
    s = (v or "").strip().lower()
    return s if s in _ALLOWED else "probe"


@router.get("/api/providers/ssh", response_model=SshProviderOut)
def get_effective_ssh_provider() -> Dict[str, Any]:
    eff = resolve_ssh_provider()
    return eff.to_dict()


@router.get("/api/providers/ssh/sources", response_model=SshProviderSourcesOut)
def get_ssh_provider_sources_api() -> Dict[str, Any]:
    # Do not include secrets; current schema has none.
    return {"ok": True, "sources": get_ssh_provider_sources()}


@router.post("/api/providers/ssh", response_model=SshProviderOut)
def upsert_ssh_provider(
    payload: SshProviderUpsertIn,
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> Dict[str, Any]:
    token = _require_admin_token(admin_token)
    provider = _normalize_provider(payload.provider)
    allow_real = bool(payload.allow_real)
    mcp_profile = (payload.mcp_profile or "").strip() or None

    if provider == "probe":
        allow_real = False
        mcp_profile = None
    if provider != "mcp":
        mcp_profile = None

    if not payload.confirm:
        now_ms = int(utc_now_ms())
        confirm_payload = {
            "op": "ssh_provider.upsert",
            "ts_ms": now_ms,
            "exp_ms": now_ms + int(_CONFIRM_TTL_MS),
            "provider": provider,
            "allow_real": bool(allow_real),
            "mcp_profile": mcp_profile,
            "admin_fp": _token_fingerprint(token),
            "nonce": uuid4().hex,
        }
        confirm_token = _make_confirm_token(admin_token=token, payload=confirm_payload)

        _audit(
            "ssh_provider.upsert.confirm_required",
            endpoint="/api/providers/ssh",
            payload={"provider": provider, "allow_real": bool(allow_real), "mcp_profile": mcp_profile, "capability_id": _CAP_WRITE, "risk_tier": _RISK_WRITE},
            result={"ok": False, "error_code": "CONFIRM_REQUIRED"},
        )
        raise HTTPException(
            status_code=409,
            detail=gate_detail(
                error_code="CONFIRM_REQUIRED",
                gate="confirm",
                confirm_token=confirm_token,
                message="High-risk operation. Re-submit with confirm=true, confirm_token, and reason to proceed.",
                context={"op": "ssh_provider.upsert", "provider": provider, "allow_real": bool(allow_real), "mcp_profile": mcp_profile},
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
    if str(decoded.get("op") or "") != "ssh_provider.upsert":
        raise HTTPException(
            status_code=409,
            detail=gate_detail(
                error_code="INVALID_CONFIRM_TOKEN",
                gate="confirm",
                message="payload mismatch",
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
    if (
        _normalize_provider(str(decoded.get("provider") or "")) != provider
        or bool(decoded.get("allow_real", False)) != bool(allow_real)
        or (str(decoded.get("mcp_profile") or "").strip() or None) != mcp_profile
    ):
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

    # Apply DB write if available.
    conn = _connect_registry_db()
    try:
        _ensure_db_available_or_gate(conn)
        updated_by = f"admin:{_token_fingerprint(token)}"
        conn.execute(
            """
            INSERT INTO ssh_provider_config (id, provider, allow_real, mcp_profile, updated_at, updated_by)
            VALUES (1, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              provider=excluded.provider,
              allow_real=excluded.allow_real,
              mcp_profile=excluded.mcp_profile,
              updated_at=excluded.updated_at,
              updated_by=excluded.updated_by
            """,
            (provider, 1 if allow_real else 0, mcp_profile, int(utc_now_ms()), updated_by),
        )
        conn.commit()
    finally:
        conn.close()

    eff = reload_ssh_provider_config()
    _audit(
        "ssh_provider.upsert",
        endpoint="/api/providers/ssh",
        payload={"provider": provider, "allow_real": bool(allow_real), "mcp_profile": mcp_profile, "reason": reason, "capability_id": _CAP_WRITE, "risk_tier": _RISK_WRITE},
        result={"ok": True, "source": eff.source},
    )
    return eff.to_dict()


@router.post("/api/providers/ssh/reload")
def reload_ssh_provider(
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> Dict[str, Any]:
    _require_admin_token(admin_token)
    eff = reload_ssh_provider_config()
    _audit(
        "ssh_provider.reload",
        endpoint="/api/providers/ssh/reload",
        payload={"capability_id": _CAP_WRITE, "risk_tier": _RISK_WRITE},
        result={"ok": True, "source": eff.source, "provider": eff.provider},
    )
    return {"ok": True, "effective": eff.to_dict()}


@router.post("/api/providers/ssh/db/init")
def init_ssh_provider_db(
    payload: DbInitIn,
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> Dict[str, Any]:
    token = _require_admin_token(admin_token)
    tables = ["ssh_provider_config", "ssh_provider_change_requests"]

    if not payload.confirm:
        now_ms = int(utc_now_ms())
        confirm_payload = {
            "op": "ssh_provider.db_init",
            "ts_ms": now_ms,
            "exp_ms": now_ms + int(_CONFIRM_TTL_MS),
            "tables": tables,
            "admin_fp": _token_fingerprint(token),
            "nonce": uuid4().hex,
        }
        confirm_token = _make_confirm_token(admin_token=token, payload=confirm_payload)
        _audit(
            "ssh_provider.db_init.confirm_required",
            endpoint="/api/providers/ssh/db/init",
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
                context={"op": "ssh_provider.db_init", "tables": tables},
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
    if str(decoded.get("op") or "") != "ssh_provider.db_init":
        raise HTTPException(
            status_code=409,
            detail=gate_detail(
                error_code="INVALID_CONFIRM_TOKEN",
                gate="confirm",
                message="payload mismatch",
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
        existed = _table_exists(conn, "ssh_provider_config")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ssh_provider_config (
              id INTEGER PRIMARY KEY CHECK (id = 1),
              provider TEXT NOT NULL,
              allow_real INTEGER NOT NULL,
              mcp_profile TEXT,
              updated_at INTEGER NOT NULL,
              updated_by TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ssh_provider_change_requests (
              request_id TEXT PRIMARY KEY,
              payload_json TEXT NOT NULL,
              status TEXT NOT NULL,
              created_at INTEGER NOT NULL,
              expires_at INTEGER NOT NULL,
              reason TEXT
            )
            """
        )
        conn.commit()
    finally:
        conn.close()

    reload_ssh_provider_config()
    status = "ALREADY_INITIALIZED" if existed else "INITIALIZED"
    _audit(
        "ssh_provider.db_init",
        endpoint="/api/providers/ssh/db/init",
        payload={"tables": tables, "status": status, "reason": reason, "capability_id": _CAP_WRITE, "risk_tier": _RISK_WRITE},
        result={"ok": True},
    )
    return {"ok": True, "status": status, "tables": tables, "db": "registry", "reloaded": True}


@router.get("/api/providers/ssh/export")
def export_ssh_provider() -> Dict[str, Any]:
    eff = resolve_ssh_provider().to_dict()
    sources = get_ssh_provider_sources()
    generated_at = _now_iso()
    blob = json.dumps(
        {"generated_at": generated_at, "effective": eff, "sources": sources},
        ensure_ascii=False,
        sort_keys=True,
    ).encode("utf-8")
    sha = hashlib.sha256(blob).hexdigest()
    export_id = sha[:16]
    out_dir = Path(os.getcwd()) / "output" / "ssh_provider_exports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{export_id}.json"
    out_path.write_bytes(blob)

    _audit(
        "ssh_provider.export",
        endpoint="/api/providers/ssh/export",
        payload={"capability_id": _CAP_READ, "risk_tier": _RISK_READ},
        result={"ok": True, "sha256": sha, "export_id": export_id},
    )
    return {"ok": True, "export_id": export_id, "sha256": sha, "generated_at": generated_at, "download_url": f"/api/providers/ssh/exports/{export_id}"}


@router.get("/api/providers/ssh/exports/{export_id}")
def download_ssh_provider_export(export_id: str):
    out_path = Path(os.getcwd()) / "output" / "ssh_provider_exports" / f"{export_id}.json"
    if not out_path.exists():
        raise HTTPException(status_code=404, detail="export not found")
    return StreamingResponse(out_path.open("rb"), media_type="application/json")

