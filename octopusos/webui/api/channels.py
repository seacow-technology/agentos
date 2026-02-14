"""Channels API - CommunicationOS channel management + WhatsApp Web QR flow.

This router provides a real implementation for:
- Channel marketplace listing (manifests)
- Channel config (including default model route/provider/model)
- Connect/status/qr for local QR channels (whatsapp_web)
- Webhook bridging for channels that expose handle_webhook() (e.g., teams/imessage)
- Per-peer bindings and model switching without reconnecting WhatsApp
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from octopusos.core.capabilities.admin_token import validate_admin_token
from octopusos.communicationos.runtime import get_communication_runtime
from octopusos.channels.teams.store import TeamsConnectionStore
from octopusos.webui.api.compat_state import audit_event, db_connect, ensure_schema

router = APIRouter(prefix="/api", tags=["channels"])
logger = logging.getLogger(__name__)


def _extract_teams_tenant_id(activity: Dict[str, Any]) -> str:
    """
    Extract Teams tenant id from a Bot Framework activity payload.

    Teams activities commonly include tenant id in one of:
    - channelData.tenant.id
    - channelData.tenantId
    - conversation.tenantId
    """
    channel_data = activity.get("channelData") or {}
    if isinstance(channel_data, dict):
        tenant = channel_data.get("tenant") or {}
        if isinstance(tenant, dict):
            v = str(tenant.get("id") or "").strip()
            if v:
                return v
        v = str(channel_data.get("tenantId") or "").strip()
        if v:
            return v

    conv = activity.get("conversation") or {}
    if isinstance(conv, dict):
        v = str(conv.get("tenantId") or "").strip()
        if v:
            return v

    return ""


async def _handle_bridge_webhook(*, channel_id: str, request: Request) -> JSONResponse:
    rt = get_communication_runtime()
    try:
        rt.ensure_adapter_started(channel_id)
    except Exception as e:
        return JSONResponse(status_code=200, content={"ok": False, "error": f"adapter_not_ready:{e}"})

    state = rt._adapters.get(channel_id)  # type: ignore[attr-defined]
    if not state:
        return JSONResponse(status_code=200, content={"ok": False, "error": "adapter_not_running"})

    adapter = state.adapter
    if not hasattr(adapter, "handle_webhook"):
        return JSONResponse(status_code=501, content={"ok": False, "error": "webhook_not_supported"})

    body = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}

    try:
        code, resp = adapter.handle_webhook(headers=headers, body_bytes=body)
        if isinstance(resp, dict):
            resp.setdefault("source", "real")
        return JSONResponse(status_code=int(code), content=resp)
    except PermissionError as e:
        return JSONResponse(status_code=403, content={"ok": False, "error": str(e)})
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": f"webhook_failed:{e}"})


def _extract_teams_tenant_id(activity: Dict[str, Any]) -> str:
    if not isinstance(activity, dict):
        return ""
    channel_data = activity.get("channelData")
    if isinstance(channel_data, dict):
        tenant_obj = channel_data.get("tenant")
        if isinstance(tenant_obj, dict):
            tenant_id = str(tenant_obj.get("id") or "").strip()
            if tenant_id:
                return tenant_id
        tenant_id = str(channel_data.get("tenantId") or "").strip()
        if tenant_id:
            return tenant_id
    conversation = activity.get("conversation")
    if isinstance(conversation, dict):
        tenant_id = str(conversation.get("tenantId") or "").strip()
        if tenant_id:
            return tenant_id
    return ""


def _resolve_teams_tenant_id(activity: Dict[str, Any]) -> str:
    tenant_id = _extract_teams_tenant_id(activity)
    if tenant_id:
        return tenant_id
    # Some Teams system activities can omit tenant metadata; in single-tenant
    # local deployments fallback to the only connected org to avoid false 403s.
    try:
        store = TeamsConnectionStore()
        connected = [x for x in store.list_connections() if x.status != "Disconnected"]
        if len(connected) == 1:
            return str(connected[0].tenant_id or "").strip()
    except Exception:
        return ""
    return ""


def _audit_teams_tenant_reject(*, reason: str, tenant_id: str, channel_id: str) -> None:
    conn = db_connect()
    try:
        ensure_schema(conn)
        audit_event(
            conn,
            event_type="teams_webhook_rejected",
            endpoint="/api/channels/teams/webhook",
            actor="system",
            payload={
                "reason": reason,
                "tenant_id": tenant_id,
                "channel_id": channel_id,
            },
            result={"ok": False},
        )
        conn.commit()
    finally:
        conn.close()


def _require_admin_token(token: Optional[str]) -> str:
    if not token:
        raise HTTPException(status_code=401, detail="Admin token required")
    if not validate_admin_token(token):
        raise HTTPException(status_code=403, detail="Invalid admin token")
    return "admin"


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@router.get("/channels-marketplace")
def list_channels_marketplace() -> Dict[str, Any]:
    rt = get_communication_runtime()
    return {"items": rt.list_marketplace(), "total": len(rt.list_marketplace()), "source": "real"}


@router.get("/channels")
def list_configured_channels() -> Dict[str, Any]:
    rt = get_communication_runtime()
    rows = rt.config_store.list_channels()
    return {"channels": rows, "total": len(rows), "source": "real"}


@router.get("/channels/{channel_id}/config")
def get_channel_config(channel_id: str) -> Dict[str, Any]:
    rt = get_communication_runtime()
    try:
        return rt.get_channel_config_for_ui(channel_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/channels/{channel_id}/configure")
def configure_channel(
    channel_id: str,
    payload: Dict[str, Any] = Body(default={}),
) -> Dict[str, Any]:
    actor = "webui"
    config = payload.get("config")
    if not isinstance(config, dict):
        raise HTTPException(status_code=400, detail="config must be an object")

    rt = get_communication_runtime()
    try:
        rt.configure_channel(channel_id, config, performed_by=actor)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    conn = db_connect()
    try:
        ensure_schema(conn)
        audit_event(
            conn,
            event_type="channel_configure",
            endpoint=f"/api/channels/{channel_id}/configure",
            actor=actor,
            payload={"channel_id": channel_id, "config_keys": sorted(list(config.keys()))},
            result={"ok": True},
        )
        conn.commit()
    finally:
        conn.close()

    return {"ok": True, "channel_id": channel_id, "source": "real"}


@router.post("/channels/{channel_id}/enable")
def enable_channel(
    channel_id: str,
) -> Dict[str, Any]:
    actor = "webui"
    rt = get_communication_runtime()
    try:
        rt.enable_channel(channel_id, True, performed_by=actor)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True, "enabled": True, "channel_id": channel_id, "source": "real"}


@router.post("/channels/{channel_id}/disable")
def disable_channel(
    channel_id: str,
) -> Dict[str, Any]:
    actor = "webui"
    rt = get_communication_runtime()
    rt.enable_channel(channel_id, False, performed_by=actor)
    return {"ok": True, "enabled": False, "channel_id": channel_id, "source": "real"}


@router.post("/channels/{channel_id}/connect")
def connect_channel(channel_id: str) -> Dict[str, Any]:
    rt = get_communication_runtime()
    try:
        rt.ensure_adapter_started(channel_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    status = rt.get_adapter_status(channel_id)
    state = status.get("state")
    return {"ok": True, "channel_id": channel_id, "state": state, "status": status, "source": "real"}


@router.get("/channels/{channel_id}/status")
def channel_status(channel_id: str) -> Dict[str, Any]:
    rt = get_communication_runtime()
    return {"ok": True, "channel_id": channel_id, "status": rt.get_adapter_status(channel_id), "source": "real"}


@router.get("/channels/{channel_id}/qr")
def channel_qr(channel_id: str) -> Dict[str, Any]:
    rt = get_communication_runtime()
    try:
        return {"channel_id": channel_id, **rt.get_adapter_qr(channel_id), "source": "real"}
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.get("/channels/{channel_id}/bindings")
def list_bindings(channel_id: str, limit: int = Query(default=200, ge=1, le=1000)) -> Dict[str, Any]:
    rt = get_communication_runtime()
    items = [b.to_dict() for b in rt.bindings_store.list_by_channel(channel_id=channel_id, limit=int(limit))]
    return {"ok": True, "bindings": items, "total": len(items), "source": "real"}


@router.post("/channels/{channel_id}/bindings/{binding_id}/switch")
def switch_binding(
    channel_id: str,
    binding_id: str,
    payload: Dict[str, Any] = Body(default={}),
) -> Dict[str, Any]:
    actor = "webui"
    mode = payload.get("model_route")
    provider = payload.get("provider")
    model = payload.get("model")
    rt = get_communication_runtime()
    binding = rt.bindings_store.get_by_id(binding_id=binding_id)
    if not binding or binding.channel_id != channel_id:
        raise HTTPException(status_code=404, detail="binding not found")

    updated = rt.bindings_store.update_binding(binding_id=binding_id, model_route=mode, provider=provider, model=model)
    if not updated:
        raise HTTPException(status_code=404, detail="binding not found")

    # Apply to session metadata so next message uses new route/provider/model without reconnecting WhatsApp.
    try:
        rt.chat_service.update_session_metadata(
            session_id=updated.session_id,
            metadata={"model_route": updated.model_route, "provider": updated.provider, "model": updated.model},
        )
    except Exception:
        pass

    conn = db_connect()
    try:
        ensure_schema(conn)
        audit_event(
            conn,
            event_type="channel_binding_switch",
            endpoint=f"/api/channels/{channel_id}/bindings/{binding_id}/switch",
            actor=actor,
            payload={"channel_id": channel_id, "binding_id": binding_id, "patch": {"model_route": mode, "provider": provider, "model": model}},
            result={"ok": True},
        )
        conn.commit()
    finally:
        conn.close()

    return {"ok": True, "binding": updated.to_dict(), "source": "real"}


@router.post("/channels/{channel_id}/send")
def send_message_tool(
    channel_id: str,
    payload: Dict[str, Any] = Body(default={}),
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> Dict[str, Any]:
    """
    Minimal tool-style endpoint used by MCP server / internal tools.

    Payload:
      - peer_user_key: string (display/user key)
      - peer_conversation_key: string (provider chat id, e.g. 123@c.us)
      - text: string
      - session_id: optional string
    """
    actor = _require_admin_token(admin_token)
    peer_user_key = str(payload.get("peer_user_key") or "").strip()
    peer_conversation_key = str(payload.get("peer_conversation_key") or "").strip()
    text = str(payload.get("text") or "").strip()
    session_id = payload.get("session_id")
    if not peer_conversation_key:
        raise HTTPException(status_code=400, detail="peer_conversation_key required")
    if not text:
        raise HTTPException(status_code=400, detail="text required")

    rt = get_communication_runtime()

    # Send is async under the hood; best-effort fire-and-forget here.
    try:
        from octopusos.communicationos.runtime import _run_async_send  # type: ignore
        from octopusos.communicationos.models import OutboundMessage, MessageType

        rt.ensure_adapter_started(channel_id)
        outbound = OutboundMessage(
            channel_id=channel_id,
            user_key=peer_user_key or peer_conversation_key,
            conversation_key=peer_conversation_key,
            type=MessageType.TEXT,
            text=text,
            metadata={"session_id": session_id, "content_hash": _hash_text(text), "source": "tool"},
        )
        _run_async_send(rt.bus, outbound)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"send_failed:{e}") from e

    conn = db_connect()
    try:
        ensure_schema(conn)
        audit_event(
            conn,
            event_type="communication_send_message",
            endpoint=f"/api/channels/{channel_id}/send",
            actor=actor,
            payload={
                "channel_id": channel_id,
                "peer_user_key": peer_user_key,
                "peer_conversation_key": peer_conversation_key,
                "text_hash": _hash_text(text),
                "text_len": len(text),
            },
            result={"ok": True},
        )
        conn.commit()
    finally:
        conn.close()

    return {"ok": True, "queued": True, "source": "real"}


@router.post("/channels/teams/webhook")
async def teams_webhook(request: Request) -> JSONResponse:
    body = await request.body()
    try:
        activity = json.loads(body.decode("utf-8") or "{}")
    except Exception:
        activity = {}
    channel_id = str(activity.get("channelId") or "").strip().lower() if isinstance(activity, dict) else ""
    if channel_id == "msteams":
        activity_type = str(activity.get("type") or "").strip() if isinstance(activity, dict) else ""
        tenant_id = _resolve_teams_tenant_id(activity)
        logger.info("teams_webhook_inbound type=%s tenant_id=%s", activity_type or "unknown", tenant_id or "missing")
        if not tenant_id:
            _audit_teams_tenant_reject(reason="missing_tenant_id", tenant_id="", channel_id=channel_id)
            return JSONResponse(status_code=403, content={"ok": False, "error": "unknown_tenant"})
        store = TeamsConnectionStore()
        if not store.has_connection(tenant_id):
            _audit_teams_tenant_reject(reason="unknown_tenant", tenant_id=tenant_id, channel_id=channel_id)
            return JSONResponse(status_code=403, content={"ok": False, "error": "unknown_tenant", "tenant_id": tenant_id})
        request.state.teams_tenant_id = tenant_id

    rt = get_communication_runtime()
    try:
        rt.ensure_adapter_started("teams")
    except Exception as e:
        return JSONResponse(status_code=200, content={"ok": False, "error": f"adapter_not_ready:{e}"})

    state = rt._adapters.get("teams")  # type: ignore[attr-defined]
    if not state:
        return JSONResponse(status_code=200, content={"ok": False, "error": "adapter_not_running"})

    adapter = state.adapter
    headers = {k.lower(): v for k, v in request.headers.items()}
    try:
        code, resp = adapter.handle_webhook(headers=headers, body_bytes=body)
        if isinstance(resp, dict):
            resp.setdefault("source", "real")
            if getattr(request.state, "teams_tenant_id", None):
                resp.setdefault("tenant_id", str(request.state.teams_tenant_id))
        return JSONResponse(status_code=int(code), content=resp)
    except PermissionError as e:
        return JSONResponse(status_code=403, content={"ok": False, "error": str(e)})
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": f"webhook_failed:{e}"})


@router.post("/channels/imessage/webhook")
async def imessage_webhook(request: Request) -> JSONResponse:
    return await _handle_bridge_webhook(channel_id="imessage", request=request)


@router.post("/channels/{channel_id}/webhook")
async def generic_bridge_webhook(channel_id: str, request: Request) -> JSONResponse:
    return await _handle_bridge_webhook(channel_id=channel_id, request=request)
