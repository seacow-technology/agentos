"""NetworkOS capability API (M2).

Exposes a governance-first interface:
- request capability (declarative)
- approve (for explain_confirm)
- revoke
- status

Auditing is written to NetworkOS DB (network_audit_log) and must remain isolated
from CommunicationOS message_audit.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Header, HTTPException, Query

from octopusos.core.capabilities.admin_token import validate_admin_token
from octopusos.core.mcp.cloudflare_discovery import discover_cloudflare_setup
from octopusos.networkos.capabilities.engine import NetworkCapabilityEngine
from octopusos.networkos.config_store import NetworkConfigStore, ALLOWED_KEYS

router = APIRouter(prefix="/api/network", tags=["networkos"])
logger = logging.getLogger(__name__)


def _require_admin_token(token: Optional[str]) -> str:
    if not token:
        raise HTTPException(status_code=401, detail="Admin token required")
    if not validate_admin_token(token):
        raise HTTPException(status_code=403, detail="Invalid admin token")
    return "admin"


@router.post("/capabilities/request")
def request_capability(
    payload: Dict[str, Any] = Body(default={}),
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> Dict[str, Any]:
    actor = _require_admin_token(admin_token)
    capability = str(payload.get("capability") or "").strip()
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    if not capability:
        raise HTTPException(status_code=400, detail="capability required")
    engine = NetworkCapabilityEngine()
    res = engine.request_capability(capability=capability, params=params, requested_by=actor)
    if not res.get("ok"):
        raise HTTPException(status_code=400, detail=str(res.get("error") or "request_failed"))
    return {"ok": True, **res, "source": "real"}


@router.get("/capabilities/status")
def capabilities_status() -> Dict[str, Any]:
    engine = NetworkCapabilityEngine()
    res = engine.get_status()
    return {"ok": True, **res, "source": "real"}


@router.post("/capabilities/{request_id}/approve")
def approve_request(
    request_id: str,
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> Dict[str, Any]:
    actor = _require_admin_token(admin_token)
    engine = NetworkCapabilityEngine()
    res = engine.approve(request_id=str(request_id), actor=actor)
    if not res.get("ok"):
        raise HTTPException(status_code=400, detail=str(res.get("error") or "approve_failed"))
    return {"ok": True, **res, "source": "real"}


@router.post("/capabilities/{request_id}/revoke")
def revoke_request(
    request_id: str,
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> Dict[str, Any]:
    actor = _require_admin_token(admin_token)
    engine = NetworkCapabilityEngine()
    res = engine.revoke(request_id=str(request_id), actor=actor)
    if not res.get("ok"):
        raise HTTPException(status_code=400, detail=str(res.get("error") or "revoke_failed"))
    return {"ok": True, **res, "source": "real"}


@router.get("/config")
def get_network_config() -> Dict[str, Any]:
    store = NetworkConfigStore()
    resolved = store.resolve_cloudflare_config()
    return {
        "ok": True,
        "items": {k: v.to_dict() for k, v in resolved.items()},
        "source": "real",
    }


@router.post("/config")
def set_network_config(
    payload: Dict[str, Any] = Body(default={}),
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> Dict[str, Any]:
    actor = _require_admin_token(admin_token)
    items = payload.get("items")
    if not isinstance(items, dict):
        raise HTTPException(status_code=422, detail="items must be an object")
    store = NetworkConfigStore()
    for k, v in items.items():
        key = str(k or "").strip()
        if key not in ALLOWED_KEYS:
            raise HTTPException(status_code=422, detail=f"key_not_allowed:{key}")
        store.set_db_value(key=key, value=v, updated_by=actor)
    return {"ok": True, "updated": sorted(list(items.keys())), "source": "real"}


@router.post("/cloudflare/access/provision")
def provision_cloudflare_access(
    payload: Dict[str, Any] = Body(default={}),
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> Dict[str, Any]:
    actor = _require_admin_token(admin_token)
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    engine = NetworkCapabilityEngine()
    res = engine.request_capability(
        capability="network.cloudflare.access.provision",
        params=params,
        requested_by=actor,
    )
    if not res.get("ok"):
        raise HTTPException(status_code=400, detail=str(res.get("error") or "request_failed"))
    return {"ok": True, **res, "source": "real"}


@router.post("/cloudflare/access/revoke")
def revoke_cloudflare_access(
    payload: Dict[str, Any] = Body(default={}),
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> Dict[str, Any]:
    actor = _require_admin_token(admin_token)
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    engine = NetworkCapabilityEngine()
    res = engine.request_capability(
        capability="network.cloudflare.access.revoke",
        params=params,
        requested_by=actor,
    )
    if not res.get("ok"):
        raise HTTPException(status_code=400, detail=str(res.get("error") or "request_failed"))
    # revoke capability is also high-risk; requires approve if explain_confirm.
    return {"ok": True, **res, "source": "real"}


@router.get("/cloudflare/access/status")
def cloudflare_access_status(
    hostname: Optional[str] = Query(default=None),
    debug: int = Query(default=0, ge=0, le=1),
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> Dict[str, Any]:
    # Default output is intentionally minimal to avoid turning status into a control plane.
    # Extra IDs are returned only when explicitly requested via debug=1 (and admin-gated).
    if debug:
        _require_admin_token(admin_token)
    engine = NetworkCapabilityEngine()
    cfg = NetworkConfigStore().resolve_cloudflare_config()
    status = engine.cloudflare.access_status({"hostname": hostname} if hostname else {})
    # Expose non-sensitive service token id source/value for optional script assertions.
    st = cfg.get("network.cloudflare.service_token_id")
    scoping = engine.cloudflare.get_policy_scoping_status(
        {"hostname": hostname} if hostname else {},
        debug=bool(debug),
    )
    res: Dict[str, Any] = {
        "ok": True,
        "status": status.to_dict(),
        "service_token_id": (st.value if st else None),
        "service_token_id_source": (st.source if st else "missing"),
        "policy_scoped_token_id": scoping.get("policy_scoped_token_id"),
        "policy_scoping_ok": bool(scoping.get("policy_scoping_ok")),
        "policy_scoping_reason": scoping.get("policy_scoping_reason"),
        "source": "real",
    }
    if debug:
        res.update(
            {
                "access_app_id": scoping.get("access_app_id"),
                "service_auth_policy_id": scoping.get("service_auth_policy_id"),
                "policies_seen_count": scoping.get("policies_seen_count"),
                "policy_name_matched": bool(scoping.get("policy_name_matched")),
            }
        )
    return res


def _request_network_capability(
    *,
    capability: str,
    params: Dict[str, Any],
    admin_token: Optional[str],
) -> Dict[str, Any]:
    actor = _require_admin_token(admin_token)
    engine = NetworkCapabilityEngine()
    logger.info(
        "[networkos.webui] capability request received capability=%s actor=%s params_keys=%s",
        capability,
        actor,
        sorted(list((params or {}).keys())),
    )
    res = engine.request_capability(capability=str(capability), params=params or {}, requested_by=actor)
    if not res.get("ok"):
        logger.warning(
            "[networkos.webui] capability request failed capability=%s actor=%s error=%s",
            capability,
            actor,
            res.get("error"),
        )
        raise HTTPException(status_code=400, detail=str(res.get("error") or "request_failed"))
    request = res.get("request") if isinstance(res.get("request"), dict) else {}
    logger.info(
        "[networkos.webui] capability request created capability=%s request_id=%s decision=%s status=%s",
        capability,
        request.get("id"),
        request.get("decision"),
        request.get("status"),
    )
    return {"ok": True, **res, "source": "real"}


@router.get("/cloudflare/daemon/status")
def cloudflare_daemon_status(
    debug: int = Query(default=0, ge=0, le=1),
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> Dict[str, Any]:
    # Minimal status by default; debug expands to include logs tail (admin-gated).
    if debug:
        _require_admin_token(admin_token)
    engine = NetworkCapabilityEngine()
    st = engine.cloudflare.daemon_status({}, debug=bool(debug))
    return {"ok": True, "status": st, "source": "real"}


@router.post("/cloudflare/daemon/logs/clear")
def cloudflare_daemon_clear_logs(
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> Dict[str, Any]:
    _require_admin_token(admin_token)
    engine = NetworkCapabilityEngine()
    data = engine.cloudflare.daemon_clear_logs({})
    return {"ok": True, **data, "source": "real"}


@router.get("/cloudflare/tunnels")
def cloudflare_tunnels(
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> Dict[str, Any]:
    _require_admin_token(admin_token)
    engine = NetworkCapabilityEngine()
    data = engine.cloudflare.daemon_list_tunnels({})
    return {"ok": True, **data, "source": "real"}


@router.post("/cloudflare/tunnels/create")
def cloudflare_tunnels_create(
    payload: Dict[str, Any] = Body(default={}),
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> Dict[str, Any]:
    _require_admin_token(admin_token)
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    name = str(params.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="name_required")
    engine = NetworkCapabilityEngine()
    try:
        data = engine.cloudflare.daemon_create_tunnel({"name": name})
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True, **data, "source": "real"}


@router.post("/cloudflare/daemon/install")
def cloudflare_daemon_install(
    payload: Dict[str, Any] = Body(default={}),
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> Dict[str, Any]:
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    return _request_network_capability(capability="network.cloudflare.daemon.install", params=params, admin_token=admin_token)


@router.post("/cloudflare/daemon/uninstall")
def cloudflare_daemon_uninstall(
    payload: Dict[str, Any] = Body(default={}),
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> Dict[str, Any]:
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    return _request_network_capability(capability="network.cloudflare.daemon.uninstall", params=params, admin_token=admin_token)


@router.post("/cloudflare/cli/install")
def cloudflare_cli_install(
    payload: Dict[str, Any] = Body(default={}),
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> Dict[str, Any]:
    _require_admin_token(admin_token)
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    engine = NetworkCapabilityEngine()
    res = engine.cloudflare.cli_install(params)
    if not res.ok:
        raise HTTPException(status_code=400, detail=str(res.detail or "cli_install_failed"))
    return {"ok": True, "result": res.to_dict(), "source": "real"}


@router.get("/cloudflare/mcp/discover")
def cloudflare_mcp_discover(
    account_id: Optional[str] = Query(default=None),
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> Dict[str, Any]:
    _require_admin_token(admin_token)
    result = discover_cloudflare_setup(account_id=account_id)
    if not result.ok:
        raise HTTPException(status_code=400, detail=str(result.error or "mcp_discovery_failed"))
    return {"ok": True, "result": result.to_dict(), "source": "real"}


@router.post("/cloudflare/daemon/start")
def cloudflare_daemon_start(
    payload: Dict[str, Any] = Body(default={}),
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> Dict[str, Any]:
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    return _request_network_capability(capability="network.cloudflare.daemon.start", params=params, admin_token=admin_token)


@router.post("/cloudflare/daemon/stop")
def cloudflare_daemon_stop(
    payload: Dict[str, Any] = Body(default={}),
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> Dict[str, Any]:
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    return _request_network_capability(capability="network.cloudflare.daemon.stop", params=params, admin_token=admin_token)


@router.post("/cloudflare/daemon/restart")
def cloudflare_daemon_restart(
    payload: Dict[str, Any] = Body(default={}),
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> Dict[str, Any]:
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    return _request_network_capability(capability="network.cloudflare.daemon.restart", params=params, admin_token=admin_token)


@router.post("/cloudflare/daemon/autostart/enable")
def cloudflare_daemon_enable_autostart(
    payload: Dict[str, Any] = Body(default={}),
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> Dict[str, Any]:
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    return _request_network_capability(
        capability="network.cloudflare.daemon.enable_autostart", params=params, admin_token=admin_token
    )


@router.post("/cloudflare/daemon/autostart/disable")
def cloudflare_daemon_disable_autostart(
    payload: Dict[str, Any] = Body(default={}),
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> Dict[str, Any]:
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    return _request_network_capability(
        capability="network.cloudflare.daemon.disable_autostart", params=params, admin_token=admin_token
    )
