"""Teams Channel Provisioning API (Phase B local multi-organization)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query

from octopusos.channels.teams.models import TeamsOrganizationConnection
from octopusos.channels.teams.oauth import TeamsOAuthService
from octopusos.channels.teams.provisioning.orchestrator import TeamsProvisionOrchestrator
from octopusos.channels.teams.store import TeamsConnectionStore


router = APIRouter(prefix="/api/channels/teams", tags=["channels-teams"])


def _connection_to_public(obj: TeamsOrganizationConnection) -> Dict[str, Any]:
    data = obj.to_dict()
    # Never expose token refs to browser payloads.
    data.pop("token_ref", None)
    return data


@router.get("/orgs")
def list_org_connections() -> Dict[str, Any]:
    store = TeamsConnectionStore()
    rows = [_connection_to_public(x) for x in store.list_connections()]
    return {"ok": True, "items": rows, "total": len(rows)}


@router.get("/oauth/start")
def teams_oauth_start(tenant_hint: str = Query(default="")) -> Dict[str, Any]:
    svc = TeamsOAuthService()
    try:
        return svc.build_auth_url(tenant_hint=tenant_hint)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/oauth/callback")
def teams_oauth_callback(
    code: Optional[str] = Query(default=None),
    state: Optional[str] = Query(default=None),
    error: Optional[str] = Query(default=None),
    error_description: Optional[str] = Query(default=None),
    reconcile: bool = Query(default=True),
) -> Dict[str, Any]:
    if error:
        raise HTTPException(status_code=400, detail={"error": error, "error_description": error_description or ""})
    if not code or not state:
        raise HTTPException(status_code=400, detail="missing_code_or_state")

    svc = TeamsOAuthService()
    store = TeamsConnectionStore()
    try:
        token_data = svc.exchange_code(code=code, state=state)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    tenant_id = str(token_data.get("tenant_id") or "").strip()
    if not tenant_id:
        raise HTTPException(status_code=400, detail="cannot_resolve_tenant_id")

    existing = store.get_connection(tenant_id) or TeamsOrganizationConnection(tenant_id=tenant_id)
    existing.status = "Authorized"
    existing.token_ref = str(token_data.get("token_ref") or "")
    existing.token_expires_at_ms = int(token_data.get("token_expires_at_ms") or 0)
    existing.scopes = str(token_data.get("scopes") or "")
    existing.deployment_strategy = "shared"
    stored = store.upsert_connection(existing)
    store.log_event(tenant_id, "oauth_connected", payload={"scopes": existing.scopes.split()})

    response: Dict[str, Any] = {
        "ok": True,
        "tenant_id": tenant_id,
        "connection": _connection_to_public(stored),
        "reconcile_started": False,
    }

    if reconcile:
        orchestrator = TeamsProvisionOrchestrator(store=store)
        result = orchestrator.reconcile_teams_connection(tenant_id)
        response["reconcile_started"] = True
        response["reconcile_result"] = result.to_dict()

    return response


@router.post("/{tenant_id}/reconcile")
def reconcile_org(tenant_id: str) -> Dict[str, Any]:
    store = TeamsConnectionStore()
    if not store.get_connection(tenant_id):
        raise HTTPException(status_code=404, detail="tenant_not_found")
    orchestrator = TeamsProvisionOrchestrator(store=store)
    result = orchestrator.reconcile_teams_connection(tenant_id)
    return {"ok": result.ok, "tenant_id": tenant_id, "result": result.to_dict()}


@router.post("/{tenant_id}/disconnect")
def disconnect_org(tenant_id: str) -> Dict[str, Any]:
    store = TeamsConnectionStore()
    row = store.get_connection(tenant_id)
    if not row:
        raise HTTPException(status_code=404, detail="tenant_not_found")
    row.status = "Disconnected"
    row.token_ref = ""
    row.token_expires_at_ms = 0
    row.teams_app_id = ""
    updated = store.upsert_connection(row)
    store.log_event(tenant_id, "org_disconnected", payload={"catalog_app_preserved": True})
    return {
        "ok": True,
        "connection": _connection_to_public(updated),
        "catalog_app_preserved": True,
        "note": "Disconnect only clears local connection/token state and does not delete tenant catalog app.",
    }


@router.get("/{tenant_id}/events")
def list_org_events(tenant_id: str, limit: int = Query(default=200, ge=1, le=2000)) -> Dict[str, Any]:
    store = TeamsConnectionStore()
    items = store.list_events(tenant_id, limit=limit)
    return {"ok": True, "items": items, "total": len(items)}


@router.get("/{tenant_id}/evidence")
def get_latest_evidence(tenant_id: str) -> Dict[str, Any]:
    store = TeamsConnectionStore()
    row = store.get_connection(tenant_id)
    if not row:
        raise HTTPException(status_code=404, detail="tenant_not_found")
    base = str(row.last_evidence_path or "").strip()
    if not base:
        return {"ok": True, "tenant_id": tenant_id, "evidence": None}

    report_dir = Path(base)
    md_path = report_dir / "deploy_report.md"
    json_path = report_dir / "deploy_report.json"

    payload: Dict[str, Any] = {
        "dir": str(report_dir),
        "md_path": str(md_path),
        "json_path": str(json_path),
        "md": md_path.read_text(encoding="utf-8") if md_path.exists() else "",
        "json": {},
    }
    if json_path.exists():
        try:
            payload["json"] = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception:
            payload["json"] = {}

    return {"ok": True, "tenant_id": tenant_id, "evidence": payload}
