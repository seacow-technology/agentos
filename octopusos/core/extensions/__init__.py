"""AgentOS Extensions System

Extension system for managing installable capability packages.

Core principles:
1. Extensions cannot import/patch AgentOS internal logic
2. Extensions only produce capability declarations and controlled installer plans
3. All actual actions are executed by Core's controlled executors
4. Extensions have no network/execution permissions by default
5. Extensions can only be installed via zip (local upload or URL)

Components:
- registry: Extension registry for CRUD operations
- validator: Zip and manifest validator
- installer: Zip installer
- downloader: URL downloader with sha256 verification
- models: Pydantic data models
- exceptions: Custom exceptions
"""

from agentos.core.extensions.exceptions import (
    ExtensionError,
    ValidationError,
    InstallationError,
    DownloadError,
    RegistryError,
)
from agentos.core.extensions.models import (
    ExtensionManifest,
    ExtensionCapability,
    ExtensionInstallConfig,
    ExtensionStatus,
    InstallStatus,
    InstallSource,
    RuntimeType,
    PythonConfig,
)
from agentos.core.extensions.validator import ExtensionValidator
from agentos.core.extensions.downloader import URLDownloader
from agentos.core.extensions.installer import ZipInstaller
from agentos.core.extensions.registry import ExtensionRegistry
from agentos.core.extensions.engine import (
    ExtensionInstallEngine,
    InstallResult,
    InstallProgress,
    InstallErrorCode,
)

__all__ = [
    # Exceptions
    "ExtensionError",
    "ValidationError",
    "InstallationError",
    "DownloadError",
    "RegistryError",
    # Models
    "ExtensionManifest",
    "ExtensionCapability",
    "ExtensionInstallConfig",
    "ExtensionStatus",
    "InstallStatus",
    "InstallSource",
    "RuntimeType",
    "PythonConfig",
    # Engine
    "ExtensionInstallEngine",
    "InstallResult",
    "InstallProgress",
    "InstallErrorCode",
    # Components
    "ExtensionValidator",
    "URLDownloader",
    "ZipInstaller",
    "ExtensionRegistry",
]
