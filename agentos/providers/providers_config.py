"""
Provider Instances Configuration Manager

Manages configurable endpoints and instances for all providers:
- ~/.agentos/config/providers.json
- Support for multiple instances per provider
- Launch configurations for local providers
- Fingerprint-based provider detection

Sprint B+ Provider Architecture Refactor
"""

import json
import logging
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


@dataclass
class LaunchConfig:
    """Launch configuration for local providers (especially llamacpp)"""
    bin: str  # Binary name or path
    args: Dict[str, Any] = field(default_factory=dict)  # Command line arguments


@dataclass
class ProviderInstance:
    """Single provider instance configuration"""
    id: str  # Instance identifier (e.g., "default", "glm47flash-q8")
    base_url: str  # Endpoint URL
    enabled: bool = True
    launch: Optional[LaunchConfig] = None  # For locally-managed services
    metadata: Dict[str, Any] = field(default_factory=dict)  # Extra fields


@dataclass
class ProviderConfig:
    """Provider configuration with multiple instances"""
    provider_id: str
    enabled: bool = True
    instances: List[ProviderInstance] = field(default_factory=list)


class ProvidersConfigManager:
    """
    Manages provider instances configuration

    Features:
    - File-based storage (~/.agentos/config/providers.json)
    - Multiple instances per provider
    - Launch config for local providers
    - Default configurations if file doesn't exist
    """

    DEFAULT_CONFIG = {
        "providers": {
            "ollama": {
                "enabled": True,
                "instances": [
                    {
                        "id": "default",
                        "base_url": "http://127.0.0.1:11434",
                        "enabled": True,
                        "metadata": {
                            "note": "Default port may conflict with llama-server. Check fingerprint on first probe."
                        }
                    }
                ],
            },
            "lmstudio": {
                "enabled": True,
                "instances": [
                    {
                        "id": "default",
                        "base_url": "http://127.0.0.1:1234",
                        "enabled": True,
                    }
                ],
            },
            "llamacpp": {
                "enabled": True,
                "instances": [
                    {
                        "id": "default",
                        "base_url": "http://127.0.0.1:8080",
                        "enabled": True,
                    }
                ],
            },
            # Note: Cloud providers (openai, anthropic) are NOT managed here
            # They are registered separately and use CloudConfigManager for API keys
        }
    }

    def __init__(self, config_file: Optional[Path] = None):
        if config_file is None:
            # Default to ~/.agentos/config/providers.json
            home = Path.home()
            config_dir = home / ".agentos" / "config"
            config_dir.mkdir(parents=True, exist_ok=True)
            config_file = config_dir / "providers.json"

        self.config_file = config_file
        self._config: Dict[str, Any] = {}
        self._load()

    def _load(self):
        """Load configuration from disk"""
        if not self.config_file.exists():
            logger.info(f"No config file found at {self.config_file}, using defaults")
            self._config = self.DEFAULT_CONFIG.copy()
            self._save()  # Create default config file
            return

        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                self._config = json.load(f)
            logger.info(f"Loaded providers config: {len(self._config.get('providers', {}))} providers")
        except Exception as e:
            logger.error(f"Failed to load providers config: {e}, using defaults")
            self._config = self.DEFAULT_CONFIG.copy()

    def _save(self):
        """Save configuration to disk (atomic write)"""
        try:
            # Write to temp file
            temp_file = self.config_file.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=2)

            # Atomic rename
            temp_file.replace(self.config_file)

            logger.debug(f"Saved providers config: {len(self._config.get('providers', {}))} providers")
        except Exception as e:
            logger.error(f"Failed to save providers config: {e}")
            raise

    def get_provider_config(self, provider_id: str) -> Optional[ProviderConfig]:
        """Get configuration for a provider"""
        providers = self._config.get("providers", {})
        provider_dict = providers.get(provider_id)

        if not provider_dict:
            return None

        try:
            instances = []
            for inst_dict in provider_dict.get("instances", []):
                launch = None
                if "launch" in inst_dict:
                    launch_dict = inst_dict["launch"]
                    launch = LaunchConfig(
                        bin=launch_dict["bin"],
                        args=launch_dict.get("args", {}),
                    )

                instance = ProviderInstance(
                    id=inst_dict["id"],
                    base_url=inst_dict["base_url"],
                    enabled=inst_dict.get("enabled", True),
                    launch=launch,
                    metadata=inst_dict.get("metadata", {}),
                )
                instances.append(instance)

            return ProviderConfig(
                provider_id=provider_id,
                enabled=provider_dict.get("enabled", True),
                instances=instances,
            )
        except Exception as e:
            logger.error(f"Failed to parse config for {provider_id}: {e}")
            return None

    def get_all_provider_configs(self) -> List[ProviderConfig]:
        """Get configurations for all providers"""
        providers = self._config.get("providers", {})
        configs = []

        for provider_id in providers:
            config = self.get_provider_config(provider_id)
            if config:
                configs.append(config)

        return configs

    def update_instance(
        self,
        provider_id: str,
        instance_id: str,
        base_url: Optional[str] = None,
        enabled: Optional[bool] = None,
        launch: Optional[LaunchConfig] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Update a specific provider instance"""
        providers = self._config.setdefault("providers", {})
        provider_dict = providers.setdefault(provider_id, {"enabled": True, "instances": []})

        # Find or create instance
        instances = provider_dict.setdefault("instances", [])
        instance_dict = None
        for inst in instances:
            if inst["id"] == instance_id:
                instance_dict = inst
                break

        if instance_dict is None:
            # Create new instance
            instance_dict = {"id": instance_id, "base_url": "", "enabled": True}
            instances.append(instance_dict)

        # Update fields
        if base_url is not None:
            instance_dict["base_url"] = base_url
        if enabled is not None:
            instance_dict["enabled"] = enabled
        if launch is not None:
            instance_dict["launch"] = {
                "bin": launch.bin,
                "args": launch.args,
            }
        if metadata is not None:
            instance_dict["metadata"] = metadata

        self._save()
        logger.info(f"Updated instance {provider_id}/{instance_id}")

    def add_instance(
        self,
        provider_id: str,
        instance_id: str,
        base_url: str,
        enabled: bool = True,
        launch: Optional[LaunchConfig] = None,
    ):
        """Add a new provider instance"""
        self.update_instance(
            provider_id=provider_id,
            instance_id=instance_id,
            base_url=base_url,
            enabled=enabled,
            launch=launch,
        )

    def remove_instance(self, provider_id: str, instance_id: str) -> bool:
        """Remove a provider instance"""
        providers = self._config.get("providers", {})
        provider_dict = providers.get(provider_id)

        if not provider_dict:
            return False

        instances = provider_dict.get("instances", [])
        original_len = len(instances)
        provider_dict["instances"] = [inst for inst in instances if inst["id"] != instance_id]

        if len(provider_dict["instances"]) < original_len:
            self._save()
            logger.info(f"Removed instance {provider_id}/{instance_id}")
            return True

        return False

    def set_provider_enabled(self, provider_id: str, enabled: bool):
        """Enable or disable a provider"""
        providers = self._config.setdefault("providers", {})
        provider_dict = providers.setdefault(provider_id, {"enabled": True, "instances": []})
        provider_dict["enabled"] = enabled
        self._save()
        logger.info(f"Set {provider_id} enabled={enabled}")
