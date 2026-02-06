"""Skill Manifest Parser and Validator.

This module provides:
- SkillManifest dataclass for representing skill metadata
- load_manifest() for parsing YAML manifests
- validate_manifest() for structural, type, and semantic validation
- normalize_manifest() for database serialization

Validation Layers:
1. Structural: Required fields (skill_id, name, version, entry, capabilities, requires)
2. Type: Version format (semver), FQDN validation, numeric ranges
3. Semantic: Permission consistency, capability-action alignment
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

# FQDN regex (simple validation)
FQDN_PATTERN = re.compile(
    r"^(?=.{1,253}$)"  # Total length <= 253
    r"(?!-)"  # Not start with hyphen
    r"([a-zA-Z0-9-]{1,63}\.)*"  # Subdomains
    r"[a-zA-Z0-9-]{1,63}$"  # TLD
)


@dataclass
class EntryExport:
    """Exported command definition."""

    command: str
    handler: str


@dataclass
class Entry:
    """Skill entry point configuration."""

    runtime: str  # python | nodejs | ...
    module: str  # Main module file
    exports: List[EntryExport] = field(default_factory=list)


@dataclass
class Capabilities:
    """Skill capability classification."""

    # pure: No I/O, deterministic
    # io: Read-only external resources
    # action: State-changing operations
    class_: str  # Renamed from 'class' (Python keyword)
    tags: List[str] = field(default_factory=list)


@dataclass
class NetPermission:
    """Network access permissions."""

    allow_domains: List[str] = field(default_factory=list)


@dataclass
class FsPermission:
    """Filesystem access permissions."""

    read: bool = False
    write: bool = False


@dataclass
class ActionsPermission:
    """Action permissions."""

    write_state: bool = False


@dataclass
class Permissions:
    """Permission definitions."""

    net: Optional[NetPermission] = None
    fs: Optional[FsPermission] = None
    actions: Optional[ActionsPermission] = None


@dataclass
class Requires:
    """Skill requirements and permissions."""

    phase: str  # execution | planning | ...
    permissions: Permissions = field(default_factory=Permissions)


@dataclass
class Limits:
    """Resource limits."""

    max_runtime_ms: int = 5000
    max_tokens: int = 800


@dataclass
class IntegrityFile:
    """File integrity tracking."""

    path: str
    hash: Optional[str] = None


@dataclass
class Integrity:
    """Integrity verification data."""

    files: List[str] = field(default_factory=list)


@dataclass
class SkillManifest:
    """Skill manifest data model.

    Represents the complete skill.yaml schema with all metadata,
    permissions, and configuration.
    """

    skill_id: str
    name: str
    version: str
    author: str
    description: str
    entry: Entry
    capabilities: Capabilities
    requires: Requires
    limits: Limits = field(default_factory=Limits)
    integrity: Optional[Integrity] = None


def load_manifest(path_or_bytes: Union[str, Path, bytes]) -> SkillManifest:
    """Load and parse skill manifest from file or bytes.

    Args:
        path_or_bytes: File path (str/Path) or raw YAML bytes

    Returns:
        SkillManifest instance

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
        # Entry
        entry_data = data.get("entry", {})
        exports = [
            EntryExport(command=e["command"], handler=e["handler"])
            for e in entry_data.get("exports", [])
        ]
        entry = Entry(
            runtime=entry_data.get("runtime", ""),
            module=entry_data.get("module", ""),
            exports=exports,
        )

        # Capabilities
        cap_data = data.get("capabilities", {})
        capabilities = Capabilities(
            class_=cap_data.get("class", ""),
            tags=cap_data.get("tags", []),
        )

        # Permissions
        perms_data = data.get("requires", {}).get("permissions", {})
        net_perm = None
        if "net" in perms_data:
            net_perm = NetPermission(allow_domains=perms_data["net"].get("allow_domains", []))

        fs_perm = None
        if "fs" in perms_data:
            fs_perm = FsPermission(
                read=perms_data["fs"].get("read", False),
                write=perms_data["fs"].get("write", False),
            )

        actions_perm = None
        if "actions" in perms_data:
            actions_perm = ActionsPermission(
                write_state=perms_data["actions"].get("write_state", False)
            )

        permissions = Permissions(net=net_perm, fs=fs_perm, actions=actions_perm)

        # Requires
        requires_data = data.get("requires", {})
        requires = Requires(
            phase=requires_data.get("phase", "execution"),
            permissions=permissions,
        )

        # Limits
        limits_data = data.get("limits", {})
        limits = Limits(
            max_runtime_ms=limits_data.get("max_runtime_ms", 5000),
            max_tokens=limits_data.get("max_tokens", 800),
        )

        # Integrity
        integrity = None
        if "integrity" in data:
            integrity = Integrity(files=data["integrity"].get("files", []))

        # Build manifest
        manifest = SkillManifest(
            skill_id=data.get("skill_id", ""),
            name=data.get("name", ""),
            version=data.get("version", ""),
            author=data.get("author", ""),
            description=data.get("description", ""),
            entry=entry,
            capabilities=capabilities,
            requires=requires,
            limits=limits,
            integrity=integrity,
        )

        return manifest

    except KeyError as e:
        raise ValueError(f"Missing required field in manifest: {e}")
    except Exception as e:
        raise ValueError(f"Failed to parse manifest: {e}")


