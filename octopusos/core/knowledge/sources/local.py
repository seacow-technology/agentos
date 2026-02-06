"""
Local File Source Implementation
=================================

This module provides a concrete implementation of BaseSource for local file system sources.
It enables scanning and indexing of documents from local directories and files.

Key Features:
    - Supports file:// URI scheme for local paths
    - Recursive directory traversal
    - File type filtering (md, txt, py, json, yaml, etc.)
    - Automatic skipping of hidden files and directories
    - File size limits to prevent memory issues
    - Graceful error handling for unreadable files
    - Comprehensive health checks and validation

Architecture:
    LocalSource implements the three core methods of BaseSource:
    1. validate() - Verify URI and path accessibility
    2. fetch() - Read files and create Document objects
    3. health_check() - Monitor source health and metrics

Usage Example:
    >>> from agentos.core.knowledge.sources.local import LocalSource
    >>>
    >>> # Single file
    >>> source = LocalSource(
    ...     source_id="readme",
    ...     config={
    ...         "uri": "file:///path/to/README.md",
    ...         "options": {}
    ...     }
    ... )
    >>> docs = source.fetch()
    >>>
    >>> # Directory with options
    >>> source = LocalSource(
    ...     source_id="docs",
    ...     config={
    ...         "uri": "file:///path/to/docs",
    ...         "options": {
    ...             "recursive": True,
    ...             "file_types": ["md", "txt"],
    ...             "max_file_size_mb": 10
    ...         }
    ...     }
    ... )
    >>> docs = source.fetch()
"""

import logging
import os
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse

from agentos.core.knowledge.sources.base import (
    BaseSource,
    Document,
    ValidationResult,
    HealthCheckResult,
)

# Configure logging
logger = logging.getLogger(__name__)


