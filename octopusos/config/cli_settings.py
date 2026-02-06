"""CLI Settings: Global configuration for CLI interactive mode"""

import json
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, Optional
import os

from agentos.core.task.run_mode import RunMode, ModelPolicy


@dataclass
class CLISettings:
    """CLI Settings: Global configuration"""
    
    default_run_mode: str = "assisted"
    default_model_policy: Dict[str, str] = field(default_factory=lambda: {
        "default": "gpt-4.1",
        "intent": "gpt-4.1-mini",
        "planning": "gpt-4.1",
        "implementation": "gpt-4.1"
    })
    executor_limits: Dict[str, int] = field(default_factory=lambda: {
        "max_parallel_tasks": 5,
        "max_retries": 3,
        "timeout_seconds": 3600
    })
    language: str = "en"  # Language code: "en" or "zh_CN"

    # WebUI 设置
    webui_auto_start: bool = True  # 是否自动启动 WebUI
    webui_host: str = "127.0.0.1"  # WebUI 绑定主机
    webui_port: int = 8080  # WebUI 端口

    # 新增：Mode-Model 绑定
    mode_model_bindings: Dict[str, str] = field(default_factory=dict)
    
    # 新增：模型调用方式配置
    model_invocation_configs: Dict[str, Dict[str, str]] = field(default_factory=dict)
    
    # 新增：模型授权信息（注意：实际应使用加密存储）
    model_credentials: Dict[str, Dict[str, str]] = field(default_factory=dict)
    
    def get_run_mode(self) -> RunMode:
        """Get run mode as enum"""
        return RunMode(self.default_run_mode)
    
    def get_model_policy(self) -> ModelPolicy:
        """Get model policy"""
        return ModelPolicy.from_dict(self.default_model_policy)
    
    def get_language(self) -> str:
        """Get language code"""
        return self.language
    
    def set_language(self, lang: str) -> None:
        """Set language code"""
        self.language = lang
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "CLISettings":
        """Create from dictionary"""
        return cls(
            default_run_mode=data.get("default_run_mode", "assisted"),
            default_model_policy=data.get("default_model_policy", cls().default_model_policy),
            executor_limits=data.get("executor_limits", cls().executor_limits),
            language=data.get("language", "en"),
            webui_auto_start=data.get("webui_auto_start", True),
            webui_host=data.get("webui_host", "127.0.0.1"),
            webui_port=data.get("webui_port", 8080),
            mode_model_bindings=data.get("mode_model_bindings", {}),
            model_invocation_configs=data.get("model_invocation_configs", {}),
            model_credentials=data.get("model_credentials", {}),
        )


class SettingsManager:
    """Manage CLI settings persistence"""
    
    def __init__(self, settings_path: Optional[Path] = None):
        """Initialize settings manager"""
        if settings_path:
            self.settings_path = settings_path
        else:
            # Default: ~/.agentos/settings.json
            home = Path.home()
            agentos_dir = home / ".agentos"
            agentos_dir.mkdir(exist_ok=True)
            self.settings_path = agentos_dir / "settings.json"
    
    def load(self) -> CLISettings:
        """Load settings from file"""
        if not self.settings_path.exists():
            return CLISettings()  # Return defaults
        
        try:
            with open(self.settings_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return CLISettings.from_dict(data)
        except Exception as e:
            print(f"Warning: Failed to load settings: {e}")
            return CLISettings()
    
    def save(self, settings: CLISettings) -> None:
        """Save settings to file"""
        try:
            self.settings_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.settings_path, "w", encoding="utf-8") as f:
                json.dump(settings.to_dict(), f, indent=2)
        except Exception as e:
            print(f"Error: Failed to save settings: {e}")
    
    def update_run_mode(self, run_mode: str) -> None:
        """Update default run mode"""
        settings = self.load()
        settings.default_run_mode = run_mode
        self.save(settings)
    
    def update_model_policy(self, policy: Dict[str, str]) -> None:
        """Update default model policy"""
        settings = self.load()
        settings.default_model_policy.update(policy)
        self.save(settings)
    
    def update_mode_binding(self, mode_id: str, model_key: str) -> None:
        """Update mode-model binding
        
        Args:
            mode_id: Mode ID (e.g., "planning", "debug")
            model_key: Model key format "model_id@brand" (e.g., "gpt-4@OpenAI")
        """
        settings = self.load()
        settings.mode_model_bindings[mode_id] = model_key
        self.save(settings)
    
    def remove_mode_binding(self, mode_id: str) -> None:
        """Remove mode-model binding"""
        settings = self.load()
        if mode_id in settings.mode_model_bindings:
            del settings.mode_model_bindings[mode_id]
            self.save(settings)
    
    def update_invocation_config(self, model_key: str, config: Dict[str, str]) -> None:
        """Update model invocation configuration
        
        Args:
            model_key: Model key format "model_id@brand"
            config: Configuration dict with keys like "method", "cli_command", "api_endpoint"
        """
        settings = self.load()
        settings.model_invocation_configs[model_key] = config
        self.save(settings)
    
    def update_credentials(self, model_key: str, credentials: Dict[str, str]) -> None:
        """Update model credentials

        Args:
            model_key: Model key format "model_id@brand"
            credentials: Credentials dict (e.g., {"api_key": "sk-..."})

        Warning:
            This stores credentials in plain text. In production, use encryption!
        """
        settings = self.load()
        settings.model_credentials[model_key] = credentials
        self.save(settings)

    def update_webui_settings(self, auto_start: Optional[bool] = None,
                             host: Optional[str] = None,
                             port: Optional[int] = None) -> None:
        """Update WebUI settings

        Args:
            auto_start: Whether to auto-start WebUI
            host: WebUI host
            port: WebUI port
        """
        settings = self.load()
        if auto_start is not None:
            settings.webui_auto_start = auto_start
        if host is not None:
            settings.webui_host = host
        if port is not None:
            settings.webui_port = port
        self.save(settings)


# Global instance
_settings_manager: Optional[SettingsManager] = None


def get_settings_manager() -> SettingsManager:
    """Get global settings manager"""
    global _settings_manager
    if _settings_manager is None:
        _settings_manager = SettingsManager()
    return _settings_manager


def load_settings() -> CLISettings:
    """Load settings (convenience function)"""
    return get_settings_manager().load()


def save_settings(settings: CLISettings) -> None:
    """Save settings (convenience function)"""
    get_settings_manager().save(settings)
