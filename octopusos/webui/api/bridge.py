"""BridgeOS API.

Provides profile management + channel bindings + Cloudflare exposure requests.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Header, HTTPException

from octopusos.bridgeos.service import BridgeService
from octopusos.core.capabilities.admin_token import validate_admin_token

router = APIRouter(prefix="/api/bridge", tags=["bridgeos"])


def _require_admin_token(token: Optional[str]) -> str:
    if not token:
        raise HTTPException(status_code=401, detail="Admin token required")
    if not validate_admin_token(token):
        raise HTTPException(status_code=403, detail="Invalid admin token")
    return "admin"


def _public_runtime_payload(runtime: Any) -> Optional[Dict[str, Any]]:
    if not runtime:
        return None
    return {
        "profile_id": runtime.profile_id,
        "bridge_base_url": runtime.bridge_base_url,
        "send_path": runtime.send_path,
        "webhook_token_present": bool(runtime.webhook_token),
        "cloudflare_proxy_url": runtime.cloudflare_proxy_url,
    }


@router.get("/profiles")
def list_profiles() -> Dict[str, Any]:
    svc = BridgeService()
    items = [p.to_dict() for p in svc.list_profiles()]
    return {"ok": True, "profiles": items, "total": len(items), "source": "real"}


@router.post("/profiles")
def create_profile(
    payload: Dict[str, Any] = Body(default={}),
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> Dict[str, Any]:
    _require_admin_token(admin_token)
    svc = BridgeService()
    try:
        profile = svc.create_profile(
            name=str(payload.get("name") or "").strip(),
            provider=str(payload.get("provider") or "custom").strip(),
            bridge_base_url=str(payload.get("bridge_base_url") or "").strip(),
            send_path=str(payload.get("send_path") or "/api/imessage/send").strip(),
            webhook_token=str(payload.get("webhook_token") or "").strip() or None,
            local_target=str(payload.get("local_target") or "").strip() or None,
            cloudflare_hostname=str(payload.get("cloudflare_hostname") or "").strip() or None,
            metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True, "profile": profile.to_dict(), "source": "real"}


@router.get("/profiles/{profile_id}")
def get_profile(profile_id: str) -> Dict[str, Any]:
    svc = BridgeService()
    profile = svc.get_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="profile_not_found")
    runtime = svc.resolve_runtime_for_profile(profile.profile_id)
    return {
        "ok": True,
        "profile": profile.to_dict(),
        "runtime": _public_runtime_payload(runtime),
        "source": "real",
    }


@router.patch("/profiles/{profile_id}")
def patch_profile(
    profile_id: str,
    payload: Dict[str, Any] = Body(default={}),
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> Dict[str, Any]:
    _require_admin_token(admin_token)
    svc = BridgeService()
    try:
        profile = svc.update_profile(profile_id, patch=payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if not profile:
        raise HTTPException(status_code=404, detail="profile_not_found")
    return {"ok": True, "profile": profile.to_dict(), "source": "real"}


@router.post("/profiles/{profile_id}/bind")
def bind_profile_to_channel(
    profile_id: str,
    payload: Dict[str, Any] = Body(default={}),
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> Dict[str, Any]:
    _require_admin_token(admin_token)
    channel_id = str(payload.get("channel_id") or "").strip()
    if not channel_id:
        raise HTTPException(status_code=400, detail="channel_id_required")
    svc = BridgeService()
    try:
        binding = svc.bind_channel(channel_id=channel_id, profile_id=profile_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {"ok": True, "binding": binding.to_dict(), "source": "real"}


@router.get("/channels/{channel_id}/binding")
def get_channel_binding(channel_id: str) -> Dict[str, Any]:
    svc = BridgeService()
    binding = svc.get_channel_binding(channel_id)
    if not binding:
        return {"ok": True, "binding": None, "source": "real"}
    profile = svc.get_profile(binding.profile_id)
    return {
        "ok": True,
        "binding": binding.to_dict(),
        "profile": profile.to_dict() if profile else None,
        "runtime": _public_runtime_payload(svc.resolve_runtime_for_profile(binding.profile_id)) if profile else None,
        "source": "real",
    }


@router.post("/profiles/{profile_id}/expose/cloudflare")
def request_cloudflare_expose(
    profile_id: str,
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> Dict[str, Any]:
    actor = _require_admin_token(admin_token)
    svc = BridgeService()
    res = svc.request_cloudflare_exposure(profile_id=profile_id, requested_by=actor)
    if not res.get("ok"):
        raise HTTPException(status_code=400, detail=str(res.get("error") or "request_failed"))
    return {"ok": True, **res, "source": "real"}


@router.get("/profiles/{profile_id}/proxy")
def get_proxy(profile_id: str) -> Dict[str, Any]:
    svc = BridgeService()
    profile = svc.get_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="profile_not_found")
    runtime = svc.resolve_runtime_for_profile(profile_id)
    return {
        "ok": True,
        "profile_id": profile_id,
        "proxy_url": runtime.cloudflare_proxy_url if runtime else None,
        "runtime": _public_runtime_payload(runtime),
        "source": "real",
    }
