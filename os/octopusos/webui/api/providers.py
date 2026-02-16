"""Providers API endpoints (executable detection, instances, models)."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from octopusos.providers import platform_utils
from octopusos.core.status_store import StatusStore
from octopusos.providers.process_manager import ProcessManager
from octopusos.providers.providers_config import ProvidersConfigManager
from octopusos.providers.registry import ProviderRegistry
from octopusos.providers.base import ProviderType
from octopusos.providers.cloud_config import CloudConfigManager, CloudAuthConfig
from octopusos.providers.providers_config import LaunchConfig
from octopusos.webui.api.providers_errors import get_install_suggestion
from octopusos.providers.model_prefs import ProviderModelPrefsManager
from octopusos.providers.cloud_model_catalog import get_catalog


class _ModelShim:
    id: str
    label: Optional[str]
    metadata: Optional[Dict[str, Any]]

    def __init__(self, mid: str, label: Optional[str], metadata: Optional[Dict[str, Any]]):
        self.id = mid
        self.label = label
        self.metadata = metadata

router = APIRouter(prefix="/api/providers", tags=["providers"])
logger = logging.getLogger(__name__)


class ValidateExecutableRequest(BaseModel):
    path: Optional[str] = Field(None, description="Executable path to validate")


class SetExecutableRequest(BaseModel):
    path: Optional[str] = Field(None, description="Executable path to set")
    auto_detect: bool = Field(False, description="Auto-detect executable path")


class ModelsDirectoryRequest(BaseModel):
    provider_id: str
    path: str


class InstanceRequest(BaseModel):
    id: str
    base_url: str
    enabled: bool = True


class CloudConfigSetRequest(BaseModel):
    api_key: str = Field(..., min_length=1, description="Cloud provider API key")
    base_url: Optional[str] = Field(None, description="Optional base URL override")


class CloudConfigRecordUpsertRequest(BaseModel):
    label: Optional[str] = Field(None, description="Human label for this credential record")
    api_key: str = Field(..., min_length=1, description="Cloud provider API key")
    base_url: Optional[str] = Field(None, description="Optional base URL override")
    make_active: bool = Field(True, description="Whether to activate this record after save")


class CloudConfigRecordCreateRequest(CloudConfigRecordUpsertRequest):
    config_id: Optional[str] = Field(None, description="Optional stable id; generated when omitted")

class ModelPricingUpsertRequest(BaseModel):
    input_per_1m: float = Field(..., ge=0, description="USD per 1,000,000 input tokens")
    output_per_1m: float = Field(..., ge=0, description="USD per 1,000,000 output tokens")
    currency: str = Field("USD", description="Currency code (currently only USD)")
    source: Optional[str] = Field(None, description="Pricing source label (optional)")
    enabled: bool = Field(True, description="Whether pricing is enabled for cost computation")


def _get_config_manager() -> ProvidersConfigManager:
    get_instance = getattr(ProvidersConfigManager, "get_instance", None)
    if callable(get_instance):
        return get_instance()
    return ProvidersConfigManager()


def _provider_ids() -> List[str]:
    manager = _get_config_manager()
    return list(manager._config.get("providers", {}).keys())


def _get_instances(provider_id: str) -> List[Dict[str, Any]]:
    manager = _get_config_manager()
    get_instances = getattr(manager, "get_instances", None)
    if callable(get_instances):
        return get_instances(provider_id)
    return manager._config.get("providers", {}).get(provider_id, {}).get("instances", [])


def _instance_exists(provider_id: str, instance_id: str) -> bool:
    return any(inst.get("id") == instance_id for inst in _get_instances(provider_id))


def _provider_label(provider_id: str) -> str:
    label_map = {
        "ollama": "Ollama",
        "lmstudio": "LM Studio",
        "llamacpp": "Llama.cpp",
        "openai": "OpenAI",
        "anthropic": "Anthropic",
        "google": "Google",
        "meta": "Meta",
        "deepseek": "Deepseek",
        "amazon": "Amazon",
        "alibaba_cloud": "Alibaba Cloud",
        "zai": "Z.ai",
        "moonshot": "Moonshot AI",
        "microsoft": "Microsoft",
        "xai": "xAI",
    }
    return label_map.get(provider_id, provider_id)


def _provider_executable_name(provider_id: str) -> str:
    name_map = {
        "ollama": "ollama",
        "llamacpp": "llama-server",
        "lmstudio": "lmstudio",
    }
    return name_map.get(provider_id, provider_id)


def _candidate_search_paths(executable_name: str) -> List[str]:
    candidates: List[str] = []

    for standard in platform_utils.get_standard_paths(executable_name):
        candidates.append(str(standard))

    path_env = os.environ.get("PATH", "")
    if path_env:
        for dir_path in path_env.split(os.pathsep):
            if not dir_path:
                continue
            candidates.append(str(Path(dir_path) / executable_name))

    # De-duplicate while preserving order
    return list(dict.fromkeys(candidates))


def _get_instance_config(provider_id: str, instance_id: str) -> Optional[Dict[str, Any]]:
    cfg = _get_config_manager()
    instances = cfg.get_instances(provider_id)
    for inst in instances:
        if str(inst.get("id")) == str(instance_id):
            return inst
    return None


def _ensure_local_provider(provider_id: str) -> None:
    registry = ProviderRegistry.get_instance()
    provider = registry.get(provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="Unknown provider")
    if getattr(provider, "type", None) != ProviderType.LOCAL:
        raise HTTPException(status_code=400, detail="Provider is not a local provider")


def _parse_endpoint_host_port(base_url: str) -> tuple[str, Optional[int]]:
    from urllib.parse import urlparse
    parsed = urlparse(base_url or "")
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port
    return host, port


async def _start_local_instance(provider_id: str, instance_id: str) -> tuple[bool, str]:
    """
    Start a local provider instance using ProcessManager.

    For providers that are manual lifecycle (e.g. LM Studio), we best-effort open the app.
    """
    cfg = _get_config_manager()
    provider_cfg = cfg.get_provider_config(provider_id)
    inst = _get_instance_config(provider_id, instance_id)
    if inst is None:
        return False, "Unknown instance"

    supported = set((provider_cfg.supported_actions if provider_cfg else []) or [])
    if "start" not in supported and "open_app" not in supported:
        return False, "Start is not supported for this provider"

    # Manual lifecycle: attempt to open app and return.
    if provider_cfg and provider_cfg.manual_lifecycle:
        if provider_id == "lmstudio":
            import platform
            try:
                if platform.system() == "Darwin":
                    import subprocess
                    subprocess.Popen(["open", "-a", "LM Studio"])
                    return True, "LM Studio opened. Enable the local server from the app."
                return True, "Manual lifecycle provider. Start the server from the provider app."
            except Exception as exc:
                return False, f"Failed to open app: {exc}"
        return True, "Manual lifecycle provider. Start the server from the provider app."

    # Build command.
    instance_key = f"{provider_id}:{instance_id}"
    base_url = str(inst.get("base_url") or "")
    host, port = _parse_endpoint_host_port(base_url)

    # Provider-specific defaults.
    if provider_id == "ollama":
        exe = cfg.get_executable_path("ollama")
        bin_name = str(exe) if exe else "ollama"
        manager = ProcessManager.get_instance()
        return await manager.start_process(
            instance_key=instance_key,
            command=[bin_name, "serve"],
            check_port=False,
            base_url=base_url or None,
        )

    if provider_id == "llamacpp":
        launch = (inst.get("launch") or {}) if isinstance(inst.get("launch"), dict) else {}
        bin_name = str(launch.get("bin") or "") or "llama-server"

        # If bin is the generic name, try to resolve user-configured executable_path.
        if bin_name in {"llama-server", "llamacpp"}:
            exe = cfg.get_executable_path("llamacpp")
            if exe:
                bin_name = str(exe)

        args = launch.get("args") if isinstance(launch.get("args"), dict) else {}
        args = dict(args or {})

        # Fill host/port defaults from base_url if not explicitly set.
        args.setdefault("host", host)
        if port is not None:
            args.setdefault("port", port)

        # Model is required for llama-server; enforce early for clearer UX.
        if not args.get("model"):
            return False, "Missing launch args: model. Configure llama.cpp launch first (model path)."

        manager = ProcessManager.get_instance()
        return await manager.start_process(
            instance_key=instance_key,
            bin_name=bin_name,
            args=args,
            check_port=True,
            base_url=base_url or None,
        )

    return False, "Unsupported local provider"


async def _stop_local_instance(provider_id: str, instance_id: str, force: bool = False) -> tuple[bool, str, Optional[int]]:
    instance_key = f"{provider_id}:{instance_id}"
    manager = ProcessManager.get_instance()
    ok, msg, _old_pid = await manager.stop_process(instance_key, force=force)
    return ok, msg, _old_pid


def _ensure_cloud_provider(provider_id: str) -> None:
    registry = ProviderRegistry.get_instance()
    provider = registry.get(provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="Unknown provider")
    if getattr(provider, "type", None) != ProviderType.CLOUD:
        raise HTTPException(status_code=400, detail="Provider is not a cloud provider")

 
def _cloud_config_manager() -> CloudConfigManager:
    """
    Use the registry-managed CloudConfigManager instance.

    This avoids stale reads: ProviderRegistry caches a CloudConfigManager and cloud
    providers read from it. If we instantiate a new manager here, status probes
    may keep reading the old in-memory config until restart.
    """
    registry = ProviderRegistry.get_instance()
    getter = getattr(registry, "get_config_manager", None)
    if callable(getter):
        mgr = getter()
        if isinstance(mgr, CloudConfigManager):
            return mgr
    return CloudConfigManager()


@router.get("")
def list_providers() -> Dict[str, List[Dict[str, Any]]]:
    registry = ProviderRegistry.get_instance()
    config_manager = _get_config_manager()

    local: List[Dict[str, Any]] = []
    cloud: List[Dict[str, Any]] = []

    for provider in registry.list_all():
        provider_base_id = provider.provider_id
        provider_type = provider.type

        supports_start = False
        if provider_type == ProviderType.LOCAL:
            config = config_manager.get_provider_config(provider_base_id)
            if config is not None:
                supports_start = (
                    not config.manual_lifecycle and
                    "start" in (config.supported_actions or [])
                )
            else:
                supports_start = provider_base_id in {"ollama", "llamacpp"}

        supports_auth: List[str] = ["api_key"] if provider_type == ProviderType.CLOUD else []
        payload = {
            "id": provider.id,
            "label": _provider_label(provider_base_id),
            "type": provider_type.value,
            "supports_models": True,
            "supports_start": supports_start,
            "supports_auth": supports_auth,
        }

        if provider_type == ProviderType.CLOUD:
            cloud.append(payload)
        else:
            local.append(payload)

    return {"local": local, "cloud": cloud}


@router.get("/{provider_id}/cloud-config")
def get_cloud_config(provider_id: str) -> Dict[str, Any]:
    """
    Get cloud provider credential configuration (masked).

    Uses ~/.octopusos/secrets/providers.json via CloudConfigManager.
    """
    _ensure_cloud_provider(provider_id)
    manager = _cloud_config_manager()
    masked = manager.get_masked_config(provider_id)
    return {
        "provider_id": provider_id,
        "configured": masked is not None,
        "config": masked,
    }


@router.put("/{provider_id}/cloud-config")
def set_cloud_config(provider_id: str, payload: CloudConfigSetRequest) -> Dict[str, Any]:
    """
    Set cloud provider credentials.

    Stores API key securely in ~/.octopusos/secrets/providers.json via CloudConfigManager.
    """
    _ensure_cloud_provider(provider_id)
    manager = _cloud_config_manager()
    manager.set(
        provider_id=provider_id,
        auth=CloudAuthConfig(type="api_key", api_key=payload.api_key),
        base_url=payload.base_url or None,
    )
    return {
        "ok": True,
        "provider_id": provider_id,
        "config": manager.get_masked_config(provider_id),
    }


@router.delete("/{provider_id}/cloud-config")
def delete_cloud_config(provider_id: str) -> Dict[str, Any]:
    """
    Clear cloud provider credentials.
    """
    _ensure_cloud_provider(provider_id)
    manager = _cloud_config_manager()
    deleted = manager.delete(provider_id)
    return {
        "ok": True,
        "provider_id": provider_id,
        "deleted": deleted,
    }


@router.get("/{provider_id}/cloud-configs")
def list_cloud_configs(provider_id: str) -> Dict[str, Any]:
    """
    List all credential records for a cloud provider (masked).
    """
    _ensure_cloud_provider(provider_id)
    manager = _cloud_config_manager()
    configs = manager.list_masked_configs(provider_id)
    active = None
    for c in configs:
        if c.get("active"):
            active = c.get("config_id")
            break
    return {"provider_id": provider_id, "active_config_id": active, "configs": configs}


@router.post("/{provider_id}/cloud-configs")
def create_cloud_config(provider_id: str, payload: CloudConfigRecordCreateRequest) -> Dict[str, Any]:
    """
    Create a new credential record for a cloud provider.
    """
    _ensure_cloud_provider(provider_id)
    manager = _cloud_config_manager()
    config_id = (payload.config_id or "").strip()
    if not config_id:
        import uuid
        config_id = f"cfg_{uuid.uuid4().hex[:10]}"

    manager.set(
        provider_id=provider_id,
        config_id=config_id,
        label=payload.label,
        auth=CloudAuthConfig(type="api_key", api_key=payload.api_key),
        base_url=payload.base_url or None,
        make_active=bool(payload.make_active),
    )
    return {"ok": True, "provider_id": provider_id, "config_id": config_id, "config": manager.get_masked_config(provider_id)}


@router.put("/{provider_id}/cloud-configs/{config_id}")
def update_cloud_config(provider_id: str, config_id: str, payload: CloudConfigRecordUpsertRequest) -> Dict[str, Any]:
    """
    Update an existing credential record.
    """
    _ensure_cloud_provider(provider_id)
    manager = _cloud_config_manager()
    manager.set(
        provider_id=provider_id,
        config_id=config_id,
        label=payload.label,
        auth=CloudAuthConfig(type="api_key", api_key=payload.api_key),
        base_url=payload.base_url or None,
        make_active=bool(payload.make_active),
    )
    return {"ok": True, "provider_id": provider_id, "config_id": config_id}


@router.post("/{provider_id}/cloud-configs/{config_id}/activate")
def activate_cloud_config(provider_id: str, config_id: str) -> Dict[str, Any]:
    _ensure_cloud_provider(provider_id)
    manager = _cloud_config_manager()
    ok = manager.set_active(provider_id, config_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Unknown config_id")
    return {"ok": True, "provider_id": provider_id, "active_config_id": config_id}


@router.delete("/{provider_id}/cloud-configs/{config_id}")
def delete_cloud_config_record(provider_id: str, config_id: str) -> Dict[str, Any]:
    _ensure_cloud_provider(provider_id)
    manager = _cloud_config_manager()
    deleted = manager.delete(provider_id, config_id=config_id)
    return {"ok": True, "provider_id": provider_id, "config_id": config_id, "deleted": deleted}


@router.post("/{provider_id}/cloud-configs/{config_id}/test")
async def test_cloud_config(provider_id: str, config_id: str) -> Dict[str, Any]:
    """
    Test API reachability/auth for a given credential record, and persist the result.
    """
    _ensure_cloud_provider(provider_id)
    manager = _cloud_config_manager()
    # Find config record
    configs = manager.list_masked_configs(provider_id)
    target = next((c for c in configs if c.get("config_id") == config_id), None)
    if target is None:
        raise HTTPException(status_code=404, detail="Unknown config_id")

    # Use unmasked active config by temporarily activating, then restoring.
    # We avoid reading secrets from list_masked_configs.
    active_cfg, active_id = manager._get_active_config_dict(provider_id)  # type: ignore[attr-defined]
    prev_active = active_id
    manager.set_active(provider_id, config_id)

    import asyncio as _asyncio
    import httpx
    from datetime import datetime, timezone

    ok = False
    error: Optional[str] = None
    latency_ms: Optional[float] = None

    cfg = manager.get(provider_id)
    if cfg is None:
        error = "Not configured"
    else:
        base_url = (cfg.base_url or "").rstrip("/")
        start = _asyncio.get_event_loop().time()
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                if provider_id == "anthropic":
                    resp = await client.get(
                        f"{base_url}/models" if base_url else "https://api.anthropic.com/v1/models",
                        headers={
                            "x-api-key": cfg.auth.api_key,
                            "anthropic-version": "2023-06-01",
                        },
                    )
                else:
                    resp = await client.get(
                        f"{base_url}/models",
                        headers={"Authorization": f"Bearer {cfg.auth.api_key}"},
                    )
            latency_ms = (_asyncio.get_event_loop().time() - start) * 1000
            ok = resp.status_code == 200
            if not ok:
                error = f"HTTP {resp.status_code}"
        except Exception as exc:
            error = str(exc)[:200]
        finally:
            # Restore previous active config if any
            if prev_active and prev_active != config_id:
                manager.set_active(provider_id, prev_active)

    at = datetime.now(timezone.utc).isoformat()
    manager.record_test_result(provider_id, config_id, ok=ok, at=at, latency_ms=latency_ms, error=error)
    return {"ok": True, "provider_id": provider_id, "config_id": config_id, "test": {"ok": ok, "at": at, "latency_ms": latency_ms, "error": error}}


@router.get("/{provider_id}/executable/detect")
def detect_executable(provider_id: str):
    if provider_id not in _provider_ids():
        raise HTTPException(status_code=404, detail="Unknown provider")

    config_manager = _get_config_manager()
    raw_provider = config_manager._config.get("providers", {}).get(provider_id, {})
    custom_path = raw_provider.get("executable_path")
    auto_detect = raw_provider.get("auto_detect", True)

    executable_name = _provider_executable_name(provider_id)
    search_paths = _candidate_search_paths(executable_name)

    resolved_path: Optional[Path] = None
    detection_source: Optional[str] = None

    if custom_path:
        custom_candidate = Path(custom_path)
        if platform_utils.validate_executable(custom_candidate):
            resolved_path = custom_candidate
            detection_source = "config"

    if resolved_path is None and auto_detect:
        for standard in platform_utils.get_standard_paths(executable_name):
            if platform_utils.validate_executable(standard):
                resolved_path = standard
                detection_source = "standard"
                break

        if resolved_path is None:
            path_hit = platform_utils.find_in_path(executable_name)
            if path_hit:
                resolved_path = path_hit
                detection_source = "path"

    version = platform_utils.get_executable_version(resolved_path) if resolved_path else None

    return {
        "detected": resolved_path is not None,
        "path": str(resolved_path) if resolved_path else None,
        "custom_path": custom_path,
        "resolved_path": str(resolved_path) if resolved_path else None,
        "version": version,
        "platform": platform_utils.get_platform(),
        "search_paths": search_paths,
        "is_valid": resolved_path is not None,
        "detection_source": detection_source,
    }


@router.post("/{provider_id}/executable/validate")
def validate_executable(provider_id: str, payload: ValidateExecutableRequest):
    if provider_id not in _provider_ids():
        raise HTTPException(status_code=404, detail="Unknown provider")
    if not payload.path:
        raise HTTPException(status_code=400, detail="path is required")

    validation = platform_utils.validate_executable_detailed(Path(payload.path))
    return {
        "is_valid": validation.get("is_valid", False),
        "path": str(payload.path),
        "exists": validation.get("exists", False),
        "is_executable": validation.get("is_executable", False),
        "version": validation.get("version"),
        "error": validation.get("error"),
    }


@router.put("/{provider_id}/executable")
def set_executable(provider_id: str, payload: SetExecutableRequest):
    if provider_id not in _provider_ids():
        raise HTTPException(status_code=404, detail="Unknown provider")

    config_manager = _get_config_manager()

    try:
        if payload.auto_detect:
            config_manager.set_executable_path(provider_id, None)
            return {"ok": True, "path": None, "message": "Auto-detection enabled"}
        if not payload.path:
            raise HTTPException(status_code=400, detail="path or auto_detect required")

        config_manager.set_executable_path(provider_id, payload.path)
        return {"ok": True, "path": payload.path, "message": "Executable path updated"}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/models/directories")
def get_models_directories() -> Dict[str, Optional[str]]:
    return {pid: str(platform_utils.get_models_dir(pid)) for pid in _provider_ids()}


@router.put("/models/directories")
def set_models_directory(payload: ModelsDirectoryRequest):
    if payload.provider_id not in _provider_ids():
        raise HTTPException(status_code=404, detail="Unknown provider")
    return {"ok": True, "provider_id": payload.provider_id, "path": payload.path}


@router.get("/models/directories/detect")
def detect_models_directories() -> Dict[str, Optional[str]]:
    return {pid: str(platform_utils.get_models_dir(pid)) for pid in _provider_ids()}


@router.get("/models/files")
def list_models_files(provider_id: Optional[str] = Query(None)):
    if not provider_id:
        raise HTTPException(status_code=400, detail="provider_id is required")
    if provider_id not in _provider_ids():
        raise HTTPException(status_code=404, detail="Unknown provider")
    models_dir = platform_utils.get_models_dir(provider_id)
    if not models_dir or not models_dir.exists():
        raise HTTPException(status_code=404, detail="Models directory not found")
    if not models_dir.is_dir():
        raise HTTPException(status_code=400, detail="Models directory is not a directory")
    return [path.name for path in models_dir.iterdir()]


@router.get("/{provider_id}/models")
async def list_provider_models(provider_id: str) -> Dict[str, Any]:
    registry = ProviderRegistry.get_instance()
    provider = registry.get(provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="Unknown provider")

    prefs = ProviderModelPrefsManager()
    used = prefs.get_used_models(provider_id)

    source = "live"
    models = []
    try:
        # For cloud providers, avoid network calls when not configured.
        if provider.type == ProviderType.CLOUD:
            manager = _cloud_config_manager()
            masked = manager.get_masked_config(provider_id)
            if masked is None:
                raise RuntimeError("cloud_not_configured")
        models = await provider.list_models()
    except Exception:
        source = "catalog"
        models = [_ModelShim(m.id, m.label, m.metadata) for m in get_catalog(provider_id)]

    return {
        "models": [
            {
                "id": m.id,
                "name": m.label or m.id,
                "label": m.label or m.id,
                "metadata": m.metadata or {},
                "used": m.id in used,
            }
            for m in models
        ],
        "total": len(models),
        "source": source,
    }


@router.get("/{provider_id}/models/pricing")
def list_model_pricing(provider_id: str) -> Dict[str, Any]:
    """List pricing for models under a provider (DB-backed)."""
    from octopusos.core.time.clock import utc_now_ms
    from octopusos.store import get_db

    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT provider, model, input_per_1m, output_per_1m, currency, source, enabled, created_at_ms, updated_at_ms "
            "FROM llm_model_pricing WHERE provider = ? ORDER BY model ASC",
            (provider_id,),
        ).fetchall()
    except Exception:
        rows = []
    return {
        "provider_id": provider_id,
        "ts_ms": utc_now_ms(),
        "pricing": [
            {
                "provider": str(r["provider"]),
                "model": str(r["model"]),
                "input_per_1m": float(r["input_per_1m"]),
                "output_per_1m": float(r["output_per_1m"]),
                "currency": str(r["currency"]),
                "source": r["source"],
                "enabled": bool(r["enabled"]),
                "created_at_ms": int(r["created_at_ms"]),
                "updated_at_ms": int(r["updated_at_ms"]),
            }
            for r in rows
        ],
    }


@router.put("/{provider_id}/models/{model_id}/pricing")
def upsert_model_pricing(provider_id: str, model_id: str, payload: ModelPricingUpsertRequest) -> Dict[str, Any]:
    """Upsert pricing for a specific model under a provider."""
    from octopusos.core.time.clock import utc_now_ms
    from octopusos.store import get_db

    if payload.currency != "USD":
        raise HTTPException(status_code=400, detail="Only USD pricing is supported")

    now_ms = utc_now_ms()
    conn = get_db()
    try:
        conn.execute(
            """
            INSERT INTO llm_model_pricing (
                provider, model, input_per_1m, output_per_1m, currency, source, enabled, created_at_ms, updated_at_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(provider, model) DO UPDATE SET
                input_per_1m = excluded.input_per_1m,
                output_per_1m = excluded.output_per_1m,
                currency = excluded.currency,
                source = excluded.source,
                enabled = excluded.enabled,
                updated_at_ms = excluded.updated_at_ms
            """,
            (
                provider_id,
                model_id,
                float(payload.input_per_1m),
                float(payload.output_per_1m),
                payload.currency,
                payload.source,
                1 if payload.enabled else 0,
                now_ms,
                now_ms,
            ),
        )
        conn.commit()
        try:
            from octopusos.core.llm.pricing import invalidate_pricing_db_cache
            invalidate_pricing_db_cache()
        except Exception:
            pass
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    row = conn.execute(
        "SELECT provider, model, input_per_1m, output_per_1m, currency, source, enabled, created_at_ms, updated_at_ms "
        "FROM llm_model_pricing WHERE provider = ? AND model = ?",
        (provider_id, model_id),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=500, detail="Upsert failed")
    return {
        "ok": True,
        "provider_id": provider_id,
        "model_id": model_id,
        "pricing": {
            "provider": str(row["provider"]),
            "model": str(row["model"]),
            "input_per_1m": float(row["input_per_1m"]),
            "output_per_1m": float(row["output_per_1m"]),
            "currency": str(row["currency"]),
            "source": row["source"],
            "enabled": bool(row["enabled"]),
            "created_at_ms": int(row["created_at_ms"]),
            "updated_at_ms": int(row["updated_at_ms"]),
        },
    }


@router.delete("/{provider_id}/models/{model_id}/pricing")
def delete_model_pricing(provider_id: str, model_id: str) -> Dict[str, Any]:
    """Delete pricing for a specific model under a provider."""
    from octopusos.store import get_db

    conn = get_db()
    try:
        cur = conn.execute(
            "DELETE FROM llm_model_pricing WHERE provider = ? AND model = ?",
            (provider_id, model_id),
        )
        conn.commit()
        try:
            from octopusos.core.llm.pricing import invalidate_pricing_db_cache
            invalidate_pricing_db_cache()
        except Exception:
            pass
        deleted = cur.rowcount > 0
    except Exception:
        deleted = False
    return {"ok": True, "provider_id": provider_id, "model_id": model_id, "deleted": deleted}


@router.get("/{provider_id}/models/used")
def get_used_models(provider_id: str) -> Dict[str, Any]:
    registry = ProviderRegistry.get_instance()
    if registry.get(provider_id) is None:
        raise HTTPException(status_code=404, detail="Unknown provider")
    prefs = ProviderModelPrefsManager()
    return {"provider_id": provider_id, "used_models": sorted(prefs.get_used_models(provider_id))}


@router.put("/{provider_id}/models/{model_id}/used")
def set_model_used(provider_id: str, model_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    registry = ProviderRegistry.get_instance()
    if registry.get(provider_id) is None:
        raise HTTPException(status_code=404, detail="Unknown provider")
    used = bool(payload.get("used"))
    prefs = ProviderModelPrefsManager()
    used_models = prefs.set_model_used(provider_id, model_id, used)
    return {
      "ok": True,
        "provider_id": provider_id,
        "model_id": model_id,
        "used": used,
        "used_models": sorted(used_models),
    }


@router.get("/{provider_id}/instances")
def list_instances(provider_id: str) -> List[Dict[str, Any]]:
    if provider_id not in _provider_ids():
        raise HTTPException(status_code=404, detail="Unknown provider")
    config_manager = _get_config_manager()
    return config_manager.get_instances(provider_id)


@router.post("/{provider_id}/instances")
def add_instance(provider_id: str, payload: InstanceRequest):
    if provider_id not in _provider_ids():
        raise HTTPException(status_code=404, detail="Unknown provider")
    config_manager = _get_config_manager()
    config_manager.add_instance(
        provider_id=provider_id,
        instance={
            "id": payload.instance_id,
            "base_url": payload.base_url,
            "enabled": payload.enabled,
            "metadata": payload.metadata or {},
            "launch": payload.launch or None,
        },
    )
    return {"ok": True, "instance_key": f"{provider_id}:{payload.instance_id}"}


@router.put("/{provider_id}/instances/{instance_id}")
def update_instance(provider_id: str, instance_id: str, payload: Dict[str, Any]):
    """
    Update provider instance configuration (endpoint, enabled, launch, metadata).

    Payload is permissive to keep UI forwards-compatible.
    """
    if provider_id not in _provider_ids():
        raise HTTPException(status_code=404, detail="Unknown provider")
    config_manager = _get_config_manager()

    base_url = payload.get("base_url")
    enabled = payload.get("enabled")
    metadata = payload.get("metadata")
    launch_payload = payload.get("launch")
    launch_obj: Optional[LaunchConfig] = None
    if isinstance(launch_payload, dict):
        # Accept either {bin,args} or legacy-ish shapes.
        bin_name = launch_payload.get("bin") or launch_payload.get("executable_path") or launch_payload.get("bin_name")
        args = launch_payload.get("args")
        if isinstance(args, list):
            # Best-effort: turn ["--foo","bar"] into {"extra_args":[...]}
            args = {"extra_args": args}
        if bin_name:
            launch_obj = LaunchConfig(bin=str(bin_name), args=dict(args or {}))

    config_manager.update_instance(
        provider_id=provider_id,
        instance_id=instance_id,
        base_url=base_url,
        enabled=enabled,
        launch=launch_obj,
        metadata=metadata,
    )
    return {"ok": True, "instance_key": f"{provider_id}:{instance_id}"}


@router.delete("/{provider_id}/instances/{instance_id}")
def delete_instance(provider_id: str, instance_id: str):
    if provider_id not in _provider_ids():
        raise HTTPException(status_code=404, detail="Unknown provider")
    config_manager = _get_config_manager()
    deleted = config_manager.remove_instance(provider_id, instance_id)
    return {"ok": True, "instance_key": f"{provider_id}:{instance_id}", "deleted": deleted}


@router.post("/{provider_id}/instances/{instance_id}/start")
async def start_instance(provider_id: str, instance_id: str):
    if provider_id not in _provider_ids():
        raise HTTPException(status_code=404, detail="Unknown provider")
    _ensure_local_provider(provider_id)
    if _get_instance_config(provider_id, instance_id) is None:
        raise HTTPException(status_code=404, detail="Unknown instance")
    ok, message = await _start_local_instance(provider_id, instance_id)
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    manager = ProcessManager.get_instance()
    return {
        "ok": True,
        "instance_key": f"{provider_id}:{instance_id}",
        "status": "started",
        "running": manager.is_process_running(f"{provider_id}:{instance_id}"),
        "message": message,
    }


@router.post("/{provider_id}/instances/{instance_id}/stop")
async def stop_instance(provider_id: str, instance_id: str, force: bool = False):
    if provider_id not in _provider_ids():
        raise HTTPException(status_code=404, detail="Unknown provider")
    _ensure_local_provider(provider_id)
    if _get_instance_config(provider_id, instance_id) is None:
        raise HTTPException(status_code=404, detail="Unknown instance")
    ok, message, old_pid = await _stop_local_instance(provider_id, instance_id, force=force)
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    manager = ProcessManager.get_instance()
    return {
        "ok": True,
        "instance_key": f"{provider_id}:{instance_id}",
        "status": "stopped",
        "running": manager.is_process_running(f"{provider_id}:{instance_id}"),
        "old_pid": old_pid,
        "message": message,
    }


@router.post("/{provider_id}/instances/{instance_id}/restart")
async def restart_instance(provider_id: str, instance_id: str):
    if provider_id not in _provider_ids():
        raise HTTPException(status_code=404, detail="Unknown provider")
    _ensure_local_provider(provider_id)
    if _get_instance_config(provider_id, instance_id) is None:
        raise HTTPException(status_code=404, detail="Unknown instance")
    # Best-effort restart: stop then start
    await _stop_local_instance(provider_id, instance_id, force=False)
    ok, message = await _start_local_instance(provider_id, instance_id)
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    return {"ok": True, "instance_key": f"{provider_id}:{instance_id}", "status": "restarted", "message": message}


@router.get("/{provider_id}/instances/{instance_id}/status")
def instance_status(provider_id: str, instance_id: str):
    if provider_id not in _provider_ids():
        raise HTTPException(status_code=404, detail="Unknown provider")
    if not _instance_exists(provider_id, instance_id):
        raise HTTPException(status_code=404, detail="Unknown instance")
    manager = ProcessManager.get_instance()
    running = manager.is_process_running(f"{provider_id}:{instance_id}")
    return {"status": "running" if running else "stopped", "running": running}


@router.get("/{provider_id}/instances/{instance_id}/logs")
def instance_logs(
    provider_id: str,
    instance_id: str,
    lines: int = Query(200, ge=1, le=2000),
    stream: str = Query("stdout"),
):
    if provider_id not in _provider_ids():
        raise HTTPException(status_code=404, detail="Unknown provider")
    _ensure_local_provider(provider_id)
    if _get_instance_config(provider_id, instance_id) is None:
        raise HTTPException(status_code=404, detail="Unknown instance")
    if stream not in {"stdout", "stderr"}:
        raise HTTPException(status_code=400, detail="Invalid stream")
    manager = ProcessManager.get_instance()
    out = manager.get_process_output(f"{provider_id}:{instance_id}", lines=lines, stream=stream)
    return {
        "ok": True,
        "instance_key": f"{provider_id}:{instance_id}",
        "stream": stream,
        "lines": out,
    }


@router.get("/{provider_id}/install-hint")
def get_install_hint(provider_id: str) -> Dict[str, Any]:
    """
    Return installation guidance for a provider CLI/app (no side effects).
    """
    if provider_id not in _provider_ids():
        raise HTTPException(status_code=404, detail="Unknown provider")
    platform = platform_utils.get_platform()
    suggestion = get_install_suggestion(provider_id, platform)
    return {"provider_id": provider_id, "platform": platform, "suggestion": suggestion}


@router.post("/refresh")
async def refresh_providers_status(provider_id: str | None = None):
    store = StatusStore.get_instance()
    if provider_id:
        store.invalidate_provider(provider_id)
        logger.info(f"Triggered refresh for provider: {provider_id}")
        return {
            "status": "refresh_triggered",
            "provider_id": provider_id,
            "message": f"Refresh triggered for provider {provider_id}",
        }
    store.invalidate_all_providers()
    logger.info("Triggered refresh for all providers")
    return {
        "status": "refresh_triggered",
        "scope": "all",
        "message": "Refresh triggered for all providers",
    }
