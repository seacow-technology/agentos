"""
Instance Profile Builder - Build instance profiles from provider registry

Aggregates provider status, configuration, and metadata into InstanceProfile objects
for routing decisions.

PR-1: Router Core
"""

import logging
from typing import List, Optional, Dict, Any
from agentos.router.models import InstanceProfile
from agentos.providers.registry import ProviderRegistry
from agentos.providers.base import ProviderState

logger = logging.getLogger(__name__)


class InstanceProfileBuilder:
    """
    Build instance profiles from provider registry

    Combines:
    - Provider runtime status (from probe)
    - Provider configuration (from providers.json)
    - Capability tags and metadata
    """

    def __init__(self, registry: Optional[ProviderRegistry] = None):
        """
        Initialize builder

        Args:
            registry: ProviderRegistry instance (uses singleton if None)
        """
        self.registry = registry or ProviderRegistry.get_instance()

    async def build_all_profiles(self) -> List[InstanceProfile]:
        """
        Build profiles for all registered provider instances

        Returns:
            List of InstanceProfile objects
        """
        profiles = []

        # Get all provider status
        status_list = await self.registry.get_all_status()

        # Get providers config manager
        config_manager = self.registry.get_providers_config_manager()

        for status in status_list:
            try:
                profile = await self._build_profile_from_status(status, config_manager)
                if profile:
                    profiles.append(profile)
            except Exception as e:
                logger.error(f"Failed to build profile for {status.id}: {e}", exc_info=True)

        logger.info(f"Built {len(profiles)} instance profiles")
        return profiles

    async def _build_profile_from_status(
        self,
        status: "ProviderStatus",
        config_manager: Any,
    ) -> Optional[InstanceProfile]:
        """
        Build InstanceProfile from ProviderStatus and configuration

        Args:
            status: ProviderStatus object
            config_manager: ProvidersConfigManager

        Returns:
            InstanceProfile or None
        """
        # Extract provider_type and instance_id from status.id
        # Format: "provider_type:instance_id" or "provider_type"
        parts = status.id.split(":", 1)
        provider_type = parts[0]
        instance_id = parts[1] if len(parts) > 1 else "default"

        # Get configuration for this provider
        provider_config = config_manager.get_provider_config(provider_type)

        # Find instance configuration
        tags: List[str] = []
        ctx: Optional[int] = None
        model: Optional[str] = None
        metadata: Dict[str, Any] = {}

        if provider_config:
            for inst in provider_config.instances:
                if inst.id == instance_id:
                    # Extract tags from metadata
                    if inst.metadata:
                        tags = inst.metadata.get("tags", [])
                        ctx = inst.metadata.get("ctx")
                        model = inst.metadata.get("model")
                        metadata = inst.metadata.copy()
                    break

        # Determine cost category
        cost_category = "cloud" if provider_type in ["openai", "anthropic"] else "local"

        # Create profile
        profile = InstanceProfile(
            instance_id=status.id,
            provider_type=provider_type,
            base_url=status.endpoint or "",
            state=status.state.value,
            latency_ms=status.latency_ms,
            fingerprint=None,  # TODO: Extract from status metadata if available
            tags=tags,
            ctx=ctx,
            cost_category=cost_category,
            model=model,
            metadata=metadata,
        )

        return profile

    async def get_profile(self, instance_id: str) -> Optional[InstanceProfile]:
        """
        Get profile for a specific instance

        Args:
            instance_id: Instance ID (e.g., "llamacpp:qwen3-coder-30b")

        Returns:
            InstanceProfile or None
        """
        # Get provider by ID
        provider = self.registry.get(instance_id)
        if not provider:
            logger.warning(f"Provider not found: {instance_id}")
            return None

        # Probe provider
        status = await provider.probe()

        # Get config manager
        config_manager = self.registry.get_providers_config_manager()

        # Build profile
        profile = await self._build_profile_from_status(status, config_manager)
        return profile
