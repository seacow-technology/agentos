"""
llama.cpp Provider - Local LLM via llama-server or llama.cpp server

v0.3.2 Closeout: Updated to use standard reason codes
"""

import asyncio
import httpx
from typing import List
from agentos.providers.base import (
    Provider,
    ProviderType,
    ProviderStatus,
    ProviderState,
    ModelInfo,
)
from agentos.common.reasons import ReasonCode, get_hint


class LlamaCppProvider(Provider):
    """llama.cpp local model provider"""

    def __init__(
        self,
        endpoint: str = "http://127.0.0.1:8080",
        instance_id: str = "default",
    ):
        super().__init__("llamacpp", ProviderType.LOCAL, instance_id=instance_id)
        self.endpoint = endpoint

    async def probe(self) -> ProviderStatus:
        """Probe llama.cpp server health with fingerprint verification"""
        from agentos.providers.fingerprint import verify_expected_fingerprint, FingerprintResult

        start_time = asyncio.get_event_loop().time()

        # Verify service fingerprint (llamacpp can be native or OpenAI-compatible)
        matches, detected, fingerprint_meta = await verify_expected_fingerprint(
            self.endpoint,
            FingerprintResult.LLAMACPP,
            timeout=1.5,
        )

        if not matches:
            if detected == FingerprintResult.NO_SERVICE:
                reason = ReasonCode.CONN_REFUSED
                error_msg = "No service running on endpoint"
            elif detected == FingerprintResult.UNKNOWN:
                reason = ReasonCode.FINGERPRINT_MISMATCH
                error_msg = f"Service fingerprint unrecognized (expected llama.cpp)"
            else:
                reason = ReasonCode.PORT_OCCUPIED_BY_OTHER_PROVIDER
                error_msg = f"Port occupied by {detected.value} (expected llama.cpp)"

            status = ProviderStatus(
                id=self.id,
                type=self.type,
                state=ProviderState.ERROR,
                endpoint=self.endpoint,
                latency_ms=None,
                last_ok_at=None,
                last_error=error_msg,
                reason_code=reason,
                hint=get_hint(reason),
            )
            self._cache_status(status)
            return status

        try:
            async with httpx.AsyncClient(timeout=1.5) as client:
                # Try OpenAI-compatible endpoint first
                try:
                    response = await client.get(f"{self.endpoint}/v1/models")
                    if response.status_code == 200:
                        latency_ms = (asyncio.get_event_loop().time() - start_time) * 1000
                        status = ProviderStatus(
                            id=self.id,
                            type=self.type,
                            state=ProviderState.RUNNING,
                            endpoint=self.endpoint,
                            latency_ms=round(latency_ms, 2),
                            last_ok_at=self.now_iso(),
                            last_error=None,
                            reason_code=ReasonCode.OK,
                            hint=None,
                        )
                        self._cache_status(status)
                        return status
                except httpx.HTTPStatusError:
                    pass

                # Fallback: try /health endpoint
                response = await client.get(f"{self.endpoint}/health")
                if response.status_code == 200:
                    latency_ms = (asyncio.get_event_loop().time() - start_time) * 1000
                    status = ProviderStatus(
                        id=self.id,
                        type=self.type,
                        state=ProviderState.RUNNING,
                        endpoint=self.endpoint,
                        latency_ms=round(latency_ms, 2),
                        last_ok_at=self.now_iso(),
                        last_error=None,
                        reason_code=ReasonCode.OK,
                        hint=None,
                    )
                else:
                    # Map HTTP status to reason code
                    if response.status_code == 404:
                        reason = ReasonCode.HTTP_404
                    elif response.status_code >= 500:
                        reason = ReasonCode.HTTP_5XX
                    else:
                        reason = ReasonCode.DEGRADED

                    status = ProviderStatus(
                        id=self.id,
                        type=self.type,
                        state=ProviderState.DEGRADED,
                        endpoint=self.endpoint,
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
                endpoint=self.endpoint,
                latency_ms=None,
                last_ok_at=None,
                last_error="connection refused (is llama-server running?)",
                reason_code=reason,
                hint=get_hint(reason),
            )
        except httpx.TimeoutException:
            reason = ReasonCode.TIMEOUT
            status = ProviderStatus(
                id=self.id,
                type=self.type,
                state=ProviderState.ERROR,
                endpoint=self.endpoint,
                latency_ms=None,
                last_ok_at=None,
                last_error="timeout",
                reason_code=reason,
                hint=get_hint(reason),
            )
        except Exception as e:
            reason = ReasonCode.INVALID_RESPONSE
            status = ProviderStatus(
                id=self.id,
                type=self.type,
                state=ProviderState.ERROR,
                endpoint=self.endpoint,
                latency_ms=None,
                last_ok_at=None,
                last_error=str(e),
                reason_code=reason,
                hint=get_hint(reason),
            )

        self._cache_status(status)
        return status

    async def list_models(self) -> List[ModelInfo]:
        """List available llama.cpp models"""
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                # Try OpenAI-compatible endpoint
                try:
                    response = await client.get(f"{self.endpoint}/v1/models")
                    if response.status_code == 200:
                        data = response.json()
                        models = []

                        for model_data in data.get("data", []):
                            model_id = model_data.get("id", "unknown")
                            models.append(
                                ModelInfo(
                                    id=model_id,
                                    label=model_id,
                                    metadata=model_data,
                                )
                            )

                        return models
                except httpx.HTTPStatusError:
                    pass

                # Fallback: return generic info if server is up but no models endpoint
                health_response = await client.get(f"{self.endpoint}/health")
                if health_response.status_code == 200:
                    return [
                        ModelInfo(
                            id="loaded_model",
                            label="Currently loaded model",
                            metadata={"note": "llama.cpp server doesn't expose model list"},
                        )
                    ]

        except Exception:
            pass

        return []
