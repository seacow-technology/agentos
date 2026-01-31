"""Communication adapter for Chat and CommunicationService integration.

This module provides an adapter layer between Chat commands and CommunicationOS,
ensuring proper evidence tracking, attribution, and trust tier propagation.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from agentos.core.communication.service import CommunicationService
from agentos.core.time import utc_now_iso
from agentos.core.communication.models import (
    ConnectorType,
    RequestStatus,
    TrustTier,
)
from agentos.core.communication.connectors.web_search import WebSearchConnector
from agentos.core.communication.connectors.web_fetch import WebFetchConnector

logger = logging.getLogger(__name__)


class SSRFBlockedError(Exception):
    """Exception raised when SSRF protection blocks a request."""
    pass


class RateLimitError(Exception):
    """Exception raised when rate limit is exceeded."""

    def __init__(self, message: str, retry_after: int = 60):
        """Initialize rate limit error.

        Args:
            message: Error message
            retry_after: Seconds to wait before retry
        """
        super().__init__(message)
        self.retry_after = retry_after


class CommunicationAdapter:
    """Adapter between Chat and CommunicationService.

    Provides a Chat-friendly interface to CommunicationOS while ensuring:
    - Proper evidence tracking
    - Attribution to CommunicationOS
    - Trust tier propagation
    - Audit trail linkage
    """

    def __init__(self):
        """Initialize the communication adapter."""
        # Initialize CommunicationService with default components
        self.service = CommunicationService()

        # Register connectors
        self._register_connectors()

        logger.info("CommunicationAdapter initialized")

    def _register_connectors(self) -> None:
        """Register default connectors."""
        # Register web search connector
        search_connector = WebSearchConnector(config={
            "engine": "duckduckgo",
            "max_results": 10,
            "timeout": 30,
        })
        self.service.register_connector(ConnectorType.WEB_SEARCH, search_connector)

        # Register web fetch connector
        fetch_connector = WebFetchConnector(config={
            "timeout": 60,
            "max_size": 10 * 1024 * 1024,  # 10MB
            "follow_redirects": True,
        })
        self.service.register_connector(ConnectorType.WEB_FETCH, fetch_connector)

        logger.info("Registered WebSearch and WebFetch connectors")

    async def search(
        self,
        query: str,
        session_id: str,
        task_id: str,
        max_results: int = 10,
        **kwargs
    ) -> Dict[str, Any]:
        """Execute web search and return Chat-friendly results.

        Args:
            query: Search query string
            session_id: Chat session ID
            task_id: Task ID for context
            max_results: Maximum number of results to return
            **kwargs: Additional search parameters

        Returns:
            Dictionary with search results and metadata including:
            - results: List of search results with title, url, snippet
            - metadata: Attribution, trust tier, audit info
        """
        try:
            # Build request parameters
            params = {
                "query": query,
                "max_results": max_results,
            }
            params.update(kwargs)

            # Build context
            context = {
                "session_id": session_id,
                "task_id": task_id,
            }

            # Execute search via CommunicationService
            response = await self.service.execute(
                connector_type=ConnectorType.WEB_SEARCH,
                operation="search",
                params=params,
                context=context,
                execution_phase="execution",  # Chat commands are in execution phase
            )

            # Check response status
            if response.status != RequestStatus.SUCCESS:
                return self._handle_error_response(response, session_id)

            # Extract search results from response
            data = response.data or {}
            results = data.get("results", [])

            # Add trust tier to each result
            for result in results:
                result["trust_tier"] = TrustTier.SEARCH_RESULT.value

            # Build Chat-friendly response
            return {
                "results": results,
                "metadata": {
                    "query": query,
                    "total_results": len(results),
                    "trust_tier_warning": "搜索结果是候选来源,不是验证事实",
                    "attribution": f"CommunicationOS (search) in session {session_id}",
                    "retrieved_at": utc_now_iso(),
                    "audit_id": response.evidence_id,
                    "engine": data.get("engine", "unknown"),
                }
            }

        except Exception as e:
            logger.error(f"Search failed: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "message": str(e),
                "metadata": {
                    "attribution": f"CommunicationOS (search) in session {session_id}",
                }
            }

    async def fetch(
        self,
        url: str,
        session_id: str,
        task_id: str,
        extract_content: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """Fetch URL content and return Chat-friendly results.

        Args:
            url: URL to fetch
            session_id: Chat session ID
            task_id: Task ID for context
            extract_content: Whether to extract HTML content
            **kwargs: Additional fetch parameters

        Returns:
            Dictionary with fetched content and metadata including:
            - status: Operation status
            - content: Extracted content (title, text, links, images)
            - metadata: Trust tier, citations, attribution, audit info
        """
        try:
            # Build request parameters
            params = {
                "url": url,
                "extract_content": extract_content,
            }
            params.update(kwargs)

            # Build context
            context = {
                "session_id": session_id,
                "task_id": task_id,
            }

            # Execute fetch via CommunicationService
            response = await self.service.execute(
                connector_type=ConnectorType.WEB_FETCH,
                operation="fetch",
                params=params,
                context=context,
                execution_phase="execution",  # Chat commands are in execution phase
            )

            # Check response status
            if response.status != RequestStatus.SUCCESS:
                return self._handle_error_response(response, session_id)

            # Extract fetch result from response
            data = response.data or {}

            # Determine trust tier (upgraded from SEARCH_RESULT)
            trust_tier = self._determine_trust_tier(url)

            # Build content object
            extracted = data.get("extracted", {})
            content = {
                "title": extracted.get("title", ""),
                "description": extracted.get("description", ""),
                "text": extracted.get("text", ""),
                "links": extracted.get("links", []),
                "images": extracted.get("images", []),
            }

            # Calculate content hash for verification
            content_hash = self._calculate_content_hash(content["text"])

            # Build citations
            citations = {
                "url": url,
                "title": content["title"],
                "author": self._extract_author(url, extracted),
                "publish_date": self._extract_publish_date(extracted),
                "retrieved_at": utc_now_iso(),
            }

            # Build Chat-friendly response
            return {
                "status": "success",
                "url": url,
                "content": content,
                "metadata": {
                    "trust_tier": trust_tier.value,
                    "content_hash": content_hash,
                    "retrieved_at": utc_now_iso(),
                    "citations": citations,
                    "attribution": f"CommunicationOS (fetch) in session {session_id}",
                    "audit_id": response.evidence_id,
                    "status_code": data.get("status_code"),
                    "content_type": data.get("content_type"),
                    "content_length": data.get("content_length"),
                }
            }

        except Exception as e:
            logger.error(f"Fetch failed: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "message": str(e),
                "url": url,
                "metadata": {
                    "attribution": f"CommunicationOS (fetch) in session {session_id}",
                }
            }

    def _handle_error_response(
        self,
        response: Any,
        session_id: str
    ) -> Dict[str, Any]:
        """Handle error responses from CommunicationService.

        Args:
            response: CommunicationResponse with error
            session_id: Chat session ID

        Returns:
            Chat-friendly error response
        """
        error = response.error or "Unknown error"

        # Check for SSRF blocking
        if "SSRF" in error or response.status == RequestStatus.DENIED:
            if "SSRF" in error or "localhost" in error.lower() or "private" in error.lower():
                return {
                    "status": "blocked",
                    "reason": "SSRF_PROTECTION",
                    "message": "该 URL 被安全策略阻止(内网地址或 localhost)",
                    "hint": "请使用公开的 HTTPS URL",
                    "metadata": {
                        "attribution": f"CommunicationOS in session {session_id}",
                    }
                }

        # Check for rate limiting
        if response.status == RequestStatus.RATE_LIMITED or "rate limit" in error.lower():
            # Extract retry_after from error message if available
            retry_after = 60
            if "Try again in" in error:
                try:
                    parts = error.split("Try again in")
                    if len(parts) > 1:
                        seconds_str = parts[1].split("seconds")[0].strip()
                        retry_after = int(seconds_str)
                except:
                    pass

            return {
                "status": "rate_limited",
                "message": f"超过速率限制,请等待 {retry_after} 秒",
                "retry_after": retry_after,
                "metadata": {
                    "attribution": f"CommunicationOS in session {session_id}",
                }
            }

        # Check for approval required
        if response.status == RequestStatus.REQUIRE_ADMIN:
            return {
                "status": "requires_approval",
                "message": "该操作需要管理员批准",
                "hint": error,
                "metadata": {
                    "attribution": f"CommunicationOS in session {session_id}",
                }
            }

        # Generic error
        return {
            "status": "error",
            "message": error,
            "metadata": {
                "attribution": f"CommunicationOS in session {session_id}",
            }
        }

    def _determine_trust_tier(self, url: str) -> TrustTier:
        """Determine trust tier for a URL.

        Uses the EvidenceLogger's trust tier determination logic.

        Args:
            url: URL to evaluate

        Returns:
            TrustTier enum value
        """
        try:
            # Use the evidence logger's trust tier logic
            return self.service.evidence_logger.determine_trust_tier(
                url,
                ConnectorType.WEB_FETCH
            )
        except Exception as e:
            logger.warning(f"Failed to determine trust tier: {e}")
            return TrustTier.EXTERNAL_SOURCE

    def _calculate_content_hash(self, text: str) -> str:
        """Calculate SHA256 hash of content for verification.

        Args:
            text: Content text

        Returns:
            Hex-encoded SHA256 hash
        """
        if not text:
            return ""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _extract_author(self, url: str, extracted: Dict[str, Any]) -> str:
        """Extract author information from content.

        Args:
            url: Source URL
            extracted: Extracted HTML content

        Returns:
            Author name or empty string
        """
        # Try to extract from meta tags or content
        # This is a simple implementation - can be enhanced
        from urllib.parse import urlparse
        domain = urlparse(url).netloc

        # For now, use domain as author
        return domain

    def _extract_publish_date(self, extracted: Dict[str, Any]) -> str:
        """Extract publish date from content.

        Args:
            extracted: Extracted HTML content

        Returns:
            ISO format date string or empty string
        """
        # This is a placeholder - can be enhanced with actual date extraction
        # from meta tags, article headers, etc.
        return ""

    async def get_statistics(self) -> Dict[str, Any]:
        """Get communication statistics.

        Returns:
            Dictionary with statistics from CommunicationService
        """
        return await self.service.get_statistics()

    async def list_connectors(self) -> Dict[str, Any]:
        """List available connectors.

        Returns:
            Dictionary with connector information
        """
        return await self.service.list_connectors()
