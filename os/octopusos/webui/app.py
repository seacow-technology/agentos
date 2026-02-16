"""Minimal FastAPI app for WebUI v2 API routers (Frontdesk MVP)."""

import os
import traceback
import logging
import sqlite3
import secrets
import time
import json
import threading
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4
from fastapi import HTTPException
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

from octopusos.webui.api.validation import MAX_PAYLOAD_SIZE
from octopusos.webui.api.write_guard import (
    WRITE_METHODS,
    evaluate_write_access,
    should_skip_guard,
)
from octopusos.webui.api.providers import _provider_ids
from octopusos.webui.contract.app_factory import create_contract_app
from octopusos.core.status_store import StatusStore
from octopusos.providers.registry import ProviderRegistry
from octopusos.providers.base import ProviderState
from octopusos.webui.calls import get_call_store
from octopusos.webui.config_resolver import get_config_cache, resolve_config
from octopusos.webui.config_schema import module_for_key, validate_config_entry
from octopusos.webui.config_allowlist import ALLOWLIST, get_key_policy, is_allowed_key, is_high_risk_key
from octopusos.webui.secret_resolver import is_secret_ref, secret_exists
from octopusos.webui.config_store import get_config_store
from octopusos.webui.websocket import chat as ws_chat
from octopusos.webui.websocket import coding as ws_coding
from octopusos.webui.websocket import governance as ws_governance
from octopusos.config import load_settings
from octopusos.core.attention.chat_injection_config import injection_enabled, injection_mode
from octopusos.core.db.registry_db import get_db_path as get_registry_db_path
from octopusos.store import ensure_migrations

