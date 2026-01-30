"""Installer for extension packages"""

import logging
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Optional, Tuple

from agentos.core.extensions.downloader import URLDownloader
from agentos.core.extensions.exceptions import InstallationError, ValidationError
from agentos.core.extensions.models import ExtensionManifest
from agentos.core.extensions.validator import ExtensionValidator

logger = logging.getLogger(__name__)

# Default installation directory
DEFAULT_EXTENSIONS_DIR = Path.home() / ".agentos" / "extensions"


class ZipInstaller:
    """Installer for extension zip packages"""

    def __init__(
        self,
        extensions_dir: Optional[Path] = None,
        validator: Optional[ExtensionValidator] = None
    ):
        """
        Initialize installer

        Args:
            extensions_dir: Directory to install extensions to
            validator: Extension validator instance
        """
        self.extensions_dir = extensions_dir or DEFAULT_EXTENSIONS_DIR
        self.validator = validator or ExtensionValidator()

    def _get_extension_dir(self, extension_id: str) -> Path:
        """
        Get installation directory for an extension

        Args:
            extension_id: Extension ID

        Returns:
            Path to extension directory
        """
        return self.extensions_dir / extension_id

    def extract_zip(
        self,
        zip_path: Path,
        target_dir: Path,
        root_dir: str
    ) -> None:
        """
        Extract zip to target directory with path traversal protection

        Args:
            zip_path: Path to zip file
            target_dir: Target directory for extraction
            root_dir: Root directory inside zip to strip

        Raises:
            InstallationError: If extraction fails
        """
        logger.info(f"Extracting {zip_path.name} to {target_dir}")

        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            # Resolve target directory to absolute path for security checks
            target_dir_resolved = target_dir.resolve()

            with zipfile.ZipFile(zip_path, 'r') as zf:
                # Extract all files, stripping the root directory if present
                for member in zf.namelist():
                    # Determine relative path based on root_dir
                    if root_dir:
                        # Skip the root directory itself
                        if member == root_dir or member == f"{root_dir}/":
                            continue

                        # Remove root directory prefix
                        if not member.startswith(f"{root_dir}/"):
                            continue  # Skip files not in root_dir
                        relative_path = member[len(root_dir) + 1:]
                    else:
                        # Files are directly in zip root
                        relative_path = member

                    # ADR-EXT-001: Path traversal protection
                    # Check for .. in path
                    if '..' in relative_path:
                        raise InstallationError(
                            f"Path traversal detected in zip: {member}. "
                            "See ADR-EXT-001 for security requirements."
                        )

                    # Check for absolute paths
                    if Path(relative_path).is_absolute():
                        raise InstallationError(
                            f"Absolute path detected in zip: {member}. "
                            "See ADR-EXT-001 for security requirements."
                        )

                    target_path = target_dir / relative_path

                    # ADR-EXT-001: Ensure target path is within target directory
                    target_path_resolved = target_path.resolve()
                    try:
                        target_path_resolved.relative_to(target_dir_resolved)
                    except ValueError:
                        raise InstallationError(
                            f"Zip extraction would escape target directory: {member}. "
                            "See ADR-EXT-001 for security requirements."
                        )

                    # Create parent directories
                    if member.endswith('/'):
                        target_path.mkdir(parents=True, exist_ok=True)
                    else:
                        target_path.parent.mkdir(parents=True, exist_ok=True)

                        # Extract file
                        with zf.open(member) as source, open(target_path, 'wb') as target:
                            shutil.copyfileobj(source, target)

            logger.info(f"Extraction complete: {target_dir}")

        except InstallationError:
            raise
        except Exception as e:
            raise InstallationError(f"Failed to extract zip: {e}")

    def install_from_upload(
        self,
        zip_path: Path,
        expected_sha256: Optional[str] = None
    ) -> Tuple[ExtensionManifest, str, Path]:
        """
        Install extension from uploaded zip file

        Args:
            zip_path: Path to uploaded zip file
            expected_sha256: Expected SHA256 hash (optional)

        Returns:
            Tuple of (manifest, sha256, install_dir)

        Raises:
            ValidationError: If validation fails
            InstallationError: If installation fails
        """
        logger.info(f"Installing extension from upload: {zip_path.name}")

        # Validate package
        try:
            root_dir, manifest, sha256 = self.validator.validate_extension_package(
                zip_path,
                expected_sha256
            )
        except ValidationError as e:
            logger.error(f"Validation failed: {e}")
            raise

        # Check if already installed
        install_dir = self._get_extension_dir(manifest.id)
        if install_dir.exists():
            logger.warning(f"Extension already installed: {manifest.id}")
            raise InstallationError(
                f"Extension '{manifest.id}' is already installed. "
                f"Please uninstall it first."
            )

        # Extract to installation directory
        try:
            self.extract_zip(zip_path, install_dir, root_dir)
            logger.info(f"Extension installed: {manifest.id} v{manifest.version} -> {install_dir}")

            return manifest, sha256, install_dir

        except Exception as e:
            # Clean up on failure
            if install_dir.exists():
                try:
                    shutil.rmtree(install_dir)
                except Exception as cleanup_error:
                    logger.warning(f"Failed to clean up {install_dir}: {cleanup_error}")

            raise InstallationError(f"Installation failed: {e}")

    def install_from_url(
        self,
        url: str,
        expected_sha256: Optional[str] = None
    ) -> Tuple[ExtensionManifest, str, Path]:
        """
        Install extension from URL

        Args:
            url: URL to download zip from
            expected_sha256: Expected SHA256 hash (optional)

        Returns:
            Tuple of (manifest, sha256, install_dir)

        Raises:
            DownloadError: If download fails
            ValidationError: If validation fails
            InstallationError: If installation fails
        """
        logger.info(f"Installing extension from URL: {url}")

        # Create temporary directory for download
        with tempfile.TemporaryDirectory(prefix="agentos_ext_") as temp_dir:
            temp_path = Path(temp_dir) / "extension.zip"

            # Download
            downloader = URLDownloader()
            try:
                actual_sha256 = downloader.download_with_progress(
                    url=url,
                    target_path=temp_path,
                    expected_sha256=expected_sha256
                )
            finally:
                downloader.close()

            # Install from downloaded file
            manifest, sha256, install_dir = self.install_from_upload(
                zip_path=temp_path,
                expected_sha256=actual_sha256
            )

            logger.info(f"Extension installed from URL: {manifest.id} v{manifest.version}")
            return manifest, sha256, install_dir

    def uninstall_extension(self, extension_id: str) -> None:
        """
        Uninstall an extension

        Args:
            extension_id: Extension ID to uninstall

        Raises:
            InstallationError: If uninstallation fails
        """
        install_dir = self._get_extension_dir(extension_id)

        if not install_dir.exists():
            raise InstallationError(f"Extension not found: {extension_id}")

        logger.info(f"Uninstalling extension: {extension_id} from {install_dir}")

        try:
            shutil.rmtree(install_dir)
            logger.info(f"Extension uninstalled: {extension_id}")

        except Exception as e:
            raise InstallationError(f"Failed to uninstall extension: {e}")

    def get_installed_extensions(self) -> list[str]:
        """
        Get list of installed extension IDs

        Returns:
            List of extension IDs
        """
        if not self.extensions_dir.exists():
            return []

        installed = []
        for item in self.extensions_dir.iterdir():
            if item.is_dir() and (item / "manifest.json").exists():
                installed.append(item.name)

        return installed

    def get_extension_manifest(self, extension_id: str) -> Optional[ExtensionManifest]:
        """
        Get manifest for an installed extension

        Args:
            extension_id: Extension ID

        Returns:
            ExtensionManifest or None if not found
        """
        install_dir = self._get_extension_dir(extension_id)
        manifest_path = install_dir / "manifest.json"

        if not manifest_path.exists():
            return None

        try:
            import json
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest_dict = json.load(f)
            return ExtensionManifest(**manifest_dict)
        except Exception as e:
            logger.error(f"Failed to load manifest for {extension_id}: {e}")
            return None
