"""Database configuration and engine management for AgentOS.

This module provides a unified database configuration system that supports
both SQLite (for development) and PostgreSQL (for production).

Design Goals:
1. Zero-config development experience with SQLite
2. Production-ready PostgreSQL support with connection pooling
3. Smooth migration path from SQLite to PostgreSQL
4. Environment-based configuration (12-factor app)

Usage:
    # Get database engine (automatically configured based on environment)
    from agentos.core.database import get_engine

    engine = get_engine()

    # Use with SQLAlchemy
    with engine.connect() as conn:
        result = conn.execute("SELECT 1")

Environment Variables:
    DATABASE_TYPE: Database type (sqlite | postgresql), default: sqlite
    DATABASE_HOST: PostgreSQL host, default: localhost
    DATABASE_PORT: PostgreSQL port, default: 5432
    DATABASE_NAME: Database name, default: agentos
    DATABASE_USER: PostgreSQL username, default: postgres
    DATABASE_PASSWORD: PostgreSQL password, default: empty
    SQLITE_PATH: SQLite database file path (DEPRECATED, use AGENTOS_DB_PATH)
    AGENTOS_DB_PATH: SQLite database file path (preferred)
"""

import logging
import os
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import quote_plus

from agentos.core.storage.paths import component_db_path

logger = logging.getLogger(__name__)


class DatabaseType(str, Enum):
    """Supported database types"""
    SQLITE = "sqlite"
    POSTGRESQL = "postgresql"


class DatabaseConfig:
    """Database configuration manager.

    Reads configuration from environment variables and provides
    database connection URLs and engine options for SQLAlchemy.
    """

    def __init__(self):
        """Initialize database configuration from environment variables."""
        # Read database type
        db_type_str = os.getenv("DATABASE_TYPE", "sqlite").lower()
        try:
            self.db_type = DatabaseType(db_type_str)
        except ValueError:
            logger.warning(
                f"Invalid DATABASE_TYPE '{db_type_str}', falling back to sqlite"
            )
            self.db_type = DatabaseType.SQLITE

        # PostgreSQL configuration
        self.db_host = os.getenv("DATABASE_HOST", "localhost")
        self.db_port = int(os.getenv("DATABASE_PORT", "5432"))
        self.db_name = os.getenv("DATABASE_NAME", "agentos")
        self.db_user = os.getenv("DATABASE_USER", "postgres")
        self.db_password = os.getenv("DATABASE_PASSWORD", "")

        # SQLite configuration
        # Priority:
        # 1. SQLITE_PATH (deprecated but supported for backward compatibility)
        # 2. AGENTOS_DB_PATH (preferred environment variable)
        # 3. Unified path from storage.paths module (default)
        env_path = os.getenv("SQLITE_PATH") or os.getenv("AGENTOS_DB_PATH")
        if env_path:
            self.sqlite_path = env_path
            logger.info(f"SQLite path from environment: {self.sqlite_path}")
        else:
            self.sqlite_path = str(component_db_path("agentos"))
            logger.info(f"SQLite path from storage.paths: {self.sqlite_path}")

        # Connection pool configuration (PostgreSQL only)
        self.pool_size = int(os.getenv("DATABASE_POOL_SIZE", "10"))
        self.max_overflow = int(os.getenv("DATABASE_MAX_OVERFLOW", "20"))
        self.pool_timeout = int(os.getenv("DATABASE_POOL_TIMEOUT", "30"))
        self.pool_recycle = int(os.getenv("DATABASE_POOL_RECYCLE", "3600"))

        # SQLite-specific configuration
        self.sqlite_busy_timeout = int(os.getenv("SQLITE_BUSY_TIMEOUT", "5000"))

        logger.info(f"Database configuration loaded: type={self.db_type.value}")

    def get_database_url(self) -> str:
        """Get SQLAlchemy database connection URL.

        Returns:
            Database URL string for SQLAlchemy

        Raises:
            ValueError: If database type is not supported
        """
        if self.db_type == DatabaseType.SQLITE:
            # SQLite URL: sqlite:///path/to/database.db
            sqlite_path = Path(self.sqlite_path).resolve()
            return f"sqlite:///{sqlite_path}"

        elif self.db_type == DatabaseType.POSTGRESQL:
            # PostgreSQL URL: postgresql://user:pass@host:port/dbname
            # URL-encode password to handle special characters
            password = quote_plus(self.db_password) if self.db_password else ""

            if password:
                return (
                    f"postgresql://{self.db_user}:{password}@"
                    f"{self.db_host}:{self.db_port}/{self.db_name}"
                )
            else:
                return (
                    f"postgresql://{self.db_user}@"
                    f"{self.db_host}:{self.db_port}/{self.db_name}"
                )

        else:
            raise ValueError(f"Unsupported database type: {self.db_type}")

    def get_engine_options(self) -> Dict[str, Any]:
        """Get SQLAlchemy engine configuration options.

        Returns:
            Dictionary of engine options for create_engine()
        """
        if self.db_type == DatabaseType.SQLITE:
            return {
                "echo": False,
                "connect_args": {
                    "check_same_thread": False,
                    "timeout": self.sqlite_busy_timeout / 1000.0,  # Convert ms to seconds
                },
                "pool_pre_ping": True,  # Verify connections before using
            }

        elif self.db_type == DatabaseType.POSTGRESQL:
            return {
                "echo": False,
                "pool_size": self.pool_size,           # Connection pool size
                "max_overflow": self.max_overflow,     # Max overflow connections
                "pool_timeout": self.pool_timeout,     # Connection timeout (seconds)
                "pool_recycle": self.pool_recycle,     # Recycle connections after N seconds
                "pool_pre_ping": True,                 # Verify connections before using
                "connect_args": {
                    "connect_timeout": 10,             # TCP connection timeout
                },
            }

        else:
            raise ValueError(f"Unsupported database type: {self.db_type}")

    def is_sqlite(self) -> bool:
        """Check if current database is SQLite."""
        return self.db_type == DatabaseType.SQLITE

    def is_postgresql(self) -> bool:
        """Check if current database is PostgreSQL."""
        return self.db_type == DatabaseType.POSTGRESQL


# Global configuration instance
_config: Optional[DatabaseConfig] = None


def get_config() -> DatabaseConfig:
    """Get global database configuration instance (singleton).

    Returns:
        DatabaseConfig instance
    """
    global _config
    if _config is None:
        _config = DatabaseConfig()
    return _config


def create_engine():
    """Create SQLAlchemy database engine.

    This function creates a properly configured SQLAlchemy engine
    based on the current database configuration.

    Returns:
        sqlalchemy.engine.Engine instance

    Note:
        This function requires SQLAlchemy to be installed.
        The current implementation uses raw SQL connections.
        SQLAlchemy integration is planned for future releases.
    """
    try:
        from sqlalchemy import create_engine as sa_create_engine
    except ImportError:
        raise ImportError(
            "SQLAlchemy is required for engine creation. "
            "Install it with: pip install sqlalchemy"
        )

    config = get_config()
    url = config.get_database_url()
    options = config.get_engine_options()

    logger.info(f"Creating database engine: {config.db_type.value}")
    engine = sa_create_engine(url, **options)

    return engine


# Export public API
__all__ = [
    "DatabaseType",
    "DatabaseConfig",
    "get_config",
    "create_engine",
]
