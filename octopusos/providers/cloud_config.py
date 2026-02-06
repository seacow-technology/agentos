"""
Cloud Provider Configuration Manager

Manages secure storage of cloud provider credentials:
- ~/.agentos/secrets/providers.json
- chmod 600 for security
- API Key masking for responses
- Session-scoped credentials loading

Sprint B Task #6 implementation
"""

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)


@dataclass
class CloudAuthConfig:
    """Cloud provider authentication configuration"""
    type: str  # "api_key"
    api_key: str


@dataclass
class CloudProviderConfig:
    """Complete cloud provider configuration"""
    provider_id: str
    auth: CloudAuthConfig
    base_url: Optional[str] = None
    last_verified_at: Optional[str] = None


class CloudConfigManager:
    """
    Secure configuration manager for cloud providers

    Features:
    - File-based storage with chmod 600
    - API key masking for external responses
    - No logging of sensitive data
    - Atomic write operations
    """

    def __init__(self, secrets_file: Optional[Path] = None):
        if secrets_file is None:
            # Default to ~/.agentos/secrets/providers.json
            home = Path.home()
            secrets_dir = home / ".agentos" / "secrets"
            secrets_dir.mkdir(parents=True, exist_ok=True)
            secrets_file = secrets_dir / "providers.json"

        self.secrets_file = secrets_file
        self._ensure_secure_permissions()
        self._config: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _ensure_secure_permissions(self):
        """Ensure secrets file has chmod 600 (Unix only)"""
        import platform
        if platform.system() == "Windows":
            return  # Windows 使用 ACL 权限模型

        if self.secrets_file.exists():
            try:
                os.chmod(self.secrets_file, 0o600)
                logger.debug(f"Set permissions 600 on {self.secrets_file}")
            except Exception as e:
                logger.warning(f"Failed to set permissions on secrets file: {e}")

    def _load(self):
        """Load configuration from disk (no logging of content)"""
        if not self.secrets_file.exists():
            self._config = {}
            return

        try:
            with open(self.secrets_file, "r", encoding="utf-8") as f:
                self._config = json.load(f)
            logger.debug(f"Loaded cloud config: {len(self._config)} providers")
        except Exception as e:
            logger.error(f"Failed to load cloud config: {e}")
            self._config = {}

    def _save(self):
        """
        Save configuration to disk (atomic write)

        Uses temp file + rename for atomicity
        """
        try:
            # Write to temp file
            temp_file = self.secrets_file.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=2)

            # Set permissions before rename (Unix only)
            import platform
            if platform.system() != "Windows":
                os.chmod(temp_file, 0o600)

            # Atomic rename
            temp_file.replace(self.secrets_file)

            logger.debug(f"Saved cloud config: {len(self._config)} providers")
        except Exception as e:
            logger.error(f"Failed to save cloud config: {e}")
            raise

    def get(self, provider_id: str) -> Optional[CloudProviderConfig]:
        """
        Get configuration for a provider

        Returns None if not configured
        """
        config_dict = self._config.get(provider_id)
        if not config_dict:
            return None

        try:
            auth_dict = config_dict.get("auth", {})
            auth = CloudAuthConfig(
                type=auth_dict.get("type", "api_key"),
                api_key=auth_dict.get("api_key", ""),
            )

            return CloudProviderConfig(
                provider_id=provider_id,
                auth=auth,
                base_url=config_dict.get("base_url"),
                last_verified_at=config_dict.get("last_verified_at"),
            )
        except Exception as e:
            logger.error(f"Failed to parse config for {provider_id}: {e}")
            return None

    def set(
        self,
        provider_id: str,
        auth: CloudAuthConfig,
        base_url: Optional[str] = None,
        last_verified_at: Optional[str] = None,
    ):
        """
        Set configuration for a provider

        Overwrites existing configuration
        """
        config = {
            "auth": {
                "type": auth.type,
                "api_key": auth.api_key,
            },
        }

        if base_url:
            config["base_url"] = base_url

        if last_verified_at:
            config["last_verified_at"] = last_verified_at

        self._config[provider_id] = config
        self._save()

        logger.info(f"Saved config for {provider_id} (key masked)")

    def delete(self, provider_id: str) -> bool:
        """
        Delete configuration for a provider

        Returns True if deleted, False if not found
        """
        if provider_id in self._config:
            del self._config[provider_id]
            self._save()
            logger.info(f"Deleted config for {provider_id}")
            return True
        return False

    def has_config(self, provider_id: str) -> bool:
        """Check if a provider has configuration"""
        return provider_id in self._config

    def update_verified_at(self, provider_id: str, timestamp: str):
        """Update last_verified_at timestamp"""
        if provider_id in self._config:
            self._config[provider_id]["last_verified_at"] = timestamp
            self._save()

    @staticmethod
    def mask_api_key(api_key: str) -> str:
        """
        Mask API key for external responses

        Examples:
        - sk-1234567890abcdef -> sk-****cdef
        - sk-ant-1234567890 -> sk-ant-****7890
        """
        if not api_key or len(api_key) < 8:
            return "****"

        # Show first part and last 4 chars
        if api_key.startswith("sk-ant-"):
            return f"sk-ant-****{api_key[-4:]}"
        elif api_key.startswith("sk-"):
            return f"sk-****{api_key[-4:]}"
        else:
            return f"****{api_key[-4:]}"

    def get_masked_config(self, provider_id: str) -> Optional[Dict[str, Any]]:
        """
        Get configuration with masked API key (safe for API responses)

        Returns None if not configured
        """
        config = self.get(provider_id)
        if not config:
            return None

        return {
            "provider_id": provider_id,
            "auth": {
                "type": config.auth.type,
                "api_key": self.mask_api_key(config.auth.api_key),
            },
            "base_url": config.base_url,
            "last_verified_at": config.last_verified_at,
        }
