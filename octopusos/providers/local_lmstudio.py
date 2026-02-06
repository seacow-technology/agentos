"""
LM Studio Provider - Local LLM via LM Studio (OpenAI-compatible)

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


class LMStudioProvider(Provider):
    """LM Studio local model provider (OpenAI-compatible server)"""

    def __init__(
        self,
        endpoint: str = "http://127.0.0.1:1234",
        instance_id: str = "default",
    ):
        super().__init__("lmstudio", ProviderType.LOCAL, instance_id=instance_id)
        self.endpoint = endpoint

    async def probe(self) -> ProviderStatus:
        """Probe LM Studio server health with fingerprint verification"""
        from agentos.providers.fingerprint import verify_expected_fingerprint, FingerprintResult

        start_time = asyncio.get_event_loop().time()

        # Verify service fingerprint (LM Studio is OpenAI-compatible)
        matches, detected, fingerprint_meta = await verify_expected_fingerprint(
            self.endpoint,
            FingerprintResult.LMSTUDIO,
            timeout=1.5,
        )

        if not matches:
            if detected == FingerprintResult.NO_SERVICE:
                reason = ReasonCode.CONN_REFUSED
                error_msg = "No service running on endpoint"
            elif detected == FingerprintResult.UNKNOWN:
                reason = ReasonCode.FINGERPRINT_MISMATCH
                error_msg = f"Service fingerprint unrecognized (expected LM Studio/OpenAI-compatible)"
            else:
                reason = ReasonCode.PORT_OCCUPIED_BY_OTHER_PROVIDER
                error_msg = f"Port occupied by {detected.value} (expected LM Studio)"

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
                # LM Studio uses OpenAI-compatible API
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
                last_error="connection refused (is LM Studio Server running?)",
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
        """List available LM Studio models"""
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(f"{self.endpoint}/v1/models")

                if response.status_code == 200:
                    data = response.json()
                    models = []

                    for model_data in data.get("data", []):
                        model_id = model_data.get("id", "")
                        models.append(
                            ModelInfo(
                                id=model_id,
                                label=model_id,
                                metadata=model_data,
                            )
                        )

                    return models

        except Exception:
            pass

        return []