class LocalSource(BaseSource):
    """
    Local file system source implementation.

    This class provides access to documents stored in the local file system.
    It supports both single files and directories with recursive traversal.

    Configuration:
        uri (str): File URI in format file:///absolute/path
            - Single file: file:///path/to/document.md
            - Directory: file:///path/to/docs

        options (Dict[str, Any]):
            - recursive (bool): Recursively scan subdirectories. Default: True
            - file_types (List[str]): File extensions to include. Default: ['md', 'txt', 'py', 'json', 'yaml', 'yml', 'rst']
            - max_file_size_mb (int): Maximum file size in MB. Default: 10
            - skip_hidden (bool): Skip hidden files (starting with .). Default: True

    Document Metadata:
        Each fetched document includes:
        - source_id: Source identifier
        - file_path: Absolute path to the file
        - doc_type: File extension (md, txt, py, etc.)
        - mtime: Last modification time in epoch milliseconds
        - size_bytes: File size in bytes
        - uri: Original file:// URI

    Error Handling:
        - Unreadable files are skipped with a warning
        - Encoding errors are handled gracefully
        - Files exceeding size limits are skipped
        - Missing paths return validation failures
        - Permission errors are caught and reported

    Example:
        >>> source = LocalSource(
        ...     source_id="local_001",
        ...     config={
        ...         "uri": "file:///data/documents",
        ...         "options": {
        ...             "recursive": True,
        ...             "file_types": ["md", "txt"],
        ...             "max_file_size_mb": 5
        ...         }
        ...     }
        ... )
        >>>
        >>> # Validate before use
        >>> validation = source.validate()
        >>> if not validation.valid:
        ...     print(f"Configuration error: {validation.error}")
        ...     exit(1)
        >>>
        >>> # Fetch documents
        >>> documents = source.fetch()
        >>> print(f"Fetched {len(documents)} documents")
        >>>
        >>> # Health check
        >>> health = source.health_check()
        >>> if health.healthy:
        ...     print(f"Source healthy: {health.metrics['file_count']} files available")
    """

    # Default file types to scan
    DEFAULT_FILE_TYPES = ['md', 'txt', 'py', 'json', 'yaml', 'yml', 'rst', 'log', 'cfg', 'ini', 'conf', 'sh']

    # Default maximum file size in MB
    DEFAULT_MAX_FILE_SIZE_MB = 10

    def __init__(self, source_id: str, config: Dict[str, Any]):
        """
        Initialize the local source.

        Args:
            source_id (str): Unique identifier for this source instance
            config (Dict[str, Any]): Configuration dictionary containing:
                - uri (str): file:// URI pointing to file or directory
                - options (Dict[str, Any]): Optional configuration parameters
        """
        super().__init__(source_id, config)

        # Parse options with defaults
        self.recursive = self.options.get("recursive", True)
        self.file_types = self.options.get("file_types", self.DEFAULT_FILE_TYPES)
        self.max_file_size_mb = self.options.get("max_file_size_mb", self.DEFAULT_MAX_FILE_SIZE_MB)
        self.skip_hidden = self.options.get("skip_hidden", True)

        # Convert MB to bytes
        self.max_file_size_bytes = self.max_file_size_mb * 1024 * 1024

        # Normalize file types to lowercase without dots
        self.file_types = [ft.lower().lstrip('.') for ft in self.file_types]

        logger.debug(
            f"Initialized LocalSource {source_id}: uri={self.uri}, "
            f"recursive={self.recursive}, file_types={self.file_types}, "
            f"max_size={self.max_file_size_mb}MB"
        )

    def _parse_uri(self) -> Optional[Path]:
        """
        Parse file:// URI to extract local path.

        Returns:
            Path object if URI is valid, None otherwise
        """
        if not self.uri:
            logger.error("URI is not set")
            return None

        if not self.uri.startswith("file://"):
            logger.error(f"Invalid URI scheme: {self.uri} (expected file://)")
            return None

        try:
            # Parse URI and extract path
            parsed = urlparse(self.uri)
            path_str = parsed.path

            # Handle Windows paths (file:///C:/path)
            if path_str.startswith('/') and len(path_str) > 2 and path_str[2] == ':':
                path_str = path_str[1:]  # Remove leading slash for Windows

            path = Path(path_str).resolve()
            return path
        except Exception as e:
            logger.error(f"Failed to parse URI {self.uri}: {e}")
            return None

    def validate(self) -> ValidationResult:
        """
        Validate the source configuration.

        Checks:
            1. URI is present and properly formatted
            2. URI uses file:// scheme
            3. Path exists in the file system
            4. Path is readable (has read permissions)

        Returns:
            ValidationResult: Object indicating whether configuration is valid
                - valid=True if all checks pass
                - valid=False with error message if any check fails

        Example:
            >>> result = source.validate()
            >>> if not result.valid:
            ...     print(f"Validation failed: {result.error}")
        """
        try:
            # Check URI is present
            if not self.uri:
                return ValidationResult(
                    valid=False,
                    error="Missing required field 'uri' in configuration"
                )

            # Check URI scheme
            if not self.uri.startswith("file://"):
                return ValidationResult(
                    valid=False,
                    error=f"Invalid URI scheme: {self.uri} (expected file://)"
                )

            # Parse URI to get path
            path = self._parse_uri()
            if path is None:
                return ValidationResult(
                    valid=False,
                    error=f"Failed to parse URI: {self.uri}"
                )

            # Check path exists
            if not path.exists():
                return ValidationResult(
                    valid=False,
                    error=f"Path does not exist: {path}"
                )

            # Check read permission
            if not os.access(path, os.R_OK):
                return ValidationResult(
                    valid=False,
                    error=f"No read permission for path: {path}"
                )

            logger.info(f"LocalSource {self.source_id} validation successful: {path}")
            return ValidationResult(valid=True)

        except Exception as e:
            logger.error(f"Validation error for LocalSource {self.source_id}: {e}")
            return ValidationResult(
                valid=False,
                error=f"Validation exception: {str(e)}"
            )

    def fetch(self) -> List[Document]:
        """
        Fetch documents from the local file system.

        Process:
            1. Parse and validate the URI
            2. Determine if path is a file or directory
            3. Collect all matching files (respecting filters)
            4. Read each file and create Document objects
            5. Skip files that fail to read or exceed size limits

        Returns:
            List[Document]: List of documents with content and metadata.
                Returns empty list if path is invalid or no files match filters.

        Notes:
            - Hidden files are skipped if skip_hidden=True
            - Files exceeding max_file_size_mb are skipped
            - Binary files or files with encoding errors are skipped
            - Each error is logged but doesn't prevent processing other files

        Example:
            >>> docs = source.fetch()
            >>> for doc in docs:
            ...     print(f"File: {doc.metadata['file_path']}")
            ...     print(f"Type: {doc.metadata['doc_type']}")
            ...     print(f"Size: {doc.metadata['size_bytes']} bytes")
        """
        documents = []

        try:
            # Parse URI
            path = self._parse_uri()
            if path is None:
                logger.error(f"Failed to parse URI for LocalSource {self.source_id}")
                return []

            # Check path exists
            if not path.exists():
                logger.error(f"Path does not exist for LocalSource {self.source_id}: {path}")
                return []

            # Collect files to process
            files_to_process = []

            if path.is_file():
                # Single file
                files_to_process.append(path)
            elif path.is_dir():
                # Directory - collect all matching files
                files_to_process = self._collect_files(path)
            else:
                logger.warning(f"Path is neither file nor directory: {path}")
                return []

            # Process each file
            for file_path in files_to_process:
                doc = self._process_file(file_path)
                if doc:
                    documents.append(doc)

            logger.info(
                f"LocalSource {self.source_id} fetched {len(documents)} documents "
                f"from {len(files_to_process)} files"
            )

        except Exception as e:
            logger.error(f"Error fetching documents from LocalSource {self.source_id}: {e}")

        return documents

    def _collect_files(self, directory: Path) -> List[Path]:
        """
        Collect all files from a directory matching the filters.

        Args:
            directory (Path): Directory to scan

        Returns:
            List[Path]: List of file paths matching the criteria
        """
        files = []

        try:
            if self.recursive:
                # Recursive traversal
                for root, dirs, filenames in os.walk(directory):
                    root_path = Path(root)

                    # Skip hidden directories if configured
                    if self.skip_hidden:
                        dirs[:] = [d for d in dirs if not d.startswith('.')]

                    for filename in filenames:
                        file_path = root_path / filename
                        if self._should_include_file(file_path):
                            files.append(file_path)
            else:
                # Non-recursive - only immediate children
                for item in directory.iterdir():
                    if item.is_file() and self._should_include_file(item):
                        files.append(item)

        except Exception as e:
            logger.error(f"Error collecting files from {directory}: {e}")

        return files

    def _should_include_file(self, file_path: Path) -> bool:
        """
        Determine if a file should be included based on filters.

        Args:
            file_path (Path): File to check

        Returns:
            bool: True if file should be included, False otherwise
        """
        # Skip hidden files if configured
        if self.skip_hidden and file_path.name.startswith('.'):
            return False

        # Check file extension
        file_ext = file_path.suffix.lstrip('.').lower()
        if file_ext not in self.file_types:
            return False

        return True

    def _process_file(self, file_path: Path) -> Optional[Document]:
        """
        Process a single file and create a Document.

        Args:
            file_path (Path): Path to the file

        Returns:
            Document if successful, None if file cannot be processed
        """
        try:
            # Check file size
            file_size = file_path.stat().st_size
            if file_size > self.max_file_size_bytes:
                logger.warning(
                    f"Skipping file exceeding size limit ({file_size} > {self.max_file_size_bytes}): "
                    f"{file_path}"
                )
                return None

            # Read file content
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except UnicodeDecodeError:
                # Try with different encoding
                logger.warning(f"UTF-8 decode failed, trying latin-1 for: {file_path}")
                try:
                    with open(file_path, 'r', encoding='latin-1') as f:
                        content = f.read()
                except Exception as e:
                    logger.warning(f"Failed to read file with latin-1 encoding: {file_path}: {e}")
                    return None

            # Get file metadata
            stat = file_path.stat()
            mtime_ms = int(stat.st_mtime * 1000)  # Convert to milliseconds
            file_ext = file_path.suffix.lstrip('.').lower()

            # Create document
            document = Document(
                content=content,
                metadata={
                    "source_id": self.source_id,
                    "file_path": str(file_path.resolve()),
                    "doc_type": file_ext,
                    "mtime": mtime_ms,
                    "size_bytes": file_size,
                    "uri": self.uri,
                }
            )

            logger.debug(f"Processed file: {file_path} ({file_size} bytes)")
            return document

        except Exception as e:
            logger.warning(f"Error processing file {file_path}: {e}")
            return None

    def health_check(self) -> HealthCheckResult:
        """
        Perform a health check on the local source.

        Checks:
            1. Path still exists
            2. Path is still readable
            3. Count available files
            4. Measure disk usage

        Returns:
            HealthCheckResult: Object containing health status and metrics
                - healthy=True if source is operational
                - healthy=False if source has issues
                - metrics includes: file_count, disk_usage_mb, path_exists, readable

        Example:
            >>> result = source.health_check()
            >>> if result.healthy:
            ...     print(f"Files available: {result.metrics['file_count']}")
            ...     print(f"Disk usage: {result.metrics['disk_usage_mb']} MB")
        """
        metrics = {}

        try:
            # Parse URI
            path = self._parse_uri()
            if path is None:
                return HealthCheckResult(
                    healthy=False,
                    metrics=metrics,
                    error="Failed to parse URI"
                )

            # Check path exists
            path_exists = path.exists()
            metrics["path_exists"] = path_exists

            if not path_exists:
                return HealthCheckResult(
                    healthy=False,
                    metrics=metrics,
                    error=f"Path no longer exists: {path}"
                )

            # Check readable
            readable = os.access(path, os.R_OK)
            metrics["readable"] = readable

            if not readable:
                return HealthCheckResult(
                    healthy=False,
                    metrics=metrics,
                    error=f"No read permission for path: {path}"
                )

            # Count available files
            if path.is_file():
                file_count = 1 if self._should_include_file(path) else 0
                disk_path = path.parent
            else:
                files = self._collect_files(path)
                file_count = len(files)
                disk_path = path

            metrics["file_count"] = file_count

            # Get disk usage
            try:
                usage = shutil.disk_usage(disk_path)
                metrics["disk_usage_mb"] = round(usage.used / (1024 * 1024), 2)
                metrics["disk_free_mb"] = round(usage.free / (1024 * 1024), 2)
                metrics["disk_total_mb"] = round(usage.total / (1024 * 1024), 2)
            except Exception as e:
                logger.warning(f"Failed to get disk usage: {e}")
                metrics["disk_usage_mb"] = 0

            logger.info(
                f"LocalSource {self.source_id} health check: "
                f"{file_count} files available, {metrics.get('disk_usage_mb', 0)} MB disk usage"
            )

            return HealthCheckResult(
                healthy=True,
                metrics=metrics
            )

        except Exception as e:
            logger.error(f"Health check error for LocalSource {self.source_id}: {e}")
            return HealthCheckResult(
                healthy=False,
                metrics=metrics,
                error=f"Health check exception: {str(e)}"
            )
