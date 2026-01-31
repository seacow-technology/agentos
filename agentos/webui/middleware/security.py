"""Security Middleware for XSS and CSP Protection.

This module provides Content-Security-Policy (CSP) headers and other
security headers to protect against XSS, clickjacking, and other attacks.

Security Issue: Task #34 - P0-3: Fix Sessions/Chat API XSS vulnerability
"""

import logging
from typing import Callable
from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers to all responses.

    Headers added:
    - Content-Security-Policy (CSP): Prevents XSS attacks
    - X-Content-Type-Options: Prevents MIME sniffing
    - X-Frame-Options: Prevents clickjacking
    - X-XSS-Protection: Enables browser XSS filter (legacy)
    - Referrer-Policy: Controls referrer information
    """

    def __init__(self, app: FastAPI, csp_policy: str = None):
        """Initialize security headers middleware.

        Args:
            app: FastAPI application
            csp_policy: Custom CSP policy (optional)
        """
        super().__init__(app)

        # Default CSP policy - strict but allows necessary functionality
        self.csp_policy = csp_policy or (
            "default-src 'self'; "
            # Scripts: Allow self and inline (needed for some frontend frameworks)
            # Use nonce or hash in production for better security
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            # Styles: Allow self and inline (needed for dynamic styling)
            "style-src 'self' 'unsafe-inline'; "
            # Images: Allow self and data URIs (for base64 images)
            "img-src 'self' data: https:; "
            # Fonts: Allow self and data URIs
            "font-src 'self' data:; "
            # Connect: Allow self (for API calls and WebSockets)
            "connect-src 'self' ws: wss:; "
            # Media: Allow self
            "media-src 'self'; "
            # Objects: Block all
            "object-src 'none'; "
            # Frames: Only allow self (for iframe isolation if needed)
            "frame-src 'self'; "
            # Workers: Allow self and blob (needed for some libraries)
            "worker-src 'self' blob:; "
            # Base URI: Restrict to self
            "base-uri 'self'; "
            # Form actions: Restrict to self
            "form-action 'self'; "
            # Frame ancestors: Prevent embedding (anti-clickjacking)
            "frame-ancestors 'none'; "
            # Upgrade insecure requests in production
            "upgrade-insecure-requests;"
        )

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and add security headers to response.

        Args:
            request: Incoming request
            call_next: Next middleware/route handler

        Returns:
            Response with security headers
        """
        # Process request
        response = await call_next(request)

        # Add security headers
        # Only add CSP for HTML responses (not API JSON responses)
        content_type = response.headers.get("content-type", "")
        if "text/html" in content_type:
            response.headers["Content-Security-Policy"] = self.csp_policy

        # Always add these headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Add HSTS in production (uncomment when using HTTPS)
        # response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response


def add_security_headers(app: FastAPI, csp_policy: str = None) -> None:
    """Add security headers middleware to FastAPI app.

    Args:
        app: FastAPI application
        csp_policy: Custom CSP policy (optional)

    Example:
        ```python
        from fastapi import FastAPI
        from agentos.webui.middleware.security import add_security_headers

        app = FastAPI()
        add_security_headers(app)
        ```
    """
    app.add_middleware(SecurityHeadersMiddleware, csp_policy=csp_policy)
    logger.info("Security headers middleware enabled (CSP, X-Frame-Options, etc.)")


# Convenience function for adding XSS protection to responses
def add_xss_headers(response: Response) -> Response:
    """Add XSS protection headers to a response.

    This is a convenience function for manually adding headers to
    specific responses if needed.

    Args:
        response: Response to add headers to

    Returns:
        Response with XSS headers
    """
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response
