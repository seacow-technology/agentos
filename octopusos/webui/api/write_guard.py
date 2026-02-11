"""Centralized write access guard (mode + admin token)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fastapi import Request

from octopusos.core.capabilities.admin_token import validate_admin_token
from octopusos.webui.api.compat_state import db_connect, ensure_schema, get_state


WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
EXEMPT_PREFIXES = (
    "/api/daemon/",
    "/api/voice/twilio/",
)
EXEMPT_EXACT_PATHS = {
    "/api/communication/mode",  # must remain writable to recover from locked mode
}


@dataclass
class WriteDecision:
    allowed: bool
    code: str
    detail: str
    mode: str
    http_status: int


def _normalize_mode(mode: Optional[str]) -> str:
    raw = str(mode or "").strip().lower()
    if raw in {"local_open", "localopen", "open", "local", ""}:
        return "local_open"
    if raw in {"local_locked", "locallocked", "locked"}:
        return "local_locked"
    if raw in {"remote_exposed", "remoteexposed", "exposed", "remote"}:
        return "remote_exposed"
    return "unknown"


def _read_mode() -> str:
    conn = None
    try:
        conn = db_connect()
        ensure_schema(conn)
        mode = get_state(conn, key="communication_mode", default="local_open")
        return _normalize_mode(mode)
    except Exception:
        # Fallback for environments with incomplete compat tables.
        return "local_open"
    finally:
        if conn is not None:
            conn.close()


def _extract_admin_token(request: Request) -> Optional[str]:
    for name in ("x-admin-token", "x-octopusos-token"):
        token = request.headers.get(name)
        if token and token.strip():
            return token.strip()
    return None


def should_skip_guard(request: Request) -> bool:
    path = request.url.path
    if path in EXEMPT_EXACT_PATHS:
        return True
    return any(path.startswith(prefix) for prefix in EXEMPT_PREFIXES)


def evaluate_write_access(request: Request) -> WriteDecision:
    mode = _read_mode()
    token = _extract_admin_token(request)
    has_valid_token = bool(token and validate_admin_token(token))

    if mode == "local_open":
        return WriteDecision(True, "OK", "Write allowed in LOCAL_OPEN", mode, 200)

    if mode == "local_locked":
        if has_valid_token:
            return WriteDecision(True, "OK", "Write allowed with admin token in LOCAL_LOCKED", mode, 200)
        return WriteDecision(
            False,
            "TOKEN_REQUIRED",
            "Admin token required for writes in LOCAL_LOCKED mode",
            mode,
            401,
        )

    if mode == "remote_exposed":
        if has_valid_token:
            return WriteDecision(True, "OK", "Write allowed with admin token in REMOTE_EXPOSED", mode, 200)
        return WriteDecision(
            False,
            "TOKEN_REQUIRED",
            "Admin token required for writes in REMOTE_EXPOSED mode",
            mode,
            401,
        )

    return WriteDecision(
        False,
        "MODE_UNKNOWN",
        "Write denied because runtime mode is unknown",
        mode,
        403,
    )
