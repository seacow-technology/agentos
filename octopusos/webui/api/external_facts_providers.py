"""Compatibility endpoints for user-configured external fact providers."""

from __future__ import annotations

import os
from typing import Any, Dict, Optional, Tuple

from fastapi import APIRouter, Body, Header, HTTPException, Query

from octopusos.core.capabilities.external_facts.endpoint_map_schema import validate_endpoint_map
from octopusos.core.capabilities.external_facts.mapping_assistant import (
    MappingProposal,
    infer_mapping_proposal,
    normalize_mapping,
    validate_mapping_against_sample,
)
from octopusos.core.capabilities.external_facts.mapping_store import ExternalFactsMappingStore
from octopusos.core.capabilities.external_facts.provider_store import ExternalFactsProviderStore
from octopusos.core.capabilities.external_facts.registry import get_capability
from octopusos.core.capabilities.external_facts.providers.configured_api import ConfiguredApiProvider

router = APIRouter(prefix="/api/compat/external-facts/providers", tags=["compat"])
_store = ExternalFactsProviderStore()
_runner = ConfiguredApiProvider()
_mapping_store = ExternalFactsMappingStore()


def _require_admin_token(token: Optional[str]) -> str:
    expected = os.getenv("OCTOPUSOS_ADMIN_TOKEN", "").strip()
    incoming = (token or "").strip()
    if not expected:
        raise HTTPException(status_code=401, detail="Admin token not configured")
    if not incoming:
        raise HTTPException(status_code=401, detail="Admin token required")
    if incoming != expected:
        raise HTTPException(status_code=403, detail="Invalid admin token")
    return "admin"


def _parse_endpoint_key(endpoint_key: str) -> Tuple[str, str]:
    raw = str(endpoint_key or "").strip()
    if ":" not in raw:
        raise HTTPException(status_code=422, detail="endpoint_key must be '<capability_id>:<item_id>'")
    capability_id, item_id = raw.split(":", 1)
    capability_id = capability_id.strip()
    item_id = item_id.strip()
    if not capability_id or not item_id:
        raise HTTPException(status_code=422, detail="endpoint_key must be '<capability_id>:<item_id>'")
    capability = get_capability(capability_id)
    if capability is None or capability.item(item_id) is None:
        raise HTTPException(status_code=422, detail=f"Unsupported endpoint_key: {raw}")
    return capability_id, item_id


@router.get("")
async def list_providers(kind: Optional[str] = Query(default=None)):
    data = _store.list(kind=kind)
    return {"ok": True, "data": data}


@router.post("")
async def upsert_provider(
    payload: Dict[str, Any] = Body(...),
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
):
    _require_admin_token(admin_token)
    try:
        item = _store.upsert(payload)
    except ValueError as exc:
        # Treat validation errors as client errors (OpenAPI smoke should never see 5xx here).
        raise HTTPException(status_code=422, detail=str(exc))
    return {"ok": True, "data": item}


