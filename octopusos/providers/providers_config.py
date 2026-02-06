"""
Provider Instances Configuration Manager

Manages configurable endpoints and instances for all providers:
- ~/.agentos/config/providers.json
- Support for multiple instances per provider
- Launch configurations for local providers
- Fingerprint-based provider detection
- Cross-platform executable path and models directory management

Sprint B+ Provider Architecture Refactor
Phase 2: Configuration Management Enhancement
"""

import json
import logging
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Any

from . import platform_utils

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
    """
    Provider configuration with multiple instances.

    Task #16: P0.3 - Added manual_lifecycle and supported_actions
    """
    provider_id: str
    enabled: bool = True
    instances: List[ProviderInstance] = field(default_factory=list)
    manual_lifecycle: bool = False  # If True, provider requires manual app management (e.g., LM Studio)
    supported_actions: List[str] = field(default_factory=lambda: ['start', 'stop', 'restart', 'detect'])


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
                "executable_path": None,  # Auto-detected or user-specified
                "auto_detect": True,  # Enable automatic executable detection
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
                "executable_path": None,
                "auto_detect": True,
                "manual_lifecycle": True,  # LM Studio requires manual app management
                "supported_actions": ["open_app", "detect"],  # No CLI start/stop/restart
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
                "executable_path": None,
                "auto_detect": True,
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
        },
        "global": {
            "models_directories": {
                # Provider-specific models directories
                # None means use default location from platform_utils.get_models_dir()
                "ollama": None,
                "llamacpp": None,
                "lmstudio": None,
                "global": None,  # Shared models directory for all providers
            }
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

            # Migrate old config format if needed
            if self._migrate_config():
                logger.info("Configuration migrated to new format")
                self._save()
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
        """
        Get configuration for a provider.

        Task #16: P0.3 - Now returns manual_lifecycle and supported_actions
        """
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

            # Get manual_lifecycle and supported_actions
            manual_lifecycle = provider_dict.get("manual_lifecycle", False)
            supported_actions = provider_dict.get("supported_actions", ['start', 'stop', 'restart', 'detect'])

            return ProviderConfig(
                provider_id=provider_id,
                enabled=provider_dict.get("enabled", True),
                instances=instances,
                manual_lifecycle=manual_lifecycle,
                supported_actions=supported_actions,
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

    def _migrate_config(self) -> bool:
        """
        Migrate old configuration format to new format.

        Adds missing fields for Phase 2 enhancements:
        - executable_path (default: None)
        - auto_detect (default: True)
        - global.models_directories section

        Returns:
            bool: True if migration was performed, False if no changes needed
        """
        migrated = False
        providers = self._config.setdefault("providers", {})

        # Migrate provider-level fields
        for provider_id in ["ollama", "lmstudio", "llamacpp"]:
            if provider_id in providers:
                provider_dict = providers[provider_id]

                # Add executable_path if missing
                if "executable_path" not in provider_dict:
                    provider_dict["executable_path"] = None
                    migrated = True
                    logger.debug(f"Added executable_path to {provider_id}")

                # Add auto_detect if missing
                if "auto_detect" not in provider_dict:
                    provider_dict["auto_detect"] = True
                    migrated = True
                    logger.debug(f"Added auto_detect to {provider_id}")

        # Migrate global section
        if "global" not in self._config:
            self._config["global"] = {
                "models_directories": {
                    "ollama": None,
                    "llamacpp": None,
                    "lmstudio": None,
                    "global": None,
                }
            }
            migrated = True
            logger.debug("Added global.models_directories section")
        elif "models_directories" not in self._config["global"]:
            self._config["global"]["models_directories"] = {
                "ollama": None,
                "llamacpp": None,
                "lmstudio": None,
                "global": None,
            }
            migrated = True
            logger.debug("Added models_directories to global section")

        return migrated

    def set_executable_path(self, provider_id: str, path: Optional[str]) -> None:
        """
        Set the executable path for a provider.

        Args:
            provider_id: Provider identifier ('ollama', 'llamacpp', 'lmstudio')
            path: Absolute path to the executable, or None to use auto-detection

        Raises:
            ValueError: If the path is invalid or not executable

        Note:
            - If path is None, auto_detect will be set to True
            - If path is provided, it will be validated using platform_utils.validate_executable()
            - Setting a path disables auto_detect (sets it to False)

        Examples:
            >>> manager.set_executable_path('ollama', '/usr/local/bin/ollama')
            >>> manager.set_executable_path('ollama', None)  # Use auto-detection
        """
        providers = self._config.setdefault("providers", {})
        provider_dict = providers.setdefault(provider_id, {"enabled": True, "instances": []})

        if path is None:
            # Enable auto-detection
            provider_dict["executable_path"] = None
            provider_dict["auto_detect"] = True
            logger.info(f"Enabled auto-detection for {provider_id}")
        else:
            # Validate the provided path
            path_obj = Path(path)
            if not platform_utils.validate_executable(path_obj):
                raise ValueError(
                    f"Invalid executable path for {provider_id}: {path}\n"
                    f"File must exist and be executable."
                )

            # Save the validated path
            provider_dict["executable_path"] = str(path_obj)
            provider_dict["auto_detect"] = False
            logger.info(f"Set executable path for {provider_id}: {path}")

        self._save()

    def get_executable_path(self, provider_id: str) -> Optional[Path]:
        """
        Get the executable path for a provider.

        Priority order:
        1. Configured executable_path (if set and valid)
        2. Auto-detected path (if auto_detect is True)
        3. None (if not found)

        Args:
            provider_id: Provider identifier ('ollama', 'llamacpp', 'lmstudio')

        Returns:
            Optional[Path]: Path to the executable, or None if not found

        Note:
            This method uses platform_utils.find_executable() for auto-detection.
            The result is NOT cached - each call performs a fresh search.

        Examples:
            >>> manager.get_executable_path('ollama')
            Path('/usr/local/bin/ollama')

            >>> manager.get_executable_path('nonexistent')
            None
        """
        providers = self._config.get("providers", {})
        provider_dict = providers.get(provider_id)

        if not provider_dict:
            logger.debug(f"Provider {provider_id} not found in config")
            return None

        # Priority 1: Check configured path
        configured_path = provider_dict.get("executable_path")
        if configured_path:
            path_obj = Path(configured_path)
            if platform_utils.validate_executable(path_obj):
                return path_obj
            else:
                logger.warning(
                    f"Configured executable path for {provider_id} is invalid: {configured_path}"
                )

        # Priority 2: Auto-detect if enabled
        auto_detect = provider_dict.get("auto_detect", True)
        if auto_detect:
            # Map provider_id to executable name
            executable_name_map = {
                "ollama": "ollama",
                "llamacpp": "llama-server",
                "lmstudio": "lmstudio",
            }
            executable_name = executable_name_map.get(provider_id)

            if executable_name:
                detected_path = platform_utils.find_executable(executable_name)
                if detected_path:
                    logger.debug(f"Auto-detected {provider_id} at: {detected_path}")
                    return detected_path
                else:
                    logger.debug(f"Failed to auto-detect {provider_id}")

        # Not found
        return None

    def set_models_directory(self, provider_id: str, path: str) -> None:
        """
        Set the models directory for a specific provider.

        Args:
            provider_id: Provider identifier ('ollama', 'llamacpp', 'lmstudio', 'global')
            path: Absolute path to the models directory

        Raises:
            ValueError: If the path does not exist or is not a directory

        Note:
            - Use 'global' as provider_id to set the shared models directory
            - The directory must exist before setting it
            - Setting to None reverts to the default location

        Examples:
            >>> manager.set_models_directory('ollama', '/custom/ollama/models')
            >>> manager.set_models_directory('global', '/shared/models')
        """
        path_obj = Path(path)

        # Validate that the path exists and is a directory
        if not path_obj.exists():
            raise ValueError(f"Models directory does not exist: {path}")
        if not path_obj.is_dir():
            raise ValueError(f"Path is not a directory: {path}")

        # Ensure global section exists
        global_config = self._config.setdefault("global", {})
        models_dirs = global_config.setdefault("models_directories", {})

        # Save the path
        models_dirs[provider_id] = str(path_obj)
        self._save()
        logger.info(f"Set models directory for {provider_id}: {path}")

    def get_models_directory(self, provider_id: str) -> Optional[Path]:
        """
        Get the models directory for a specific provider.

        Priority order:
        1. Provider-specific configured directory
        2. Global configured directory
        3. Default location from platform_utils.get_models_dir()

        Args:
            provider_id: Provider identifier ('ollama', 'llamacpp', 'lmstudio')

        Returns:
            Optional[Path]: Path to the models directory, or None if cannot be determined

        Note:
            - Returns the first valid directory found in priority order
            - Does NOT validate that the directory exists
            - For llamacpp, suggests a default location if not configured

        Examples:
            >>> manager.get_models_directory('ollama')
            Path('/Users/username/.ollama/models')

            >>> manager.get_models_directory('llamacpp')
            Path('/Users/username/Documents/AI Models')
        """
        global_config = self._config.get("global", {})
        models_dirs = global_config.get("models_directories", {})

        # Priority 1: Provider-specific directory
        provider_dir = models_dirs.get(provider_id)
        if provider_dir:
            return Path(provider_dir)

        # Priority 2: Global directory
        global_dir = models_dirs.get("global")
        if global_dir:
            return Path(global_dir)

        # Priority 3: Default location from platform_utils
        try:
            default_dir = platform_utils.get_models_dir(provider_id)
            return default_dir
        except Exception as e:
            logger.warning(f"Failed to get default models directory for {provider_id}: {e}")
            return None
