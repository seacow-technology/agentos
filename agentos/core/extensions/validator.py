"""Validator for extension packages"""

import hashlib
import json
import logging
import zipfile
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

import yaml

from agentos.core.extensions.exceptions import ValidationError
from agentos.core.extensions.models import ExtensionManifest

logger = logging.getLogger(__name__)

# Security limits
MAX_ZIP_SIZE = 50 * 1024 * 1024  # 50MB
MAX_MANIFEST_SIZE = 100 * 1024    # 100KB
MAX_YAML_SIZE = 500 * 1024        # 500KB


class ExtensionValidator:
    """Validator for extension packages and manifests"""

    @staticmethod
    def validate_zip_structure(zip_path: Path) -> Tuple[str, Dict[str, Any]]:
        """
        Validate zip structure and extract manifest

        Args:
            zip_path: Path to the zip file

        Returns:
            Tuple of (extension_root_dir, manifest_dict)

        Raises:
            ValidationError: If validation fails
        """
        if not zip_path.exists():
            raise ValidationError(f"Zip file not found: {zip_path}")

        # Check file size
        zip_size = zip_path.stat().st_size
        if zip_size > MAX_ZIP_SIZE:
            raise ValidationError(
                f"Zip file too large: {zip_size / 1024 / 1024:.2f}MB "
                f"(max: {MAX_ZIP_SIZE / 1024 / 1024}MB)"
            )

        logger.info(f"Validating zip structure: {zip_path.name} ({zip_size / 1024:.2f}KB)")

        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                # Get all file names
                file_list = zf.namelist()

                if not file_list:
                    raise ValidationError("Zip file is empty")

                # Check for top-level structure
                top_dirs = set()
                top_files = set()
                for name in file_list:
                    parts = Path(name).parts
                    if parts:
                        # If it's a file (no trailing /), record it
                        if not name.endswith('/') and len(parts) == 1:
                            top_files.add(parts[0])
                        else:
                            top_dirs.add(parts[0])

                # Case 1: Single top-level directory (preferred structure)
                if len(top_dirs) == 1 and len(top_files) == 0:
                    root_dir = list(top_dirs)[0]
                    logger.debug(f"Extension root directory: {root_dir}")

                # Case 2: Files directly in root (auto-handle this case)
                elif 'manifest.json' in top_files or 'manifest.json' in [str(f).split('/')[0] for f in file_list if 'manifest.json' in str(f)]:
                    # Files are directly in the root, use empty string as root
                    root_dir = ""
                    logger.info("Extension files are in zip root (no top-level directory), auto-handling")

                else:
                    raise ValidationError(
                        f"Invalid zip structure. Expected either:\n"
                        f"  1. Single top-level directory containing extension files\n"
                        f"  2. Extension files directly in zip root with manifest.json\n"
                        f"Found top-level entries: {top_dirs | top_files}"
                    )

                # Required files
                if root_dir:
                    required_files = {
                        'manifest.json': f"{root_dir}/manifest.json",
                        'install/plan.yaml': f"{root_dir}/install/plan.yaml",
                        'commands/commands.yaml': f"{root_dir}/commands/commands.yaml",
                        'docs/USAGE.md': f"{root_dir}/docs/USAGE.md",
                    }
                else:
                    # Files are directly in root
                    required_files = {
                        'manifest.json': "manifest.json",
                        'install/plan.yaml': "install/plan.yaml",
                        'commands/commands.yaml': "commands/commands.yaml",
                        'docs/USAGE.md': "docs/USAGE.md",
                    }

                missing_files = []
                for file_type, file_path in required_files.items():
                    if file_path not in file_list:
                        missing_files.append(file_path)

                if missing_files:
                    raise ValidationError(
                        f"Missing required files: {', '.join(missing_files)}"
                    )

                # F-EXT-4.2: Check for path traversal attacks, absolute paths, and symlinks
                for name in file_list:
                    # Check for path traversal
                    if '..' in name or name.startswith('/'):
                        raise ValidationError(f"Invalid file path in zip: {name}")

                    # Check for symlinks
                    info = zf.getinfo(name)
                    # In Unix systems, symlinks have external_attr with high byte = 0xA (symlink)
                    # or the file type bits indicate it's a symlink
                    is_symlink = (info.external_attr >> 28) == 0xA
                    if is_symlink:
                        raise ValidationError(
                            f"Symlinks are not allowed in extension packages: {name}. "
                            "For security reasons, symlinks are forbidden. "
                            "See F-EXT-4.2 for details."
                        )

                # F-EXT-1.2: Check for forbidden executable files in root directory
                forbidden_extensions = ['.py', '.js', '.sh', '.exe', '.bat', '.cmd', '.ps1']
                root_files = [f for f in file_list if f.count('/') == 1 and not f.endswith('/')]

                for file_path in root_files:
                    if any(file_path.lower().endswith(ext) for ext in forbidden_extensions):
                        raise ValidationError(
                            f"Forbidden executable file in extension root: {file_path}. "
                            f"Executable files are not allowed in extension root directory. "
                            f"See F-EXT-1.2 and ADR-EXT-001 for details."
                        )

                # Extract and validate manifest
                manifest_path = required_files['manifest.json']
                manifest_data = zf.read(manifest_path)

                if len(manifest_data) > MAX_MANIFEST_SIZE:
                    raise ValidationError(
                        f"manifest.json too large: {len(manifest_data) / 1024:.2f}KB "
                        f"(max: {MAX_MANIFEST_SIZE / 1024}KB)"
                    )

                try:
                    manifest_dict = json.loads(manifest_data)
                except json.JSONDecodeError as e:
                    raise ValidationError(f"Invalid JSON in manifest.json: {e}")

                logger.info(f"Zip structure validation passed: {root_dir}")
                return root_dir, manifest_dict

        except zipfile.BadZipFile as e:
            raise ValidationError(f"Invalid zip file: {e}")

    @staticmethod
    def validate_manifest(manifest_dict: Dict[str, Any]) -> ExtensionManifest:
        """
        Validate manifest schema using Pydantic

        Args:
            manifest_dict: Manifest dictionary

        Returns:
            Validated ExtensionManifest object

        Raises:
            ValidationError: If validation fails
        """
        # ADR-EXT-001: Enforce entrypoint must be null
        if manifest_dict.get("entrypoint") is not None:
            raise ValidationError(
                "Extension entrypoint must be null. "
                "Extensions cannot execute arbitrary code. "
                "Use declarative install/plan.yaml instead. "
                "See ADR-EXT-001 for details."
            )

        # PR-E3: Validate capabilities schema including permissions
        try:
            from agentos.core.capabilities.schema import validate_manifest_with_schema
            valid, errors = validate_manifest_with_schema(manifest_dict)
            if not valid:
                error_msg = "Manifest capability schema validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
                raise ValidationError(error_msg)
        except ImportError:
            # Fallback if schema module not available (backward compatibility)
            logger.warning("Capability schema validator not available, skipping capability validation")

        try:
            manifest = ExtensionManifest(**manifest_dict)
            logger.info(f"Manifest validation passed: {manifest.id} v{manifest.version}")
            return manifest
        except Exception as e:
            raise ValidationError(f"Invalid manifest schema: {e}")

    @staticmethod
    def validate_commands_yaml(commands_dict: Dict[str, Any]) -> None:
        """
        Validate commands.yaml structure, supporting both legacy and current formats

        Args:
            commands_dict: Commands dictionary from YAML

        Raises:
            ValidationError: If validation fails
        """
        if not isinstance(commands_dict, dict):
            raise ValidationError("commands.yaml must be a dictionary")

        # Support two formats: legacy 'commands' and current 'slash_commands'
        has_commands = 'commands' in commands_dict
        has_slash_commands = 'slash_commands' in commands_dict

        if not has_commands and not has_slash_commands:
            raise ValidationError(
                "commands.yaml must contain either 'commands' (legacy) or "
                "'slash_commands' (current) key. "
                f"Received keys: {list(commands_dict.keys())}. "
                "See ADR-EXT-001 for details."
            )

        # Normalize to slash_commands format for validation
        if has_commands and not has_slash_commands:
            # Legacy format: auto-convert
            commands = commands_dict['commands']
            format_type = "legacy"
        else:
            # Current format: use directly
            commands = commands_dict['slash_commands']
            format_type = "current"

        if not isinstance(commands, list):
            raise ValidationError(
                f"{'slash_commands' if format_type == 'current' else 'commands'} must be a list "
                f"(received: {type(commands).__name__})"
            )

        # Validate each command
        for idx, cmd in enumerate(commands):
            if not isinstance(cmd, dict):
                raise ValidationError(
                    f"Command at index {idx} must be a dictionary "
                    f"(received: {type(cmd).__name__})"
                )

            # Required fields differ by format
            if format_type == "legacy":
                required_fields = ['name', 'description']
            else:
                # Current format requires 'summary' instead of 'description'
                required_fields = ['name', 'summary']

            missing = [f for f in required_fields if f not in cmd]
            if missing:
                raise ValidationError(
                    f"Command at index {idx} missing required fields: {missing}. "
                    f"Available fields: {list(cmd.keys())}. "
                    f"Format: {format_type}"
                )

        logger.debug(f"Commands validation passed: {len(commands)} commands ({format_type} format)")

    @staticmethod
    def validate_plan_yaml(plan_dict: Dict[str, Any]) -> None:
        """
        Validate install/plan.yaml structure, supporting both legacy and current formats

        Args:
            plan_dict: Plan dictionary from YAML

        Raises:
            ValidationError: If validation fails
        """
        if not isinstance(plan_dict, dict):
            raise ValidationError("plan.yaml must be a dictionary")

        if 'steps' not in plan_dict:
            raise ValidationError("plan.yaml must contain 'steps' key")

        steps = plan_dict['steps']
        if not isinstance(steps, list):
            raise ValidationError("'steps' must be a list")

        for idx, step in enumerate(steps):
            if not isinstance(step, dict):
                raise ValidationError(f"Step at index {idx} must be a dictionary")

            # Support both 'action' (legacy) and 'type' (current) fields
            has_action = 'action' in step
            has_type = 'type' in step

            if not has_action and not has_type:
                raise ValidationError(
                    f"Step at index {idx} missing required field. "
                    f"Must have either 'action' (legacy) or 'type' (current). "
                    f"Available fields: {list(step.keys())}"
                )

            # Use whichever format is present
            step_type = step.get('action') or step.get('type')
            format_type = "legacy" if has_action else "current"

            # Validate step type for legacy format only
            # Current format uses flexible types like 'detect.platform', 'exec.shell', etc.
            if format_type == "legacy":
                valid_actions = {
                    'check_dependency',
                    'download_binary',
                    'install_binary',
                    'create_symlink',
                    'set_config',
                    'verify_installation',
                }

                if step_type not in valid_actions:
                    raise ValidationError(
                        f"Step at index {idx} has invalid action '{step_type}'. "
                        f"Valid actions: {valid_actions}"
                    )

        logger.debug(f"Install plan validation passed: {len(steps)} steps")

    @staticmethod
    def calculate_sha256(file_path: Path) -> str:
        """
        Calculate SHA256 hash of a file

        Args:
            file_path: Path to the file

        Returns:
            SHA256 hash as hex string

        Raises:
            ValidationError: If file cannot be read
        """
        if not file_path.exists():
            raise ValidationError(f"File not found: {file_path}")

        sha256_hash = hashlib.sha256()

        try:
            with open(file_path, 'rb') as f:
                # Read in chunks to handle large files
                for chunk in iter(lambda: f.read(8192), b''):
                    sha256_hash.update(chunk)

            hash_hex = sha256_hash.hexdigest()
            logger.debug(f"Calculated SHA256: {hash_hex}")
            return hash_hex

        except Exception as e:
            raise ValidationError(f"Failed to calculate SHA256: {e}")

    @classmethod
    def validate_extension_package(
        cls,
        zip_path: Path,
        expected_sha256: Optional[str] = None
    ) -> Tuple[str, ExtensionManifest, str]:
        """
        Comprehensive validation of an extension package

        Args:
            zip_path: Path to the zip file
            expected_sha256: Expected SHA256 hash (optional)

        Returns:
            Tuple of (root_dir, manifest, sha256)

        Raises:
            ValidationError: If any validation fails
        """
        logger.info(f"Starting comprehensive validation for: {zip_path.name}")

        # Calculate and verify SHA256
        actual_sha256 = cls.calculate_sha256(zip_path)
        if expected_sha256 and actual_sha256 != expected_sha256:
            raise ValidationError(
                f"SHA256 mismatch: expected {expected_sha256}, got {actual_sha256}"
            )

        # Validate zip structure and extract manifest
        root_dir, manifest_dict = cls.validate_zip_structure(zip_path)

        # Validate manifest schema
        manifest = cls.validate_manifest(manifest_dict)

        # Validate additional files inside zip
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                # Validate commands.yaml
                if root_dir:
                    commands_path = f"{root_dir}/commands/commands.yaml"
                    plan_path = f"{root_dir}/install/plan.yaml"
                else:
                    commands_path = "commands/commands.yaml"
                    plan_path = "install/plan.yaml"

                commands_data = zf.read(commands_path)

                if len(commands_data) > MAX_YAML_SIZE:
                    raise ValidationError(f"commands.yaml too large")

                try:
                    commands_dict = yaml.safe_load(commands_data)
                    cls.validate_commands_yaml(commands_dict)
                except yaml.YAMLError as e:
                    raise ValidationError(f"Invalid YAML in commands.yaml: {e}")

                # Validate install plan
                plan_data = zf.read(plan_path)

                if len(plan_data) > MAX_YAML_SIZE:
                    raise ValidationError(f"plan.yaml too large")

                try:
                    plan_dict = yaml.safe_load(plan_data)
                    cls.validate_plan_yaml(plan_dict)
                except yaml.YAMLError as e:
                    raise ValidationError(f"Invalid YAML in plan.yaml: {e}")

        except KeyError as e:
            raise ValidationError(f"Missing file in zip: {e}")

        logger.info(
            f"Extension package validation successful: "
            f"{manifest.id} v{manifest.version} (sha256: {actual_sha256[:16]}...)"
        )

        return root_dir, manifest, actual_sha256
