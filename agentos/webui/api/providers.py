"""
Providers API - Model provider status and management

Endpoints:
- GET /api/providers - List all providers
- GET /api/providers/status - Get status for all providers
- GET /api/providers/{provider_id}/models - Get models for a provider

Phase 3.3: Unified Error Handling
"""

from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import logging

from agentos.providers.registry import ProviderRegistry
from agentos.providers.base import ProviderType, ProviderState
from agentos.providers.detector import LocalProviderDetector
from agentos.providers.runtime import OllamaRuntimeManager
from agentos.providers.cloud_config import CloudAuthConfig
from agentos.core.status_store import StatusStore
from agentos.webui.middleware import sanitize_response
from agentos.webui.api import providers_errors
from agentos.webui.api.time_format import iso_z
from agentos.core.time import utc_now


logger = logging.getLogger(__name__)

router = APIRouter()


class ProviderInfo(BaseModel):
    """Provider information"""
    id: str
    label: str
    type: str
    supports_models: bool
    supports_start: bool = False
    supports_auth: List[str] = []


class ProviderStatusResponse(BaseModel):
    """
    Provider status response

    Task #17: P0.4 - Enhanced with health check details
    """
    id: str
    type: str
    state: str
    endpoint: str | None = None
    latency_ms: float | None = None
    last_ok_at: str | None = None
    last_error: str | None = None
    # Task #17: Health check details
    pid: int | None = None
    pid_exists: bool | None = None
    port_listening: bool | None = None
    api_responding: bool | None = None


class ModelInfoResponse(BaseModel):
    """Model information response"""
    id: str
    label: str
    context_window: int | None = None


class ProvidersListResponse(BaseModel):
    """Providers list response"""
    local: List[ProviderInfo]
    cloud: List[ProviderInfo]


class ProvidersStatusResponse(BaseModel):
    """All providers status response"""
    ts: str
    providers: List[ProviderStatusResponse]
    cache_ttl_ms: int  # Cache TTL in milliseconds


class ModelsListResponse(BaseModel):
    """Models list response"""
    provider_id: str
    models: List[ModelInfoResponse]


class LocalDetectResultResponse(BaseModel):
    """Local provider detection result"""
    id: str
    cli_found: bool
    service_reachable: bool
    endpoint: str
    models_count: int
    details: Dict[str, Any]
    state: str


class LocalDetectResponse(BaseModel):
    """Local providers detection response"""
    ts: str
    results: List[LocalDetectResultResponse]


class RuntimeActionResponse(BaseModel):
    """Runtime action response (start/stop/restart)"""
    status: str
    message: str
    pid: int | None = None
    endpoint: str | None = None


class RuntimeStatusResponse(BaseModel):
    """Runtime status response"""
    provider_id: str
    is_running: bool
    pid: int | None = None
    command: str | None = None
    started_at: str | None = None
    endpoint: str | None = None


# Cloud Config Models (Task #6)


class CloudConfigRequest(BaseModel):
    """Cloud provider configuration request"""
    provider_id: str
    auth: Dict[str, str]  # {"type": "api_key", "api_key": "..."}
    base_url: str | None = None


class CloudConfigResponse(BaseModel):
    """Cloud provider configuration response"""
    ok: bool
    message: str | None = None


class CloudTestRequest(BaseModel):
    """Cloud provider test request"""
    provider_id: str


class CloudTestResponse(BaseModel):
    """Cloud provider test response"""
    ok: bool
    state: str | None = None
    latency_ms: float | None = None
    models_count: int | None = None
    error: str | None = None


@router.get("")
async def list_providers() -> ProvidersListResponse:
    """
    List all available providers (Local & Cloud)

    Returns metadata about each provider including capabilities
    """
    # Static provider metadata (could be moved to config)
    return ProvidersListResponse(
        local=[
            ProviderInfo(
                id="ollama",
                label="Ollama",
                type="local",
                supports_models=True,
                supports_start=True,
            ),
            ProviderInfo(
                id="lmstudio",
                label="LM Studio",
                type="local",
                supports_models=True,
                supports_start=False,
            ),
            ProviderInfo(
                id="llamacpp",
                label="llama.cpp",
                type="local",
                supports_models=True,
                supports_start=True,
            ),
        ],
        cloud=[
            ProviderInfo(
                id="openai",
                label="OpenAI",
                type="cloud",
                supports_models=True,
                supports_auth=["api_key"],
            ),
            ProviderInfo(
                id="anthropic",
                label="Anthropic",
                type="cloud",
                supports_models=True,
                supports_auth=["api_key"],
            ),
        ],
    )


