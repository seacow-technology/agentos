"""
OpenAI Provider - Cloud LLM via OpenAI API

Sprint B Task #6: Integrated with SecretStore for API key management
v0.3.2 Closeout: Updated to use standard reason codes
"""

import os
import asyncio
import httpx
import logging
from typing import List, Optional
from agentos.providers.base import (
    Provider,
    ProviderType,
    ProviderStatus,
    ProviderState,
    ModelInfo,
)
from agentos.common.reasons import ReasonCode, get_hint

logger = logging.getLogger(__name__)


class OpenAIProvider(Provider):
    """OpenAI cloud model provider"""

    def __init__(
        self,
        config_manager=None,
        endpoint: str = "https://api.openai.com/v1",
        instance_id: str = "default",
    ):
        super().__init__("openai", ProviderType.CLOUD, instance_id=instance_id)
        self.config_manager = config_manager
        self.default_endpoint = endpoint
        self.endpoint = endpoint  # For consistency with local providers

    def _get_api_key(self) -> Optional[str]:
        """
        Get API key from SecretStore, config, or environment

        Priority: SecretStore > config_manager > env var
        """
        # Try SecretStore first (Sprint B Task #6)
        try:
            from agentos.webui.secrets import SecretStore
            store = SecretStore()
            api_key = store.get_secret(self.id)
            if api_key:
                logger.debug(f"Using API key from SecretStore for {self.id}")
                return api_key
        except Exception as e:
            logger.debug(f"SecretStore not available: {e}")

        # Try config manager (legacy support)
        if self.config_manager:
            config = self.config_manager.get(self.id)
            if config and config.auth.api_key:
                return config.auth.api_key

        # Fall back to environment variable
        return os.getenv("OPENAI_API_KEY")

    def _get_endpoint(self) -> str:
        """Get endpoint from config or use default"""
        if self.config_manager:
            config = self.config_manager.get(self.id)
            if config and config.base_url:
                return config.base_url

        return self.default_endpoint

    async def probe(self) -> ProviderStatus:
        """
        Probe OpenAI API health

        Task #6: Now uses config_manager for credentials
        """
        api_key = self._get_api_key()
        endpoint = self._get_endpoint()

        # No API key configured
        if not api_key:
            reason = ReasonCode.NO_CONFIG
            status = ProviderStatus(
                id=self.id,
                type=self.type,
                state=ProviderState.STOPPED,
                endpoint=endpoint,
                latency_ms=None,
                last_ok_at=None,
                last_error="API key not configured",
                reason_code=reason,
                hint=get_hint(reason),
            )
            self._cache_status(status)
            return status

        # API key exists - try a lightweight check
        start_time = asyncio.get_event_loop().time()

        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(
                    f"{endpoint}/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                )

                if response.status_code == 200:
                    latency_ms = (asyncio.get_event_loop().time() - start_time) * 1000

                    # Check if models list is empty
                    data = response.json()
                    models_count = len(data.get("data", []))

                    if models_count == 0:
                        state = ProviderState.DEGRADED
                        error = "No models available"
                        reason = ReasonCode.EMPTY_RESPONSE
                    else:
                        state = ProviderState.RUNNING
                        error = None
                        reason = ReasonCode.OK

                    status = ProviderStatus(
                        id=self.id,
                        type=self.type,
                        state=state,
                        endpoint=endpoint,
                        latency_ms=round(latency_ms, 2),
                        last_ok_at=self.now_iso() if state == ProviderState.RUNNING else None,
                        last_error=error,
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
                    # Map other HTTP errors
                    if response.status_code == 403:
                        reason = ReasonCode.HTTP_403
                    elif response.status_code == 429:
                        reason = ReasonCode.HTTP_429
                    elif response.status_code >= 500:
                        reason = ReasonCode.HTTP_5XX
                    else:
                        reason = ReasonCode.INVALID_RESPONSE

                    status = ProviderStatus(
                        id=self.id,
                        type=self.type,
                        state=ProviderState.ERROR,
                        endpoint=endpoint,
                        latency_ms=None,
                        last_ok_at=None,
                        last_error=f"HTTP {response.status_code}",
                        reason_code=reason,
                        hint=get_hint(reason),
                    )

        except httpx.TimeoutException:
            reason = ReasonCode.TIMEOUT
            status = ProviderStatus(
                id=self.id,
                type=self.type,
                state=ProviderState.ERROR,
                endpoint=endpoint,
                latency_ms=None,
                last_ok_at=None,
                last_error="Timeout",
                reason_code=reason,
                hint=get_hint(reason),
            )
        except Exception as e:
            # Keep error messages short for UI
            error_msg = str(e)[:50]
            reason = ReasonCode.INVALID_RESPONSE
            status = ProviderStatus(
                id=self.id,
                type=self.type,
                state=ProviderState.ERROR,
                endpoint=endpoint,
                latency_ms=None,
                last_ok_at=None,
                last_error=error_msg,
                reason_code=reason,
                hint=get_hint(reason),
            )

        self._cache_status(status)
        return status

    async def list_models(self) -> List[ModelInfo]:
        """
        List available OpenAI models

        Task #6: Now uses config_manager for credentials
        """
        api_key = self._get_api_key()
        endpoint = self._get_endpoint()

        if not api_key:
            return []

        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(
                    f"{endpoint}/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                )

                if response.status_code == 200:
                    data = response.json()
                    models = []

                    # Filter to only chat models
                    for model_data in data.get("data", []):
                        model_id = model_data.get("id", "")
                        if "gpt" in model_id.lower():
                            models.append(
                                ModelInfo(
                                    id=model_id,
                                    label=model_id,
                                    metadata=model_data,
                                )
                            )

                    return sorted(models, key=lambda m: m.id)

        except Exception:
            pass

        return []
