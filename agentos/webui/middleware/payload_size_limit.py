"""
Payload Size Limit Middleware

This middleware enforces a maximum payload size for HTTP requests to prevent
DoS attacks and resource exhaustion from oversized request bodies.

Addresses: L-3 - Reject payloads larger than 1MB

Security Benefits:
- Prevents memory exhaustion from large payloads
- Prevents DoS attacks via oversized requests
- Provides clear error messages for oversized payloads
- Stops oversized data at the API boundary before processing

Implementation:
- Checks Content-Length header before reading body
- Enforces 1MB limit for all POST/PUT/PATCH requests
- Returns 413 Payload Too Large with helpful error message
"""

import logging
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from agentos.webui.api.validation import MAX_PAYLOAD_SIZE

logger = logging.getLogger(__name__)


class PayloadSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware to enforce maximum payload size for HTTP requests.

    This middleware checks the Content-Length header and rejects requests
    that exceed the configured maximum payload size.

    Default limit: 1 MB (configurable via MAX_PAYLOAD_SIZE constant)
    """

    def __init__(self, app, max_size: int = MAX_PAYLOAD_SIZE):
        """
        Initialize payload size limit middleware.

        Args:
            app: ASGI application
            max_size: Maximum payload size in bytes (default: 1 MB)
        """
        super().__init__(app)
        self.max_size = max_size

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Intercept requests and check payload size.

        Args:
            request: The incoming HTTP request
            call_next: The next middleware/route handler

        Returns:
            Response from the next handler or 413 error
        """
        # Only check payload size for methods that have request bodies
        if request.method in ["POST", "PUT", "PATCH"]:
            # Get Content-Length header
            content_length = request.headers.get("content-length")

            if content_length:
                try:
                    content_length_bytes = int(content_length)

                    # Check if payload exceeds limit
                    if content_length_bytes > self.max_size:
                        logger.warning(
                            f"Payload too large: {content_length_bytes} bytes "
                            f"(max: {self.max_size} bytes) for {request.method} {request.url.path}",
                            extra={
                                "method": request.method,
                                "path": request.url.path,
                                "content_length": content_length_bytes,
                                "max_size": self.max_size,
                            }
                        )

                        # Return 413 Payload Too Large
                        # M-02: Use unified ErrorEnvelope format
                        from datetime import datetime, timezone

                        def _format_timestamp() -> str:
                            """Format current time as ISO 8601 UTC with Z suffix"""
                            return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')

                        return JSONResponse(
                            status_code=413,
                            content={
                                "ok": False,
                                "error_code": "PAYLOAD_TOO_LARGE",
                                "message": "Payload too large",
                                "details": {
                                    "hint": f"Request body must be less than {self._format_size(self.max_size)}. "
                                            f"Received: {self._format_size(content_length_bytes)}",
                                    "max_size_bytes": self.max_size,
                                    "max_size_human": self._format_size(self.max_size),
                                    "received_size_bytes": content_length_bytes,
                                    "received_size_human": self._format_size(content_length_bytes),
                                },
                                "timestamp": _format_timestamp()
                            }
                        )

                except ValueError:
                    # Invalid Content-Length header - let it through
                    # The application will handle the invalid header
                    logger.warning(
                        f"Invalid Content-Length header: {content_length} "
                        f"for {request.method} {request.url.path}"
                    )

        # Continue to the next middleware/handler
        response = await call_next(request)
        return response

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """
        Format byte size as human-readable string.

        Args:
            size_bytes: Size in bytes

        Returns:
            Human-readable size string (e.g., "1.5 MB")
        """
        if size_bytes < 1024:
            return f"{size_bytes} bytes"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"


def add_payload_size_limit_middleware(app, max_size: int = MAX_PAYLOAD_SIZE):
    """
    Add payload size limit middleware to the FastAPI application.

    This should be added early in the middleware chain to reject
    oversized payloads before they're processed.

    Usage:
        from agentos.webui.middleware.payload_size_limit import add_payload_size_limit_middleware
        add_payload_size_limit_middleware(app)

    Args:
        app: FastAPI application instance
        max_size: Maximum payload size in bytes (default: 1 MB)
    """
    app.add_middleware(PayloadSizeLimitMiddleware, max_size=max_size)
    logger.info(
        f"Payload size limit middleware enabled "
        f"(max: {PayloadSizeLimitMiddleware._format_size(max_size)})"
    )