try:
    # Ensure first-run environments have the DB file selected by registry_db
    # (includes OCTOPUSOS_DB_PATH overrides), before router imports instantiate stores.
    db_path = Path(get_registry_db_path())
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if not db_path.exists():
        conn = sqlite3.connect(str(db_path))
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_version (
                    version TEXT PRIMARY KEY,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    description TEXT
                )
                """
            )
            conn.commit()
        finally:
            conn.close()
    ensure_migrations(db_path)
except Exception as exc:
    raise RuntimeError(f"Failed to initialize OctopusOS database: {exc}") from exc

app = create_contract_app()

logger = logging.getLogger(__name__)
try:
    import sentry_sdk  # type: ignore
    SENTRY_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    sentry_sdk = None
    SENTRY_AVAILABLE = False

SENTRY_ENABLED = os.getenv("SENTRY_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}
APP_START_MONOTONIC = time.monotonic()
RUNTIME_ENV_BINDINGS = {
    "runtime.web_search_extension_entrypoint": "WEB_SEARCH_EXTENSION_ENTRYPOINT",
}

_default_origins = [
    "http://127.0.0.1:5174",
    "http://localhost:5174",
]
_origins_env = os.getenv("OCTOPUSOS_WEBUI_ORIGINS", "").strip()
if _origins_env:
    _origins = [o.strip() for o in _origins_env.split(",") if o.strip()]
else:
    _origins = _default_origins

# Desktop UI bundles (checked-in dist used by Desktop Electron).
# These are served directly by the runtime API in dev/test environments where the Electron
# proxy isn't running, so Playwright can exercise Product Shell embedding end-to-end.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_DESKTOP_PRODUCT_DIST = (_REPO_ROOT / "apps" / "desktop-electron" / "resources" / "product-dist").resolve()
_DESKTOP_WEBUI_DIST = (_REPO_ROOT / "apps" / "desktop-electron" / "resources" / "webui-dist").resolve()


def _safe_join(base: Path, rel: str) -> Optional[Path]:
    rel = (rel or "").lstrip("/")
    candidate = (base / rel).resolve()
    try:
        candidate.relative_to(base)
    except Exception:
        return None
    return candidate


def _desktop_has_ui() -> bool:
    return (_DESKTOP_PRODUCT_DIST / "index.html").exists() and (_DESKTOP_WEBUI_DIST / "index.html").exists()

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def payload_size_limit_middleware(request: Request, call_next):
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        body = await request.body()
        if len(body) > MAX_PAYLOAD_SIZE:
            return JSONResponse(
                status_code=413,
                content={
                    "ok": False,
                    "error": "Payload too large",
                    "reason_code": "PAYLOAD_TOO_LARGE",
                    "hint": f"Payload must be <= {MAX_PAYLOAD_SIZE} bytes (1MB).",
                    "details": {"max_size_bytes": MAX_PAYLOAD_SIZE},
                },
            )
    return await call_next(request)


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    headers = response.headers
    headers.setdefault("X-Content-Type-Options", "nosniff")
    is_preview_content = request.url.path.startswith("/api/preview/") and request.url.path.endswith("/content")
    is_console_embed = request.url.path.startswith("/console") and request.query_params.get("embed") == "1"
    if is_preview_content:
        headers["X-Frame-Options"] = "SAMEORIGIN"
    elif is_console_embed:
        headers["X-Frame-Options"] = "SAMEORIGIN"
    else:
        headers.setdefault("X-Frame-Options", "DENY")
    headers.setdefault("X-XSS-Protection", "1; mode=block")
    headers.setdefault("Referrer-Policy", "no-referrer")

    content_type = headers.get("content-type", "")
    if content_type.startswith("text/html"):
        frame_ancestors = (
            "frame-ancestors 'self' http://127.0.0.1:* http://localhost:*"
            if (is_preview_content or is_console_embed)
            else "frame-ancestors 'none'"
        )
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self' data:; "
            "connect-src 'self' ws: wss:; "
            "object-src 'none'; "
            f"{frame_ancestors}; "
            "base-uri 'self'; "
            "form-action 'self'; "
            "upgrade-insecure-requests"
        )
        headers.setdefault("Content-Security-Policy", csp)

    # Runtime provenance marker for semantic E2E and auditability.
    headers.setdefault("X-OctopusOS-Source", "real")
    reason = getattr(request.state, "octopusos_source_reason", None)
    if reason:
        headers.setdefault("X-OctopusOS-Reason", str(reason))

    return response


@app.middleware("http")
async def write_access_guard_middleware(request: Request, call_next):
    if request.method not in WRITE_METHODS:
        return await call_next(request)

    if not request.url.path.startswith("/api/") or should_skip_guard(request):
        return await call_next(request)

    decision = evaluate_write_access(request)
    if decision.allowed:
        return await call_next(request)

    request.state.octopusos_source_reason = decision.code
    return JSONResponse(
        status_code=decision.http_status,
        content={
            "ok": False,
            "error": decision.detail,
            "reason_code": decision.code,
            "mode": decision.mode,
            "details": {
                "path": request.url.path,
                "method": request.method,
            },
        },
        headers={
            "X-OctopusOS-Source": "real",
            "X-OctopusOS-Reason": decision.code,
        },
    )


@app.get("/")
async def root() -> HTMLResponse:
    # Desktop/dev convenience: if dist bundles exist, serve Product Shell at root.
    # This matches Desktop Electron behavior (Product at '/', Console at '/console').
    if _desktop_has_ui():
        idx = _DESKTOP_PRODUCT_DIST / "index.html"
        response = FileResponse(str(idx))
        response.set_cookie("csrf_token", secrets.token_urlsafe(16))
        return response

    response = HTMLResponse(
        "<!doctype html><html><head><title>OctopusOS</title></head>"
        "<body><h1>OctopusOS</h1></body></html>"
    )
    response.set_cookie("csrf_token", secrets.token_urlsafe(16))
    return response


@app.get("/api/csrf-token")
async def csrf_token() -> JSONResponse:
    token = secrets.token_urlsafe(16)
    response = JSONResponse(status_code=200, content={"csrfToken": token})
    response.set_cookie("csrf_token", token)
    return response


@app.get("/api/health")
async def health_check() -> JSONResponse:
    uptime_seconds = max(0, int(time.monotonic() - APP_START_MONOTONIC))
    return JSONResponse(
        status_code=200,
        content={
            "ok": True,
            "status": "ok",
            "version": app.version,
            "runtime": "embedded",
            "uptime_sec": uptime_seconds,
            "components": {
                "api": {"status": "ok"},
                "database": {"status": "ok"},
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "uptime_seconds": uptime_seconds,
        },
    )


@app.get("/api/runtime/info")
async def runtime_info() -> JSONResponse:
    uptime_seconds = max(0, int(time.monotonic() - APP_START_MONOTONIC))
    return JSONResponse(
        status_code=200,
        content={
            "version": app.version,
            "uptime": uptime_seconds,
            "environment": os.getenv("OCTOPUSOS_ENV", "development"),
            "features": ["api", "providers", "projects", "sessions"],
            "pid": os.getpid(),
        },
    )


@app.get("/api/metrics/json")
async def metrics_json() -> JSONResponse:
    payload = {
        "metrics": {
            "cpu_usage": 0.0,
            "memory_usage": 0.0,
            "disk_usage": 0.0,
            "network_rx": 0.0,
            "network_tx": 0.0,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return JSONResponse(status_code=200, content=payload)


@app.get("/api/metrics")
async def metrics() -> JSONResponse:
    return await metrics_json()


@app.get("/api/risk/current")
async def risk_current() -> JSONResponse:
    return JSONResponse(
        status_code=200,
        content={
            "overall_risk": 0.0,
            "execution_risk": 0.0,
            "trust_risk": 0.0,
            "policy_risk": 0.0,
            "capability_risk": 0.0,
        },
    )


@app.get("/api/providers/status")
async def providers_status() -> JSONResponse:
    now = datetime.now(timezone.utc).isoformat()
    store = StatusStore.get_instance()
    registry = ProviderRegistry.get_instance()

    status_list, cache_ttl_ms = await store.get_all_provider_status()
    status_map = {status.id: status for status in status_list}

    providers = []
    for provider in registry.list_all():
        status = status_map.get(provider.id)

        if status is None:
            providers.append(
                {
                    "id": provider.id,
                    "type": provider.type.value,
                    "state": ProviderState.UNKNOWN.value,
                    "endpoint": getattr(provider, "endpoint", None),
                    "latency_ms": None,
                    "last_ok_at": None,
                    "last_error": None,
                    "pid": None,
                    "pid_exists": None,
                    "port_listening": None,
                    "api_responding": None,
                }
            )
            continue

        providers.append(
            {
                "id": status.id,
                "type": status.type.value if hasattr(status.type, "value") else str(status.type),
                "state": status.state.value if hasattr(status.state, "value") else str(status.state),
                "endpoint": status.endpoint,
                "latency_ms": status.latency_ms,
                "last_ok_at": status.last_ok_at,
                "last_error": status.last_error,
                "pid": status.pid,
                "pid_exists": status.pid_exists,
                "port_listening": status.port_listening,
                "api_responding": status.api_responding,
            }
        )

    return JSONResponse(
        status_code=200,
        content={
            "ts": now,
            "providers": providers,
            "cache_ttl_ms": cache_ttl_ms,
        },
    )


@app.get("/api/selfcheck/chat-health")
async def selfcheck_chat_health() -> JSONResponse:
    return JSONResponse(
        status_code=200,
        content={
            "is_healthy": True,
            "issues": [],
            "hints": [],
        },
    )


@app.get("/api/providers/{provider_id}/models")
async def provider_models(provider_id: str) -> JSONResponse:
    # Compatibility endpoint expected by apps/webui chat page.
    if provider_id not in _provider_ids():
        raise HTTPException(status_code=404, detail="Unknown provider")
    return JSONResponse(
        status_code=200,
        content={
            "provider_id": provider_id,
            "models": [],
        },
    )


@app.get("/api/config")
async def config_get() -> JSONResponse:
    settings = load_settings()
    return JSONResponse(
        status_code=200,
        content={
            "config": settings.to_dict(),
            "source": "compat",
            "version": "v0",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
    )


@app.get("/api/config/entries")
async def config_entries_get(
    search: str | None = Query(default=None),
    scope: str | None = Query(default=None),
    project_id: str | None = Query(default=None),
    type_filter: str | None = Query(default=None, alias="type"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=25, ge=1, le=500),
) -> JSONResponse:
    store = get_config_store()
    entries, total = store.list_entries(
        search=search,
        scope=scope,
        project_id=project_id,
        type_filter=type_filter,
        page=page,
        limit=limit,
    )

    return JSONResponse(
        status_code=200,
        content={
            "entries": entries,
            "total": total,
            "page": page,
            "limit": limit,
            "source": "db",
        },
    )


@app.get("/api/config/entries/{key:path}")
async def config_entry_get(key: str, project_id: str | None = Query(default=None)) -> JSONResponse:
    entry = get_config_store().get_entry(key, project_id=project_id)
    if entry is None:
        return JSONResponse(
            status_code=404,
            content={"error": "CONFIG_ENTRY_NOT_FOUND", "key": key},
        )
    return JSONResponse(
        status_code=200,
        content={"entry": entry, "source": "db"},
    )


def _parse_value(value_type: str, raw_value: Any) -> tuple[Any, str] | tuple[None, None]:
    try:
        if value_type == "int":
            return int(raw_value), ""
        if value_type == "bool":
            if isinstance(raw_value, bool):
                return raw_value, ""
            return str(raw_value).strip().lower() in {"1", "true", "yes", "on"}, ""
        if value_type == "json":
            return raw_value if isinstance(raw_value, (dict, list)) else json.loads(str(raw_value)), ""
        return ("" if raw_value is None else str(raw_value)), ""
    except (ValueError, json.JSONDecodeError):
        return None, "Invalid value for requested type"


@app.post("/api/config/entries")
async def config_entry_create(request: Request) -> JSONResponse:
    payload = await request.json()
    key = str(payload.get("key", "")).strip()
    if not key:
        return JSONResponse(
            status_code=400,
            content={"error": "CONFIG_KEY_REQUIRED"},
        )
    if not is_allowed_key(key):
        return JSONResponse(
            status_code=403,
            content={"error": "CONFIG_KEY_NOT_ALLOWED", "key": key, "module": module_for_key(key) or "unknown"},
        )

    value_type_raw = str(payload.get("type", "String")).strip()
    type_map = {
        "String": "string",
        "Integer": "int",
        "Boolean": "bool",
        "JSON": "json",
    }
    value_type = type_map.get(value_type_raw, "string")
    raw_value = payload.get("value", "")
    parsed_value, parse_error = _parse_value(value_type, raw_value)
    if parse_error:
        return JSONResponse(
            status_code=400,
            content={"error": "CONFIG_VALUE_PARSE_FAILED", "message": parse_error},
        )

    module = module_for_key(key)
    if not module:
        return JSONResponse(
            status_code=400,
            content={
                "error": "CONFIG_SCHEMA_VALIDATION_FAILED",
                "module": "unknown",
                "schema_version_expected": 1,
                "errors": [{"path": "key", "message": f"Unsupported config key: {key}"}],
            },
        )

    scope = str(payload.get("scope", "global")).strip() or "global"
    project_id = str(payload.get("project_id", "")).strip() or None
    dry_run = bool(payload.get("dry_run", False))
    dry_run_token = str(payload.get("dry_run_token", "")).strip()
    confirm = bool(payload.get("confirm", False))
    decision_id = str(payload.get("decision_id", "")).strip() or None
    reason = str(payload.get("reason", "")).strip() or None
    description = str(payload.get("description", ""))
    schema_version = int(payload.get("schema_version", 1) or 1)
    source = str(payload.get("source", "db")).strip() or "db"
    is_secret = bool(payload.get("is_secret", False))
    is_hot_reload = bool(payload.get("is_hot_reload", True))
    actor = request.headers.get("X-Actor", "local")
    validation_failure = validate_config_entry(
        key=key,
        value=parsed_value,
        schema_version=schema_version,
    )
    if validation_failure is not None:
        return JSONResponse(
            status_code=400,
            content={
                "error": validation_failure.error,
                "module": validation_failure.module,
                "schema_version_expected": validation_failure.schema_version_expected,
                "errors": validation_failure.errors,
            },
        )

    secret_candidate = str(parsed_value) if parsed_value is not None else ""
    if is_secret or key.endswith("_ref"):
        if not is_secret_ref(secret_candidate):
            return JSONResponse(
                status_code=400,
                content={"error": "SECRET_REF_INVALID_FORMAT", "ref": secret_candidate},
            )
        if not secret_exists(secret_candidate):
            return JSONResponse(
                status_code=400,
                content={"error": "SECRET_REF_NOT_FOUND", "ref": secret_candidate},
            )

    policy = get_key_policy(key)
    risk_level = str(policy.get("risk_level", "low"))
    requires_confirmation = bool(policy.get("requires_confirmation", False))
    requires_dry_run = bool(policy.get("requires_dry_run", False))
    current = get_config_store().get_entry(key, project_id=project_id)
    impact = {
        "key": key,
        "module": module,
        "risk_level": risk_level,
        "previous": {
            "value": current.get("value") if current else None,
            "source": current.get("source") if current else "unconfigured",
        },
        "next": {
            "value": parsed_value,
            "source": source,
        },
        "is_hot_reload": is_hot_reload,
    }

    if dry_run:
        return JSONResponse(
            status_code=200,
            content={"ok": True, "dry_run": True, "impact": impact},
        )

    if requires_dry_run and not (confirm or dry_run_token):
        return JSONResponse(
            status_code=400,
            content={
                "error": "CONFIG_REQUIRES_DRY_RUN",
                "key": key,
                "module": module,
                "risk_level": risk_level,
                "impact": impact,
            },
        )

    if requires_confirmation and not confirm:
        return JSONResponse(
            status_code=400,
            content={
                "error": "CONFIG_HIGH_RISK_CONFIRMATION_REQUIRED",
                "key": key,
                "module": module,
                "risk_level": risk_level,
            },
        )

    existing = get_config_store().get_entry(key, project_id=project_id)
    entry = get_config_store().upsert_entry(
        key=key,
        value=parsed_value,
        value_type=value_type,
        module=module,
        scope=scope,
        project_id=project_id,
        description=description,
        source=source,
        schema_version=schema_version,
        is_secret=is_secret,
        is_hot_reload=is_hot_reload,
        actor=actor,
        audit_op="set",
        decision_id=decision_id,
        reason=reason,
        risk_level=risk_level,
    )
    get_config_cache().invalidate(key)
    get_config_cache().invalidate_prefix(f"{module}.")
    if key in RUNTIME_ENV_BINDINGS:
        _apply_runtime_env_overrides(key)

    return JSONResponse(
        status_code=201 if existing is None else 200,
        content={"entry": entry, "source": "db"},
    )


@app.put("/api/config/entries/{id}")
async def config_entry_update(id: int, request: Request) -> JSONResponse:
    existing_entry = get_config_store().get_entry_by_id(id)
    if existing_entry is None:
        return JSONResponse(status_code=404, content={"error": "CONFIG_ENTRY_NOT_FOUND", "id": id})

    payload = await request.json()
    key = str(payload.get("key", existing_entry.get("key", ""))).strip()
    if not key:
        return JSONResponse(status_code=400, content={"error": "CONFIG_KEY_REQUIRED"})
    if key != str(existing_entry.get("key", "")).strip():
        return JSONResponse(status_code=400, content={"error": "CONFIG_KEY_IMMUTABLE", "id": id})
    if not is_allowed_key(key):
        return JSONResponse(
            status_code=403,
            content={"error": "CONFIG_KEY_NOT_ALLOWED", "key": key, "module": module_for_key(key) or "unknown"},
        )

    value_type_raw = str(payload.get("type", existing_entry.get("type", "String"))).strip()
    type_map = {
        "String": "string",
        "Integer": "int",
        "Boolean": "bool",
        "JSON": "json",
    }
    value_type = type_map.get(value_type_raw, str(existing_entry.get("value_type", "string")))
    raw_value = payload.get("value", existing_entry.get("value", ""))
    parsed_value, parse_error = _parse_value(value_type, raw_value)
    if parse_error:
        return JSONResponse(
            status_code=400,
            content={"error": "CONFIG_VALUE_PARSE_FAILED", "message": parse_error},
        )

    module = module_for_key(key)
    if not module:
        return JSONResponse(
            status_code=400,
            content={
                "error": "CONFIG_SCHEMA_VALIDATION_FAILED",
                "module": "unknown",
                "schema_version_expected": 1,
                "errors": [{"path": "key", "message": f"Unsupported config key: {key}"}],
            },
        )

    scope = str(payload.get("scope", existing_entry.get("scope", "global"))).strip() or "global"
    project_id = str(payload.get("project_id", existing_entry.get("project_id", "") or "")).strip() or None
    dry_run = bool(payload.get("dry_run", False))
    dry_run_token = str(payload.get("dry_run_token", "")).strip()
    confirm = bool(payload.get("confirm", False))
    decision_id = str(payload.get("decision_id", "")).strip() or None
    reason = str(payload.get("reason", "")).strip() or None
    description = str(payload.get("description", existing_entry.get("description", "")))
    schema_version = int(payload.get("schema_version", existing_entry.get("schema_version", 1)) or 1)
    source = str(payload.get("source", existing_entry.get("source", "db"))).strip() or "db"
    is_secret = bool(payload.get("is_secret", existing_entry.get("is_secret", False)))
    is_hot_reload = bool(payload.get("is_hot_reload", existing_entry.get("is_hot_reload", True)))
    actor = request.headers.get("X-Actor", "local")
    validation_failure = validate_config_entry(
        key=key,
        value=parsed_value,
        schema_version=schema_version,
    )
    if validation_failure is not None:
        return JSONResponse(
            status_code=400,
            content={
                "error": validation_failure.error,
                "module": validation_failure.module,
                "schema_version_expected": validation_failure.schema_version_expected,
                "errors": validation_failure.errors,
            },
        )

    secret_candidate = str(parsed_value) if parsed_value is not None else ""
    if is_secret or key.endswith("_ref"):
        if not is_secret_ref(secret_candidate):
            return JSONResponse(
                status_code=400,
                content={"error": "SECRET_REF_INVALID_FORMAT", "ref": secret_candidate},
            )
        if not secret_exists(secret_candidate):
            return JSONResponse(
                status_code=400,
                content={"error": "SECRET_REF_NOT_FOUND", "ref": secret_candidate},
            )

    policy = get_key_policy(key)
    risk_level = str(policy.get("risk_level", "low"))
    requires_confirmation = bool(policy.get("requires_confirmation", False))
    requires_dry_run = bool(policy.get("requires_dry_run", False))
    current = get_config_store().get_entry(key, project_id=project_id)
    impact = {
        "key": key,
        "module": module,
        "risk_level": risk_level,
        "previous": {
            "value": current.get("value") if current else None,
            "source": current.get("source") if current else "unconfigured",
        },
        "next": {
            "value": parsed_value,
            "source": source,
        },
        "is_hot_reload": is_hot_reload,
    }

    if dry_run:
        return JSONResponse(
            status_code=200,
            content={"ok": True, "dry_run": True, "impact": impact},
        )

    if requires_dry_run and not (confirm or dry_run_token):
        return JSONResponse(
            status_code=400,
            content={
                "error": "CONFIG_REQUIRES_DRY_RUN",
                "key": key,
                "module": module,
                "risk_level": risk_level,
                "impact": impact,
            },
        )

    if requires_confirmation and not confirm:
        return JSONResponse(
            status_code=400,
            content={
                "error": "CONFIG_HIGH_RISK_CONFIRMATION_REQUIRED",
                "key": key,
                "module": module,
                "risk_level": risk_level,
            },
        )

    entry = get_config_store().upsert_entry(
        key=key,
        value=parsed_value,
        value_type=value_type,
        module=module,
        scope=scope,
        project_id=project_id,
        description=description,
        source=source,
        schema_version=schema_version,
        is_secret=is_secret,
        is_hot_reload=is_hot_reload,
        actor=actor,
        audit_op="update",
        decision_id=decision_id,
        reason=reason,
        risk_level=risk_level,
    )
    get_config_cache().invalidate(key)
    get_config_cache().invalidate_prefix(f"{module}.")
    if key in RUNTIME_ENV_BINDINGS:
        _apply_runtime_env_overrides(key)

    return JSONResponse(status_code=200, content={"entry": entry, "source": "db"})


@app.delete("/api/config/entries/{id}")
async def config_entry_delete(
    id: int,
    request: Request,
    decision_id: str | None = Query(default=None),
    reason: str | None = Query(default=None),
) -> JSONResponse:
    actor = request.headers.get("X-Actor", "local")
    deleted = get_config_store().delete_entry_by_id(
        entry_id=id,
        actor=actor,
        decision_id=decision_id,
        reason=reason,
    )
    if deleted is None:
        return JSONResponse(status_code=404, content={"error": "CONFIG_ENTRY_NOT_FOUND", "id": id})

    key = str(deleted.get("key") or "")
    module = str(deleted.get("module") or "")
    if key:
        get_config_cache().invalidate(key)
        if key in RUNTIME_ENV_BINDINGS:
            _apply_runtime_env_overrides(key)
    if module:
        get_config_cache().invalidate_prefix(f"{module}.")

    return JSONResponse(status_code=200, content={"ok": True, "deleted": deleted, "source": "db"})


@app.get("/api/config/modules")
async def config_modules_get() -> JSONResponse:
    return JSONResponse(
        status_code=200,
        content={"modules": get_config_store().list_modules(), "source": "db"},
    )


@app.get("/api/config/allowlist")
async def config_allowlist_get() -> JSONResponse:
    modules = []
    for module_name, data in ALLOWLIST.items():
        modules.append(
            {
                "module": module_name,
                "title": data.get("title", module_name),
                "keys": data.get("keys", []),
                "secrets": data.get("secrets", []),
                "high_risk_keys": data.get("high_risk_keys", []),
                "key_meta": data.get("key_meta", {}),
            }
        )
    return JSONResponse(status_code=200, content={"modules": modules})


@app.get("/api/config/secret-status")
async def config_secret_status(
    key: str = Query(..., min_length=1),
    project_id: str | None = Query(default=None),
) -> JSONResponse:
    entry = get_config_store().get_entry(key, project_id=project_id)
    if entry is None:
        resolved = resolve_config(key=key, project_id=project_id)
        ref = str(resolved.get("value") or "")
    else:
        ref = str(entry.get("value") or "")
    configured = bool(ref) and is_secret_ref(ref) and secret_exists(ref)
    return JSONResponse(status_code=200, content={"key": key, "configured": configured})


@app.get("/api/config/resolve")
async def config_resolve_get(
    key: str = Query(..., min_length=1),
    project_id: str | None = Query(default=None),
    request_override: str | None = Query(default=None),
    admin_token: str | None = Query(default=None),
) -> JSONResponse:
    try:
        resolved = resolve_config(
            key=key,
            project_id=project_id,
            request_override=request_override,
            admin_token=admin_token,
        )
    except PermissionError:
        return JSONResponse(
            status_code=403,
            content={"error": "REQUEST_OVERRIDE_FORBIDDEN", "key": key},
        )
    if key.endswith("_ref"):
        ref = str(resolved.get("value") or "")
        resolved["secret_configured"] = bool(ref) and is_secret_ref(ref) and secret_exists(ref)
    return JSONResponse(status_code=200, content=resolved)


@app.post("/api/config/rollback")
async def config_rollback(request: Request) -> JSONResponse:
    payload = await request.json()
    key = payload.get("key")
    module_prefix = payload.get("module_prefix")
    project_id = str(payload.get("project_id", "")).strip() or None
    target_audit_id = payload.get("target_audit_id")
    dry_run = bool(payload.get("dry_run", False))
    actor = request.headers.get("X-Actor", "local")

    if not key and not module_prefix:
        return JSONResponse(status_code=400, content={"error": "CONFIG_ROLLBACK_TARGET_REQUIRED"})

    store = get_config_store()
    candidates: list[dict[str, Any]] = []
    if target_audit_id is not None:
        try:
            audit_id = int(target_audit_id)
        except ValueError:
            return JSONResponse(status_code=400, content={"error": "CONFIG_ROLLBACK_INVALID_AUDIT_ID"})
        record = store.get_audit_record(audit_id)
        if record is None:
            return JSONResponse(status_code=404, content={"error": "CONFIG_ROLLBACK_AUDIT_NOT_FOUND"})
        candidates = [record]
    elif key:
        audits = store.list_audit(str(key), project_id=project_id)
        if len(audits) < 1:
            return JSONResponse(status_code=400, content={"error": "CONFIG_ROLLBACK_NO_PREVIOUS_VERSION", "key": key})
        candidates = [audits[-1]]
    else:
        prefix = str(module_prefix)
        entries, _ = store.list_entries(
            search=None,
            scope=None,
            project_id=project_id,
            type_filter=None,
            page=1,
            limit=5000,
        )
        filtered_keys = [e["key"] for e in entries if e["key"].startswith(prefix)]
        for cfg_key in filtered_keys:
            audits = store.list_audit(cfg_key, project_id=project_id)
            if len(audits) >= 1:
                candidates.append(audits[-1])

    if not candidates:
        return JSONResponse(status_code=400, content={"error": "CONFIG_ROLLBACK_NO_TARGETS"})

    preview: list[dict[str, Any]] = []
    for audit in candidates:
        cfg_key = str(audit["config_key"])
        old_preview = audit.get("old_preview") or audit.get("new_preview") or ""
        parsed_value: Any
        try:
            parsed_value = json.loads(old_preview) if old_preview else ""
        except json.JSONDecodeError:
            parsed_value = old_preview

        schema_version = int(audit.get("schema_version") or 1)
        validation_failure = validate_config_entry(
            key=cfg_key,
            value=parsed_value,
            schema_version=schema_version,
        )
        if validation_failure is not None:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "CONFIG_ROLLBACK_SCHEMA_FAILED",
                    "key": cfg_key,
                    "module": validation_failure.module,
                    "errors": validation_failure.errors,
                },
            )

        is_secret = cfg_key.endswith("_ref")
        if is_secret:
            secret_ref_text = str(parsed_value)
            if not is_secret_ref(secret_ref_text):
                return JSONResponse(
                    status_code=400,
                    content={"error": "CONFIG_ROLLBACK_SECRET_MISSING", "key": cfg_key, "ref": secret_ref_text},
                )
            if not secret_exists(secret_ref_text):
                return JSONResponse(
                    status_code=400,
                    content={"error": "CONFIG_ROLLBACK_SECRET_MISSING", "key": cfg_key, "ref": secret_ref_text},
                )

        preview.append({"key": cfg_key, "to_value": parsed_value, "schema_version": schema_version})

    if dry_run:
        return JSONResponse(
            status_code=200,
            content={"ok": True, "dry_run": True, "changes": preview},
        )

    applied: list[dict[str, Any]] = []
    for item in preview:
        cfg_key = str(item["key"])
        existing = store.get_entry(cfg_key, project_id=project_id)
        if existing is None:
            continue
        module = module_for_key(cfg_key) or "general"
        raw_value = item["to_value"]
        value_type = existing.get("value_type", "string")
        store.upsert_entry(
            key=cfg_key,
            value=raw_value,
            value_type=value_type,
            module=module,
            scope=existing.get("scope", "global"),
            project_id=existing.get("project_id"),
            description=existing.get("description", ""),
            source="db",
            schema_version=int(item["schema_version"]),
            is_secret=bool(existing.get("is_secret", False)),
            is_hot_reload=bool(existing.get("is_hot_reload", True)),
            actor=actor,
            audit_op="rollback",
            decision_id=str(payload.get("decision_id", "")).strip() or None,
            reason=str(payload.get("reason", "")).strip() or "rollback",
            risk_level="high" if is_high_risk_key(cfg_key) else "low",
        )
        get_config_cache().invalidate(cfg_key)
        get_config_cache().invalidate_prefix(f"{module}.")
        applied.append({"key": cfg_key})

    return JSONResponse(status_code=200, content={"ok": True, "applied": applied})


@app.post("/api/config/snapshot")
async def config_snapshot_create(request: Request) -> JSONResponse:
    payload = await request.json()
    scope = str(payload.get("scope", "global")).strip() or "global"
    project_id = str(payload.get("project_id", "")).strip() or None
    note = str(payload.get("note", "")).strip() or None
    actor = request.headers.get("X-Actor", "local")
    snapshot_id = str(payload.get("snapshot_id", "")).strip() or f"cfgsnap_{uuid4().hex[:12]}"
    snapshot = get_config_store().create_snapshot(
        snapshot_id=snapshot_id,
        scope=scope,
        project_id=project_id,
        actor=actor,
        source="db",
        note=note,
    )
    return JSONResponse(status_code=201, content={"snapshot": snapshot})


@app.get("/api/config/snapshot/{snapshot_id}")
async def config_snapshot_get(snapshot_id: str) -> JSONResponse:
    snapshot = get_config_store().get_snapshot(snapshot_id)
    if snapshot is None:
        return JSONResponse(status_code=404, content={"error": "CONFIG_SNAPSHOT_NOT_FOUND", "snapshot_id": snapshot_id})
    return JSONResponse(status_code=200, content={"snapshot": snapshot})


def _build_diff(from_entries: list[dict[str, Any]], to_entries: list[dict[str, Any]]) -> dict[str, Any]:
    from_map = {e["key"]: e for e in from_entries}
    to_map = {e["key"]: e for e in to_entries}
    added = []
    removed = []
    changed = []
    for key in sorted(to_map.keys() - from_map.keys()):
        added.append({"key": key, "new_value": to_map[key].get("value"), "source": to_map[key].get("source")})
    for key in sorted(from_map.keys() - to_map.keys()):
        removed.append({"key": key, "old_value": from_map[key].get("value"), "source": from_map[key].get("source")})
    for key in sorted(from_map.keys() & to_map.keys()):
        old_value = from_map[key].get("value")
        new_value = to_map[key].get("value")
        if old_value != new_value:
            changed.append(
                {
                    "key": key,
                    "old_value": old_value,
                    "new_value": new_value,
                    "from_source": from_map[key].get("source"),
                    "to_source": to_map[key].get("source"),
                }
            )
    return {"added": added, "removed": removed, "changed": changed}


@app.get("/api/config/diff")
async def config_diff_get(
    from_snapshot: str | None = Query(default=None, min_length=1),
    from_snapshot_id: str | None = Query(default=None, min_length=1),
    scope: str | None = Query(default=None),
    project_id: str | None = Query(default=None),
) -> JSONResponse:
    snapshot_id = (from_snapshot_id or from_snapshot or "").strip()
    if not snapshot_id:
        return JSONResponse(status_code=400, content={"error": "CONFIG_SNAPSHOT_ID_REQUIRED"})
    snapshot = get_config_store().get_snapshot(snapshot_id)
    if snapshot is None:
        return JSONResponse(status_code=404, content={"error": "CONFIG_SNAPSHOT_NOT_FOUND", "snapshot_id": snapshot_id})
    from_entries = list(snapshot.get("payload", {}).get("entries", []))
    to_entries, _ = get_config_store().list_entries(
        search=None,
        scope=scope,
        project_id=project_id,
        type_filter=None,
        page=1,
        limit=10000,
    )
    return JSONResponse(status_code=200, content={"from_snapshot": snapshot_id, "diff": _build_diff(from_entries, to_entries)})


@app.post("/api/config/rollback_from_snapshot")
async def config_rollback_from_snapshot(request: Request) -> JSONResponse:
    payload = await request.json()
    snapshot_id = str(payload.get("snapshot_id", "")).strip()
    if not snapshot_id:
        return JSONResponse(status_code=400, content={"error": "CONFIG_SNAPSHOT_ID_REQUIRED"})
    dry_run = bool(payload.get("dry_run", False))
    module_prefix = str(payload.get("module_prefix", "")).strip() or None
    actor = request.headers.get("X-Actor", "local")
    snapshot = get_config_store().get_snapshot(snapshot_id)
    if snapshot is None:
        return JSONResponse(status_code=404, content={"error": "CONFIG_SNAPSHOT_NOT_FOUND", "snapshot_id": snapshot_id})
    entries = list(snapshot.get("payload", {}).get("entries", []))
    if module_prefix:
        entries = [entry for entry in entries if str(entry.get("key", "")).startswith(module_prefix)]
    if dry_run:
        return JSONResponse(status_code=200, content={"ok": True, "dry_run": True, "changes": entries})
    applied = []
    skipped = []
    for item in entries:
        key = str(item.get("key", "")).strip()
        if not key:
            continue
        parsed_value, parse_error = _parse_value(str(item.get("type", "String")), item.get("value"))
        if parse_error:
            continue
        schema_version = int(item.get("schema_version", 1))
        failure = validate_config_entry(key=key, value=parsed_value, schema_version=schema_version)
        if failure is not None:
            return JSONResponse(status_code=400, content={"error": "CONFIG_ROLLBACK_SCHEMA_FAILED", "key": key, "errors": failure.errors})
        if key.endswith("_ref"):
            ref = str(parsed_value or "")
            if not ref:
                skipped.append({"key": key, "reason": "snapshot_secret_redacted"})
                continue
            if not is_secret_ref(ref) or not secret_exists(ref):
                return JSONResponse(status_code=400, content={"error": "CONFIG_ROLLBACK_SECRET_MISSING", "key": key, "ref": ref})
        module = module_for_key(key) or str(item.get("module", "general"))
        get_config_store().upsert_entry(
            key=key,
            value=parsed_value,
            value_type=str(item.get("value_type", "string")),
            module=module,
            scope=str(item.get("scope", "global")),
            project_id=item.get("project_id"),
            description="",
            source="db",
            schema_version=schema_version,
            is_secret=bool(item.get("is_secret", False)),
            is_hot_reload=bool(item.get("is_hot_reload", True)),
            actor=actor,
            audit_op="rollback",
            decision_id=str(payload.get("decision_id", "")).strip() or None,
            reason=str(payload.get("reason", "")).strip() or f"rollback_from_snapshot:{snapshot_id}",
            risk_level="high" if is_high_risk_key(key) else "low",
        )
        get_config_cache().invalidate(key)
        get_config_cache().invalidate_prefix(f"{module}.")
        applied.append({"key": key})
    get_config_store().append_timeline(
        event_type="config.snapshot.rollback",
        actor=actor,
        module=None,
        config_key=None,
        project_id=snapshot.get("project_id"),
        decision_id=str(payload.get("decision_id", "")).strip() or None,
        risk_level="medium",
        reason=str(payload.get("reason", "")).strip() or None,
        payload={"snapshot_id": snapshot_id, "applied_count": len(applied)},
    )
    return JSONResponse(status_code=200, content={"ok": True, "applied": applied, "skipped": skipped})


@app.get("/api/config/timeline")
async def config_timeline_get(
    limit: int = Query(default=200, ge=1, le=1000),
    scope: str | None = Query(default=None),
    project_id: str | None = Query(default=None),
) -> JSONResponse:
    events = get_config_store().list_timeline(limit=limit)
    if project_id:
        events = [event for event in events if event.get("project_id") == project_id]
    if scope:
        events = [event for event in events if event.get("payload", {}).get("scope") == scope]
    return JSONResponse(status_code=200, content={"events": events})


@app.websocket("/ws/chat/{session_id}")
async def websocket_chat(session_id: str, websocket: WebSocket) -> None:
    await ws_chat.manager.connect(session_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()

            if data.strip() == "ping":
                await websocket.send_json({"type": "pong", "ts": datetime.now(timezone.utc).isoformat()})
                continue

            if not data.strip():
                continue

            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                await ws_chat.manager.send_message(
                    session_id,
                    {"type": "message.error", "content": "Invalid JSON payload", "metadata": {"source": "real"}},
                )
                continue

            message_type = str(message.get("type", "user_message"))
            content = message.get("content", "")
            metadata = message.get("metadata", {})
            try:
                if message_type == "user_message":
                    if isinstance(content, str) and content.strip().startswith("/task"):
                        await ws_chat.handle_task_command(session_id, content, metadata if isinstance(metadata, dict) else {})
                        continue

                    command_id = str(message.get("command_id") or "").strip() or None
                    start_result = await ws_chat.start_user_message_stream(
                        session_id=session_id,
                        content=content,
                        metadata=metadata if isinstance(metadata, dict) else {},
                        command_id=command_id,
                    )
                    if not start_result.get("ok"):
                        await ws_chat.manager.send_message(
                            session_id,
                            {
                                "type": "message.error",
                                "content": f"Failed to start stream: {start_result.get('reason', 'unknown')}",
                                "metadata": {"source": "real", "error_type": "stream_start_failed"},
                            },
                        )
                    continue

                if message_type == "control.stop":
                    command_id = str(message.get("command_id", "")).strip()
                    if not command_id:
                        await ws_chat.manager.send_message(
                            session_id,
                            {
                                "type": "control.ack",
                                "session_id": session_id,
                                "command_id": "",
                                "status": "rejected",
                                "reason": "missing_command_id",
                            },
                        )
                        continue

                    ack = await ws_chat.request_stop(
                        session_id=session_id,
                        run_id=message.get("run_id"),
                        command_id=command_id,
                        reason=str(message.get("reason") or "user_clicked_stop"),
                        actor="ws",
                        scope=str(message.get("scope") or "run_and_hold"),
                    )
                    await ws_chat.manager.send_message(session_id, ack)
                    continue

                if message_type == "resume":
                    requested_run_id = str(message.get("run_id") or "").strip() or None
                    try:
                        requested_last_seq = int(message.get("last_seq") or 0)
                    except (TypeError, ValueError):
                        requested_last_seq = 0

                    resume_result = await ws_chat.resume_stream(
                        session_id=session_id,
                        run_id=requested_run_id,
                        last_seq=max(0, requested_last_seq),
                    )
                    replay_events = resume_result.pop("events", [])
                    for event in replay_events:
                        await ws_chat.manager.send_message(session_id, event)
                    await ws_chat.manager.send_message(
                        session_id,
                        {
                            "type": "resume.status",
                            **resume_result,
                            "replayed_count": len(replay_events),
                        },
                    )
                    continue

                if message_type == "control.edit_resend":
                    command_id = str(message.get("command_id", "")).strip()
                    target_message_id = str(message.get("target_message_id", "")).strip()
                    if not command_id or not target_message_id:
                        await ws_chat.manager.send_message(
                            session_id,
                            {
                                "type": "control.ack",
                                "session_id": session_id,
                                "command_id": command_id,
                                "status": "rejected",
                                "reason": "missing_command_id_or_target_message_id",
                            },
                        )
                        continue

                    ack = await ws_chat.handle_edit_resend(
                        session_id=session_id,
                        target_message_id=target_message_id,
                        new_content=str(message.get("new_content") or ""),
                        command_id=command_id,
                        reason=str(message.get("reason") or "edited_resend"),
                        metadata=metadata if isinstance(metadata, dict) else {},
                    )
                    await ws_chat.manager.send_message(session_id, ack)
                    continue

                if message_type.startswith("control."):
                    await ws_chat.manager.send_message(
                        session_id,
                        {
                            "type": "control.ack",
                            "session_id": session_id,
                            "command_id": str(message.get("command_id", "")),
                            "status": "rejected",
                            "reason": f"unsupported_message_type:{message_type}",
                        },
                    )
                else:
                    await ws_chat.manager.send_message(
                        session_id,
                        {
                            "type": "message.error",
                            "session_id": session_id,
                            "content": f"Unsupported message type: {message_type}",
                            "metadata": {"source": "real"},
                        },
                    )
            except Exception as exc:
                logger.exception("websocket_chat message processing failed (session=%s, type=%s)", session_id, message_type)
                try:
                    await ws_chat.manager.send_message(
                        session_id,
                        {
                            "type": "message.error",
                            "session_id": session_id,
                            "content": f"Request handling error: {exc}",
                            "metadata": {"source": "real", "error_type": "request_handler_failure"},
                        },
                    )
                except Exception:
                    # If sending the error fails, keep loop alive and rely on reconnect if needed.
                    pass
    except WebSocketDisconnect:
        ws_chat.manager.disconnect(session_id)
    except Exception:
        logger.exception("websocket_chat loop failed (session=%s)", session_id)
        ws_chat.manager.disconnect(session_id)


@app.post("/api/chat/runs/{run_id}/cancel")
async def cancel_chat_run(run_id: str, request: Request) -> JSONResponse:
    payload = await request.json() if request else {}
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="Invalid payload")

    session_id = str(payload.get("session_id", "")).strip()
    command_id = str(payload.get("command_id", "")).strip()
    reason = str(payload.get("reason") or "ws_disconnected")

    if not session_id or not command_id:
        return JSONResponse(
            status_code=422,
            content={"status": "rejected", "reason": "session_id_and_command_id_required", "run_id": run_id},
        )

    ack = await ws_chat.request_stop(
        session_id=session_id,
        run_id=run_id,
        command_id=command_id,
        reason=reason,
        actor="rest",
        scope=str(payload.get("scope") or "run_and_hold"),
    )
    return JSONResponse(status_code=200, content=ack)


@app.websocket("/ws/governance")
async def websocket_governance(websocket: WebSocket) -> None:
    client_id = f"client-{id(websocket)}"
    await ws_governance.manager.connect(client_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data.strip() == "ping":
                await websocket.send_json({"type": "pong", "ts": datetime.now(timezone.utc).isoformat()})
    except WebSocketDisconnect:
        ws_governance.manager.disconnect(client_id)
    except Exception:
        ws_governance.manager.disconnect(client_id)
        raise


@app.websocket("/ws/coding/{session_id}")
async def websocket_coding(session_id: str, websocket: WebSocket) -> None:
    await ws_coding.manager.connect(session_id, websocket)
    try:
        state = ws_coding.get_demo_state(session_id)
        await ws_coding.manager.send_event(
            session_id,
            {
                "run_id": str(state.get("run_id") or ""),
                "task_id": None,
                "role": "system",
                "demo_stage": str(state.get("stage") or "discussion"),
                "plan_id": state.get("plan_id"),
                "session_id": session_id,
                "seq": 0,
                "ts": datetime.now(timezone.utc).isoformat(),
                "type": "demo.state",
                "payload": state,
            },
        )
        while True:
            data = await websocket.receive_text()
            if data.strip() == "ping":
                await websocket.send_json({"type": "pong", "ts": datetime.now(timezone.utc).isoformat()})
                continue

            if not data.strip():
                continue

            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                await ws_coding.manager.send_event(
                    session_id,
                    {
                        "run_id": "",
                        "task_id": None,
                        "role": "system",
                        "demo_stage": "discussion",
                        "plan_id": None,
                        "session_id": session_id,
                        "seq": 0,
                        "ts": datetime.now(timezone.utc).isoformat(),
                        "type": "message.error",
                        "payload": {"message": "Invalid JSON payload"},
                    },
                )
                continue

            message_type = str(message.get("type", "run.start"))
            if message_type == "demo.state.get":
                current_state = ws_coding.get_demo_state(session_id)
                await ws_coding.manager.send_event(
                    session_id,
                    {
                        "run_id": str(current_state.get("run_id") or ""),
                        "task_id": None,
                        "role": "system",
                        "demo_stage": str(current_state.get("stage") or "discussion"),
                        "plan_id": current_state.get("plan_id"),
                        "session_id": session_id,
                        "seq": 0,
                        "ts": datetime.now(timezone.utc).isoformat(),
                        "type": "demo.state",
                        "payload": current_state,
                    },
                )
                continue

            if message_type == "discussion.update":
                payload = message.get("requirements") if isinstance(message.get("requirements"), dict) else {}
                current_state = await ws_coding.save_discussion_requirements(session_id=session_id, requirements=payload)
                await ws_coding.emit_external_event(
                    session_id=session_id,
                    run_id=str(current_state.get("run_id") or ""),
                    event_type="discussion.updated",
                    payload={"requirements": current_state.get("requirements", {})},
                    role="planner",
                    demo_stage="discussion",
                    plan_id=current_state.get("plan_id"),
                )
                await ws_coding.manager.send_event(
                    session_id,
                    {
                        "run_id": str(current_state.get("run_id") or ""),
                        "task_id": None,
                        "role": "system",
                        "demo_stage": str(current_state.get("stage") or "discussion"),
                        "plan_id": current_state.get("plan_id"),
                        "session_id": session_id,
                        "seq": 0,
                        "ts": datetime.now(timezone.utc).isoformat(),
                        "type": "demo.state",
                        "payload": current_state,
                    },
                )
                continue

            if message_type == "plan.generate":
                current_state = await ws_coding.generate_plan(session_id=session_id)
                await ws_coding.manager.send_event(
                    session_id,
                    {
                        "run_id": str(current_state.get("run_id") or ""),
                        "task_id": None,
                        "role": "system",
                        "demo_stage": str(current_state.get("stage") or "planning"),
                        "plan_id": current_state.get("plan_id"),
                        "session_id": session_id,
                        "seq": 0,
                        "ts": datetime.now(timezone.utc).isoformat(),
                        "type": "demo.state",
                        "payload": current_state,
                    },
                )
                continue

            if message_type == "plan.freeze":
                current_state = await ws_coding.freeze_plan(session_id=session_id)
                await ws_coding.manager.send_event(
                    session_id,
                    {
                        "run_id": str(current_state.get("run_id") or ""),
                        "task_id": None,
                        "role": "system",
                        "demo_stage": str(current_state.get("stage") or "planning"),
                        "plan_id": current_state.get("plan_id"),
                        "session_id": session_id,
                        "seq": 0,
                        "ts": datetime.now(timezone.utc).isoformat(),
                        "type": "demo.state",
                        "payload": current_state,
                    },
                )
                continue

            if message_type == "run.start":
                prompt = str(message.get("prompt") or message.get("content") or "")
                metadata = message.get("metadata") if isinstance(message.get("metadata"), dict) else {}
                started = await ws_coding.start_run(session_id=session_id, prompt=prompt, metadata=metadata)
                if not started.get("ok"):
                    await ws_coding.manager.send_event(
                        session_id,
                        {
                            "run_id": str(started.get("run_id") or ""),
                            "task_id": None,
                            "role": "system",
                            "demo_stage": str(started.get("stage") or "planning"),
                            "plan_id": None,
                            "session_id": session_id,
                            "seq": 0,
                            "ts": datetime.now(timezone.utc).isoformat(),
                            "type": "message.error",
                            "payload": {
                                "reason": str(started.get("reason") or "unknown"),
                                "stage": started.get("stage"),
                                "spec_frozen": started.get("spec_frozen"),
                            },
                        },
                    )
                continue

            if message_type == "ask.query":
                query_payload = message.get("payload") if isinstance(message.get("payload"), dict) else {}
                asked = await ws_coding.handle_ask_query(
                    session_id=session_id,
                    run_id=str(message.get("run_id") or query_payload.get("run_id") or ""),
                    scope=str(query_payload.get("scope") or "all"),
                    key=str(query_payload.get("key") or ""),
                )
                if not asked.get("ok"):
                    await ws_coding.manager.send_event(
                        session_id,
                        {
                            "run_id": str(message.get("run_id") or ""),
                            "task_id": None,
                            "role": "system",
                            "demo_stage": "worker",
                            "plan_id": None,
                            "session_id": session_id,
                            "seq": 0,
                            "ts": datetime.now(timezone.utc).isoformat(),
                            "type": "message.error",
                            "payload": {"reason": str(asked.get("reason") or "ask_failed")},
                        },
                    )
                continue

            if message_type == "control.stop":
                run_id = str(message.get("run_id") or "")
                command_id = str(message.get("command_id") or "").strip()
                if not run_id or not command_id:
                    await ws_coding.manager.send_event(
                        session_id,
                        {
                            "run_id": run_id,
                            "task_id": None,
                            "role": "system",
                            "demo_stage": "worker",
                            "plan_id": None,
                            "session_id": session_id,
                            "seq": 0,
                            "ts": datetime.now(timezone.utc).isoformat(),
                            "type": "control.ack",
                            "payload": {
                                "status": "rejected",
                                "reason": "missing_run_id_or_command_id",
                                "command_id": command_id,
                            },
                        },
                    )
                    continue
                await ws_coding.request_stop(
                    session_id=session_id,
                    run_id=run_id,
                    command_id=command_id,
                    reason=str(message.get("reason") or "user_clicked_stop"),
                )
                continue

            await ws_coding.manager.send_event(
                session_id,
                {
                    "run_id": str(message.get("run_id") or ""),
                    "task_id": None,
                    "role": "system",
                    "demo_stage": "worker",
                    "plan_id": None,
                    "session_id": session_id,
                    "seq": 0,
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "type": "control.ack",
                    "payload": {"status": "rejected", "reason": f"unsupported_message_type:{message_type}"},
                },
            )
    except WebSocketDisconnect:
        ws_coding.manager.disconnect(session_id)
    except Exception:
        ws_coding.manager.disconnect(session_id)
        raise


def _apply_runtime_env_overrides(changed_key: str | None = None) -> None:
    keys = [changed_key] if changed_key else list(RUNTIME_ENV_BINDINGS.keys())
    for key in keys:
        env_var = RUNTIME_ENV_BINDINGS.get(key)
        if not env_var:
            continue
        resolved = resolve_config(key=key)
        source = str(resolved.get("source") or "")
        value = resolved.get("value")
        if source in {"db", "env"} and value is not None:
            os.environ[env_var] = str(value)
            logger.info("Applied runtime config to environment: %s -> %s (source=%s)", key, env_var, source)
        else:
            os.environ.pop(env_var, None)
            logger.info("Cleared runtime environment override: %s -> %s (source=%s)", key, env_var, source)


def _debug_enabled() -> bool:
    """Determine whether to include debug info in error responses."""
    debug_flag = os.getenv("OCTOPUSOS_DEBUG", "").strip().lower()
    if debug_flag in {"1", "true", "yes", "on"}:
        return True
    if debug_flag in {"0", "false", "no", "off"}:
        return False
    return os.getenv("OCTOPUSOS_ENV", "").strip().lower() != "production"


async def custom_http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Log HTTP exceptions while returning a structured error response."""
    logger.warning(
        "HTTPException %s %s -> %s: %s"
        % (request.method, request.url.path, exc.status_code, exc.detail)
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "ok": False,
            "error": exc.detail,
            "detail": exc.detail,
            "status_code": exc.status_code,
        },
    )


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler with environment-aware debug output."""
    logger.error(
        "Unhandled exception %s %s" % (request.method, request.url.path),
        exc_info=exc,
    )
    if SENTRY_AVAILABLE and SENTRY_ENABLED:
        try:
            sentry_sdk.capture_exception(exc)
        except Exception:  # pragma: no cover - defensive logging
            logger.warning("Failed to report exception to Sentry")
    if _debug_enabled():
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
                "debug_info": {
                    "traceback": "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
                    "exception_type": type(exc).__name__,
                    "request_path": request.url.path,
                    "request_method": request.method,
                },
            },
        )

    return JSONResponse(
        status_code=500,
        content={"ok": False, "error": "Internal server error"},
    )


app.add_exception_handler(HTTPException, custom_http_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)


@app.on_event("startup")
async def startup_calls_cleanup() -> None:
    _apply_runtime_env_overrides()
    get_call_store().run_configured_cleanup()


_attention_injector_thread: threading.Thread | None = None
_work_exec_scheduler_thread: threading.Thread | None = None
_email_digest_scheduler_thread: threading.Thread | None = None


@app.on_event("startup")
async def startup_attention_injector_daemon() -> None:
    # Phase 3: drain chat injection queue in the background when enabled.
    # Safe by default because attention.chat_injection.enabled=false and/or mode!=chat_allowed.
    global _attention_injector_thread
    if _attention_injector_thread is not None and _attention_injector_thread.is_alive():
        return

    if os.getenv("OCTOPUSOS_ATTENTION_INJECTOR_DAEMON", "1").strip().lower() in {"0", "false", "no", "off"}:
        return

    def _loop() -> None:
        from octopusos.core.attention.chat_injector import ChatInjector

        injector = ChatInjector()
        while True:
            try:
                if injection_enabled() and injection_mode() == "chat_allowed":
                    injector.drain_queue(limit=50)
                    time.sleep(1.0)
                else:
                    time.sleep(2.0)
            except Exception:
                time.sleep(2.0)

    _attention_injector_thread = threading.Thread(target=_loop, daemon=True, name="attention-injector")
    _attention_injector_thread.start()


@app.on_event("startup")
async def startup_work_exec_scheduler_daemon() -> None:
    # Phase 4: background execution tasks (safe by default; requires work.auto_execute.enabled=true).
    global _work_exec_scheduler_thread
    if _work_exec_scheduler_thread is not None and _work_exec_scheduler_thread.is_alive():
        return

    if os.getenv("OCTOPUSOS_WORK_EXEC_SCHEDULER_DAEMON", "1").strip().lower() in {"0", "false", "no", "off"}:
        return

    def _loop() -> None:
        from octopusos.core.work.exec_scheduler import ExecScheduler
        from octopusos.core.work.work_mode import auto_execute_enabled

        scheduler = ExecScheduler()
        while True:
            try:
                if auto_execute_enabled():
                    scheduler.drain_once()
                    time.sleep(1.0)
                else:
                    time.sleep(2.0)
            except Exception:
                time.sleep(2.0)

    _work_exec_scheduler_thread = threading.Thread(target=_loop, daemon=True, name="work-exec-scheduler")
    _work_exec_scheduler_thread.start()


@app.on_event("startup")
async def startup_email_digest_scheduler_daemon() -> None:
    # Email digest scheduler: enqueue daily digest tasks (safe by default; gated by work mode + auto-exec).
    global _email_digest_scheduler_thread
    if _email_digest_scheduler_thread is not None and _email_digest_scheduler_thread.is_alive():
        return

    if os.getenv("OCTOPUSOS_EMAIL_DIGEST_SCHEDULER_DAEMON", "1").strip().lower() in {"0", "false", "no", "off"}:
        return

    def _loop() -> None:
        from octopusos.core.email.digest_scheduler import maybe_enqueue_daily_email_digest

        while True:
            try:
                maybe_enqueue_daily_email_digest()
                time.sleep(30.0)
            except Exception:
                time.sleep(30.0)

    _email_digest_scheduler_thread = threading.Thread(target=_loop, daemon=True, name="email-digest-scheduler")
    _email_digest_scheduler_thread.start()


@app.on_event("startup")
async def startup_communicationos_runtime() -> None:
    # Ensure CommunicationOS runtime is initialized at startup so logs clearly show
    # available channels and QR-capable adapters.
    try:
        from octopusos.communicationos.runtime import get_communication_runtime

        rt = get_communication_runtime()
        items = rt.list_marketplace()
        logger.info("CommunicationOS runtime initialized. Manifests: %s", [c.get("id") for c in items])
    except Exception as exc:
        logger.warning("CommunicationOS runtime init failed: %s", exc)


# ---------------------------------------------------------------------------
# Desktop Product Shell + embedded Console static serving (dev/test convenience)
# ---------------------------------------------------------------------------
#
# Desktop Electron normally serves:
# - Product UI at '/'
# - Console (WebUI) under '/console/*'
# and proxies '/api' + '/ws' to this backend.
#
# In dev/test environments where the Electron proxy is not running, we serve the
# checked-in dist bundles directly from this backend so Playwright can validate
# Product Shell navigation and iframe embedding end-to-end.


@app.get("/console")
@app.get("/console/")
@app.get("/console/{full_path:path}")
async def console_spa(full_path: str = "") -> FileResponse:
    """Serve the WebUI SPA under /console (Desktop embedding target)."""
    if not _desktop_has_ui():
        raise HTTPException(status_code=404, detail="Console UI dist not available")
    idx = _DESKTOP_WEBUI_DIST / "index.html"
    response = FileResponse(str(idx))
    response.set_cookie("csrf_token", secrets.token_urlsafe(16))
    return response


@app.get("/{full_path:path}")
async def desktop_static(full_path: str, request: Request):
    """Static file + SPA fallback for Desktop Product Shell and Console assets."""
    if not _desktop_has_ui():
        raise HTTPException(status_code=404, detail="Desktop UI dist not available")

    # If something reaches here under these prefixes, treat it as a true 404 rather
    # than serving HTML (prevents confusion when an API route is missing).
    if full_path.startswith("api") or full_path.startswith("ws"):
        raise HTTPException(status_code=404, detail="Not Found")

    # Serve static file if present (Product first, then WebUI assets).
    for base in (_DESKTOP_PRODUCT_DIST, _DESKTOP_WEBUI_DIST):
        p = _safe_join(base, full_path)
        if p and p.exists() and p.is_file():
            return FileResponse(str(p))

    # SPA fallback: Product Shell.
    idx = _DESKTOP_PRODUCT_DIST / "index.html"
    response = FileResponse(str(idx))
    response.set_cookie("csrf_token", secrets.token_urlsafe(16))
    return response