@router.get("/status")
async def get_providers_status() -> ProvidersStatusResponse:
    """
    Get current status for all providers

    Uses StatusStore for caching to prevent redundant probes.
    Cache TTL: 5 seconds (configurable)

    Fast: typically completes in < 100ms when cached, < 1.5s on fresh probe.
    """
    from datetime import datetime, timezone

    # Use StatusStore for unified caching
    store = StatusStore.get_instance()
    status_list, cache_ttl_ms = await store.get_all_provider_status(ttl_ms=5000)

    # Convert to response format
    providers_status = [
        ProviderStatusResponse(
            id=status.id,
            type=status.type.value,
            state=status.state.value,
            endpoint=status.endpoint,
            latency_ms=status.latency_ms,
            last_ok_at=status.last_ok_at,
            last_error=status.last_error,
            # Task #17: Include health check details
            pid=status.pid,
            pid_exists=status.pid_exists,
            port_listening=status.port_listening,
            api_responding=status.api_responding,
        )
        for status in status_list
    ]

    response = ProvidersStatusResponse(
        ts=iso_z(utc_now()),
        providers=providers_status,
        cache_ttl_ms=cache_ttl_ms,
    )

    # Apply sanitization as safety net
    return sanitize_response(response.model_dump())


@router.post("/refresh")
async def refresh_providers_status(
    provider_id: str | None = None
):
    """
    触发一次 providers 状态刷新（异步执行）

    如果提供 provider_id，只刷新该 provider
    否则刷新所有 providers

    返回：202 Accepted，实际刷新通过清除缓存触发
    下次 GET /status 会重新探测
    """
    store = StatusStore.get_instance()

    if provider_id:
        store.invalidate_provider(provider_id)
        logger.info(f"Triggered refresh for provider: {provider_id}")
        return {
            "status": "refresh_triggered",
            "provider_id": provider_id,
            "message": "Cache cleared, next status request will refresh"
        }
    else:
        store.invalidate_all_providers()
        logger.info("Triggered refresh for all providers")
        return {
            "status": "refresh_triggered",
            "scope": "all",
            "message": "All caches cleared, next status request will refresh"
        }


@router.get("/{provider_id}/models")
async def get_provider_models(provider_id: str) -> ModelsListResponse:
    """
    Get available models for a specific provider

    Supports both:
    - Specific instances: "llamacpp:qwen3-coder-30b"
    - Provider types: "llamacpp" (aggregates all llamacpp:* instances)

    Returns empty list if provider is not available or doesn't support models.
    """
    registry = ProviderRegistry.get_instance()

    # Try to get specific provider instance
    provider = registry.get(provider_id)

    if provider:
        # Single provider found
        try:
            models = await provider.list_models()

            return ModelsListResponse(
                provider_id=provider_id,
                models=[
                    ModelInfoResponse(
                        id=model.id,
                        label=model.label,
                        context_window=model.context_window,
                    )
                    for model in models
                ],
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to list models for provider '{provider_id}': {str(e)}",
            )
    else:
        # Provider not found, try to find all instances with this prefix
        # e.g., "llamacpp" -> ["llamacpp:qwen3-coder-30b", "llamacpp:qwen2.5-coder-7b"]
        all_providers = registry.list_all()
        prefix = f"{provider_id}:"
        matching_providers = [p for p in all_providers if p.id.startswith(prefix)]

        if not matching_providers:
            # No matching providers found
            raise HTTPException(
                status_code=404,
                detail=f"Provider '{provider_id}' not found and no instances with prefix '{prefix}' exist"
            )

        # Aggregate models from all matching instances
        all_models = []
        seen_model_ids = set()

        for provider in matching_providers:
            try:
                models = await provider.list_models()
                for model in models:
                    # Deduplicate by model ID
                    if model.id not in seen_model_ids:
                        all_models.append(
                            ModelInfoResponse(
                                id=model.id,
                                label=model.label,
                                context_window=model.context_window,
                            )
                        )
                        seen_model_ids.add(model.id)
            except Exception as e:
                # Log error but continue with other providers
                print(f"Warning: Failed to list models from {provider.id}: {e}")
                continue

        return ModelsListResponse(
            provider_id=provider_id,
            models=all_models,
        )


@router.get("/local/detect")
async def detect_local_providers() -> LocalDetectResponse:
    """
    Detect local model provider environments

    Checks for:
    - CLI/executable presence
    - Service reachability
    - Available models
    - Installation status

    Returns detection results with hints for setup.
    """
    from datetime import datetime, timezone

    results = await LocalProviderDetector.detect_all()

    return LocalDetectResponse(
        ts=iso_z(utc_now()),
        results=[
            LocalDetectResultResponse(
                id=result.id,
                cli_found=result.cli_found,
                service_reachable=result.service_reachable,
                endpoint=result.endpoint,
                models_count=result.models_count,
                details=result.details,
                state=result.state,
            )
            for result in results
        ],
    )


# Ollama Runtime Management Endpoints (Task #5)


@router.post("/ollama/start")
async def start_ollama() -> RuntimeActionResponse:
    """
    Start Ollama server

    Starts 'ollama serve' as a background process and tracks PID.
    Returns error if Ollama CLI is not installed.
    """
    manager = OllamaRuntimeManager()
    result = await manager.start()

    return RuntimeActionResponse(
        status=result["status"],
        message=result["message"],
        pid=result.get("pid"),
        endpoint=result.get("endpoint"),
    )


