"""Tests for Web Fetch Connector.

This module tests the web content fetching functionality,
including HTTP requests, content extraction, and error handling.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
import httpx

from agentos.core.communication.connectors.web_fetch import WebFetchConnector


class TestWebFetchConnector:
    """Test suite for WebFetchConnector."""

    def setup_method(self):
        """Set up test fixtures."""
        self.connector = WebFetchConnector()

    def test_connector_initialization(self):
        """Test connector initialization with default config."""
        assert self.connector.enabled is True
        assert self.connector.timeout == 30
        assert self.connector.max_size == 10 * 1024 * 1024
        assert self.connector.follow_redirects is True

    def test_connector_custom_config(self):
        """Test connector initialization with custom config."""
        config = {
            "timeout": 60,
            "max_size": 5 * 1024 * 1024,
            "user_agent": "CustomBot/1.0",
            "follow_redirects": False,
        }
        connector = WebFetchConnector(config)
        assert connector.timeout == 60
        assert connector.max_size == 5 * 1024 * 1024
        assert connector.user_agent == "CustomBot/1.0"
        assert connector.follow_redirects is False

    def test_get_supported_operations(self):
        """Test getting supported operations."""
        operations = self.connector.get_supported_operations()
        assert "fetch" in operations
        assert "download" in operations
        assert len(operations) == 2

    def test_validate_config(self):
        """Test configuration validation."""
        assert self.connector.validate_config() is True

        # Invalid timeout
        invalid_connector = WebFetchConnector({"timeout": -1})
        assert invalid_connector.validate_config() is False

        # Invalid max_size
        invalid_connector2 = WebFetchConnector({"max_size": 0})
        assert invalid_connector2.validate_config() is False

    @pytest.mark.asyncio
    async def test_execute_invalid_operation(self):
        """Test executing invalid operation."""
        with pytest.raises(ValueError, match="Unsupported operation"):
            await self.connector.execute("invalid_op", {})

    @pytest.mark.asyncio
    async def test_execute_when_disabled(self):
        """Test executing when connector is disabled."""
        self.connector.disable()
        with pytest.raises(Exception, match="disabled"):
            await self.connector.execute("fetch", {"url": "https://example.com"})

    @pytest.mark.asyncio
    async def test_fetch_missing_url(self):
        """Test fetch operation without URL parameter."""
        with pytest.raises(ValueError, match="URL is required"):
            await self.connector.execute("fetch", {})

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_fetch_success(self, mock_client_class):
        """Test successful fetch operation."""
        # Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "<html><head><title>Test Page</title></head><body>Test content</body></html>"
        mock_response.url = "https://example.com"
        mock_response.headers = {
            "content-type": "text/html",
            "content-length": "100",
        }
        mock_response.raise_for_status = Mock()

        # Mock client
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        # Execute fetch
        result = await self.connector.execute("fetch", {
            "url": "https://example.com",
        })

        # Verify result
        assert result["url"] == "https://example.com"
        assert result["status_code"] == 200
        assert "Test content" in result["content"]
        assert result["content_type"] == "text/html"
        assert "extracted" in result

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_fetch_with_custom_headers(self, mock_client_class):
        """Test fetch with custom headers."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "Response"
        mock_response.url = "https://example.com"
        mock_response.headers = {"content-type": "text/plain"}
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        custom_headers = {"Authorization": "Bearer token123"}
        await self.connector.execute("fetch", {
            "url": "https://example.com",
            "headers": custom_headers,
        })

        # Verify custom headers were included
        call_args = mock_client.request.call_args
        assert call_args is not None
        headers_used = call_args.kwargs["headers"]
        assert "Authorization" in headers_used
        assert headers_used["Authorization"] == "Bearer token123"

    @pytest.mark.asyncio
    @patch("socket.getaddrinfo")
    @patch("httpx.AsyncClient")
    async def test_fetch_post_request(self, mock_client_class, mock_getaddrinfo):
        """Test POST request with body."""
        # Mock DNS resolution to return a public IP
        import socket
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('93.184.216.34', 443))
        ]

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '{"success": true}'
        mock_response.url = "https://api.example.com"
        mock_response.headers = {"content-type": "application/json"}
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        result = await self.connector.execute("fetch", {
            "url": "https://api.example.com",
            "method": "POST",
            "body": '{"data": "test"}',
        })

        # Verify POST method was used
        call_args = mock_client.request.call_args
        assert call_args.kwargs["method"] == "POST"
        assert call_args.kwargs["content"] == '{"data": "test"}'
        assert result["status_code"] == 200

    @pytest.mark.asyncio
    @patch("socket.getaddrinfo")
    @patch("httpx.AsyncClient")
    async def test_fetch_timeout(self, mock_client_class, mock_getaddrinfo):
        """Test fetch operation timeout."""
        # Mock DNS resolution to return a public IP
        import socket
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('93.184.216.34', 443))
        ]

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.request = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
        mock_client_class.return_value = mock_client

        with pytest.raises(Exception, match="timeout"):
            await self.connector.execute("fetch", {"url": "https://slow-site.com"})

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_fetch_http_error(self, mock_client_class):
        """Test fetch operation HTTP error."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.reason_phrase = "Not Found"

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.request = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "404 Not Found",
                request=Mock(),
                response=mock_response
            )
        )
        mock_client_class.return_value = mock_client

        with pytest.raises(Exception, match="HTTP 404"):
            await self.connector.execute("fetch", {"url": "https://example.com/notfound"})

    @pytest.mark.asyncio
    @patch("socket.getaddrinfo")
    @patch("httpx.AsyncClient")
    async def test_fetch_network_error(self, mock_client_class, mock_getaddrinfo):
        """Test fetch operation network error."""
        # Mock DNS resolution to return a public IP
        import socket
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('93.184.216.34', 443))
        ]

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.request = AsyncMock(
            side_effect=httpx.RequestError("Connection failed")
        )
        mock_client_class.return_value = mock_client

        with pytest.raises(Exception, match="Network error"):
            await self.connector.execute("fetch", {"url": "https://unreachable.com"})

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_fetch_content_too_large(self, mock_client_class):
        """Test fetch with content exceeding max size."""
        # Create large content (11MB)
        large_content = "x" * (11 * 1024 * 1024)

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = large_content
        mock_response.url = "https://example.com"
        mock_response.headers = {
            "content-type": "text/plain",
            "content-length": str(len(large_content)),
        }
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        with pytest.raises(Exception, match="exceeds maximum"):
            await self.connector.execute("fetch", {"url": "https://example.com"})

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_fetch_html_extraction(self, mock_client_class):
        """Test HTML content extraction."""
        html_content = """
        <html>
        <head>
            <title>Test Page</title>
            <meta name="description" content="Test description">
        </head>
        <body>
            <nav>Navigation</nav>
            <main>
                <h1>Main Title</h1>
                <p>This is the main content.</p>
                <a href="https://example.com">Link</a>
                <img src="image.jpg" alt="Test image">
            </main>
            <script>alert('test');</script>
        </body>
        </html>
        """

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html_content
        mock_response.url = "https://example.com"
        mock_response.headers = {"content-type": "text/html"}
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        result = await self.connector.execute("fetch", {
            "url": "https://example.com",
            "extract_content": True,
        })

        # Verify extraction
        assert "extracted" in result
        extracted = result["extracted"]
        assert extracted["title"] == "Test Page"
        assert extracted["description"] == "Test description"
        assert "Main Title" in extracted["text"]
        assert len(extracted["links"]) > 0
        assert len(extracted["images"]) > 0

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_download_missing_url(self, mock_client_class):
        """Test download without URL parameter."""
        with pytest.raises(ValueError, match="URL is required"):
            await self.connector.execute("download", {})

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    @patch("tempfile.NamedTemporaryFile")
    @patch("builtins.open", create=True)
    async def test_download_success(self, mock_open, mock_tempfile, mock_client_class):
        """Test successful download operation."""
        # Mock temp file
        mock_temp = Mock()
        mock_temp.name = "/tmp/test_download.pdf"
        mock_tempfile.return_value = mock_temp

        # Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.url = "https://example.com/file.pdf"
        mock_response.headers = {
            "content-type": "application/pdf",
            "content-length": "1024",
        }
        mock_response.raise_for_status = Mock()

        # Mock streaming
        async def mock_aiter_bytes(chunk_size):
            yield b"chunk1"
            yield b"chunk2"

        mock_response.aiter_bytes = mock_aiter_bytes

        # Mock client
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.stream = Mock()
        mock_stream_ctx = AsyncMock()
        mock_stream_ctx.__aenter__.return_value = mock_response
        mock_stream_ctx.__aexit__.return_value = None
        mock_client.stream.return_value = mock_stream_ctx
        mock_client_class.return_value = mock_client

        # Mock file operations
        mock_file = Mock()
        mock_open.return_value.__enter__.return_value = mock_file

        result = await self.connector.execute("download", {
            "url": "https://example.com/file.pdf",
        })

        # Verify result
        assert result["url"] == "https://example.com/file.pdf"
        assert result["size"] == 12  # len("chunk1") + len("chunk2")
        assert result["content_type"] == "application/pdf"

    def test_get_file_extension(self):
        """Test file extension extraction from URL."""
        assert self.connector._get_file_extension("https://example.com/file.pdf") == ".pdf"
        assert self.connector._get_file_extension("https://example.com/image.jpg") == ".jpg"
        assert self.connector._get_file_extension("https://example.com/page") == ""
        assert self.connector._get_file_extension("https://example.com/") == ""


class TestHTMLExtraction:
    """Test suite for HTML content extraction."""

    def setup_method(self):
        """Set up test fixtures."""
        self.connector = WebFetchConnector()

    def test_extract_title(self):
        """Test title extraction."""
        html = "<html><head><title>Test Title</title></head><body></body></html>"
        result = self.connector._extract_html_content(html, "https://example.com")
        assert result["title"] == "Test Title"

    def test_extract_og_title(self):
        """Test OpenGraph title extraction."""
        html = '<html><head><meta property="og:title" content="OG Title"></head><body></body></html>'
        result = self.connector._extract_html_content(html, "https://example.com")
        assert result["title"] == "OG Title"

    def test_extract_description(self):
        """Test meta description extraction."""
        html = '<html><head><meta name="description" content="Test description"></head><body></body></html>'
        result = self.connector._extract_html_content(html, "https://example.com")
        assert result["description"] == "Test description"

    def test_extract_links(self):
        """Test link extraction."""
        html = """
        <html><body>
            <a href="https://example.com/page1">Page 1</a>
            <a href="https://example.com/page2">Page 2</a>
            <a href="#fragment">Fragment</a>
        </body></html>
        """
        result = self.connector._extract_html_content(html, "https://example.com")
        # Fragment links should be excluded
        assert len(result["links"]) == 2
        assert any(link["url"] == "https://example.com/page1" for link in result["links"])

    def test_extract_images(self):
        """Test image extraction."""
        html = """
        <html><body>
            <img src="image1.jpg" alt="Image 1">
            <img src="image2.png" alt="Image 2">
        </body></html>
        """
        result = self.connector._extract_html_content(html, "https://example.com")
        assert len(result["images"]) == 2
        assert result["images"][0]["url"] == "image1.jpg"
        assert result["images"][0]["alt"] == "Image 1"

    def test_remove_scripts_and_styles(self):
        """Test removal of scripts and styles."""
        html = """
        <html><body>
            <p>Content</p>
            <script>alert('test');</script>
            <style>.test { color: red; }</style>
        </body></html>
        """
        result = self.connector._extract_html_content(html, "https://example.com")
        assert "alert" not in result["text"]
        assert "color: red" not in result["text"]
        assert "Content" in result["text"]

    def test_remove_navigation(self):
        """Test removal of navigation elements."""
        html = """
        <html><body>
            <nav><a href="/">Home</a></nav>
            <main>Main content</main>
            <footer>Footer content</footer>
        </body></html>
        """
        result = self.connector._extract_html_content(html, "https://example.com")
        # Navigation and footer should be removed
        assert "Main content" in result["text"]
