"""Data models for the Extension system"""

from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


class ExtensionStatus(str, Enum):
    """Extension installation status"""
    INSTALLED = "INSTALLED"
    INSTALLING = "INSTALLING"
    FAILED = "FAILED"
    UNINSTALLED = "UNINSTALLED"


class InstallStatus(str, Enum):
    """Installation process status"""
    INSTALLING = "INSTALLING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    UNINSTALLING = "UNINSTALLING"


class InstallSource(str, Enum):
    """Source of extension installation"""
    UPLOAD = "upload"
    URL = "url"


class RuntimeType(str, Enum):
    """Runtime types for extensions"""
    PYTHON = "python"


class CapabilityType(str, Enum):
    """Types of capabilities an extension can provide"""
    SLASH_COMMAND = "slash_command"
    TOOL = "tool"
    AGENT = "agent"
    WORKFLOW = "workflow"


class ExtensionCapability(BaseModel):
    """A capability provided by an extension"""
    type: CapabilityType
    name: str
    description: str
    config: Optional[Dict[str, Any]] = None


class ExtensionInstallConfig(BaseModel):
    """Installation configuration for an extension"""
    mode: str = Field(default="agentos_managed", description="Installation mode")
    plan: str = Field(description="Path to install plan YAML")


class ExtensionDocs(BaseModel):
    """Documentation references for an extension"""
    usage: str = Field(description="Path to usage documentation")


class PythonConfig(BaseModel):
    """Python runtime configuration"""
    version: str = Field(description="Python version (e.g., '3.11')")
    dependencies: List[str] = Field(default_factory=list, description="List of Python dependencies (e.g., ['requests>=2.28.0'])")

    @field_validator('version')
    @classmethod
    def validate_version(cls, v: str) -> str:
        """Validate Python version format"""
        import re
        if not re.match(r'^\d+\.\d+$', v):
            raise ValueError("Python version must be in format 'X.Y' (e.g., '3.11')")
        return v


class ExtensionManifest(BaseModel):
    """Extension manifest.json schema"""
    id: str = Field(description="Unique extension identifier (e.g., 'tools.postman')")
    name: str = Field(description="Human-readable extension name")
    version: str = Field(description="Semantic version (e.g., '0.1.0')")
    description: str = Field(description="Brief description of the extension")
    author: str = Field(description="Extension author")
    license: str = Field(description="License identifier (e.g., 'Apache-2.0')")
    runtime: RuntimeType = Field(description="Extension runtime type. Currently only 'python' is supported.")
    python: PythonConfig = Field(description="Python runtime configuration")
    external_bins: List[str] = Field(default_factory=list, description="List of external binaries required. Must be empty for Python-only extensions.")
    entrypoint: Optional[str] = Field(default=None, description="Entrypoint script (legacy)")
    icon: Optional[str] = Field(default=None, description="Path to icon file")
    capabilities: List[ExtensionCapability] = Field(description="List of capabilities")
    permissions_required: List[str] = Field(default_factory=list, description="Required permissions")
    platforms: List[str] = Field(description="Supported platforms (e.g., ['linux', 'darwin', 'win32'])")
    install: ExtensionInstallConfig = Field(description="Installation configuration")
    docs: ExtensionDocs = Field(description="Documentation references")

    @field_validator('id')
    @classmethod
    def validate_id(cls, v: str) -> str:
        """Validate extension ID format"""
        if not v or not v.strip():
            raise ValueError("Extension ID cannot be empty")
        if not all(c.isalnum() or c in '._-' for c in v):
            raise ValueError("Extension ID can only contain alphanumeric characters, dots, underscores, and hyphens")
        return v

    @field_validator('version')
    @classmethod
    def validate_version(cls, v: str) -> str:
        """Validate semantic version format"""
        parts = v.split('.')
        if len(parts) != 3:
            raise ValueError("Version must follow semantic versioning (e.g., '0.1.0')")
        if not all(part.isdigit() for part in parts):
            raise ValueError("Version parts must be numeric")
        return v

    @field_validator('platforms')
    @classmethod
    def validate_platforms(cls, v: List[str]) -> List[str]:
        """Validate platform identifiers"""
        valid_platforms = {'linux', 'darwin', 'win32', 'all'}
        for platform in v:
            if platform not in valid_platforms:
                raise ValueError(f"Invalid platform '{platform}'. Must be one of: {valid_platforms}")
        return v

    def model_post_init(self, __context):
        """Validate Python-only policy after model initialization"""
        # Enforce Python-only policy: no external binaries allowed
        if self.runtime == RuntimeType.PYTHON and self.external_bins:
            raise ValueError(
                "Python-only extensions cannot have external_bins. "
                "Found external_bins: " + ", ".join(self.external_bins) + ". "
                "See ADR-EXT-002 for Python-only policy."
            )


class ExtensionRecord(BaseModel):
    """Database record for an installed extension"""
    id: str
    name: str
    version: str
    description: Optional[str] = None
    icon_path: Optional[str] = None
    installed_at: datetime
    enabled: bool = True
    status: ExtensionStatus
    sha256: str
    source: InstallSource
    source_url: Optional[str] = None
    permissions_required: List[str] = Field(default_factory=list)
    capabilities: List[ExtensionCapability] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = None


class ExtensionInstallRecord(BaseModel):
    """Database record for an installation process"""
    install_id: str
    extension_id: str
    status: InstallStatus
    progress: int = Field(default=0, ge=0, le=100)
    current_step: Optional[str] = None
    started_at: datetime
    ended_at: Optional[datetime] = None
    error: Optional[str] = None


class ExtensionConfig(BaseModel):
    """Configuration for an installed extension"""
    extension_id: str
    config_json: Optional[Dict[str, Any]] = None
    secrets_ref: Optional[str] = None
    updated_at: datetime
