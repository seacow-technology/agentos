"""
Capability Schema Validator

Validates extension manifest schema, ensuring all required fields
are present and correctly formatted, including permissions.

Part of PR-E3: Permissions + Deny/Audit System
"""

import logging
from typing import Dict, Any, List, Tuple, Optional

logger = logging.getLogger(__name__)


# ============================================
# Schema Validator
# ============================================

class CapabilitySchema:
    """
    Validator for extension manifest schema

    Ensures manifests have all required fields and correct structure,
    especially the new permissions field required for PR-E3.

    Example:
        >>> schema = CapabilitySchema()
        >>> valid, errors = schema.validate_manifest({
        ...     "id": "tools.postman",
        ...     "name": "Postman",
        ...     "version": "0.1.0",
        ...     "capabilities": [
        ...         {
        ...             "command": "/postman",
        ...             "runner": "exec.postman_cli",
        ...             "permissions": ["exec_shell", "network_http"]
        ...         }
        ...     ]
        ... })
        >>> assert valid is True
        >>> assert len(errors) == 0
    """

    # Required top-level fields
    REQUIRED_MANIFEST_FIELDS = [
        "id",
        "name",
        "version",
        "capabilities"
    ]

    # Required capability fields (new format - PR-E3)
    REQUIRED_CAPABILITY_FIELDS_NEW = [
        "command",
        "runner",
        "permissions"
    ]

    # Required capability fields (legacy format)
    REQUIRED_CAPABILITY_FIELDS_LEGACY = [
        "type",
        "name"
    ]

    # Optional capability fields
    OPTIONAL_CAPABILITY_FIELDS = [
        "args_schema",
        "timeout_sec",
        "description",
        "summary"
    ]

    # Valid permission values
    VALID_PERMISSIONS = [
        "read_status",
        "fs_read",
        "fs_write",
        "network_http",
        "builtin.exec",
        "exec_shell"
    ]

    def validate_manifest(self, manifest_dict: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate complete manifest structure

        Args:
            manifest_dict: Manifest dictionary from manifest.json

        Returns:
            Tuple of (valid: bool, errors: List[str])

        Example:
            >>> schema = CapabilitySchema()
            >>> manifest = {
            ...     "id": "tools.example",
            ...     "name": "Example",
            ...     "version": "1.0.0",
            ...     "capabilities": [
            ...         {
            ...             "command": "/example",
            ...             "runner": "exec.example",
            ...             "permissions": ["read_status"]
            ...         }
            ...     ]
            ... }
            >>> valid, errors = schema.validate_manifest(manifest)
            >>> assert valid is True
        """
        errors = []

        # Check type
        if not isinstance(manifest_dict, dict):
            errors.append("Manifest must be a dictionary")
            return False, errors

        # Check required top-level fields
        for field in self.REQUIRED_MANIFEST_FIELDS:
            if field not in manifest_dict:
                errors.append(f"Missing required manifest field: '{field}'")

        # Early exit if missing required fields
        if errors:
            return False, errors

        # Validate id format
        ext_id = manifest_dict.get("id", "")
        if not ext_id or not isinstance(ext_id, str):
            errors.append("Manifest 'id' must be a non-empty string")
        elif "." not in ext_id:
            errors.append(
                f"Manifest 'id' should follow convention 'category.name' "
                f"(e.g., 'tools.postman'), got: '{ext_id}'"
            )

        # Validate name
        name = manifest_dict.get("name", "")
        if not name or not isinstance(name, str):
            errors.append("Manifest 'name' must be a non-empty string")

        # Validate version (basic semantic version check)
        version = manifest_dict.get("version", "")
        if not version or not isinstance(version, str):
            errors.append("Manifest 'version' must be a non-empty string")
        elif not self._is_valid_semver(version):
            errors.append(
                f"Manifest 'version' should follow semantic versioning "
                f"(e.g., '0.1.0'), got: '{version}'"
            )

        # Validate capabilities array
        capabilities = manifest_dict.get("capabilities", [])
        if not isinstance(capabilities, list):
            errors.append("Manifest 'capabilities' must be a list")
            return False, errors

        if len(capabilities) == 0:
            errors.append("Manifest 'capabilities' must contain at least one capability")
            return False, errors

        # Validate each capability
        for idx, cap in enumerate(capabilities):
            cap_errors = self.validate_capability(cap, idx)
            errors.extend(cap_errors)

        return len(errors) == 0, errors

    def validate_capability(self, capability: Dict[str, Any], index: int = 0) -> List[str]:
        """
        Validate single capability object

        Supports both formats:
        - Legacy format: {"type": "slash_command", "name": "/postman", "description": "..."}
        - New format (PR-E3): {"command": "/postman", "runner": "exec.postman_cli", "permissions": ["..."]}

        Args:
            capability: Capability dictionary
            index: Index in capabilities array (for error messages)

        Returns:
            List of error messages (empty if valid)

        Example:
            >>> schema = CapabilitySchema()
            >>> cap = {
            ...     "command": "/postman",
            ...     "runner": "exec.postman_cli",
            ...     "permissions": ["exec_shell"]
            ... }
            >>> errors = schema.validate_capability(cap)
            >>> assert len(errors) == 0
        """
        errors = []
        prefix = f"Capability at index {index}"

        # Check type
        if not isinstance(capability, dict):
            errors.append(f"{prefix}: must be a dictionary")
            return errors

        # Detect format: legacy or new
        is_legacy = "type" in capability and "name" in capability
        is_new = "command" in capability and "runner" in capability

        if not is_legacy and not is_new:
            # Missing required fields from both formats
            errors.append(
                f"{prefix}: must use either legacy format "
                f"(type, name, description) or new format (command, runner, permissions)"
            )
            return errors

        # Validate based on detected format
        if is_legacy:
            return self._validate_capability_legacy(capability, index)
        else:
            return self._validate_capability_new(capability, index)

    def _validate_capability_legacy(self, capability: Dict[str, Any], index: int) -> List[str]:
        """
        Validate legacy capability format

        Args:
            capability: Capability dictionary
            index: Index in capabilities array

        Returns:
            List of error messages (empty if valid)
        """
        errors = []
        prefix = f"Capability at index {index}"

        # Check required fields
        for field in self.REQUIRED_CAPABILITY_FIELDS_LEGACY:
            if field not in capability:
                errors.append(f"{prefix}: missing required field '{field}'")

        # Early exit if missing required fields
        if errors:
            return errors

        # Validate type
        cap_type = capability.get("type", "")
        if not cap_type or not isinstance(cap_type, str):
            errors.append(f"{prefix}: 'type' must be a non-empty string")
        elif cap_type not in ["slash_command", "tool", "agent", "workflow"]:
            errors.append(
                f"{prefix}: 'type' must be one of: "
                f"slash_command, tool, agent, workflow. Got: '{cap_type}'"
            )

        # Validate name
        name = capability.get("name", "")
        if not name or not isinstance(name, str):
            errors.append(f"{prefix}: 'name' must be a non-empty string")

        # Description is optional but should be string if present
        description = capability.get("description")
        if description is not None and not isinstance(description, str):
            errors.append(f"{prefix}: 'description' must be a string if provided")

        return errors

    def _validate_capability_new(self, capability: Dict[str, Any], index: int) -> List[str]:
        """
        Validate new capability format (PR-E3)

        Args:
            capability: Capability dictionary
            index: Index in capabilities array

        Returns:
            List of error messages (empty if valid)
        """
        errors = []
        prefix = f"Capability at index {index}"

        # Check required fields
        for field in self.REQUIRED_CAPABILITY_FIELDS_NEW:
            if field not in capability:
                errors.append(f"{prefix}: missing required field '{field}'")

        # Early exit if missing required fields
        if errors:
            return errors

        # Validate command
        command = capability.get("command", "")
        if not command or not isinstance(command, str):
            errors.append(f"{prefix}: 'command' must be a non-empty string")
        elif not command.startswith("/"):
            errors.append(
                f"{prefix}: 'command' should start with '/' "
                f"(slash command format), got: '{command}'"
            )

        # Validate runner
        runner = capability.get("runner", "")
        if not runner or not isinstance(runner, str):
            errors.append(f"{prefix}: 'runner' must be a non-empty string")
        elif "." not in runner:
            errors.append(
                f"{prefix}: 'runner' should follow convention 'type.name' "
                f"(e.g., 'exec.postman_cli'), got: '{runner}'"
            )

        # Validate permissions (PR-E3 requirement)
        permissions = capability.get("permissions", [])
        if not isinstance(permissions, list):
            errors.append(f"{prefix}: 'permissions' must be a list")
        elif len(permissions) == 0:
            errors.append(
                f"{prefix}: 'permissions' must contain at least one permission. "
                f"Valid permissions: {', '.join(self.VALID_PERMISSIONS)}"
            )
        else:
            # Validate each permission
            for perm_idx, perm in enumerate(permissions):
                if not isinstance(perm, str):
                    errors.append(
                        f"{prefix}: permission at index {perm_idx} must be a string"
                    )
                elif perm not in self.VALID_PERMISSIONS:
                    errors.append(
                        f"{prefix}: invalid permission '{perm}'. "
                        f"Valid permissions: {', '.join(self.VALID_PERMISSIONS)}"
                    )

        # Validate optional fields if present
        timeout_sec = capability.get("timeout_sec")
        if timeout_sec is not None:
            if not isinstance(timeout_sec, (int, float)) or timeout_sec <= 0:
                errors.append(
                    f"{prefix}: 'timeout_sec' must be a positive number, "
                    f"got: {timeout_sec}"
                )

        args_schema = capability.get("args_schema")
        if args_schema is not None and not isinstance(args_schema, dict):
            errors.append(
                f"{prefix}: 'args_schema' must be a dictionary (JSON Schema format)"
            )

        return errors

    def _is_valid_semver(self, version: str) -> bool:
        """
        Check if version string follows semantic versioning

        Args:
            version: Version string to validate

        Returns:
            True if valid semver format (e.g., "0.1.0")

        Example:
            >>> schema = CapabilitySchema()
            >>> assert schema._is_valid_semver("0.1.0") is True
            >>> assert schema._is_valid_semver("1.2.3-beta") is True
            >>> assert schema._is_valid_semver("invalid") is False
        """
        # Basic semver check: X.Y.Z format
        parts = version.split("-")[0].split(".")
        if len(parts) < 3:
            return False

        try:
            # Check that major, minor, patch are integers
            for part in parts[:3]:
                int(part)
            return True
        except ValueError:
            return False

    def get_required_permissions(self, manifest_dict: Dict[str, Any]) -> List[str]:
        """
        Extract all required permissions from manifest

        Args:
            manifest_dict: Manifest dictionary

        Returns:
            Deduplicated list of all permissions required by capabilities

        Example:
            >>> schema = CapabilitySchema()
            >>> manifest = {
            ...     "capabilities": [
            ...         {"command": "/a", "runner": "exec.a", "permissions": ["exec_shell"]},
            ...         {"command": "/b", "runner": "exec.b", "permissions": ["network_http", "exec_shell"]}
            ...     ]
            ... }
            >>> perms = schema.get_required_permissions(manifest)
            >>> assert set(perms) == {"exec_shell", "network_http"}
        """
        all_permissions = set()

        capabilities = manifest_dict.get("capabilities", [])
        for cap in capabilities:
            if isinstance(cap, dict):
                permissions = cap.get("permissions", [])
                if isinstance(permissions, list):
                    all_permissions.update(permissions)

        return sorted(list(all_permissions))


# ============================================
# Integration with ExtensionValidator
# ============================================

def validate_manifest_with_schema(manifest_dict: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Convenience function for manifest validation

    Args:
        manifest_dict: Manifest dictionary from manifest.json

    Returns:
        Tuple of (valid: bool, errors: List[str])

    Example:
        >>> from agentos.core.capabilities.schema import validate_manifest_with_schema
        >>> valid, errors = validate_manifest_with_schema({
        ...     "id": "tools.example",
        ...     "name": "Example",
        ...     "version": "1.0.0",
        ...     "capabilities": [
        ...         {
        ...             "command": "/example",
        ...             "runner": "exec.example",
        ...             "permissions": ["read_status"]
        ...         }
        ...     ]
        ... })
        >>> assert valid is True
    """
    schema = CapabilitySchema()
    return schema.validate_manifest(manifest_dict)