@router.post("/ollama/stop")
async def stop_ollama(force: bool = False) -> RuntimeActionResponse:
    """
    Stop Ollama server

    Sends SIGTERM and waits 2s for graceful shutdown.
    Falls back to SIGKILL if still running.

    Query params:
    - force: If true, use SIGKILL immediately
    """
    manager = OllamaRuntimeManager()
    result = await manager.stop(force=force)

    return RuntimeActionResponse(
        status=result["status"],
        message=result["message"],
        pid=result.get("pid"),
    )


@router.post("/ollama/restart")
async def restart_ollama() -> RuntimeActionResponse:
    """
    Restart Ollama server

    Stops (if running) then starts Ollama server.
    """
    manager = OllamaRuntimeManager()
    result = await manager.restart()

    return RuntimeActionResponse(
        status=result["status"],
        message=result["message"],
        pid=result.get("pid"),
    )


@router.get("/ollama/runtime")
async def get_ollama_runtime() -> RuntimeStatusResponse:
    """
    Get Ollama runtime status

    Returns current PID, start time, and endpoint if running.
    """
    manager = OllamaRuntimeManager()
    runtime = manager.get_runtime()

    if runtime:
        return RuntimeStatusResponse(
            provider_id="ollama",
            is_running=True,
            pid=runtime["pid"],
            command=runtime["command"],
            started_at=runtime["started_at"],
            endpoint=runtime["endpoint"],
        )
    else:
        return RuntimeStatusResponse(
            provider_id="ollama",
            is_running=False,
        )


# Cloud Config Management Endpoints (Task #6)


@router.post("/cloud/config")
async def save_cloud_config(request: CloudConfigRequest) -> CloudConfigResponse:
    """
    Save or update cloud provider configuration

    Stores credentials securely in ~/.agentos/secrets/providers.json (chmod 600)
    Automatically triggers a test connection after saving.

    Security:
    - API keys are never logged
    - Only masked keys are returned in responses
    - File permissions set to 600
    """
    from datetime import datetime, timezone

    registry = ProviderRegistry.get_instance()
    config_manager = registry.get_config_manager()

    # Validate provider exists
    provider = registry.get(request.provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail=f"Provider '{request.provider_id}' not found")

    # Validate auth type
    auth_type = request.auth.get("type", "api_key")
    api_key = request.auth.get("api_key", "")

    if not api_key:
        raise HTTPException(status_code=400, detail="API key is required")

    # Save configuration
    try:
        auth = CloudAuthConfig(type=auth_type, api_key=api_key)
        config_manager.set(
            provider_id=request.provider_id,
            auth=auth,
            base_url=request.base_url,
        )

        # Trigger a test connection
        status = await provider.probe()

        # Update last_verified_at if successful
        if status.state == ProviderState.READY:
            config_manager.update_verified_at(
                request.provider_id,
                iso_z(utc_now()),
            )

        return CloudConfigResponse(
            ok=True,
            message=f"Configuration saved and tested ({status.state.value})",
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save configuration: {str(e)}",
        )


@router.post("/cloud/test")
async def test_cloud_provider(request: CloudTestRequest) -> CloudTestResponse:
    """
    Test connection to a cloud provider

    Makes a real API call to verify credentials and measure latency.
    Returns provider state, latency, and model count.

    This is a lightweight check - typically completes in < 2s.
    """
    registry = ProviderRegistry.get_instance()
    provider = registry.get(request.provider_id)

    if not provider:
        raise HTTPException(status_code=404, detail=f"Provider '{request.provider_id}' not found")

    try:
        # Probe the provider
        status = await provider.probe()

        if status.state == ProviderState.READY:
            # Get model count
            models = await provider.list_models()
            models_count = len(models)

            return CloudTestResponse(
                ok=True,
                state=status.state.value,
                latency_ms=status.latency_ms,
                models_count=models_count,
            )
        else:
            return CloudTestResponse(
                ok=False,
                state=status.state.value,
                error=status.last_error,
            )

    except Exception as e:
        return CloudTestResponse(
            ok=False,
            state="ERROR",
            error=str(e)[:100],  # Keep error short
        )


@router.delete("/cloud/config/{provider_id}")
async def delete_cloud_config(provider_id: str) -> CloudConfigResponse:
    """
    Delete cloud provider configuration

    Removes stored credentials from ~/.agentos/secrets/providers.json
    """
    registry = ProviderRegistry.get_instance()
    config_manager = registry.get_config_manager()

    # Validate provider exists
    provider = registry.get(provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_id}' not found")

    # Delete configuration
    deleted = config_manager.delete(provider_id)

    if deleted:
        return CloudConfigResponse(
            ok=True,
            message=f"Configuration for '{provider_id}' deleted",
        )
    else:
        return CloudConfigResponse(
            ok=False,
            message=f"No configuration found for '{provider_id}'",
        )
