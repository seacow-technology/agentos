"""
Centralized Configuration Management for AgentOS

Provides pydantic-based configuration with:
- Environment variable loading (.env support)
- Type validation
- Default values
- Sensitive settings validation

Usage:
    from agentos.core.config import get_config

    config = get_config()
    print(config.database_url)
    print(config.secret_key)
"""

import os
import secrets
from pathlib import Path
from typing import Optional
from pydantic import BaseSettings, Field, validator

from agentos.core.storage.paths import component_db_path


class AgentOSConfig(BaseSettings):
    """
    Central configuration for AgentOS

    All settings can be overridden via environment variables with AGENTOS_ prefix.
    For example: AGENTOS_DATABASE_URL, AGENTOS_SECRET_KEY, etc.
    """

    # ============================================
    # Database Configuration
    # ============================================

    _database_url: Optional[str] = Field(
        default=None,
        alias="database_url",
        description="Database connection URL (override via AGENTOS_DATABASE_URL)"
    )

    @property
    def database_url(self) -> str:
        """Get database URL (uses unified path management if not overridden).

        Priority:
        1. Explicitly set database_url (via env or config)
        2. Unified path from storage.paths module

        Returns:
            SQLite database URL string
        """
        if self._database_url:
            return self._database_url

        # Use unified path management
        path = component_db_path("agentos")
        return f"sqlite:///{path.resolve().as_posix()}"

    database_pool_size: int = Field(
        default=10,
        description="Database connection pool size (PostgreSQL only)"
    )

    database_max_overflow: int = Field(
        default=20,
        description="Maximum overflow connections (PostgreSQL only)"
    )

    sqlite_busy_timeout: int = Field(
        default=5000,
        description="SQLite busy timeout in milliseconds"
    )

    # ============================================
    # Security Configuration
    # ============================================

    secret_key: str = Field(
        default_factory=lambda: secrets.token_urlsafe(32),
        description="Secret key for signing tokens and sessions (MUST be set in production)"
    )

    csrf_cookie_secure: bool = Field(
        default=False,
        description="Use secure cookies for CSRF protection (MUST be True in production)"
    )

    session_max_age: int = Field(
        default=86400,
        description="Session maximum age in seconds (default: 24 hours)"
    )

    session_secure_only: bool = Field(
        default=False,
        description="Only send session cookie over HTTPS (MUST be True in production)"
    )

    # ============================================
    # Application Configuration
    # ============================================

    environment: str = Field(
        default="development",
        description="Environment: development, staging, production"
    )

    debug: bool = Field(
        default=False,
        description="Enable debug mode"
    )

    log_level: str = Field(
        default="INFO",
        description="Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL"
    )

    # ============================================
    # Upload Configuration
    # ============================================

    max_upload_size: int = Field(
        default=50 * 1024 * 1024,  # 50MB
        description="Maximum upload size in bytes"
    )

    allowed_extensions: str = Field(
        default=".zip,.yaml,.yml,.json,.md",
        description="Comma-separated list of allowed file extensions"
    )

    # ============================================
    # Maintenance Configuration
    # ============================================

    temp_cleanup_interval_hours: int = Field(
        default=6,
        description="Interval between temp file cleanup runs"
    )

    temp_cleanup_max_age_hours: int = Field(
        default=24,
        description="Maximum age of temp files before cleanup"
    )

    # ============================================
    # Monitoring Configuration
    # ============================================

    metrics_enabled: bool = Field(
        default=True,
        description="Enable metrics collection"
    )

    health_check_enabled: bool = Field(
        default=True,
        description="Enable health check endpoints"
    )

    sentry_enabled: bool = Field(
        default=False,
        description="Enable Sentry error tracking"
    )

    sentry_dsn: Optional[str] = Field(
        default=None,
        description="Sentry DSN for error tracking"
    )

    # ============================================
    # Voice Configuration (v0.2)
    # ============================================

    voice_runtime: str = Field(
        default="embedded",
        description="Voice runtime mode: 'embedded' (in-process) or 'sidecar' (separate Python 3.13 process)"
    )

    voice_sidecar_python: str = Field(
        default="python3.13",
        description="Path to Python 3.13 executable for sidecar mode"
    )

    voice_sidecar_port: int = Field(
        default=50051,
        description="gRPC port for voice sidecar communication"
    )

    voice_sidecar_fallback_to_embedded: bool = Field(
        default=True,
        description="Automatically fall back to embedded mode if sidecar fails to start"
    )

    voice_sidecar_auto_start: bool = Field(
        default=True,
        description="Automatically start sidecar process if using sidecar mode"
    )

    # ============================================
    # Validators
    # ============================================

    @validator("secret_key")
    def validate_secret_key(cls, v, values):
        """Ensure secret key is strong in production"""
        env = values.get("environment", "development")
        if env == "production":
            if len(v) < 32:
                raise ValueError(
                    "secret_key must be at least 32 characters in production. "
                    "Generate one with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
                )
            if v.startswith("dev-") or v == "change-me":
                raise ValueError(
                    "secret_key must be changed from default value in production"
                )
        return v

    @validator("csrf_cookie_secure")
    def validate_csrf_secure(cls, v, values):
        """Ensure CSRF cookies are secure in production"""
        env = values.get("environment", "development")
        if env == "production" and not v:
            raise ValueError(
                "csrf_cookie_secure must be True in production environment"
            )
        return v

    @validator("session_secure_only")
    def validate_session_secure(cls, v, values):
        """Ensure session cookies are secure in production"""
        env = values.get("environment", "development")
        if env == "production" and not v:
            raise ValueError(
                "session_secure_only must be True in production environment"
            )
        return v

    @validator("log_level")
    def validate_log_level(cls, v):
        """Validate log level"""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(
                f"log_level must be one of: {', '.join(valid_levels)}"
            )
        return v.upper()

    class Config:
        env_file = ".env"
        env_prefix = "AGENTOS_"
        case_sensitive = False


# Global config instance
_config: Optional[AgentOSConfig] = None


def get_config(force_reload: bool = False) -> AgentOSConfig:
    """
    Get the global configuration instance

    Args:
        force_reload: Force reload configuration from environment

    Returns:
        AgentOSConfig instance

    Example:
        >>> config = get_config()
        >>> print(config.database_url)
        >>> print(config.secret_key)
    """
    global _config

    if _config is None or force_reload:
        _config = AgentOSConfig()

    return _config


def validate_config() -> tuple[bool, list[str]]:
    """
    Validate current configuration

    Returns:
        Tuple of (is_valid, list_of_errors)

    Example:
        >>> is_valid, errors = validate_config()
        >>> if not is_valid:
        >>>     for error in errors:
        >>>         print(f"Config error: {error}")
    """
    errors = []

    try:
        config = get_config()

        # Check production settings
        if config.environment == "production":
            if len(config.secret_key) < 32:
                errors.append("secret_key too short for production (min 32 chars)")

            if not config.csrf_cookie_secure:
                errors.append("csrf_cookie_secure must be True in production")

            if not config.session_secure_only:
                errors.append("session_secure_only must be True in production")

            if config.debug:
                errors.append("debug mode should be disabled in production")

        # Check file paths
        db_path = Path(config.database_url.replace("sqlite:///", ""))
        if db_path.parent and not db_path.parent.exists():
            errors.append(f"Database directory does not exist: {db_path.parent}")

        return len(errors) == 0, errors

    except Exception as e:
        errors.append(f"Configuration validation failed: {str(e)}")
        return False, errors
