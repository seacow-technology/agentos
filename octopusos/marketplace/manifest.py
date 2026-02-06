"""Capability Manifest Parser and Validator.

This module provides the data model and validation for capability manifests
that can be registered in the Marketplace Registry.

A capability manifest describes:
- What the capability does (metadata, description)
- Who published it (publisher_id)
- What it requires (dependencies, permissions)
- How to use it (API, parameters)

Validation Layers:
1. Structural: Required fields present
2. Type: Correct data types and formats
3. Semantic: Logical consistency and completeness
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    import yaml
except ImportError:
    raise ImportError(
        "PyYAML is required for manifest parsing. "
        "Install it with: pip install pyyaml"
    )


# Semver regex (simplified, compatible with PEP 440)
SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+(-[a-zA-Z0-9\.\-]+)?(\+[a-zA-Z0-9\.\-]+)?$")

# Publisher ID pattern (namespace.name)
PUBLISHER_ID_PATTERN = re.compile(r"^[a-z0-9_]+(\.[a-z0-9_]+)*$")

# Capability name pattern (lowercase, alphanumeric, underscore)
CAPABILITY_NAME_PATTERN = re.compile(r"^[a-z0-9_]+$")


@dataclass
class CapabilityMetadata:
    """Capability metadata and description."""

    name: str                           # Short name (e.g., "web_scraper")
    display_name: str                   # Human-readable name
    description: str                    # Short description
    long_description: Optional[str] = None
    category: Optional[str] = None      # Category (e.g., "data", "communication")
    tags: List[str] = field(default_factory=list)
    icon: Optional[str] = None          # Icon URL or identifier
    documentation_url: Optional[str] = None


@dataclass
class PublisherInfo:
    """Publisher identity and contact information."""

    publisher_id: str                   # Unique publisher ID (e.g., "official", "community.john")
    name: str                           # Publisher display name
    contact: Optional[str] = None       # Email or contact URL
    website: Optional[str] = None


@dataclass
class DependencySpec:
    """Dependency specification."""

    name: str                           # Dependency name
    version: Optional[str] = None       # Version constraint (e.g., ">=1.0.0")
    optional: bool = False


@dataclass
class ParameterSpec:
    """Parameter specification for capability invocation."""

    name: str
    type: str                           # Type hint (e.g., "string", "integer", "boolean")
    description: str
    required: bool = True
    default: Optional[Any] = None


@dataclass
class CapabilityAPI:
    """Capability API specification."""

    endpoint: str                       # Entry point (e.g., "execute", "process")
    parameters: List[ParameterSpec] = field(default_factory=list)
    returns: Optional[str] = None       # Return type description


@dataclass
class CapabilityRequirements:
    """Capability requirements and constraints."""

    runtime: str                        # Runtime environment (e.g., "python", "nodejs")
    min_version: Optional[str] = None   # Minimum runtime version
    dependencies: List[DependencySpec] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)  # Required permissions


@dataclass
class CapabilityManifest:
    """Complete capability manifest.

    This is the primary data model for capabilities registered in the
    Marketplace Registry. It contains all metadata, API specs, and
    requirements needed to discover, evaluate, and use a capability.

    Attributes:
        version: Manifest schema version (e.g., "1.0.0")
        metadata: Capability metadata and description
        publisher: Publisher information
        capability_version: Capability version (semver)
        api: API specification
        requirements: Runtime requirements
        signature: Optional cryptographic signature
    """

    version: str                        # Manifest schema version
    metadata: CapabilityMetadata
    publisher: PublisherInfo
    capability_version: str             # Capability version (semver)
    api: CapabilityAPI
    requirements: CapabilityRequirements
    signature: Optional[str] = None


def load_manifest(path_or_bytes: Union[str, Path, bytes]) -> CapabilityManifest:
    """Load and parse capability manifest from file or bytes.

    Args:
        path_or_bytes: File path (str/Path) or raw YAML bytes

    Returns:
        CapabilityManifest instance

    Raises:
        FileNotFoundError: If path does not exist
        yaml.YAMLError: If YAML parsing fails
        ValueError: If manifest structure is invalid
    """
    # Parse YAML
    if isinstance(path_or_bytes, bytes):
        data = yaml.safe_load(path_or_bytes)
    else:
        path = Path(path_or_bytes)
        if not path.exists():
            raise FileNotFoundError(f"Manifest file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError("Manifest must be a YAML dictionary")

    # Parse nested structures
    try:
        # Metadata
        metadata_data = data.get("metadata", {})
        metadata = CapabilityMetadata(
            name=metadata_data.get("name", ""),
            display_name=metadata_data.get("display_name", ""),
            description=metadata_data.get("description", ""),
            long_description=metadata_data.get("long_description"),
            category=metadata_data.get("category"),
            tags=metadata_data.get("tags", []),
            icon=metadata_data.get("icon"),
            documentation_url=metadata_data.get("documentation_url"),
        )

        # Publisher
        publisher_data = data.get("publisher", {})
        publisher = PublisherInfo(
            publisher_id=publisher_data.get("publisher_id", ""),
            name=publisher_data.get("name", ""),
            contact=publisher_data.get("contact"),
            website=publisher_data.get("website"),
        )

        # API
        api_data = data.get("api", {})
        parameters = [
            ParameterSpec(
                name=p.get("name", ""),
                type=p.get("type", "string"),
                description=p.get("description", ""),
                required=p.get("required", True),
                default=p.get("default"),
            )
            for p in api_data.get("parameters", [])
        ]
        api = CapabilityAPI(
            endpoint=api_data.get("endpoint", ""),
            parameters=parameters,
            returns=api_data.get("returns"),
        )

        # Requirements
        requirements_data = data.get("requirements", {})
        dependencies = [
            DependencySpec(
                name=d.get("name", ""),
                version=d.get("version"),
                optional=d.get("optional", False),
            )
            for d in requirements_data.get("dependencies", [])
        ]
        requirements = CapabilityRequirements(
            runtime=requirements_data.get("runtime", ""),
            min_version=requirements_data.get("min_version"),
            dependencies=dependencies,
            permissions=requirements_data.get("permissions", []),
        )

        # Build manifest
        manifest = CapabilityManifest(
            version=data.get("version", ""),
            metadata=metadata,
            publisher=publisher,
            capability_version=data.get("capability_version", ""),
            api=api,
            requirements=requirements,
            signature=data.get("signature"),
        )

        return manifest

    except KeyError as e:
        raise ValueError(f"Missing required field in manifest: {e}")
    except Exception as e:
        raise ValueError(f"Failed to parse manifest: {e}")


def validate_manifest(manifest: CapabilityManifest) -> Tuple[bool, List[str]]:
    """Validate capability manifest with structural, type, and semantic checks.

    Args:
        manifest: CapabilityManifest to validate

    Returns:
        Tuple of (is_valid, error_messages)
    """
    errors = []

    # ==================== STRUCTURAL VALIDATION ====================
    # Required fields
    if not manifest.version:
        errors.append("version is required")

    if not manifest.metadata.name:
        errors.append("metadata.name is required")
    elif not CAPABILITY_NAME_PATTERN.match(manifest.metadata.name):
        errors.append("metadata.name must contain only lowercase letters, numbers, underscores")

    if not manifest.metadata.display_name:
        errors.append("metadata.display_name is required")

    if not manifest.metadata.description:
        errors.append("metadata.description is required")

    if not manifest.publisher.publisher_id:
        errors.append("publisher.publisher_id is required")
    elif not PUBLISHER_ID_PATTERN.match(manifest.publisher.publisher_id):
        errors.append("publisher.publisher_id must be lowercase with dots (e.g., 'official' or 'community.john')")

    if not manifest.publisher.name:
        errors.append("publisher.name is required")

    if not manifest.capability_version:
        errors.append("capability_version is required")

    if not manifest.api.endpoint:
        errors.append("api.endpoint is required")

    if not manifest.requirements.runtime:
        errors.append("requirements.runtime is required")

    # ==================== TYPE VALIDATION ====================
    # Version formats (semver)
    if manifest.version and not SEMVER_PATTERN.match(manifest.version):
        errors.append(f"version '{manifest.version}' is not valid semver (e.g., 1.0.0)")

    if manifest.capability_version and not SEMVER_PATTERN.match(manifest.capability_version):
        errors.append(f"capability_version '{manifest.capability_version}' is not valid semver")

    # Parameter types validation
    valid_types = ["string", "integer", "float", "boolean", "array", "object", "any"]
    for param in manifest.api.parameters:
        if not param.name:
            errors.append("api.parameters: parameter name cannot be empty")
        if not param.description:
            errors.append(f"api.parameters.{param.name}: description is required")
        if param.type not in valid_types:
            errors.append(f"api.parameters.{param.name}: type must be one of {valid_types}")

    # ==================== SEMANTIC VALIDATION ====================
    # Duplicate parameter names
    param_names = [p.name for p in manifest.api.parameters]
    if len(param_names) != len(set(param_names)):
        errors.append("api.parameters: duplicate parameter names found")

    # Required parameters cannot have defaults
    for param in manifest.api.parameters:
        if param.required and param.default is not None:
            errors.append(f"api.parameters.{param.name}: required parameters cannot have defaults")

    # Dependency names must be unique
    dep_names = [d.name for d in manifest.requirements.dependencies]
    if len(dep_names) != len(set(dep_names)):
        errors.append("requirements.dependencies: duplicate dependency names found")

    return (len(errors) == 0, errors)


def normalize_manifest(manifest: CapabilityManifest) -> Dict[str, Any]:
    """Normalize manifest to JSON-serializable dictionary for database storage.

    Args:
        manifest: CapabilityManifest to normalize

    Returns:
        Dictionary ready for JSON serialization
    """
    return {
        "version": manifest.version,
        "metadata": {
            "name": manifest.metadata.name,
            "display_name": manifest.metadata.display_name,
            "description": manifest.metadata.description,
            "long_description": manifest.metadata.long_description,
            "category": manifest.metadata.category,
            "tags": manifest.metadata.tags,
            "icon": manifest.metadata.icon,
            "documentation_url": manifest.metadata.documentation_url,
        },
        "publisher": {
            "publisher_id": manifest.publisher.publisher_id,
            "name": manifest.publisher.name,
            "contact": manifest.publisher.contact,
            "website": manifest.publisher.website,
        },
        "capability_version": manifest.capability_version,
        "api": {
            "endpoint": manifest.api.endpoint,
            "parameters": [
                {
                    "name": p.name,
                    "type": p.type,
                    "description": p.description,
                    "required": p.required,
                    "default": p.default,
                }
                for p in manifest.api.parameters
            ],
            "returns": manifest.api.returns,
        },
        "requirements": {
            "runtime": manifest.requirements.runtime,
            "min_version": manifest.requirements.min_version,
            "dependencies": [
                {
                    "name": d.name,
                    "version": d.version,
                    "optional": d.optional,
                }
                for d in manifest.requirements.dependencies
            ],
            "permissions": manifest.requirements.permissions,
        },
        "signature": manifest.signature,
    }


__all__ = [
    "CapabilityManifest",
    "CapabilityMetadata",
    "PublisherInfo",
    "DependencySpec",
    "ParameterSpec",
    "CapabilityAPI",
    "CapabilityRequirements",
    "load_manifest",
    "validate_manifest",
    "normalize_manifest",
]
