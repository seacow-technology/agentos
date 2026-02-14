"""
Generic OpenAI-compatible Cloud Provider

Used for vendors that expose an OpenAI-compatible API shape:
- GET {base_url}/models
- Authorization: Bearer <api_key>

Note: Some vendors (Google/AWS/Azure) may not be OpenAI-compatible by default.
This provider is still useful when the user configures an OpenAI-compatible gateway
or vendor-specific OpenAI-compatible endpoint.
"""

from __future__ import annotations

import asyncio
import logging
from typing import List, Optional

import httpx

from octopusos.common.reasons import ReasonCode, get_hint
from octopusos.providers.base import Provider, ProviderType, ProviderStatus, ProviderState, ModelInfo

logger = logging.getLogger(__name__)


class OpenAICompatibleCloudProvider(Provider):
    def __init__(
        self,
        provider_id: str,
        config_manager=None,
        endpoint: str = "",
        instance_id: str = "default",
        env_api_key: Optional[str] = None,
    ):
        super().__init__(provider_id, ProviderType.CLOUD, instance_id=instance_id)
        self.config_manager = config_manager
        self.default_endpoint = endpoint or ""
        self.endpoint = endpoint or ""
        self.env_api_key = env_api_key

    def _get_api_key(self) -> Optional[str]:
        if self.config_manager:
            cfg = self.config_manager.get(self.id)
            if cfg and cfg.auth.api_key:
                return cfg.auth.api_key
        if self.env_api_key:
            import os
            return os.getenv(self.env_api_key)
        return None

    def _get_endpoint(self) -> str:
        if self.config_manager:
            cfg = self.config_manager.get(self.id)
            if cfg and cfg.base_url:
                return cfg.base_url
        return self.default_endpoint

    async def probe(self) -> ProviderStatus:
        api_key = self._get_api_key()
        endpoint = (self._get_endpoint() or "").rstrip("/")

        if not api_key:
            reason = ReasonCode.NO_CONFIG
            status = ProviderStatus(
                id=self.id,
                type=self.type,
                state=ProviderState.STOPPED,
                endpoint=endpoint or None,
                latency_ms=None,
                last_ok_at=None,
                last_error="API key not configured",
                reason_code=reason,
                hint=get_hint(reason),
            )
            self._cache_status(status)
            return status

        if not endpoint:
            reason = ReasonCode.NO_CONFIG
            status = ProviderStatus(
                id=self.id,
                type=self.type,
                state=ProviderState.STOPPED,
                endpoint=None,
                latency_ms=None,
                last_ok_at=None,
                last_error="API base URL not configured",
                reason_code=reason,
                hint=get_hint(reason),
            )
            self._cache_status(status)
            return status

        start_time = asyncio.get_event_loop().time()
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(
                    f"{endpoint}/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                )

            if response.status_code == 200:
                latency_ms = (asyncio.get_event_loop().time() - start_time) * 1000
                data = response.json() if response.content else {}
                models_count = len(data.get("data", []) or [])
                state = ProviderState.RUNNING if models_count > 0 else ProviderState.DEGRADED
                reason = ReasonCode.OK if state == ProviderState.RUNNING else ReasonCode.EMPTY_RESPONSE
                status = ProviderStatus(
                    id=self.id,
                    type=self.type,
                    state=state,
                    endpoint=endpoint,
                    latency_ms=round(latency_ms, 2),
                    last_ok_at=self.now_iso() if state == ProviderState.RUNNING else None,
                    last_error=None if state == ProviderState.RUNNING else "No models available",
                    reason_code=reason,
                    hint=get_hint(reason) if reason != ReasonCode.OK else None,
                )
            elif response.status_code == 401:
                reason = ReasonCode.HTTP_401
                status = ProviderStatus(
                    id=self.id,
                    type=self.type,
                    state=ProviderState.ERROR,
                    endpoint=endpoint,
                    latency_ms=None,
                    last_ok_at=None,
                    last_error="401 Unauthorized",
                    reason_code=reason,
                    hint=get_hint(reason),
                )
            else:
                reason = ReasonCode.DEGRADED
                status = ProviderStatus(
                    id=self.id,
                    type=self.type,
                    state=ProviderState.DEGRADED,
                    endpoint=endpoint,
                    latency_ms=None,
                    last_ok_at=None,
                    last_error=f"HTTP {response.status_code}",
                    reason_code=reason,
                    hint=get_hint(reason),
                )
        except httpx.ConnectError:
            reason = ReasonCode.CONN_REFUSED
            status = ProviderStatus(
                id=self.id,
                type=self.type,
                state=ProviderState.STOPPED,
                endpoint=endpoint,
                latency_ms=None,
                last_ok_at=None,
                last_error="connection refused",
                reason_code=reason,
                hint=get_hint(reason),
            )
        except httpx.TimeoutException:
            reason = ReasonCode.TIMEOUT
            status = ProviderStatus(
                id=self.id,
                type=self.type,
                state=ProviderState.DEGRADED,
                endpoint=endpoint,
                latency_ms=None,
                last_ok_at=None,
                last_error="timeout",
                reason_code=reason,
                hint=get_hint(reason),
            )
        except Exception as exc:
            reason = ReasonCode.INVALID_RESPONSE
            status = ProviderStatus(
                id=self.id,
                type=self.type,
                state=ProviderState.ERROR,
                endpoint=endpoint,
                latency_ms=None,
                last_ok_at=None,
                last_error=str(exc)[:200],
                reason_code=reason,
                hint=get_hint(reason),
            )

        self._cache_status(status)
        return status

    async def list_models(self) -> List[ModelInfo]:
        api_key = self._get_api_key()
        endpoint = (self._get_endpoint() or "").rstrip("/")
        if not api_key or not endpoint:
            return []
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                response = await client.get(
                    f"{endpoint}/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
            if response.status_code != 200:
                return []
            data = response.json() if response.content else {}
            models = []
            for m in data.get("data", []) or []:
                mid = m.get("id", "") or ""
                if not mid:
                    continue
                models.append(ModelInfo(id=mid, label=mid, metadata=m))
            return models
        except Exception:
            return []

