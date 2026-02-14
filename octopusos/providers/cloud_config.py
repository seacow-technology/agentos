"""
Cloud Provider Configuration Manager

Manages secure storage of cloud provider credentials:
- ~/.octopusos/secrets/providers.json
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
from typing import Dict, Optional, Any, List, Tuple

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
            # Default to ~/.octopusos/secrets/providers.json
            home = Path.home()
            secrets_dir = home / ".octopusos" / "secrets"
            secrets_dir.mkdir(parents=True, exist_ok=True)
            secrets_file = secrets_dir / "providers.json"

        self.secrets_file = secrets_file
        self._ensure_secure_permissions()
        # On-disk format (v2):
        # {
        #   "<provider_id>": {
        #     "active": "<config_id>",
        #     "configs": {
        #       "<config_id>": {
        #         "label": "...",
        #         "auth": {"type":"api_key","api_key":"..."},
        #         "base_url": "...",
        #         "last_verified_at": "...",
        #         "last_test": {"ok":true,"at":"...","latency_ms":123,"error":null},
        #         "last_usage": {"status":"unknown","at":null,"error":null}
        #       }
        #     }
        #   }
        # }
        #
        # Legacy format (v1) is also supported:
        # { "<provider_id>": { "auth": {...}, "base_url": "...", "last_verified_at": "..." } }
        self._config: Dict[str, Any] = {}
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
            migrated = self._migrate_legacy_format_in_memory()
            if migrated:
                # Persist migration so UI and runtime are consistent across restarts.
                self._save()
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
        Get ACTIVE configuration for a provider.

        Returns None if not configured.
        """
        cfg, _cid = self._get_active_config_dict(provider_id)
        if not cfg:
            return None

        try:
            auth_dict = cfg.get("auth", {}) if isinstance(cfg, dict) else {}
            auth = CloudAuthConfig(
                type=auth_dict.get("type", "api_key"),
                api_key=auth_dict.get("api_key", ""),
            )

            return CloudProviderConfig(
                provider_id=provider_id,
                auth=auth,
                base_url=cfg.get("base_url") if isinstance(cfg, dict) else None,
                last_verified_at=cfg.get("last_verified_at") if isinstance(cfg, dict) else None,
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
        *,
        config_id: str = "default",
        label: Optional[str] = None,
        make_active: bool = True,
    ):
        """
        Set configuration for a provider

        Upsert a specific config record for a provider (default: "default").
        """
        entry = self._ensure_provider_entry(provider_id)
        configs = entry.setdefault("configs", {})
        rec = configs.setdefault(config_id, {})
        rec["auth"] = {"type": auth.type, "api_key": auth.api_key}
        if label is not None:
            rec["label"] = label
        elif "label" not in rec and config_id == "default":
            rec["label"] = "Default"

        if base_url:
            rec["base_url"] = base_url
        elif "base_url" in rec and base_url is None:
            # allow clearing base_url when caller explicitly passes None? keep as-is by default
            pass

        if last_verified_at:
            rec["last_verified_at"] = last_verified_at

        if make_active:
            entry["active"] = config_id
        self._save()

        logger.info(f"Saved config for {provider_id} (key masked)")

    def delete(self, provider_id: str, config_id: Optional[str] = None) -> bool:
        """
        Delete configuration for a provider.

        If config_id is None, deletes all configs for that provider.
        If config_id is set, deletes only that config record.
        """
        if provider_id not in self._config:
            return False

        if config_id is None:
            del self._config[provider_id]
            self._save()
            logger.info(f"Deleted all configs for {provider_id}")
            return True

        entry = self._config.get(provider_id)
        if not isinstance(entry, dict):
            return False
        configs = entry.get("configs")
        if not isinstance(configs, dict) or config_id not in configs:
            return False

        del configs[config_id]
        if entry.get("active") == config_id:
            entry["active"] = next(iter(configs.keys()), None)
        self._save()
        logger.info(f"Deleted config {provider_id}:{config_id}")
        return True

    def has_config(self, provider_id: str) -> bool:
        """Check if a provider has configuration"""
        cfg, _cid = self._get_active_config_dict(provider_id)
        return cfg is not None

    def update_verified_at(self, provider_id: str, timestamp: str):
        """Update last_verified_at timestamp"""
        entry = self._ensure_provider_entry(provider_id)
        cfg, cid = self._get_active_config_dict(provider_id)
        if cid and isinstance(cfg, dict):
            cfg["last_verified_at"] = timestamp
            entry.setdefault("configs", {})[cid] = cfg
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
        Get ACTIVE configuration with masked API key (safe for API responses).

        Returns None if not configured
        """
        cfg, cid = self._get_active_config_dict(provider_id)
        if not cfg or not cid:
            return None

        config = self.get(provider_id)
        if not config:
            return None

        return {
            "provider_id": provider_id,
            "config_id": cid,
            "label": (cfg.get("label") if isinstance(cfg, dict) else None),
            "auth": {
                "type": config.auth.type,
                "api_key": self.mask_api_key(config.auth.api_key),
            },
            "base_url": config.base_url,
            "last_verified_at": config.last_verified_at,
            "last_test": (cfg.get("last_test") if isinstance(cfg, dict) else None),
            "last_usage": (cfg.get("last_usage") if isinstance(cfg, dict) else None),
        }

    def list_masked_configs(self, provider_id: str) -> List[Dict[str, Any]]:
        entry = self._config.get(provider_id)
        if entry is None:
            return []
        entry = self._normalize_entry(provider_id, entry)
        active = entry.get("active")
        configs = entry.get("configs", {})
        out: List[Dict[str, Any]] = []
        if not isinstance(configs, dict):
            return out
        for cid, cfg in configs.items():
            if not isinstance(cfg, dict):
                continue
            auth = cfg.get("auth") or {}
            api_key = str((auth.get("api_key") or "")).strip()
            out.append(
                {
                    "provider_id": provider_id,
                    "config_id": cid,
                    "label": cfg.get("label") or cid,
                    "active": cid == active,
                    "auth": {"type": auth.get("type", "api_key"), "api_key": self.mask_api_key(api_key)},
                    "base_url": cfg.get("base_url"),
                    "last_verified_at": cfg.get("last_verified_at"),
                    "last_test": cfg.get("last_test"),
                    "last_usage": cfg.get("last_usage"),
                }
            )
        return out

    def set_active(self, provider_id: str, config_id: str) -> bool:
        entry = self._config.get(provider_id)
        if entry is None:
            return False
        entry = self._normalize_entry(provider_id, entry)
        configs = entry.get("configs", {})
        if not isinstance(configs, dict) or config_id not in configs:
            return False
        entry["active"] = config_id
        self._config[provider_id] = entry
        self._save()
        return True

    def record_test_result(
        self,
        provider_id: str,
        config_id: str,
        *,
        ok: bool,
        at: str,
        latency_ms: Optional[float] = None,
        error: Optional[str] = None,
    ) -> None:
        entry = self._ensure_provider_entry(provider_id)
        configs = entry.setdefault("configs", {})
        cfg = configs.get(config_id)
        if not isinstance(cfg, dict):
            return
        cfg["last_test"] = {"ok": bool(ok), "at": at, "latency_ms": latency_ms, "error": error}
        # Initialize last_usage if absent, so UI has stable shape
        cfg.setdefault("last_usage", {"status": "unknown", "at": None, "error": None})
        configs[config_id] = cfg
        self._save()

    # -------------------------
    # Internal helpers
    # -------------------------

    def _migrate_legacy_format_in_memory(self) -> bool:
        migrated = False
        if not isinstance(self._config, dict):
            self._config = {}
            return False
        for provider_id, entry in list(self._config.items()):
            if isinstance(entry, dict) and "auth" in entry and "configs" not in entry:
                self._config[provider_id] = {
                    "active": "default",
                    "configs": {
                        "default": {
                            "label": "Default",
                            "auth": entry.get("auth"),
                            "base_url": entry.get("base_url"),
                            "last_verified_at": entry.get("last_verified_at"),
                        }
                    },
                }
                migrated = True
        return migrated

    def _normalize_entry(self, provider_id: str, entry: Any) -> Dict[str, Any]:
        if not isinstance(entry, dict):
            return {"active": None, "configs": {}}
        if "configs" not in entry and "auth" in entry:
            # legacy
            return {
                "active": "default",
                "configs": {
                    "default": {
                        "label": "Default",
                        "auth": entry.get("auth"),
                        "base_url": entry.get("base_url"),
                        "last_verified_at": entry.get("last_verified_at"),
                    }
                },
            }
        if "configs" not in entry:
            entry["configs"] = {}
        if "active" not in entry:
            entry["active"] = next(iter(entry.get("configs", {}).keys()), None)
        return entry

    def _ensure_provider_entry(self, provider_id: str) -> Dict[str, Any]:
        entry = self._config.get(provider_id)
        entry = self._normalize_entry(provider_id, entry)
        self._config[provider_id] = entry
        return entry

    def _get_active_config_dict(self, provider_id: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        entry = self._config.get(provider_id)
        if entry is None:
            return None, None
        entry = self._normalize_entry(provider_id, entry)
        active = entry.get("active")
        configs = entry.get("configs", {})
        if not isinstance(configs, dict):
            return None, None
        if active and active in configs and isinstance(configs[active], dict):
            return configs[active], str(active)
        # fallback
        for cid, cfg in configs.items():
            if isinstance(cfg, dict):
                entry["active"] = cid
                self._config[provider_id] = entry
                return cfg, str(cid)
        return None, None
