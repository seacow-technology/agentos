"""Session Validation Middleware for AgentOS WebUI.

This middleware validates session integrity on every request and handles
session expiration gracefully.

Security Issue: M-25 - Session Fixation and Session Management

Key Features:
- Automatic session validation on every request
- Session expiry detection and handling
- Session initialization for new sessions
- Graceful error responses for expired sessions
"""

import logging
from typing import Callable
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .session_security import (
    validate_session_integrity,
    initialize_session,
    mark_unauthenticated,
    get_session_info,
)

logger = logging.getLogger(__name__)

# Paths that don't require session validation
EXEMPT_PATHS = [
    "/health",
    "/api/health",
    "/static/",
    "/ws/",  # WebSocket endpoints
    "/api/auth/login",  # Allow login without valid session
]


class SessionValidationMiddleware(BaseHTTPMiddleware):
    """Middleware to validate session integrity on every request.

    This middleware:
    1. Initializes new sessions with security metadata
    2. Validates existing sessions for expiry and integrity
    3. Returns 401 for expired/invalid sessions
    4. Clears invalid sessions automatically
    """

    def __init__(self, app: FastAPI, exempt_paths: list[str] = None):
        """Initialize session validation middleware.

        Args:
            app: FastAPI application
            exempt_paths: List of paths to exempt from validation
        """
        super().__init__(app)
        self.exempt_paths = exempt_paths or EXEMPT_PATHS

    def _is_exempt(self, path: str) -> bool:
        """Check if path is exempt from session validation.

        Args:
            path: Request path

        Returns:
            True if path is exempt, False otherwise
        """
        return any(path.startswith(exempt) for exempt in self.exempt_paths)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Validate session on every request.

        Args:
            request: Incoming request
            call_next: Next middleware/route handler

        Returns:
            Response or 401 error if session is invalid
        """
        # Skip validation for exempt paths
        if self._is_exempt(request.url.path):
            return await call_next(request)

        try:
            # Check if session exists
            session = request.scope.get("session")
            if session is None:
                # No session middleware configured, skip validation
                logger.warning("Session middleware not configured")
                return await call_next(request)

            # Initialize new sessions
            initialize_session(request)

            # Validate session integrity
            is_valid = validate_session_integrity(request)

            if not is_valid:
                # Session is invalid or expired
                logger.warning(
                    f"Invalid session detected for {request.url.path} "
                    f"from {request.client.host if request.client else 'unknown'}"
                )

                # Clear the invalid session
                mark_unauthenticated(request)

                # Return 401 Unauthorized
                # M-02: Use unified ErrorEnvelope format
                from datetime import datetime, timezone

                def _format_timestamp() -> str:
                    """Format current time as ISO 8601 UTC with Z suffix"""
                    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')

                return JSONResponse(
                    status_code=401,
                    content={
                        "ok": False,
                        "error_code": "SESSION_EXPIRED",
                        "message": "Session expired or invalid",
                        "details": {
                            "hint": "Your session has expired. Please refresh the page or login again."
                        },
                        "timestamp": _format_timestamp()
                    }
                )

            # Session is valid, proceed with request
            response = await call_next(request)
            return response

        except Exception as e:
            logger.error(f"Session validation error: {e}", exc_info=True)
            # On error, allow request to proceed but log the issue
            # (Fail open for better user experience, but log for security monitoring)
            return await call_next(request)


def add_session_validation(
    app: FastAPI,
    exempt_paths: list[str] = None
) -> None:
    """Add session validation middleware to FastAPI app.

    Args:
        app: FastAPI application
        exempt_paths: List of paths to exempt from validation

    Example:
        ```python
        from fastapi import FastAPI
        from agentos.webui.middleware.session_validation import add_session_validation

        app = FastAPI()

        # Add session middleware first
        from starlette.middleware.sessions import SessionMiddleware
        app.add_middleware(SessionMiddleware, secret_key="your-secret-key")

        # Add session validation
        add_session_validation(app)
        ```

    Note:
        - SessionMiddleware must be added before session validation
        - Validation runs on every request except exempt paths
        - Invalid sessions receive 401 responses
    """
    app.add_middleware(
        SessionValidationMiddleware,
        exempt_paths=exempt_paths,
    )
    logger.info(
        f"Session validation middleware enabled "
        f"(exempt_paths={exempt_paths or 'default'})"
    )
