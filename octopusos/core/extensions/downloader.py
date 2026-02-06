"""URL downloader for extension packages"""

import logging
import time
from pathlib import Path
from typing import Optional, Callable
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from agentos.core.extensions.exceptions import DownloadError
from agentos.core.extensions.validator import ExtensionValidator

logger = logging.getLogger(__name__)

# Download limits
DEFAULT_MAX_SIZE = 50 * 1024 * 1024  # 50MB
DEFAULT_TIMEOUT = 300  # 5 minutes
CHUNK_SIZE = 8192  # 8KB chunks


class URLDownloader:
    """Downloader for extension packages from URLs"""

    def __init__(
        self,
        max_retries: int = 3,
        timeout: int = DEFAULT_TIMEOUT
    ):
        """
        Initialize downloader

        Args:
            max_retries: Maximum number of retry attempts
            timeout: Request timeout in seconds
        """
        self.timeout = timeout

        # Configure session with retry strategy
        self.session = requests.Session()

        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "HEAD"]
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def _validate_url(self, url: str) -> None:
        """
        Validate URL format and scheme

        Args:
            url: URL to validate

        Raises:
            DownloadError: If URL is invalid
        """
        try:
            parsed = urlparse(url)
            if parsed.scheme not in ('http', 'https'):
                raise DownloadError(f"Invalid URL scheme: {parsed.scheme}. Only http/https allowed.")
            if not parsed.netloc:
                raise DownloadError(f"Invalid URL: missing hostname")
        except Exception as e:
            raise DownloadError(f"Invalid URL format: {e}")

    def download(
        self,
        url: str,
        target_path: Path,
        expected_sha256: Optional[str] = None,
        max_size: int = DEFAULT_MAX_SIZE,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> str:
        """
        Download file from URL with validation

        Args:
            url: URL to download from
            target_path: Target file path
            expected_sha256: Expected SHA256 hash for verification (optional)
            max_size: Maximum file size in bytes
            progress_callback: Callback function (downloaded_bytes, total_bytes)

        Returns:
            SHA256 hash of downloaded file

        Raises:
            DownloadError: If download fails
        """
        logger.info(f"Starting download from: {url}")

        self._validate_url(url)

        # Create parent directory
        target_path.parent.mkdir(parents=True, exist_ok=True)

        # Use temporary file during download
        temp_path = target_path.with_suffix(target_path.suffix + '.tmp')

        try:
            # Start download with streaming
            response = self.session.get(
                url,
                stream=True,
                timeout=self.timeout,
                headers={
                    'User-Agent': 'AgentOS-Extension-Downloader/1.0'
                }
            )

            response.raise_for_status()

            # Check content length
            content_length = response.headers.get('Content-Length')
            if content_length:
                total_size = int(content_length)
                if total_size > max_size:
                    raise DownloadError(
                        f"File too large: {total_size / 1024 / 1024:.2f}MB "
                        f"(max: {max_size / 1024 / 1024}MB)"
                    )
            else:
                total_size = 0
                logger.warning("Content-Length header not present, size check disabled")

            # Download with progress tracking
            downloaded_bytes = 0
            start_time = time.time()

            with open(temp_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                    if chunk:  # Filter out keep-alive chunks
                        f.write(chunk)
                        downloaded_bytes += len(chunk)

                        # Enforce size limit even without Content-Length
                        if downloaded_bytes > max_size:
                            raise DownloadError(
                                f"Download exceeded size limit: {downloaded_bytes / 1024 / 1024:.2f}MB"
                            )

                        # Call progress callback
                        if progress_callback:
                            progress_callback(downloaded_bytes, total_size)

            elapsed_time = time.time() - start_time
            speed_mbps = (downloaded_bytes / 1024 / 1024) / elapsed_time if elapsed_time > 0 else 0

            logger.info(
                f"Download complete: {downloaded_bytes / 1024:.2f}KB "
                f"in {elapsed_time:.2f}s ({speed_mbps:.2f} MB/s)"
            )

            # Calculate SHA256
            actual_sha256 = ExtensionValidator.calculate_sha256(temp_path)

            # Verify SHA256 if expected
            if expected_sha256:
                if actual_sha256 != expected_sha256:
                    raise DownloadError(
                        f"SHA256 verification failed: "
                        f"expected {expected_sha256}, got {actual_sha256}"
                    )
                logger.info(f"SHA256 verification passed: {actual_sha256}")

            # Move to final location
            if target_path.exists():
                target_path.unlink()
            temp_path.rename(target_path)

            logger.info(f"File saved to: {target_path}")
            return actual_sha256

        except requests.RequestException as e:
            raise DownloadError(f"Download failed: {e}")

        except Exception as e:
            raise DownloadError(f"Unexpected error during download: {e}")

        finally:
            # Clean up temporary file
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception as e:
                    logger.warning(f"Failed to clean up temporary file {temp_path}: {e}")

    def download_with_progress(
        self,
        url: str,
        target_path: Path,
        expected_sha256: Optional[str] = None,
        max_size: int = DEFAULT_MAX_SIZE
    ) -> str:
        """
        Download with console progress output

        Args:
            url: URL to download from
            target_path: Target file path
            expected_sha256: Expected SHA256 hash
            max_size: Maximum file size

        Returns:
            SHA256 hash of downloaded file
        """
        def progress_callback(downloaded: int, total: int):
            if total > 0:
                percentage = (downloaded / total) * 100
                logger.debug(f"Download progress: {percentage:.1f}% ({downloaded / 1024:.2f}KB / {total / 1024:.2f}KB)")
            else:
                logger.debug(f"Downloaded: {downloaded / 1024:.2f}KB")

        return self.download(
            url=url,
            target_path=target_path,
            expected_sha256=expected_sha256,
            max_size=max_size,
            progress_callback=progress_callback
        )

    def close(self):
        """Close the session"""
        self.session.close()

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
