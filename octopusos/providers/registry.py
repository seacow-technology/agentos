"""
Provider Registry - Central registry for all model providers

Task #6: Now supports CloudConfigManager injection for cloud providers
Sprint B+: Configurable endpoints and multi-instance support
"""

import asyncio
import logging
from typing import Dict, List, Optional
from octopusos.providers.base import Provider, ProviderStatus

logger = logging.getLogger(__name__)


class ProviderRegistry:
    """
    Central registry for all providers (Local & Cloud)

    Singleton pattern - use get_instance()
    Now supports configurable endpoints and multiple instances per provider
    """

    _instance: Optional["ProviderRegistry"] = None

    def __init__(self):
        self._providers: Dict[str, Provider] = {}
        self._config_manager = None  # Lazy-loaded (CloudConfigManager)
        self._providers_config_manager = None  # Lazy-loaded (ProvidersConfigManager)

    @classmethod
    def get_instance(cls) -> "ProviderRegistry":
        """Get singleton instance"""
        if cls._instance is None:
            cls._instance = cls()
            cls._instance._register_default_providers()
        return cls._instance

    def register(self, provider: Provider):
        """Register a provider"""
        self._providers[provider.id] = provider

    def get(self, provider_id: str) -> Optional[Provider]:
        """Get provider by ID"""
        return self._providers.get(provider_id)

    def list_all(self) -> List[Provider]:
        """List all registered providers"""
        return list(self._providers.values())

    async def get_all_status(self) -> List[ProviderStatus]:
        """
        Get status for all providers (concurrently)

        Fast: runs all probes in parallel with timeout protection
        """
        tasks = [provider.probe() for provider in self._providers.values()]

        # Run all probes concurrently with timeout
        try:
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=3.0
            )
        except asyncio.TimeoutError:
            # Return cached status for all if global timeout
            results = [p.get_cached_status() for p in self._providers.values()]

        # Filter out exceptions and None
        status_list = []
        for result in results:
            if isinstance(result, ProviderStatus):
                status_list.append(result)
            elif isinstance(result, Exception):
                # Log but don't crash
                pass

        return status_list

    def _get_config_manager(self):
        """Get or create CloudConfigManager (lazy-loaded)"""
        if self._config_manager is None:
            from octopusos.providers.cloud_config import CloudConfigManager
            self._config_manager = CloudConfigManager()
        return self._config_manager

    def get_config_manager(self):
        """Public accessor for CloudConfigManager"""
        return self._get_config_manager()

    def _get_providers_config_manager(self):
        """Get or create ProvidersConfigManager (lazy-loaded)"""
        if self._providers_config_manager is None:
            from octopusos.providers.providers_config import ProvidersConfigManager
            self._providers_config_manager = ProvidersConfigManager()
        return self._providers_config_manager

    def get_providers_config_manager(self):
        """Public accessor for ProvidersConfigManager"""
        return self._get_providers_config_manager()

    def _register_default_providers(self):
        """
        Register providers from configuration

        Sprint B+: Now reads from ~/.octopusos/config/providers.json
        Supports multiple instances per provider
        """
        # Import here to avoid circular dependency
        from octopusos.providers.local_ollama import OllamaProvider
        from octopusos.providers.local_lmstudio import LMStudioProvider
        from octopusos.providers.local_llamacpp import LlamaCppProvider
        from octopusos.providers.cloud_openai import OpenAIProvider
        from octopusos.providers.cloud_anthropic import AnthropicProvider
        from octopusos.providers.cloud_openai_compatible import OpenAICompatibleCloudProvider

        # Get configuration managers
        providers_config = self._get_providers_config_manager()
        cloud_config = self._get_config_manager()

        # Map provider IDs to classes
        provider_classes = {
            "ollama": OllamaProvider,
            "lmstudio": LMStudioProvider,
            "llamacpp": LlamaCppProvider,
            "openai": OpenAIProvider,
            "anthropic": AnthropicProvider,
            # OpenAI-compatible cloud vendors
            "google": OpenAICompatibleCloudProvider,
            "meta": OpenAICompatibleCloudProvider,
            "deepseek": OpenAICompatibleCloudProvider,
            "amazon": OpenAICompatibleCloudProvider,
            "alibaba_cloud": OpenAICompatibleCloudProvider,
            "zai": OpenAICompatibleCloudProvider,
            "moonshot": OpenAICompatibleCloudProvider,
            "microsoft": OpenAICompatibleCloudProvider,
            "xai": OpenAICompatibleCloudProvider,
        }

        # Register all configured provider instances
        all_configs = providers_config.get_all_provider_configs()

        # Separate local and cloud providers
        local_provider_ids = ["ollama", "lmstudio", "llamacpp"]
        cloud_provider_ids = [
            "openai",
            "anthropic",
            "google",
            "meta",
            "deepseek",
            "amazon",
            "alibaba_cloud",
            "zai",
            "moonshot",
            "microsoft",
            "xai",
        ]

        for prov_config in all_configs:
            # CRITICAL: Only register LOCAL providers from providers.json
            # Cloud providers are managed separately via CloudConfigManager
            if prov_config.provider_id in cloud_provider_ids:
                logger.debug(
                    f"Skipping {prov_config.provider_id} from providers.json "
                    f"(cloud providers managed by CloudConfigManager)"
                )
                continue

            if not prov_config.enabled:
                logger.info(f"Provider {prov_config.provider_id} is disabled, skipping")
                continue

            provider_class = provider_classes.get(prov_config.provider_id)
            if not provider_class:
                logger.warning(f"Unknown provider type: {prov_config.provider_id}")
                continue

            # Create an instance for each configured instance
            for instance_config in prov_config.instances:
                if not instance_config.enabled:
                    logger.debug(f"Instance {prov_config.provider_id}:{instance_config.id} disabled")
                    continue

                try:
                    # Create local provider instance
                    provider = provider_class(
                        endpoint=instance_config.base_url,
                        instance_id=instance_config.id,
                    )

                    self.register(provider)
                    logger.info(
                        f"Registered local provider instance: {provider.id} @ {instance_config.base_url}"
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to register {prov_config.provider_id}:{instance_config.id}: {e}"
                    )

        # Register cloud providers separately (always default instances)
        # Cloud providers use CloudConfigManager for API keys, not providers.json
        logger.info("Registering cloud providers (managed by CloudConfigManager)")
        try:
            self.register(
                provider_classes["openai"](
                    config_manager=cloud_config,
                    endpoint="https://api.openai.com/v1",
                    instance_id="default",
                )
            )
            logger.info("Registered cloud provider: openai")
        except Exception as e:
            logger.error(f"Failed to register openai: {e}")

        try:
            self.register(
                provider_classes["anthropic"](
                    config_manager=cloud_config,
                    endpoint="https://api.anthropic.com/v1",
                    instance_id="default",
                )
            )
            logger.info("Registered cloud provider: anthropic")
        except Exception as e:
            logger.error(f"Failed to register anthropic: {e}")

        # OpenAI-compatible vendor stubs (base_url typically configured by user)
        vendor_defaults = {
            "google": "",
            "meta": "",
            "deepseek": "https://api.deepseek.com/v1",
            "amazon": "",
            "alibaba_cloud": "",
            "zai": "",
            "moonshot": "https://api.moonshot.cn/v1",
            "microsoft": "",
            "xai": "https://api.x.ai/v1",
        }

        for vendor_id, default_endpoint in vendor_defaults.items():
            try:
                self.register(
                    provider_classes[vendor_id](
                        provider_id=vendor_id,
                        config_manager=cloud_config,
                        endpoint=default_endpoint,
                        instance_id="default",
                    )
                )
                logger.info(f"Registered cloud provider: {vendor_id}")
            except Exception as e:
                logger.error(f"Failed to register {vendor_id}: {e}")
