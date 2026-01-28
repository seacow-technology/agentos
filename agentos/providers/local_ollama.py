"""
Ollama Provider - Local LLM via Ollama

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


class OllamaProvider(Provider):
    """Ollama local model provider"""

    def __init__(
        self,
        endpoint: str = "http://127.0.0.1:11434",
        instance_id: str = "default",
    ):
        super().__init__("ollama", ProviderType.LOCAL, instance_id=instance_id)
        self.endpoint = endpoint

    async def probe(self) -> ProviderStatus:
        """Probe Ollama server health with fingerprint verification"""
        from agentos.providers.fingerprint import verify_expected_fingerprint, FingerprintResult

        start_time = asyncio.get_event_loop().time()

        # Verify service fingerprint first
        matches, detected, fingerprint_meta = await verify_expected_fingerprint(
            self.endpoint,
            FingerprintResult.OLLAMA,
            timeout=1.5,
        )

        if not matches:
            # Service exists but wrong fingerprint
            if detected == FingerprintResult.NO_SERVICE:
                reason = ReasonCode.CONN_REFUSED
                error_msg = "No service running on endpoint"
            elif detected == FingerprintResult.UNKNOWN:
                reason = ReasonCode.FINGERPRINT_MISMATCH
                error_msg = f"Service fingerprint unrecognized (expected Ollama)"
            else:
                reason = ReasonCode.PORT_OCCUPIED_BY_OTHER_PROVIDER
                error_msg = f"Port occupied by {detected.value} (expected Ollama)"

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

        # Fingerprint verified, proceed with normal probe
        try:
            async with httpx.AsyncClient(timeout=1.5) as client:
                response = await client.get(f"{self.endpoint}/api/tags")

                if response.status_code == 200:
                    latency_ms = (asyncio.get_event_loop().time() - start_time) * 1000

                    status = ProviderStatus(
                        id=self.id,
                        type=self.type,
                        state=ProviderState.READY,
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
                state=ProviderState.DISCONNECTED,
                endpoint=self.endpoint,
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
                state=ProviderState.ERROR,
                endpoint=self.endpoint,
                latency_ms=None,
                last_ok_at=None,
                last_error="timeout",
                reason_code=reason,
                hint=get_hint(reason),
            )
        except Exception as e:
            status = ProviderStatus(
                id=self.id,
                type=self.type,
                state=ProviderState.ERROR,
                endpoint=self.endpoint,
                latency_ms=None,
                last_ok_at=None,
                last_error=str(e)[:100],
                reason_code=ReasonCode.INVALID_RESPONSE,
                hint=get_hint(ReasonCode.INVALID_RESPONSE),
            )

        self._cache_status(status)
        return status

    async def list_models(self) -> List[ModelInfo]:
        """List available Ollama models"""
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(f"{self.endpoint}/api/tags")

                if response.status_code == 200:
                    data = response.json()
                    models = []

                    for model_data in data.get("models", []):
                        model_name = model_data.get("name", "")
                        models.append(
                            ModelInfo(
                                id=model_name,
                                label=model_name,
                                metadata={"size": model_data.get("size", 0)},
                            )
                        )

                    return models

        except Exception:
            pass

        return []
