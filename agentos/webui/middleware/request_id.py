"""
Request ID Middleware - Request tracing for M-02 API Contract Consistency

This middleware adds X-Request-ID header to all requests/responses for distributed
tracing and debugging support.

Created for BACKLOG M-02: Request Tracking ID Implementation
"""

import uuid
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from fastapi import FastAPI

logger = logging.getLogger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware to inject X-Request-ID header for request tracking

    Features:
    - Uses client-provided X-Request-ID if present
    - Generates UUID if not provided
    - Adds X-Request-ID to response headers
    - Makes request_id available in request.state for logging

    Example usage:
        app.add_middleware(RequestIDMiddleware)

        # In endpoint:
        @router.get("/api/tasks")
        async def list_tasks(request: Request):
            request_id = request.state.request_id
            logger.info(f"[{request_id}] Processing request")
    """

    async def dispatch(self, request: Request, call_next):
        """
        Process request and inject request ID

        Args:
            request: Incoming request
            call_next: Next middleware/handler in chain

        Returns:
            Response with X-Request-ID header
        """
        # Get or generate request ID
        request_id = request.headers.get("X-Request-ID")

        if not request_id:
            # Generate new UUID for this request
            request_id = str(uuid.uuid4())

        # Store in request state for access in handlers
        request.state.request_id = request_id

        # Log request with ID
        logger.debug(
            f"[{request_id}] {request.method} {request.url.path} "
            f"from {request.client.host if request.client else 'unknown'}"
        )

        # Call next handler
        try:
            response = await call_next(request)

            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id

            # Log response with ID
            logger.debug(
                f"[{request_id}] Response: {response.status_code}"
            )

            return response

        except Exception as e:
            # Log error with request ID
            logger.error(
                f"[{request_id}] Request failed: {str(e)}",
                exc_info=True
            )
            raise


def add_request_id_middleware(app: FastAPI) -> None:
    """
    Register RequestIDMiddleware with FastAPI app

    Args:
        app: FastAPI application instance

    Example:
        from agentos.webui.middleware.request_id import add_request_id_middleware
        add_request_id_middleware(app)
    """
    app.add_middleware(RequestIDMiddleware)
    logger.info("Registered RequestIDMiddleware for request tracing (M-02)")


def get_request_id(request: Request) -> str:
    """
    Helper function to get request ID from request state

    Args:
        request: FastAPI Request object

    Returns:
        Request ID string, or "unknown" if not set

    Example:
        @router.get("/api/tasks")
        async def list_tasks(request: Request):
            request_id = get_request_id(request)
            logger.info(f"[{request_id}] Fetching tasks")
    """
    return getattr(request.state, "request_id", "unknown")


class RequestIDFilter(logging.Filter):
    """
    Logging filter to add request_id to log records

    This allows including request ID in all log messages automatically.

    Example:
        import logging
        from agentos.webui.middleware.request_id import RequestIDFilter

        # Add to logger
        logger = logging.getLogger(__name__)
        logger.addFilter(RequestIDFilter())

        # Use in format string
        formatter = logging.Formatter(
            '%(asctime)s [%(request_id)s] %(name)s - %(levelname)s - %(message)s'
        )
    """

    def filter(self, record):
        """
        Add request_id to log record

        Args:
            record: LogRecord to filter

        Returns:
            True (always pass through)
        """
        # Try to get request_id from context
        # This requires contextvars or similar mechanism
        # For now, set to "no-request-id" as placeholder
        if not hasattr(record, 'request_id'):
            record.request_id = 'no-request-id'

        return True
