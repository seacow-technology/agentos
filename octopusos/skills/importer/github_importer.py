"""
GitHub Skill Importer: Download and import skills from GitHub repositories.

Key principles:
1. Server-side fetch: Download via GitHub API (no client-side execution)
2. Read-only: Never execute downloaded code
3. Default disabled: Status is 'imported_disabled' after import
4. Cache management: Store in ~/.agentos/store/skills_cache/<skill_id>/<repo_hash>/
"""

import hashlib
import io
import shutil
import tarfile
import tempfile
import zipfile
from pathlib import Path
from typing import Optional
import logging

import requests

from agentos.skills.manifest import (
    load_manifest,
    validate_manifest,
    normalize_manifest,
)
from agentos.skills.registry import SkillRegistry


logger = logging.getLogger(__name__)


class GitHubFetchError(Exception):
    """Raised when GitHub download fails."""
    pass


class GitHubImporter:
    """Import skills from GitHub repositories."""

    def __init__(self, registry: SkillRegistry, cache_dir: Optional[Path] = None):
        """
        Initialize GitHub importer.

        Args:
            registry: SkillRegistry instance for storing imported skills
            cache_dir: Cache directory for downloaded repositories
                      (default: ~/.agentos/store/skills_cache/)
        """
        self.registry = registry
        self.cache_dir = cache_dir or (Path.home() / ".agentos" / "store" / "skills_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def import_from_github(
        self,
        owner: str,
        repo: str,
        ref: Optional[str] = None,
        subdir: Optional[str] = None
    ) -> str:
        """
        Import a skill from GitHub repository.

        Process:
        1. Download repository tarball from GitHub API
        2. Extract to temporary directory
        3. Navigate to subdir if specified
        4. Locate and validate skill.yaml
        5. Compute repo hash
        6. Move to cache directory
        7. Register in database with status='imported_disabled'

        Args:
            owner: GitHub username or organization
            repo: Repository name
            ref: Branch/tag/commit SHA (default: 'main')
            subdir: Subdirectory path within repo (e.g., 'skills/example')

        Returns:
            skill_id of the imported skill

        Raises:
            GitHubFetchError: Download failed (404, network error)
            FileNotFoundError: skill.yaml not found
            ValueError: Invalid manifest

        Example:
            >>> importer = GitHubImporter(registry)
            >>> skill_id = importer.import_from_github('owner', 'repo', 'main', 'skills/hello')
        """
        if ref is None:
            ref = 'main'

        logger.info(f"Importing skill from GitHub: {owner}/{repo}@{ref}" +
                   (f":{subdir}" if subdir else ""))

        try:
            # Download repository
            temp_dir = self._download_repo(owner, repo, ref)

            # Navigate to subdir if specified
            skill_dir = temp_dir
            if subdir:
                skill_dir = temp_dir / subdir
                if not skill_dir.exists():
                    raise FileNotFoundError(
                        f"Subdirectory not found: {subdir} in {owner}/{repo}@{ref}"
                    )

            # Find manifest
            manifest_file = None
            for name in ["skill.yaml", "manifest.yaml", "skill.yml", "manifest.yml"]:
                candidate = skill_dir / name
                if candidate.exists():
                    manifest_file = candidate
                    break

            if not manifest_file:
                raise FileNotFoundError(
                    f"No skill manifest found in {owner}/{repo}@{ref}" +
                    (f":{subdir}" if subdir else "")
                )

            # Load and validate manifest
            manifest = load_manifest(manifest_file)
            is_valid, errors = validate_manifest(manifest)

            if not is_valid:
                raise ValueError(
                    f"Manifest validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
                )

            # Compute hash
            repo_hash = self._compute_hash(skill_dir)

            # Move to cache
            cache_path = self.cache_dir / manifest.skill_id / repo_hash
            if cache_path.exists():
                logger.info(f"Skill already cached at {cache_path}, skipping copy")
            else:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(skill_dir, cache_path)
                logger.info(f"Cached skill to {cache_path}")

            # Normalize manifest
            manifest_dict = normalize_manifest(manifest)

            # Build source_ref
            source_ref = f"{owner}/{repo}@{ref}"
            if subdir:
                source_ref += f":{subdir}"

            # Register skill
            self.registry.upsert_skill(
                skill_id=manifest.skill_id,
                manifest=manifest_dict,
                source_type='github',
                source_ref=source_ref,
                repo_hash=repo_hash
            )

            logger.info(
                f"Successfully imported skill '{manifest.skill_id}' "
                f"version {manifest.version} from GitHub (status: imported_disabled)"
            )

            return manifest.skill_id

        except requests.exceptions.RequestException as e:
            raise GitHubFetchError(f"Failed to fetch from GitHub: {e}")
        except Exception as e:
            logger.error(f"Import failed: {e}")
            raise

    def _download_repo(self, owner: str, repo: str, ref: str) -> Path:
        """
        Download GitHub repository tarball and extract.

        Uses GitHub API to download repository archive:
        https://api.github.com/repos/{owner}/{repo}/tarball/{ref}

        Args:
            owner: Repository owner
            repo: Repository name
            ref: Git reference (branch/tag/commit)

        Returns:
            Path to extracted temporary directory

        Raises:
            GitHubFetchError: Download or extraction failed
        """
        # Construct download URL
        url = f"https://api.github.com/repos/{owner}/{repo}/tarball/{ref}"

        logger.info(f"Downloading from {url}")

        try:
            # Download with timeout
            response = requests.get(url, timeout=30, stream=True)
            response.raise_for_status()

            # Create temporary directory
            temp_dir = Path(tempfile.mkdtemp(prefix='skill_github_'))

            # GitHub returns tarball
            try:
                # Read response content
                content = response.content

                # Extract tarball
                with tarfile.open(fileobj=io.BytesIO(content), mode='r:gz') as tar:
                    # GitHub tarball has single root directory: {repo}-{commit_sha}
                    # We need to extract and return the content inside it
                    members = tar.getmembers()

                    if not members:
                        raise GitHubFetchError("Downloaded tarball is empty")

                    # Find root directory
                    root_dir = members[0].name.split('/')[0]

                    # Extract all
                    tar.extractall(temp_dir)

                    # Return path to content (inside root directory)
                    extracted_path = temp_dir / root_dir

                    if not extracted_path.exists():
                        raise GitHubFetchError(f"Extraction failed: {extracted_path} not found")

                    return extracted_path

            except (tarfile.TarError, zipfile.BadZipFile) as e:
                raise GitHubFetchError(f"Failed to extract archive: {e}")

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                raise GitHubFetchError(
                    f"Repository or ref not found: {owner}/{repo}@{ref}"
                )
            raise GitHubFetchError(f"HTTP error: {e}")

        except requests.exceptions.Timeout:
            raise GitHubFetchError("Download timeout (30s exceeded)")

        except requests.exceptions.RequestException as e:
            raise GitHubFetchError(f"Network error: {e}")

    def _compute_hash(self, path: Path) -> str:
        """
        Compute recursive hash of directory contents.

        Same algorithm as LocalImporter for consistency.

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

                rel_path = file.relative_to(path)
                files.append(rel_path)

        # Hash file paths and contents
        for rel_path in files:
            hasher.update(str(rel_path).encode('utf-8'))

            file_path = path / rel_path
            try:
                hasher.update(file_path.read_bytes())
            except Exception as e:
                logger.warning(f"Failed to read {file_path}: {e}")
                continue

        return hasher.hexdigest()


__all__ = ["GitHubImporter", "GitHubFetchError"]
