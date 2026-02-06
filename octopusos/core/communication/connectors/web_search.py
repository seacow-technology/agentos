"""Web search connector for searching the internet.

This connector provides web search capabilities using various
search engines (Google, Bing, DuckDuckGo, etc.).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse

from agentos.core.communication.connectors.base import BaseConnector
from agentos.core.communication.priority import calculate_priority_score
from agentos.core.communication.config import load_trusted_sources

logger = logging.getLogger(__name__)


class WebSearchError(Exception):
    """Base exception for web search errors."""
    pass


class APIError(WebSearchError):
    """API-related errors."""
    pass


class NetworkError(WebSearchError):
    """Network-related errors."""
    pass


class RateLimitError(WebSearchError):
    """Rate limit errors."""
    pass


class WebSearchConnector(BaseConnector):
    """Connector for web search operations.

    Supports searching the web using various search engines
    and returns structured search results.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize web search connector.

        Args:
            config: Configuration including:
                - api_key: Search API key (required for Google/Bing)
                - engine: Search engine (google, bing, duckduckgo)
                - max_results: Maximum number of results (default: 10)
                - timeout: Request timeout in seconds (default: 30)
                - deduplicate: Whether to deduplicate results by URL (default: True)
        """
        super().__init__(config)
        self.api_key = self.config.get("api_key")
        self.engine = self.config.get("engine", "duckduckgo")
        self.max_results = self.config.get("max_results", 10)
        self.timeout = self.config.get("timeout", 30)
        self.deduplicate = self.config.get("deduplicate", True)

        # Load trusted sources for priority scoring
        try:
            self.trusted_sources = load_trusted_sources()
        except Exception as e:
            logger.warning(f"Failed to load trusted sources: {e}")
            self.trusted_sources = {
                "official_policy": [],
                "recognized_ngo": []
            }

    async def execute(self, operation: str, params: Dict[str, Any]) -> Any:
        """Execute a web search operation.

        Args:
            operation: Operation to perform (e.g., "search")
            params: Operation parameters

        Returns:
            Search results

        Raises:
            ValueError: If operation is not supported
            Exception: If search fails
        """
        if not self.enabled:
            raise Exception("Web search connector is disabled")

        if operation == "search":
            return await self._search(params)
        else:
            raise ValueError(f"Unsupported operation: {operation}")

    async def _search(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Perform web search.

        Args:
            params: Search parameters including:
                - query: Search query string
                - max_results: Maximum results to return
                - language: Language code (optional)

        Returns:
            Dictionary containing:
                - query: Original query
                - results: List of search results with title, url, snippet
                - total_results: Total number of results found
                - engine: Search engine used

        Raises:
            ValueError: If query is missing or invalid
            WebSearchError: If search fails
        """
        query = params.get("query")
        if not query:
            raise ValueError("Search query is required")

        if not isinstance(query, str) or not query.strip():
            raise ValueError("Search query must be a non-empty string")

        max_results = params.get("max_results", self.max_results)
        language = params.get("language", "en")

        logger.info(f"Performing {self.engine} search: {query}")

        try:
            # Route to appropriate search provider
            if self.engine == "duckduckgo":
                raw_results = await self._search_duckduckgo(query, max_results, language)
            elif self.engine == "google":
                raw_results = await self._search_google(query, max_results, language)
            elif self.engine == "bing":
                raw_results = await self._search_bing(query, max_results, language)
            else:
                raise ValueError(f"Unsupported search engine: {self.engine}")

            # Standardize and deduplicate results
            results = self._standardize_results(raw_results)
            if self.deduplicate:
                results = self._deduplicate_results(results)

            # Limit results to max_results
            results = results[:max_results]

            return {
                "query": query,
                "results": results,
                "total_results": len(results),
                "engine": self.engine,
            }

        except WebSearchError:
            raise
        except Exception as e:
            logger.error(f"Search failed: {str(e)}", exc_info=True)
            raise WebSearchError(f"Search failed: {str(e)}") from e

    async def _search_duckduckgo(
        self, query: str, max_results: int, language: str
    ) -> List[Dict[str, Any]]:
        """Perform DuckDuckGo search.

        Args:
            query: Search query
            max_results: Maximum number of results
            language: Language code

        Returns:
            List of raw search results

        Raises:
            NetworkError: If network request fails
            RateLimitError: If rate limited
            APIError: If API returns an error
        """
        # Try to import DDGS from either package (ddgs is newer, duckduckgo_search is older)
        DDGS = None
        import_error = None

        try:
            from ddgs import DDGS
        except ImportError:
            try:
                from duckduckgo_search import DDGS
            except ImportError as e:
                import_error = e

        if DDGS is None:
            raise APIError(
                "DuckDuckGo search library not installed. "
                "Install it with: pip install ddgs (recommended) or pip install duckduckgo-search"
            ) from import_error

        try:
            # Run synchronous DDGS in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None,
                lambda: self._ddgs_search(query, max_results, language, DDGS)
            )
            return results

        except Exception as e:
            error_msg = str(e).lower()

            # Check for rate limiting
            if "ratelimit" in error_msg or "429" in error_msg:
                raise RateLimitError(f"DuckDuckGo rate limit exceeded: {str(e)}") from e

            # Check for network errors
            if any(term in error_msg for term in ["timeout", "connection", "network"]):
                raise NetworkError(f"Network error during DuckDuckGo search: {str(e)}") from e

            # Generic API error
            raise APIError(f"DuckDuckGo search failed: {str(e)}") from e

    def _ddgs_search(self, query: str, max_results: int, language: str, DDGS) -> List[Dict[str, Any]]:
        """Synchronous DuckDuckGo search helper.

        Args:
            query: Search query
            max_results: Maximum number of results
            language: Language code
            DDGS: DDGS class from either ddgs or duckduckgo_search package

        Returns:
            List of raw search results
        """
        results = []

        try:
            with DDGS() as ddgs:
                # Use text search with region parameter for language
                region = f"{language}-{language}" if language else "wt-wt"

                # Try new API first (query as positional arg), fallback to old API (keywords param)
                try:
                    # New API: ddgs.text(query, region=..., max_results=...)
                    search_results = ddgs.text(
                        query,
                        region=region,
                        max_results=max_results,
                        safesearch="moderate",
                    )
                except TypeError:
                    # Old API: ddgs.text(keywords=query, region=..., max_results=...)
                    search_results = ddgs.text(
                        keywords=query,
                        region=region,
                        max_results=max_results,
                        safesearch="moderate",
                    )

                # Convert generator to list
                for result in search_results:
                    results.append(result)

        except Exception as e:
            logger.error(f"DDGS search error: {str(e)}")
            raise

        return results

    async def _search_google(
        self, query: str, max_results: int, language: str
    ) -> List[Dict[str, Any]]:
        """Perform Google search.

        Note: This is a skeleton implementation. To use Google search:
        1. Sign up for Google Custom Search API at: https://developers.google.com/custom-search
        2. Create a Custom Search Engine (CSE) at: https://cse.google.com/
        3. Get your API key and Search Engine ID
        4. Set api_key in connector config
        5. Set search_engine_id in connector config
        6. Install required library: pip install google-api-python-client

        Args:
            query: Search query
            max_results: Maximum number of results
            language: Language code

        Returns:
            List of raw search results

        Raises:
            APIError: This method is not yet implemented
        """
        # TODO: Implement Google Custom Search API integration
        # Example implementation:
        #
        # from googleapiclient.discovery import build
        #
        # service = build("customsearch", "v1", developerKey=self.api_key)
        # result = service.cse().list(
        #     q=query,
        #     cx=self.config.get("search_engine_id"),
        #     num=min(max_results, 10),
        #     lr=f"lang_{language}"
        # ).execute()
        #
        # return [
        #     {
        #         "title": item.get("title"),
        #         "url": item.get("link"),
        #         "snippet": item.get("snippet"),
        #     }
        #     for item in result.get("items", [])
        # ]

        raise APIError(
            "Google search not yet implemented. "
            "Please use 'duckduckgo' engine or implement Google Custom Search API."
        )

    async def _search_bing(
        self, query: str, max_results: int, language: str
    ) -> List[Dict[str, Any]]:
        """Perform Bing search.

        Note: This is a skeleton implementation. To use Bing search:
        1. Sign up for Bing Search API at: https://www.microsoft.com/en-us/bing/apis/bing-web-search-api
        2. Get your API key (subscription key)
        3. Set api_key in connector config
        4. Install required library: pip install requests

        Args:
            query: Search query
            max_results: Maximum number of results
            language: Language code

        Returns:
            List of raw search results

        Raises:
            APIError: This method is not yet implemented
        """
        # TODO: Implement Bing Search API integration
        # Example implementation:
        #
        # import httpx
        #
        # endpoint = "https://api.bing.microsoft.com/v7.0/search"
        # headers = {"Ocp-Apim-Subscription-Key": self.api_key}
        # params = {
        #     "q": query,
        #     "count": max_results,
        #     "mkt": f"{language}-{language.upper()}",
        #     "textDecorations": False,
        #     "textFormat": "Raw"
        # }
        #
        # async with httpx.AsyncClient(timeout=self.timeout) as client:
        #     response = await client.get(endpoint, headers=headers, params=params)
        #     response.raise_for_status()
        #     data = response.json()
        #
        # return [
        #     {
        #         "title": item.get("name"),
        #         "url": item.get("url"),
        #         "snippet": item.get("snippet"),
        #     }
        #     for item in data.get("webPages", {}).get("value", [])
        # ]

        raise APIError(
            "Bing search not yet implemented. "
            "Please use 'duckduckgo' engine or implement Bing Search API."
        )

    def _standardize_results(self, raw_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Standardize search results to uniform format with priority scoring.

        Args:
            raw_results: Raw results from search provider

        Returns:
            Standardized results with title, url, snippet, domain, priority_score,
            and priority_reasons fields, sorted by priority_score descending
        """
        standardized = []

        for result in raw_results:
            try:
                # DuckDuckGo format: {'title': ..., 'href': ..., 'body': ...}
                # Google format: {'title': ..., 'link': ..., 'snippet': ...}
                # Bing format: {'name': ..., 'url': ..., 'snippet': ...}

                title = result.get("title") or result.get("name", "")
                url = result.get("href") or result.get("url") or result.get("link", "")
                snippet = result.get("body") or result.get("snippet", "")

                # Skip if URL is missing
                if not url:
                    logger.warning(f"Skipping result without URL: {result}")
                    continue

                # Validate URL format
                try:
                    parsed = urlparse(url)
                    if not parsed.scheme or not parsed.netloc:
                        logger.warning(f"Invalid URL format: {url}")
                        continue
                    domain = parsed.netloc
                except Exception:
                    logger.warning(f"Failed to parse URL: {url}")
                    continue

                # Calculate priority score
                try:
                    priority_score_obj = calculate_priority_score(
                        url=url.strip(),
                        snippet=snippet.strip() if snippet else "",
                        trusted_sources=self.trusted_sources
                    )
                    priority_score = priority_score_obj.total_score
                    priority_reasons = [reason.value for reason in priority_score_obj.reasons]
                except Exception as e:
                    logger.warning(f"Failed to calculate priority score for {url}: {e}")
                    priority_score = 0
                    priority_reasons = []

                standardized.append({
                    "title": title.strip() if title else "",
                    "url": url.strip(),
                    "snippet": snippet.strip() if snippet else "",
                    "domain": domain,
                    "priority_score": priority_score,
                    "priority_reasons": priority_reasons,
                })

            except Exception as e:
                logger.warning(f"Failed to standardize result: {e}")
                continue

        # Sort by priority_score descending
        standardized.sort(key=lambda x: x["priority_score"], reverse=True)

        return standardized

    def _deduplicate_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate results based on URL.

        Args:
            results: List of standardized results

        Returns:
            Deduplicated results
        """
        seen_urls: Set[str] = set()
        deduplicated = []

        for result in results:
            url = result["url"].lower().rstrip("/")

            # Normalize URL for comparison
            try:
                parsed = urlparse(url)
                normalized_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            except Exception:
                normalized_url = url

            if normalized_url not in seen_urls:
                seen_urls.add(normalized_url)
                deduplicated.append(result)
            else:
                logger.debug(f"Skipping duplicate URL: {url}")

        return deduplicated

    def get_supported_operations(self) -> List[str]:
        """Get list of supported operations.

        Returns:
            List of supported operation names
        """
        return ["search"]

    def validate_config(self) -> bool:
        """Validate connector configuration.

        Returns:
            True if configuration is valid
        """
        if self.engine in ["google", "bing"] and not self.api_key:
            logger.warning(f"{self.engine} search requires API key")
            return False

        if self.engine not in ["duckduckgo", "google", "bing"]:
            logger.error(f"Unsupported search engine: {self.engine}")
            return False

        return True
