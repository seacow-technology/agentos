"""Web fetch connector for downloading web content.

This connector provides capabilities to fetch content from URLs,
including HTML pages, APIs, and files.
"""

from __future__ import annotations

import hashlib
import ipaddress
import logging
import re
import socket
import tempfile
from datetime import datetime, UTC
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from agentos.core.communication.connectors.base import BaseConnector

logger = logging.getLogger(__name__)


class WebFetchConnector(BaseConnector):
    """Connector for web content fetching operations.

    Supports downloading content from URLs with proper
    error handling and security controls.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize web fetch connector.

        Args:
            config: Configuration including:
                - timeout: Request timeout in seconds (default: 30)
                - max_size: Maximum content size in bytes
                - user_agent: Custom user agent string
                - follow_redirects: Whether to follow redirects (default: True)
        """
        super().__init__(config)
        self.timeout = self.config.get("timeout", 30)
        self.max_size = self.config.get("max_size", 10 * 1024 * 1024)  # 10MB
        self.user_agent = self.config.get("user_agent", "AgentOS/1.0")
        self.follow_redirects = self.config.get("follow_redirects", True)

        # Initialize HTTP client (will be created per request for async context)
        self._client: Optional[httpx.AsyncClient] = None

        # DNS cache for performance (stores domain -> list of IP addresses)
        self._dns_cache: Dict[str, List[str]] = {}

    def validate_url(self, url: str) -> None:
        """Validate URL to prevent SSRF attacks.

        This function implements comprehensive SSRF protection by:
        1. Validating URL scheme (only http/https allowed)
        2. Blocking private IP addresses and ranges
        3. Resolving domain names and validating resolved IPs
        4. Preventing DNS rebinding attacks

        Args:
            url: URL to validate

        Raises:
            ValueError: If URL is invalid or targets forbidden resources

        Blocked ranges:
            - localhost/127.0.0.0/8: Local loopback
            - 169.254.0.0/16: Link-local addresses (cloud metadata)
            - 10.0.0.0/8: Private network (Class A)
            - 172.16.0.0/12: Private network (Class B)
            - 192.168.0.0/16: Private network (Class C)
            - ::1: IPv6 loopback
            - fc00::/7: IPv6 unique local addresses
            - fe80::/10: IPv6 link-local addresses
        """
        if not url:
            raise ValueError("URL cannot be empty")

        # Parse URL
        try:
            parsed = urlparse(url)
        except Exception as e:
            raise ValueError(f"Invalid URL format: {str(e)}")

        # Check scheme - only http and https allowed
        if parsed.scheme not in ["http", "https"]:
            raise ValueError(
                f"Invalid URL scheme: {parsed.scheme}. Only http and https are allowed"
            )

        # Extract hostname
        hostname = parsed.hostname
        if not hostname:
            raise ValueError("URL must contain a valid hostname")

        # Check if hostname is an IP address
        try:
            # Try to parse as IP address directly
            ip_obj = ipaddress.ip_address(hostname)
            self._validate_ip_address(ip_obj, hostname)
            return
        except ValueError:
            # Not an IP address, it's a domain name - continue to DNS resolution
            pass

        # Resolve domain name to IP addresses
        try:
            # Check DNS cache first
            if hostname in self._dns_cache:
                ip_addresses = self._dns_cache[hostname]
            else:
                # Resolve DNS (supports both IPv4 and IPv6)
                addr_info = socket.getaddrinfo(
                    hostname,
                    None,
                    family=socket.AF_UNSPEC,  # Support both IPv4 and IPv6
                    type=socket.SOCK_STREAM
                )

                # Extract unique IP addresses
                ip_addresses = list(set(addr[4][0] for addr in addr_info))

                # Cache for performance
                self._dns_cache[hostname] = ip_addresses

        except socket.gaierror as e:
            raise ValueError(f"Cannot resolve hostname '{hostname}': {str(e)}")
        except Exception as e:
            raise ValueError(f"DNS resolution error for '{hostname}': {str(e)}")

        # Validate all resolved IP addresses
        for ip_str in ip_addresses:
            try:
                # Remove zone ID from IPv6 addresses (e.g., fe80::1%eth0 -> fe80::1)
                ip_str_clean = ip_str.split('%')[0]
                ip_obj = ipaddress.ip_address(ip_str_clean)
                self._validate_ip_address(ip_obj, hostname)
            except ValueError as e:
                # If any IP is blocked, reject the entire request
                raise ValueError(f"Hostname '{hostname}' resolves to forbidden IP {ip_str}: {str(e)}")

    def _validate_ip_address(self, ip_obj: ipaddress.IPv4Address | ipaddress.IPv6Address, hostname: str) -> None:
        """Validate that an IP address is not in a forbidden range.

        Args:
            ip_obj: IP address object to validate
            hostname: Original hostname (for error messages)

        Raises:
            ValueError: If IP address is in a forbidden range
        """
        # Check in specific order: loopback > link-local > private > multicast > reserved
        # This ensures the most specific error messages are shown first

        # Check if IP is loopback (127.0.0.0/8 for IPv4, ::1 for IPv6)
        if ip_obj.is_loopback:
            raise ValueError(
                f"Access to loopback addresses is forbidden: {ip_obj} (hostname: {hostname})"
            )

        # Check if IP is link-local (169.254.0.0/16 for IPv4, fe80::/10 for IPv6)
        if ip_obj.is_link_local:
            raise ValueError(
                f"Access to link-local addresses is forbidden: {ip_obj} (hostname: {hostname}). "
                f"This includes cloud metadata endpoints like 169.254.169.254"
            )

        # Check if IP is private (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16 for IPv4, fc00::/7 for IPv6)
        if ip_obj.is_private:
            raise ValueError(
                f"Access to private IP addresses is forbidden: {ip_obj} (hostname: {hostname})"
            )

        # Check if IP is multicast
        if ip_obj.is_multicast:
            raise ValueError(
                f"Access to multicast addresses is forbidden: {ip_obj} (hostname: {hostname})"
            )

        # Check if IP is reserved
        if ip_obj.is_reserved:
            raise ValueError(
                f"Access to reserved addresses is forbidden: {ip_obj} (hostname: {hostname})"
            )

        # Additional check for IPv4 0.0.0.0/8 (not always caught by is_reserved)
        if isinstance(ip_obj, ipaddress.IPv4Address):
            if ip_obj.packed[0] == 0:
                raise ValueError(
                    f"Access to 0.0.0.0/8 network is forbidden: {ip_obj} (hostname: {hostname})"
                )

        # Additional check for IPv6 unspecified address (::)
        if isinstance(ip_obj, ipaddress.IPv6Address):
            if ip_obj.is_unspecified:
                raise ValueError(
                    f"Access to unspecified IPv6 address is forbidden: {ip_obj} (hostname: {hostname})"
                )

    async def execute(self, operation: str, params: Dict[str, Any]) -> Any:
        """Execute a web fetch operation.

        Args:
            operation: Operation to perform (e.g., "fetch", "download")
            params: Operation parameters

        Returns:
            Fetched content

        Raises:
            ValueError: If operation is not supported
            Exception: If fetch fails
        """
        if not self.enabled:
            raise Exception("Web fetch connector is disabled")

        if operation == "fetch":
            return await self._fetch(params)
        elif operation == "download":
            return await self._download(params)
        else:
            raise ValueError(f"Unsupported operation: {operation}")

    async def _fetch(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch content from a URL.

        Args:
            params: Fetch parameters including:
                - url: URL to fetch
                - method: HTTP method (default: GET)
                - headers: Custom headers
                - timeout: Request timeout
                - body: Request body (for POST/PUT)
                - extract_content: Whether to extract HTML content (default: True)

        Returns:
            Dictionary containing:
                - url: Original URL
                - final_url: Final URL after redirects
                - status_code: HTTP status code
                - content: Response content (raw or extracted)
                - headers: Response headers
                - content_type: Content type
                - content_length: Content length in bytes
                - extracted: Extracted HTML content (if extract_content=True and HTML)

        Raises:
            ValueError: If URL is invalid
            httpx.TimeoutException: If request times out
            httpx.HTTPStatusError: If HTTP error status code
            Exception: For other network errors
        """
        url = params.get("url")
        if not url:
            raise ValueError("URL is required")

        # SSRF protection: validate URL before making any requests
        try:
            self.validate_url(url)
        except ValueError as e:
            logger.warning(f"SSRF protection blocked URL {url}: {str(e)}")
            raise

        method = params.get("method", "GET").upper()
        custom_headers = params.get("headers", {})
        timeout = params.get("timeout", self.timeout)
        body = params.get("body")
        extract_content = params.get("extract_content", True)

        logger.info(f"Fetching content from: {url} (method: {method})")

        # Build headers
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
        }
        headers.update(custom_headers)

        try:
            # Create async HTTP client
            async with httpx.AsyncClient(
                follow_redirects=self.follow_redirects,
                timeout=httpx.Timeout(timeout),
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            ) as client:
                # Make request
                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    content=body if body else None,
                )

                # Check content size
                content_length = int(response.headers.get("content-length", 0))
                if content_length > self.max_size:
                    raise Exception(
                        f"Content size ({content_length} bytes) exceeds maximum "
                        f"allowed size ({self.max_size} bytes)"
                    )

                # Read response content
                content = response.text

                # Check actual content size
                actual_size = len(content.encode("utf-8"))
                if actual_size > self.max_size:
                    raise Exception(
                        f"Content size ({actual_size} bytes) exceeds maximum "
                        f"allowed size ({self.max_size} bytes)"
                    )

                # Raise for HTTP errors
                response.raise_for_status()

                # Build result
                result = {
                    "url": url,
                    "final_url": str(response.url),
                    "status_code": response.status_code,
                    "content": content,
                    "headers": dict(response.headers),
                    "content_type": response.headers.get("content-type", ""),
                    "content_length": actual_size,
                }

                # Extract HTML content if requested
                content_type = response.headers.get("content-type", "").lower()
                if extract_content and "text/html" in content_type:
                    try:
                        extracted = self._extract_html_content(content, str(response.url))
                        result["extracted"] = extracted

                        # Generate structured fetched_document format
                        fetched_document = self._build_fetched_document(
                            url=str(response.url),
                            extracted=extracted,
                            content=content,
                            status_code=response.status_code,
                            content_type=content_type,
                            content_length=actual_size
                        )
                        result["fetched_document"] = fetched_document

                        logger.info(f"Extracted HTML content: {extracted.get('title', 'N/A')}")
                    except Exception as e:
                        logger.warning(f"Failed to extract HTML content: {str(e)}")
                        result["extracted"] = None
                        result["fetched_document"] = None

                logger.info(
                    f"Successfully fetched {actual_size} bytes from {url} "
                    f"(status: {response.status_code})"
                )

                return result

        except httpx.TimeoutException as e:
            logger.error(f"Timeout fetching {url}: {str(e)}")
            raise Exception(f"Request timeout after {timeout} seconds")
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching {url}: {e.response.status_code}")
            raise Exception(f"HTTP {e.response.status_code}: {e.response.reason_phrase}")
        except httpx.RequestError as e:
            logger.error(f"Network error fetching {url}: {str(e)}")
            raise Exception(f"Network error: {str(e)}")
        except Exception as e:
            logger.error(f"Error fetching {url}: {str(e)}")
            raise

    async def _download(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Download a file from a URL.

        Args:
            params: Download parameters including:
                - url: URL to download
                - destination: Local file path to save (optional, uses temp file if not provided)
                - chunk_size: Download chunk size (default: 8192 bytes)

        Returns:
            Dictionary containing:
                - url: Original URL
                - final_url: Final URL after redirects
                - destination: Local file path
                - size: Downloaded file size
                - content_type: Content type
                - headers: Response headers

        Raises:
            ValueError: If URL is invalid
            httpx.TimeoutException: If request times out
            httpx.HTTPStatusError: If HTTP error status code
            Exception: For other network or I/O errors
        """
        url = params.get("url")
        if not url:
            raise ValueError("URL is required")

        # SSRF protection: validate URL before making any requests
        try:
            self.validate_url(url)
        except ValueError as e:
            logger.warning(f"SSRF protection blocked URL {url}: {str(e)}")
            raise

        destination = params.get("destination")
        chunk_size = params.get("chunk_size", 8192)

        # Create temp file if no destination provided
        if not destination:
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=self._get_file_extension(url))
            destination = temp_file.name
            temp_file.close()
            logger.info(f"Using temporary file: {destination}")

        logger.info(f"Downloading file from: {url} to {destination}")

        try:
            total_size = 0

            # Create async HTTP client
            async with httpx.AsyncClient(
                follow_redirects=self.follow_redirects,
                timeout=httpx.Timeout(self.timeout),
            ) as client:
                # Stream download
                async with client.stream("GET", url, headers={"User-Agent": self.user_agent}) as response:
                    # Check content length
                    content_length = int(response.headers.get("content-length", 0))
                    if content_length > self.max_size:
                        raise Exception(
                            f"File size ({content_length} bytes) exceeds maximum "
                            f"allowed size ({self.max_size} bytes)"
                        )

                    # Raise for HTTP errors
                    response.raise_for_status()

                    # Write to file in chunks
                    with open(destination, "wb") as f:
                        async for chunk in response.aiter_bytes(chunk_size=chunk_size):
                            f.write(chunk)
                            total_size += len(chunk)

                            # Check if we exceeded max size
                            if total_size > self.max_size:
                                # Clean up partial file
                                Path(destination).unlink(missing_ok=True)
                                raise Exception(
                                    f"Downloaded size ({total_size} bytes) exceeds maximum "
                                    f"allowed size ({self.max_size} bytes)"
                                )

                    result = {
                        "url": url,
                        "final_url": str(response.url),
                        "destination": destination,
                        "size": total_size,
                        "content_type": response.headers.get("content-type", "application/octet-stream"),
                        "headers": dict(response.headers),
                    }

                    logger.info(f"Successfully downloaded {total_size} bytes to {destination}")
                    return result

        except httpx.TimeoutException as e:
            logger.error(f"Timeout downloading {url}: {str(e)}")
            # Clean up partial file
            Path(destination).unlink(missing_ok=True)
            raise Exception(f"Download timeout after {self.timeout} seconds")
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error downloading {url}: {e.response.status_code}")
            # Clean up partial file
            Path(destination).unlink(missing_ok=True)
            raise Exception(f"HTTP {e.response.status_code}: {e.response.reason_phrase}")
        except httpx.RequestError as e:
            logger.error(f"Network error downloading {url}: {str(e)}")
            # Clean up partial file
            Path(destination).unlink(missing_ok=True)
            raise Exception(f"Network error: {str(e)}")
        except Exception as e:
            logger.error(f"Error downloading {url}: {str(e)}")
            # Clean up partial file if it exists
            if destination:
                Path(destination).unlink(missing_ok=True)
            raise

    def get_supported_operations(self) -> List[str]:
        """Get list of supported operations.

        Returns:
            List of supported operation names
        """
        return ["fetch", "download"]

    def validate_config(self) -> bool:
        """Validate connector configuration.

        Returns:
            True if configuration is valid
        """
        if self.timeout <= 0:
            logger.warning("Timeout must be positive")
            return False
        if self.max_size <= 0:
            logger.warning("Max size must be positive")
            return False
        return True

    def _build_fetched_document(
        self,
        url: str,
        extracted: Dict[str, Any],
        content: str,
        status_code: int,
        content_type: str,
        content_length: int
    ) -> Dict[str, Any]:
        """Build structured fetched_document format.

        This format conforms to ADR-COMM-002 SEARCH→FETCH→BRIEF pipeline
        and ADR-EXTERNAL-INFO-DECLARATION-001 requirements.

        Args:
            url: Source URL
            extracted: Extracted HTML content dictionary
            content: Raw content string
            status_code: HTTP status code
            content_type: Content type header
            content_length: Content length in bytes

        Returns:
            Structured fetched_document dictionary with:
            - type: "fetched_document"
            - trust_tier: Trust level based on domain
            - url: Source URL
            - source_domain: Extracted domain
            - content: Structured content object (NO analytical fields)
            - metadata: Technical metadata only
        """
        # Extract domain from URL
        parsed_url = urlparse(url)
        source_domain = parsed_url.netloc

        # Determine trust tier based on domain
        trust_tier = self._determine_trust_tier(source_domain)

        # Calculate content hash
        content_hash = hashlib.sha256(extracted.get("text", "").encode()).hexdigest()

        # Build body_text (plain text content)
        body_text = extracted.get("text", "")

        # Build sections list
        sections = extracted.get("sections", [])

        # Build references list
        references = extracted.get("references", [])

        # Build structured fetched_document
        fetched_document = {
            "type": "fetched_document",
            "trust_tier": trust_tier,
            "url": url,
            "source_domain": source_domain,
            "content": {
                "title": extracted.get("title", ""),
                "publish_date": extracted.get("publish_date"),
                "author": extracted.get("author"),
                "body_text": body_text,
                "sections": sections,
                "references": references
            },
            "metadata": {
                "fetched_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                "content_hash": content_hash,
                "status_code": status_code,
                "content_type": content_type,
                "content_length": content_length
            }
        }

        return fetched_document

    def _determine_trust_tier(self, domain: str) -> str:
        """Determine trust tier based on source domain.

        Follows ADR-COMM-002 trust tier definitions:
        - AUTHORITATIVE_SOURCE: .gov, .edu, WHO, UN, scientific publishers
        - PRIMARY_SOURCE: Official docs, original publishers, verified sources
        - VERIFIED_SOURCE: General websites (default for fetch stage)

        Args:
            domain: Source domain

        Returns:
            Trust tier string
        """
        domain_lower = domain.lower()

        # Authoritative sources (Tier 3)
        authoritative_domains = [
            ".gov", ".edu", ".mil",
            "who.int", "un.org", "unesco.org",
            "nature.com", "science.org", "springer.com",
            "ieee.org", "acm.org", "nih.gov"
        ]
        if any(auth in domain_lower for auth in authoritative_domains):
            return "authoritative_source"

        # Primary sources (Tier 2) - official documentation sites
        primary_domains = [
            "docs.", "documentation.", "developer.",
            "github.io", "readthedocs.io",
            "python.org", "nodejs.org", "rust-lang.org",
            "w3.org", "ietf.org", "rfc-editor.org"
        ]
        if any(primary in domain_lower for primary in primary_domains):
            return "primary_source"

        # Default: verified_source (general websites)
        return "verified_source"

    def _extract_html_content(self, html: str, url: str) -> Dict[str, Any]:
        """Extract meaningful content from HTML.

        Uses BeautifulSoup to extract title, description, main content,
        and remove boilerplate (navigation, ads, etc.).

        Args:
            html: HTML content
            url: Source URL

        Returns:
            Dictionary containing:
                - title: Page title
                - description: Meta description
                - content: Main content (cleaned)
                - text: Plain text version
                - links: List of links
                - images: List of image URLs
                - author: Author information (if available)
                - publish_date: Publication date (if available)
                - sections: List of section headings and paragraphs
                - references: List of reference links
        """
        soup = BeautifulSoup(html, "html.parser")

        # Extract title
        title = ""
        if soup.title:
            title = soup.title.string.strip() if soup.title.string else ""
        if not title:
            # Try og:title
            og_title = soup.find("meta", property="og:title")
            if og_title and og_title.get("content"):
                title = og_title["content"].strip()

        # Extract description
        description = ""
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content"):
            description = meta_desc["content"].strip()
        if not description:
            # Try og:description
            og_desc = soup.find("meta", property="og:description")
            if og_desc and og_desc.get("content"):
                description = og_desc["content"].strip()

        # Extract author
        author = self._extract_author(soup)

        # Extract publish date
        publish_date = self._extract_publish_date(soup)

        # Remove unwanted elements (scripts, styles, nav, ads, etc.)
        for element in soup(["script", "style", "nav", "footer", "header", "aside", "iframe"]):
            element.decompose()

        # Remove common ad/boilerplate classes and IDs
        ad_patterns = [
            "advertisement", "ad-", "ads-", "banner", "sidebar", "social-share",
            "related-posts", "comments", "footer", "header", "navigation"
        ]
        for pattern in ad_patterns:
            for element in soup.find_all(class_=lambda x: x and pattern in x.lower()):
                element.decompose()
            for element in soup.find_all(id=lambda x: x and pattern in x.lower()):
                element.decompose()

        # Extract main content
        # Try to find main content area
        main_content = None
        for tag in ["main", "article", ["div", {"class": "content"}], ["div", {"id": "content"}]]:
            if isinstance(tag, list):
                main_content = soup.find(tag[0], tag[1])
            else:
                main_content = soup.find(tag)
            if main_content:
                break

        # If no main content found, use body
        if not main_content:
            main_content = soup.find("body")

        # Extract sections (headings and paragraphs)
        sections = self._extract_sections(main_content) if main_content else []

        # Extract text
        content_html = str(main_content) if main_content else ""
        content_text = main_content.get_text(separator="\n", strip=True) if main_content else ""

        # Clean up text (remove multiple newlines)
        lines = [line.strip() for line in content_text.split("\n") if line.strip()]
        content_text = "\n".join(lines)

        # Extract links
        links = []
        for link in soup.find_all("a", href=True):
            href = link["href"]
            text = link.get_text(strip=True)
            if href and not href.startswith("#"):
                links.append({"url": href, "text": text})

        # Extract reference links (typically in footer or reference sections)
        references = self._extract_references(soup)

        # Extract images
        images = []
        for img in soup.find_all("img", src=True):
            src = img["src"]
            alt = img.get("alt", "")
            if src:
                images.append({"url": src, "alt": alt})

        return {
            "title": title,
            "description": description,
            "author": author,
            "publish_date": publish_date,
            "content": content_html[:5000],  # Limit HTML content
            "text": content_text[:10000],  # Limit text content
            "sections": sections[:20],  # Limit number of sections
            "links": links[:50],  # Limit number of links
            "references": references[:30],  # Limit number of references
            "images": images[:20],  # Limit number of images
            "url": url,
        }

    def _extract_author(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract author information from HTML.

        Args:
            soup: BeautifulSoup parsed HTML

        Returns:
            Author name if found, None otherwise
        """
        # Try meta tags first
        author_meta = soup.find("meta", attrs={"name": "author"})
        if author_meta and author_meta.get("content"):
            return author_meta["content"].strip()

        # Try article:author (OpenGraph)
        og_author = soup.find("meta", property="article:author")
        if og_author and og_author.get("content"):
            return og_author["content"].strip()

        # Try schema.org author
        author_schema = soup.find("span", {"itemprop": "author"})
        if author_schema:
            return author_schema.get_text(strip=True)

        # Try common class names
        author_elem = soup.find(class_=lambda x: x and "author" in x.lower() and "name" in x.lower())
        if author_elem:
            return author_elem.get_text(strip=True)

        return None

    def _extract_publish_date(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract publication date from HTML.

        Args:
            soup: BeautifulSoup parsed HTML

        Returns:
            ISO format date string if found, None otherwise
        """
        # Try meta tags first
        date_meta = soup.find("meta", property="article:published_time")
        if date_meta and date_meta.get("content"):
            return self._normalize_date(date_meta["content"])

        # Try published date meta tag
        date_meta = soup.find("meta", attrs={"name": "date"})
        if date_meta and date_meta.get("content"):
            return self._normalize_date(date_meta["content"])

        # Try schema.org datePublished
        date_schema = soup.find("time", {"itemprop": "datePublished"})
        if date_schema and date_schema.get("datetime"):
            return self._normalize_date(date_schema["datetime"])

        # Try time tag
        time_elem = soup.find("time")
        if time_elem and time_elem.get("datetime"):
            return self._normalize_date(time_elem["datetime"])

        return None

    def _normalize_date(self, date_str: str) -> str:
        """Normalize date string to ISO format.

        Args:
            date_str: Date string in various formats

        Returns:
            ISO format date string (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)
        """
        try:
            # Try to parse ISO format first
            if "T" in date_str:
                # ISO datetime format
                dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                return dt.strftime("%Y-%m-%dT%H:%M:%S")
            else:
                # Just date
                return date_str[:10]  # Return first 10 chars (YYYY-MM-DD)
        except Exception:
            # Return as-is if parsing fails
            return date_str

    def _extract_sections(self, content_elem) -> List[Dict[str, str]]:
        """Extract document sections (headings and content).

        Args:
            content_elem: BeautifulSoup element containing main content

        Returns:
            List of sections with heading and content
        """
        sections = []
        if not content_elem:
            return sections

        # Find all heading tags (h1-h6)
        headings = content_elem.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])

        for heading in headings:
            heading_text = heading.get_text(strip=True)
            if not heading_text:
                continue

            # Get content between this heading and the next heading
            content_parts = []
            for sibling in heading.next_siblings:
                if sibling.name and sibling.name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
                    # Stop at next heading
                    break
                if sibling.name == "p":
                    # Extract paragraph text
                    para_text = sibling.get_text(strip=True)
                    if para_text:
                        content_parts.append(para_text)

            if content_parts:
                sections.append({
                    "heading": heading_text,
                    "content": " ".join(content_parts[:3])  # Limit to first 3 paragraphs
                })

        return sections

    def _extract_references(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """Extract reference links from document.

        Args:
            soup: BeautifulSoup parsed HTML

        Returns:
            List of reference links with URL and text
        """
        references = []

        # Try to find reference sections
        ref_sections = soup.find_all(
            lambda tag: tag.name in ["div", "section", "aside"] and
            tag.get("class") and
            any(cls and ("reference" in cls.lower() or "citation" in cls.lower() or "source" in cls.lower())
                for cls in tag.get("class", []))
        )

        # Also check by ID
        if not ref_sections:
            ref_sections = soup.find_all(
                lambda tag: tag.name in ["div", "section", "aside"] and
                tag.get("id") and
                any(keyword in tag.get("id", "").lower() for keyword in ["reference", "citation", "source", "footnote"])
            )

        # Extract links from reference sections
        for section in ref_sections:
            for link in section.find_all("a", href=True):
                href = link["href"]
                text = link.get_text(strip=True)
                if href and not href.startswith("#") and text:
                    references.append({
                        "url": href,
                        "text": text
                    })

        return references

    def _get_file_extension(self, url: str) -> str:
        """Get file extension from URL.

        Args:
            url: URL to extract extension from

        Returns:
            File extension (e.g., '.pdf', '.jpg') or empty string
        """
        try:
            parsed = urlparse(url)
            path = Path(parsed.path)
            extension = path.suffix
            if extension:
                return extension
            return ""
        except Exception:
            return ""