@router.delete("/{provider_id}")
async def delete_provider(
    provider_id: str,
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
):
    _require_admin_token(admin_token)
    ok = _store.delete(provider_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Provider not found")
    return {"ok": True, "data": {"provider_id": provider_id}}


@router.post("/{provider_id}/test")
async def test_provider(
    provider_id: str,
    payload: Dict[str, Any] = Body(default={}),
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
):
    _require_admin_token(admin_token)
    providers = _store.list(include_disabled=True)
    provider = next((item for item in providers if item.get("provider_id") == provider_id), None)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    # fetch unmasked credential row
    enabled_rows = _store.list_enabled_for_kind(provider["kind"])
    raw = next((item for item in enabled_rows if item.get("provider_id") == provider_id), None)
    if not raw:
        # if disabled, use metadata from masked row and fail fast
        raise HTTPException(status_code=400, detail="Provider must be enabled before test")

    sample_query = str(payload.get("query") or "")
    if not sample_query:
        kind = str(raw.get("kind") or "")
        sample_query = {
            "fx": "AUD 对 USD 汇率",
            "weather": "悉尼天气",
            "index": "S&P 500",
        }.get(kind, f"{kind} latest")

    result = await _runner.resolve(
        kind=raw["kind"],
        query=sample_query,
        context={},
        provider=raw,
    )
    if result is None:
        raise HTTPException(status_code=422, detail="Provider returned no result")

    return {
        "ok": True,
        "data": {
            "provider_id": provider_id,
            "query": sample_query,
            "result": result.to_dict(),
        },
    }


@router.post("/{provider_id}/endpoint/{endpoint_key:path}/infer-mapping")
async def infer_mapping(
    provider_id: str,
    endpoint_key: str,
    payload: Dict[str, Any] = Body(...),
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
):
    actor = _require_admin_token(admin_token)
    provider = _store.get(provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    capability_id, item_id = _parse_endpoint_key(endpoint_key)
    sample_raw = payload.get("sample_json")
    if isinstance(sample_raw, str):
        import json
        try:
            sample_json = json.loads(sample_raw)
        except Exception:
            raise HTTPException(status_code=422, detail="sample_json must be valid JSON object")
    else:
        sample_json = sample_raw
    if not isinstance(sample_json, dict):
        raise HTTPException(status_code=422, detail="sample_json must be a JSON object")

    endpoint_meta = payload.get("endpoint") if isinstance(payload.get("endpoint"), dict) else {}
    endpoint_url = str(endpoint_meta.get("url") or provider.get("endpoint_url") or "").strip()
    method = str(endpoint_meta.get("method") or "GET").upper()

    sample = _mapping_store.save_sample(
        provider_id=provider_id,
        endpoint_key=f"{capability_id}:{item_id}",
        capability_id=capability_id,
        item_id=item_id,
        sample_json=sample_json,
        created_by=actor,
    )
    proposal, llm_model, prompt_hash = infer_mapping_proposal(
        capability_id=capability_id,
        item_id=item_id,
        sample_json=sample_json,
    )
    validation_report = validate_mapping_against_sample(proposal, sample_json)
    proposal_row = _mapping_store.save_proposal(
        provider_id=provider_id,
        endpoint_key=f"{capability_id}:{item_id}",
        proposal_json=proposal.model_dump(),
        confidence=float(proposal.confidence),
        llm_model=llm_model,
        prompt_hash=prompt_hash,
        sample_id=sample["id"],
    )
    can_apply = bool(validation_report.get("ok")) and float(proposal.confidence) >= 0.6 and bool(endpoint_url)
    return {
        "ok": True,
        "data": {
            "provider_id": provider_id,
            "endpoint_key": f"{capability_id}:{item_id}",
            "sample_id": sample["id"],
            "proposal_id": proposal_row["id"],
            "proposal": proposal.model_dump(),
            "confidence": float(proposal.confidence),
            "validation_report": validation_report,
            "can_apply": can_apply,
            "endpoint": {"url": endpoint_url, "method": method},
        },
    }


@router.post("/{provider_id}/endpoint/{endpoint_key:path}/apply-mapping")
async def apply_mapping(
    provider_id: str,
    endpoint_key: str,
    payload: Dict[str, Any] = Body(...),
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
):
    actor = _require_admin_token(admin_token)
    provider = _store.get(provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    capability_id, item_id = _parse_endpoint_key(endpoint_key)
    key = f"{capability_id}:{item_id}"

    sample_id = str(payload.get("sample_id") or "").strip()
    sample_json: Dict[str, Any] = {}
    validated_sample_id: Optional[str] = None
    if sample_id:
        bundle = _mapping_store.list_endpoint_bundle(provider_id=provider_id, endpoint_key=key, limit=100)
        sample = next((s for s in bundle["samples"] if s["id"] == sample_id), None)
        sample_json = sample["sample_json"] if sample and isinstance(sample.get("sample_json"), dict) else {}
        validated_sample_id = sample["id"] if sample else None
    else:
        latest_sample = _mapping_store.get_latest_sample(provider_id=provider_id, endpoint_key=key)
        sample_json = latest_sample["sample_json"] if latest_sample and isinstance(latest_sample.get("sample_json"), dict) else {}
        validated_sample_id = latest_sample["id"] if latest_sample else None
    if not sample_json:
        raise HTTPException(status_code=422, detail="NO_SAMPLE_AVAILABLE_FOR_VALIDATION")

    endpoint_meta = payload.get("endpoint") if isinstance(payload.get("endpoint"), dict) else {}
    endpoint_url = str(endpoint_meta.get("url") or "").strip()
    endpoint_method = str(endpoint_meta.get("method") or "GET").upper()
    if not endpoint_url:
        endpoint_url = str(provider.get("endpoint_url") or "").strip()
    if not endpoint_url:
        raise HTTPException(status_code=422, detail="endpoint.url is required")

    proposal_id = str(payload.get("proposal_id") or "").strip()
    mapping_json_payload = payload.get("mapping_json")
    proposal_obj: Optional[MappingProposal] = None
    if proposal_id:
        proposal_row = _mapping_store.get_proposal(proposal_id)
        if not proposal_row:
            raise HTTPException(status_code=404, detail="proposal not found")
        try:
            proposal_obj = MappingProposal.model_validate(proposal_row["proposal_json"])
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"invalid proposal: {exc}")
    elif isinstance(mapping_json_payload, dict):
        mapping_json = mapping_json_payload
        validation_report = payload.get("validation_report") if isinstance(payload.get("validation_report"), dict) else {}
        if not validation_report:
            response = mapping_json.get("response") if isinstance(mapping_json.get("response"), dict) else {}
            try:
                proposal_obj = MappingProposal.model_validate(
                    {
                        "response_kind": response.get("kind", "point"),
                        "time_path": response.get("time_path", ""),
                        "value_path": response.get("value_path", ""),
                        "points_path": response.get("points_path"),
                        "summary_path": response.get("summary_path"),
                        "method": mapping_json.get("method", "GET"),
                        "reasoning": "manual_mapping",
                        "confidence": 0.7,
                    }
                )
            except Exception:
                proposal_obj = None
            if proposal_obj is not None:
                validation_report = validate_mapping_against_sample(proposal_obj, sample_json)
        status = "active" if bool(validation_report.get("ok")) else "draft"
        version = _mapping_store.create_mapping_version(
            provider_id=provider_id,
            endpoint_key=key,
            mapping_json=mapping_json,
            validation_report=validation_report or {"ok": False, "errors": ["validation report missing"]},
            status=status,
            approved_by=actor,
        )
        if status == "active":
            _store.set_active_mapping_version(provider_id, key, version["id"])
        return {"ok": True, "data": {"version": version, "status": status, "sample_id": validated_sample_id}}
    else:
        raise HTTPException(status_code=422, detail="proposal_id or mapping_json is required")

    mapping_json = normalize_mapping(
        endpoint_url=endpoint_url,
        method=endpoint_method,
        proposal=proposal_obj,
        headers=None,
        query=None,
    )
    validation_report = validate_mapping_against_sample(proposal_obj, sample_json) if sample_json else {"ok": False, "errors": ["sample_json missing"]}
    supported_items = {capability_id: [item_id]}
    endpoint_map = {capability_id: {"items": {item_id: mapping_json}}}
    schema_check = validate_endpoint_map(endpoint_map=endpoint_map, supported_items=supported_items, version=1)
    if not schema_check.ok:
        validation_report = {
            "ok": False,
            "kind": proposal_obj.response_kind,
            "extracted": validation_report.get("extracted", {}),
            "errors": list(validation_report.get("errors") or []) + schema_check.errors,
        }
    status = "active" if bool(validation_report.get("ok")) and float(proposal_obj.confidence) >= 0.6 else "draft"
    version = _mapping_store.create_mapping_version(
        provider_id=provider_id,
        endpoint_key=key,
        mapping_json=mapping_json,
        validation_report=validation_report,
        status=status,
        approved_by=actor,
    )
    if status == "active":
        _store.set_active_mapping_version(provider_id, key, version["id"])
    return {"ok": True, "data": {"version": version, "status": status, "sample_id": validated_sample_id}}


@router.get("/{provider_id}/endpoint/{endpoint_key:path}/mappings")
async def list_mappings(
    provider_id: str,
    endpoint_key: str,
    limit: int = Query(default=20, ge=1, le=200),
):
    provider = _store.get(provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    capability_id, item_id = _parse_endpoint_key(endpoint_key)
    key = f"{capability_id}:{item_id}"
    data = _mapping_store.list_endpoint_bundle(provider_id=provider_id, endpoint_key=key, limit=limit)
    return {"ok": True, "data": {"provider_id": provider_id, "endpoint_key": key, **data}}
