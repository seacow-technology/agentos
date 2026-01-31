"""
Local Skill Importer: Import skills from local filesystem.

Key principles:
1. Read-only operations: Never execute imported code
2. Default disabled: Imported skills start as 'imported_disabled'
3. Hash verification: Compute directory hash for change detection
"""

import hashlib
import json
from pathlib import Path
from typing import Optional
import logging

from agentos.skills.manifest import (
    load_manifest,
    validate_manifest,
    normalize_manifest,
)
from agentos.skills.registry import SkillRegistry


logger = logging.getLogger(__name__)


class LocalImporter:
    """Import skills from local filesystem paths."""

    def __init__(self, registry: SkillRegistry):
        """
        Initialize local importer.

        Args:
            registry: SkillRegistry instance for storing imported skills
        """
        self.registry = registry

    def import_from_path(self, path: str) -> str:
        """
        Import a skill from local filesystem.

        Process:
        1. Locate skill.yaml in the directory
        2. Load and validate manifest
        3. Compute directory hash
        4. Copy skill files to cache
        5. Register in database with status='imported_disabled'

        Args:
            path: Path to skill directory containing skill.yaml

        Returns:
            skill_id of the imported skill

        Raises:
            FileNotFoundError: skill.yaml not found or path does not exist
            ValueError: Invalid manifest
        """
        skill_path = Path(path).resolve()

        if not skill_path.exists():
            raise FileNotFoundError(f"Skill path does not exist: {skill_path}")

        if not skill_path.is_dir():
            raise ValueError(f"Skill path must be a directory: {skill_path}")

        # Find manifest file (skill.yaml or manifest.yaml)
        manifest_file = None
        for name in ["skill.yaml", "manifest.yaml", "skill.yml", "manifest.yml"]:
            candidate = skill_path / name
            if candidate.exists():
                manifest_file = candidate
                break

        if not manifest_file:
            raise FileNotFoundError(
                f"No skill manifest found in {skill_path}. "
                "Expected skill.yaml or manifest.yaml"
            )

        logger.info(f"Loading manifest from {manifest_file}")

        # Load and validate manifest
        manifest = load_manifest(manifest_file)
        is_valid, errors = validate_manifest(manifest)

        if not is_valid:
            raise ValueError(
                f"Manifest validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
            )

        # Compute directory hash
        repo_hash = self._compute_hash(skill_path)

        # Normalize manifest for storage
        manifest_dict = normalize_manifest(manifest)

        # Register skill
        self.registry.upsert_skill(
            skill_id=manifest.skill_id,
            manifest=manifest_dict,
            source_type='local',
            source_ref=str(skill_path),
            repo_hash=repo_hash
        )

        logger.info(
            f"Successfully imported skill '{manifest.skill_id}' "
            f"version {manifest.version} (status: imported_disabled)"
        )

        return manifest.skill_id

    def _compute_hash(self, path: Path) -> str:
        """
        Compute recursive hash of directory contents.

        Includes:
        - File paths (relative to directory)
        - File contents (binary)

        Excludes:
        - .git directory
        - __pycache__
        - *.pyc files
        - .DS_Store

        Args:
            path: Directory path

        Returns:
            SHA-256 hash hex string
        """
        hasher = hashlib.sha256()

        # Collect all files (sorted for deterministic hash)
        files = []
        for file in sorted(path.rglob('*')):
            if file.is_file():
                # Skip excluded patterns
                if any(exclude in file.parts for exclude in ['.git', '__pycache__', '.DS_Store']):
                    continue
                if file.suffix == '.pyc':
                    continue

                # Add relative path and content
                rel_path = file.relative_to(path)
                files.append(rel_path)

        # Hash file paths and contents
        for rel_path in files:
            # Hash path
            hasher.update(str(rel_path).encode('utf-8'))

            # Hash content
            file_path = path / rel_path
            try:
                hasher.update(file_path.read_bytes())
            except Exception as e:
                logger.warning(f"Failed to read {file_path}: {e}")
                continue

        return hasher.hexdigest()


__all__ = ["LocalImporter"]