def validate_manifest(manifest: SkillManifest) -> Tuple[bool, List[str]]:
    """Validate skill manifest with structural, type, and semantic checks.

    Args:
        manifest: SkillManifest to validate

    Returns:
        Tuple of (is_valid, error_messages)
    """
    errors = []

    # ==================== STRUCTURAL VALIDATION ====================
    # Required fields
    if not manifest.skill_id:
        errors.append("skill_id is required")
    elif not re.match(r"^[a-z0-9\._\-]+$", manifest.skill_id):
        errors.append("skill_id must contain only lowercase letters, numbers, dots, underscores, hyphens")

    if not manifest.name:
        errors.append("name is required")

    if not manifest.version:
        errors.append("version is required")

    if not manifest.author:
        errors.append("author is required")

    if not manifest.description:
        errors.append("description is required")

    if not manifest.entry.runtime:
        errors.append("entry.runtime is required")

    if not manifest.entry.module:
        errors.append("entry.module is required")

    if not manifest.entry.exports:
        errors.append("entry.exports must have at least one command")

    if not manifest.capabilities.class_:
        errors.append("capabilities.class is required")

    if not manifest.requires.phase:
        errors.append("requires.phase is required")

    # ==================== TYPE VALIDATION ====================
    # Version format (semver)
    if manifest.version and not SEMVER_PATTERN.match(manifest.version):
        errors.append(f"version '{manifest.version}' is not valid semver (e.g., 1.0.0)")

    # Capability class values
    if manifest.capabilities.class_ not in ["pure", "io", "action"]:
        errors.append(f"capabilities.class must be one of: pure, io, action (got '{manifest.capabilities.class_}')")

    # FQDN validation for allow_domains
    if manifest.requires.permissions.net:
        for domain in manifest.requires.permissions.net.allow_domains:
            if not FQDN_PATTERN.match(domain):
                errors.append(f"Invalid FQDN in allow_domains: '{domain}'")

    # Limits must be positive
    if manifest.limits.max_runtime_ms <= 0:
        errors.append(f"limits.max_runtime_ms must be positive (got {manifest.limits.max_runtime_ms})")

    if manifest.limits.max_tokens <= 0:
        errors.append(f"limits.max_tokens must be positive (got {manifest.limits.max_tokens})")

    # ==================== SEMANTIC VALIDATION ====================
    # Rule 1: capabilities.class=action requires explicit actions permission
    if manifest.capabilities.class_ == "action":
        if not manifest.requires.permissions.actions:
            errors.append("capabilities.class=action requires explicit requires.permissions.actions")
        elif not manifest.requires.permissions.actions.write_state:
            errors.append("capabilities.class=action requires actions.write_state=true")

    # Rule 2: If net permission is declared, allow_domains cannot be empty
    if manifest.requires.permissions.net:
        if not manifest.requires.permissions.net.allow_domains:
            errors.append("requires.permissions.net.allow_domains cannot be empty if net permission is declared")

    # Rule 3: Integrity files must exist (basic check - just non-empty)
    if manifest.integrity and not manifest.integrity.files:
        errors.append("integrity.files cannot be empty if integrity is declared")

    return (len(errors) == 0, errors)


def normalize_manifest(manifest: SkillManifest) -> Dict[str, Any]:
    """Normalize manifest to JSON-serializable dictionary for database storage.

    Args:
        manifest: SkillManifest to normalize

    Returns:
        Dictionary ready for JSON serialization
    """
    result = {
        "skill_id": manifest.skill_id,
        "name": manifest.name,
        "version": manifest.version,
        "author": manifest.author,
        "description": manifest.description,
        "entry": {
            "runtime": manifest.entry.runtime,
            "module": manifest.entry.module,
            "exports": [
                {"command": e.command, "handler": e.handler} for e in manifest.entry.exports
            ],
        },
        "capabilities": {
            "class": manifest.capabilities.class_,
            "tags": manifest.capabilities.tags,
        },
        "requires": {
            "phase": manifest.requires.phase,
            "permissions": {},
        },
        "limits": {
            "max_runtime_ms": manifest.limits.max_runtime_ms,
            "max_tokens": manifest.limits.max_tokens,
        },
    }

    # Add permissions if present
    if manifest.requires.permissions.net:
        result["requires"]["permissions"]["net"] = {
            "allow_domains": manifest.requires.permissions.net.allow_domains
        }

    if manifest.requires.permissions.fs:
        result["requires"]["permissions"]["fs"] = {
            "read": manifest.requires.permissions.fs.read,
            "write": manifest.requires.permissions.fs.write,
        }

    if manifest.requires.permissions.actions:
        result["requires"]["permissions"]["actions"] = {
            "write_state": manifest.requires.permissions.actions.write_state
        }

    # Add integrity if present
    if manifest.integrity:
        result["integrity"] = {"files": manifest.integrity.files}

    return result


__all__ = [
    "SkillManifest",
    "load_manifest",
    "validate_manifest",
    "normalize_manifest",
    "Entry",
    "EntryExport",
    "Capabilities",
    "Permissions",
    "NetPermission",
    "FsPermission",
    "ActionsPermission",
    "Requires",
    "Limits",
    "Integrity",
]
