"""Keychain API (BridgeOS).

Stores references to secrets (secret_ref) without persisting plaintext.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from octopusos.webui.api.compat_state import ensure_schema as ensure_compat_schema
from octopusos.webui.api.shell import _audit_db_connect  # reuse audit DB connector
from octopusos.webui.api._db_bridgeos import connect_bridgeos, ensure_bridgeos_schema
from octopusos.webui.api._secret_store import encrypt_secret


router = APIRouter()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _audit(event_type: str, *, endpoint: str, payload: Any, result: Any) -> None:
    conn: Optional[sqlite3.Connection] = None
    try:
        conn = _audit_db_connect()
        ensure_compat_schema(conn)
        from octopusos.webui.api import compat_state

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


class SecretIn(BaseModel):
    kind: str = Field(..., min_length=1, max_length=64)
    label: Optional[str] = Field(default=None, max_length=200)
    secret_ref: str = Field(..., min_length=1, max_length=2000)
    meta: Dict[str, Any] = Field(default_factory=dict)


class SecretOut(BaseModel):
    secret_id: str
    kind: str
    label: Optional[str]
    secret_ref: str
    meta: Dict[str, Any]
    created_at: str
    updated_at: str


def _row_to_secret(row: sqlite3.Row) -> SecretOut:
    try:
        meta = json.loads(row["meta_json"]) if row["meta_json"] else {}
    except Exception:
        meta = {}
    return SecretOut(
        secret_id=str(row["secret_id"]),
        kind=str(row["kind"]),
        label=row["label"],
        secret_ref=str(row["secret_ref"]),
        meta=dict(meta) if isinstance(meta, dict) else {},
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


class SecretCreateIn(BaseModel):
    kind: str = Field(..., min_length=1, max_length=64)
    label: Optional[str] = Field(default=None, max_length=200)
    secret: str = Field(..., min_length=1, max_length=100_000)
    meta: Dict[str, Any] = Field(default_factory=dict)


class SecretCreateOut(BaseModel):
    secret_id: str
    secret_ref: str


@router.get("/api/keychain", response_model=List[SecretOut])
def keychain_list() -> List[SecretOut]:
    conn = connect_bridgeos()
    try:
        ensure_bridgeos_schema(conn)
        rows = conn.execute(
            "SELECT secret_id, kind, label, secret_ref, meta_json, created_at, updated_at FROM secrets ORDER BY updated_at DESC"
        ).fetchall()
        return [_row_to_secret(r) for r in rows]
    finally:
        conn.close()


@router.post("/api/keychain", response_model=SecretOut)
def keychain_create(payload: SecretIn) -> SecretOut:
    secret_id = uuid4().hex
    now = _now_iso()
    conn = connect_bridgeos()
    try:
        ensure_bridgeos_schema(conn)
        conn.execute(
            """
            INSERT INTO secrets (secret_id, kind, label, secret_ref, meta_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                secret_id,
                payload.kind.strip(),
                payload.label,
                payload.secret_ref.strip(),
                json.dumps(payload.meta, ensure_ascii=False, sort_keys=True),
                now,
                now,
            ),
        )
        conn.commit()
        row = conn.execute(
            "SELECT secret_id, kind, label, secret_ref, meta_json, created_at, updated_at FROM secrets WHERE secret_id = ?",
            (secret_id,),
        ).fetchone()
        assert row is not None
        item = _row_to_secret(row)
    finally:
        conn.close()

    _audit(
        "keychain.secret.create",
        endpoint="/api/keychain",
        payload={"secret_id": secret_id, "kind": item.kind, "capability_id": "ssh.exec"},
        result={"ok": True},
    )
    return item


@router.post("/api/keychain/secrets", response_model=SecretCreateOut)
def keychain_create_secret(payload: SecretCreateIn) -> SecretCreateOut:
    """Create a secret in the local encrypted store.

    Returns a secret_ref that can be used as auth_ref in connections.
    """
    secret_id = uuid4().hex
    secret_ref = f"secret_ref://keychain/{secret_id}"
    now = _now_iso()
    encrypted = encrypt_secret(payload.secret)

    conn = connect_bridgeos()
    try:
        ensure_bridgeos_schema(conn)
        conn.execute(
            """
            INSERT INTO secrets (secret_id, kind, label, secret_ref, meta_json, encrypted_blob, enc_version, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                secret_id,
                payload.kind.strip(),
                payload.label,
                secret_ref,
                json.dumps(payload.meta, ensure_ascii=False, sort_keys=True),
                encrypted,
                1,
                now,
                now,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    _audit(
        "keychain.secret.create",
        endpoint="/api/keychain/secrets",
        payload={"secret_id": secret_id, "kind": payload.kind, "capability_id": "ssh.exec", "risk_tier": "MEDIUM"},
        result={"ok": True, "secret_ref": secret_ref},
    )
    return SecretCreateOut(secret_id=secret_id, secret_ref=secret_ref)


@router.delete("/api/keychain/{secret_id}")
def keychain_delete(secret_id: str) -> Dict[str, Any]:
    conn = connect_bridgeos()
    try:
        ensure_bridgeos_schema(conn)
        row = conn.execute("SELECT secret_id FROM secrets WHERE secret_id = ?", (secret_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="secret not found")
        conn.execute("DELETE FROM secrets WHERE secret_id = ?", (secret_id,))
        conn.commit()
    finally:
        conn.close()

    _audit(
        "keychain.secret.delete",
        endpoint=f"/api/keychain/{secret_id}",
        payload={"secret_id": secret_id, "capability_id": "ssh.exec"},
        result={"ok": True},
    )
    return {"ok": True, "secret_id": secret_id}
