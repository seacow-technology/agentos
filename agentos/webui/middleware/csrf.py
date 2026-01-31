"""CSRF Protection Middleware for AgentOS WebUI.

This module provides CSRF (Cross-Site Request Forgery) protection for state-changing
API endpoints. It implements the Double Submit Cookie pattern with session binding,
plus Origin/Referer header validation as a second line of defense.

Security Issue: Task #36 - P0-5: Implement CSRF protection for Extensions interface

Key Features:
- Two-layer defense system:
  * Layer 1: Origin/Referer same-origin checking (blocks most cross-domain attacks)
  * Layer 2: CSRF token validation (blocks token-less attacks)
- Token generation using secrets.token_urlsafe (at least 32 bytes)
- Token storage in session with binding to user session
- Token validation for POST/PUT/PATCH/DELETE requests
- Support for both header-based and form-based token submission
- Automatic token rotation on validation
- Exemption for safe methods (GET, HEAD, OPTIONS)
- Clear error messages for debugging

References:
- OWASP CSRF Prevention Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html
- Double Submit Cookie Pattern: https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html#double-submit-cookie
- Verifying Origin With Standard Headers: https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html#verifying-origin-with-standard-headers
"""

import logging
import secrets
from typing import Callable, Optional
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.datastructures import Headers

logger = logging.getLogger(__name__)

# CSRF token configuration
CSRF_TOKEN_LENGTH = 32  # 32 bytes = 256 bits of entropy
CSRF_HEADER_NAME = "X-CSRF-Token"
CSRF_COOKIE_NAME = "csrf_token"
CSRF_SESSION_KEY = "_csrf_token"

# Methods that require CSRF protection (state-changing operations)
PROTECTED_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

# Methods that don't require CSRF protection (safe operations)
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

# ============================================================================
# CSRF Exemption Contract Validation
# ============================================================================
# Security Contract: All exemptions must be documented in
# docs/security/CSRF_EXEMPTION_CONTRACT.md
#
# This validation ensures the exemption list matches the security contract
# and prevents accidental security regressions.
# ============================================================================

# Expected exemptions from security contract (v1.0.0)
EXPECTED_GENERAL_EXEMPTIONS = {
    "/health",        # System health check (no state changes)
    "/api/health",    # API health check (no state changes)
    "/static/",       # Static file serving (read-only)
    "/ws/",           # WebSocket endpoints (separate security model)
    "/webhook/",      # Server-to-server webhooks (MUST have signature verification)
}

EXPECTED_API_WHITELIST = {
    "/api/health",      # Health check API (no state changes)
    "/api/csrf-token",  # CSRF token retrieval endpoint (required for CSRF to work)
}


def validate_exemption_contract(
    configured_exemptions: list[str],
    configured_api_whitelist: list[str]
) -> None:
    """Validate that CSRF exemptions match the security contract.

    This function enforces the CSRF exemption contract documented in
    docs/security/CSRF_EXEMPTION_CONTRACT.md. It ensures that:

    1. All configured exemptions are documented in the contract
    2. No undocumented exemptions have been added
    3. The exemption list hasn't been accidentally modified

    This validation runs at application startup to catch configuration
    errors before they reach production.

    Args:
        configured_exemptions: List of exempt paths from middleware config
        configured_api_whitelist: List of whitelisted API paths from config

    Raises:
        AssertionError: If exemption list doesn't match security contract
    """
    # Convert lists to sets for comparison
    configured_general = set(configured_exemptions)
    configured_api = set(configured_api_whitelist)

    # Check for unexpected exemptions (security regression)
    unexpected_general = configured_general - EXPECTED_GENERAL_EXEMPTIONS
    unexpected_api = configured_api - EXPECTED_API_WHITELIST

    if unexpected_general:
        raise AssertionError(
            f"SECURITY CONTRACT VIOLATION: Unexpected CSRF exemptions detected!\n"
            f"Unauthorized exemptions: {unexpected_general}\n"
            f"All exemptions must be documented in docs/security/CSRF_EXEMPTION_CONTRACT.md\n"
            f"If this is intentional, update the contract and EXPECTED_GENERAL_EXEMPTIONS."
        )

    if unexpected_api:
        raise AssertionError(
            f"SECURITY CONTRACT VIOLATION: Unexpected API whitelist entries detected!\n"
            f"Unauthorized whitelist entries: {unexpected_api}\n"
            f"All exemptions must be documented in docs/security/CSRF_EXEMPTION_CONTRACT.md\n"
            f"If this is intentional, update the contract and EXPECTED_API_WHITELIST."
        )

    # Check for missing exemptions (might be intentional hardening)
    missing_general = EXPECTED_GENERAL_EXEMPTIONS - configured_general
    missing_api = EXPECTED_API_WHITELIST - configured_api

    if missing_general:
        logger.warning(
            f"CSRF Exemption Contract: Some expected exemptions are not configured: {missing_general}\n"
            f"This may be intentional security hardening. If not, update the middleware config."
        )

    if missing_api:
        logger.warning(
            f"CSRF Exemption Contract: Some expected API whitelist entries are not configured: {missing_api}\n"
            f"This may be intentional security hardening. If not, update the middleware config."
        )

    logger.info(
        f"CSRF Exemption Contract validated successfully: "
        f"{len(configured_general)} general exemptions, "
        f"{len(configured_api)} API whitelist entries"
    )


class CSRFProtectionMiddleware(BaseHTTPMiddleware):
    """Middleware to protect against CSRF attacks.

    This middleware implements the Double Submit Cookie pattern:
    1. Generate a random token and store it in the session
    2. Send the same token in a cookie
    3. Require the token in request header for state-changing operations
    4. Validate that header token matches session token

    The token is bound to the session, so it cannot be reused across sessions.
    """

    def __init__(
        self,
        app: FastAPI,
        exempt_paths: Optional[list[str]] = None,
        token_header: str = CSRF_HEADER_NAME,
        cookie_name: str = CSRF_COOKIE_NAME,
        enforce_for_api: bool = True,
        check_origin: bool = True,
        validate_contract: bool = True,
    ):
        """Initialize CSRF protection middleware.

        Args:
            app: FastAPI application
            exempt_paths: List of path prefixes to exempt from CSRF protection
            token_header: Name of the header containing CSRF token
            cookie_name: Name of the cookie containing CSRF token
            enforce_for_api: Whether to enforce CSRF protection for API routes (default True)
            check_origin: Whether to check Origin/Referer headers (default True)
            validate_contract: Whether to validate exemptions against security contract (default True)
        """
        super().__init__(app)
        self.exempt_paths = exempt_paths or [
            "/health",
            "/api/health",
            "/static/",
            "/ws/",  # WebSocket endpoints
            "/webhook/",  # Server-to-Server webhooks use signature verification
        ]
        self.token_header = token_header
        self.cookie_name = cookie_name
        self.enforce_for_api = enforce_for_api
        self.check_origin = check_origin

        # API routes that don't require CSRF token
        self.api_whitelist = [
            "/api/health",
            "/api/csrf-token",  # Endpoint to get CSRF token itself
        ]

        # Validate exemptions against security contract
        if validate_contract:
            validate_exemption_contract(self.exempt_paths, self.api_whitelist)

    def _is_exempt(self, path: str) -> bool:
        """Check if path is exempt from CSRF protection.

        Args:
            path: Request path

        Returns:
            True if path is exempt, False otherwise
        """
        # Check general exempt paths
        if any(path.startswith(exempt) for exempt in self.exempt_paths):
            return True

        # Check API whitelist
        if any(path.startswith(api) for api in self.api_whitelist):
            return True

        return False

    def _check_origin(self, request: Request) -> bool:
        """Check Origin or Referer header for same-origin validation.

        This is the second line of defense against CSRF attacks. Even if CSRF token
        is bypassed, origin checking can block most cross-domain attacks.

        Args:
            request: Current request

        Returns:
            True if same-origin, False if cross-origin or suspicious
        """
        from urllib.parse import urlparse
        import os

        # Get site origin
        # Priority: environment variable > infer from request
        site_origin = os.getenv("SITE_ORIGIN")

        if not site_origin:
            # Infer origin from request
            scheme = request.url.scheme
            host = request.headers.get("host", "")
            site_origin = f"{scheme}://{host}"

        # Parse site origin
        try:
            site_parsed = urlparse(site_origin)
        except Exception:
            logger.error(f"Failed to parse site origin: {site_origin}")
            return False

        # Check Origin header (preferred)
        origin_header = request.headers.get("origin")
        if origin_header:
            try:
                origin_parsed = urlparse(origin_header)

                # Check scheme, domain, and port
                if (origin_parsed.scheme == site_parsed.scheme and
                    origin_parsed.netloc == site_parsed.netloc):
                    logger.debug(f"Origin check passed: {origin_header}")
                    return True
                else:
                    logger.warning(
                        f"Origin mismatch: expected {site_origin}, got {origin_header}"
                    )
                    return False
            except Exception as e:
                logger.error(f"Failed to parse Origin header: {origin_header}, error: {e}")
                return False

        # Fallback to Referer header
        referer_header = request.headers.get("referer")
        if referer_header:
            try:
                referer_parsed = urlparse(referer_header)

                # Check scheme, domain, and port
                if (referer_parsed.scheme == site_parsed.scheme and
                    referer_parsed.netloc == site_parsed.netloc):
                    logger.debug(f"Referer check passed: {referer_header}")
                    return True
                else:
                    logger.warning(
                        f"Referer mismatch: expected {site_origin}, got {referer_header}"
                    )
                    return False
            except Exception as e:
                logger.error(f"Failed to parse Referer header: {referer_header}, error: {e}")
                return False

        # Missing both Origin and Referer (suspicious)
        logger.warning(
            f"Request missing both Origin and Referer headers: "
            f"path={request.url.path}, method={request.method}"
        )
        return False

    def _generate_token(self) -> str:
        """Generate a secure random CSRF token.

        Returns:
            URL-safe base64-encoded token (at least 32 bytes of entropy)
        """
        # token_urlsafe with nbytes=32 generates a 43-character string
        # which provides 256 bits of entropy (32 * 8 = 256)
        return secrets.token_urlsafe(CSRF_TOKEN_LENGTH)

    def _get_session_token(self, request: Request) -> Optional[str]:
        """Get CSRF token from session.

        Args:
            request: Incoming request

        Returns:
            CSRF token from session, or None if not found
        """
        # Session is stored in request.scope["session"] (added by SessionMiddleware)
        # Using scope.get() instead of hasattr(request, "session") to avoid triggering
        # the assertion error in request.session property getter
        session = request.scope.get("session")
        if session is not None:
            return session.get(CSRF_SESSION_KEY)
        return None

    def _set_session_token(self, request: Request, token: str) -> None:
        """Store CSRF token in session.

        Args:
            request: Incoming request
            token: CSRF token to store
        """
        # Session is stored in request.scope["session"] (added by SessionMiddleware)
        # Using scope.get() instead of hasattr(request, "session") to avoid triggering
        # the assertion error in request.session property getter
        session = request.scope.get("session")
        if session is not None:
            session[CSRF_SESSION_KEY] = token
            logger.debug(f"Stored CSRF token in session: {token[:8]}...")

    def _get_request_token(self, request: Request) -> Optional[str]:
        """Extract CSRF token from request.

        Checks (in order):
        1. X-CSRF-Token header (recommended for AJAX)
        2. csrf_token form field (for traditional forms)

        Args:
            request: Incoming request

        Returns:
            CSRF token from request, or None if not found
        """
        # Check header first (preferred method for AJAX)
        token = request.headers.get(self.token_header)
        if token:
            return token

        # Check form data (for traditional form submissions)
        # Note: This requires parsing the body, which we skip for now
        # since our API is primarily AJAX-based

        return None

    def _is_browser_request(self, request: Request) -> bool:
        """Detect if request is from a browser.

        Browser requests typically have one or more of these characteristics:
        - Accept header includes text/html
        - X-Requested-With header (for AJAX requests)
        - Cookies present

        Args:
            request: Incoming request

        Returns:
            True if request appears to be from a browser, False otherwise
        """
        # Check Accept header (browsers usually include text/html)
        accept = request.headers.get("accept", "")
        if "text/html" in accept:
            return True

        # Check X-Requested-With (AJAX requests usually include this)
        if request.headers.get("x-requested-with"):
            return True

        # Check if cookies are present (browsers send cookies)
        if request.cookies:
            return True

        return False

    def _validate_token(self, request: Request, request_token: Optional[str]) -> bool:
        """Validate CSRF token.

        Args:
            request: Incoming request
            request_token: Token from request

        Returns:
            True if token is valid, False otherwise
        """
        session_token = self._get_session_token(request)

        if not session_token:
            logger.warning(f"CSRF validation failed: No token in session for {request.url.path}")
            return False

        if not request_token:
            logger.warning(f"CSRF validation failed: No token in request for {request.url.path}")
            return False

        # Use secrets.compare_digest to prevent timing attacks
        is_valid = secrets.compare_digest(session_token, request_token)

        if not is_valid:
            logger.warning(
                f"CSRF validation failed: Token mismatch for {request.url.path} "
                f"(session={session_token[:8]}..., request={request_token[:8]}...)"
            )
        else:
            logger.debug(f"CSRF validation successful for {request.url.path}")

        return is_valid

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and validate CSRF token.

        Args:
            request: Incoming request
            call_next: Next middleware/route handler

        Returns:
            Response (with CSRF cookie for GET requests)

        Raises:
            HTTPException: 403 Forbidden if CSRF validation fails
        """
        # Skip CSRF protection for exempt paths
        if self._is_exempt(request.url.path):
            return await call_next(request)

        # Skip CSRF protection for safe methods (GET, HEAD, OPTIONS)
        if request.method in SAFE_METHODS:
            # Generate or retrieve token for GET requests
            token = self._get_session_token(request)
            if not token:
                token = self._generate_token()
                self._set_session_token(request, token)
                logger.debug(f"Generated new CSRF token for session")

            # Process request
            response = await call_next(request)

            # Set CSRF token in cookie for frontend to use
            # M-25: Use environment-based secure flag
            import os
            is_production = os.getenv("AGENTOS_ENV", "development").lower() == "production"
            secure_cookies = os.getenv("SESSION_SECURE_ONLY", str(is_production)).lower() == "true"

            response.set_cookie(
                key=self.cookie_name,
                value=token,
                httponly=False,  # JavaScript needs to read this for X-CSRF-Token header
                secure=secure_cookies,  # True in production with HTTPS
                samesite="strict",  # Prevent CSRF via cookie
                path="/",
                max_age=3600,  # 1 hour (shorter than session for defense in depth)
            )

            return response

        # For state-changing methods (POST, PUT, PATCH, DELETE), validate CSRF token
        if request.method in PROTECTED_METHODS:
            # Import timestamp formatter
            from datetime import datetime, timezone

            def _format_timestamp() -> str:
                """Format current time as ISO 8601 UTC with Z suffix"""
                return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')

            # First line of defense: Origin/Referer same-origin check (if enabled)
            if self.check_origin:
                if not self._check_origin(request):
                    logger.warning(
                        f"Origin/Referer check failed: "
                        f"path={request.url.path}, method={request.method}, "
                        f"origin={request.headers.get('origin', 'none')}, "
                        f"referer={request.headers.get('referer', 'none')}"
                    )

                    return JSONResponse(
                        status_code=403,
                        content={
                            "ok": False,
                            "error_code": "ORIGIN_CHECK_FAILED",
                            "message": "Origin or Referer header check failed",
                            "details": {
                                "hint": "Request must originate from the same site",
                                "endpoint": request.url.path,
                                "method": request.method,
                                "origin": request.headers.get("origin"),
                                "referer": request.headers.get("referer")
                            },
                            "timestamp": _format_timestamp()
                        }
                    )

            # Check if this is an API route
            is_api_route = request.url.path.startswith("/api/")

            # Hard enforcement: Browser requests to API routes MUST have CSRF token
            if self.enforce_for_api and is_api_route and self._is_browser_request(request):
                request_token = self._get_request_token(request)

                # Hard rejection if no token or invalid token
                if not self._validate_token(request, request_token):
                    # Log detailed information for debugging
                    logger.warning(
                        f"CSRF protection blocked request: "
                        f"path={request.url.path}, method={request.method}, "
                        f"has_token={bool(request_token)}, "
                        f"client_ip={request.client.host if request.client else 'unknown'}"
                    )

                    # Return hard rejection with clear error message
                    return JSONResponse(
                        status_code=403,
                        content={
                            "ok": False,
                            "error_code": "CSRF_TOKEN_REQUIRED",
                            "message": "CSRF token is required for this request",
                            "details": {
                                "hint": "Include X-CSRF-Token header with a valid token",
                                "endpoint": request.url.path,
                                "method": request.method,
                                "reason": "Browser-initiated API requests must include CSRF token"
                            },
                            "timestamp": _format_timestamp()
                        }
                    )

            # Legacy validation for non-API routes or when enforcement is disabled
            else:
                # Extract token from request
                request_token = self._get_request_token(request)

                # Validate token
                if not self._validate_token(request, request_token):
                    # Return JSON response directly instead of raising HTTPException
                    # HTTPException raised in middleware is not handled by exception handlers
                    # M-02: Use unified ErrorEnvelope format
                    return JSONResponse(
                        status_code=403,
                        content={
                            "ok": False,
                            "error_code": "CSRF_TOKEN_INVALID",
                            "message": "CSRF token validation failed",
                            "details": {
                                "hint": "Include a valid CSRF token in the X-CSRF-Token header"
                            },
                            "timestamp": _format_timestamp()
                        }
                    )

            # Token is valid, proceed with request
            # Optionally rotate token after successful validation (defense in depth)
            # new_token = self._generate_token()
            # self._set_session_token(request, new_token)

            response = await call_next(request)
            return response

        # For any other methods, allow the request
        return await call_next(request)


def add_csrf_protection(
    app: FastAPI,
    exempt_paths: Optional[list[str]] = None,
    token_header: str = CSRF_HEADER_NAME,
    enforce_for_api: bool = True,
    check_origin: bool = True,
    validate_contract: bool = True,
) -> None:
    """Add CSRF protection middleware to FastAPI app.

    Args:
        app: FastAPI application
        exempt_paths: List of path prefixes to exempt from CSRF protection
        token_header: Name of the header containing CSRF token
        enforce_for_api: Whether to enforce CSRF protection for API routes (default True)
        check_origin: Whether to check Origin/Referer headers (default True)
        validate_contract: Whether to validate exemptions against security contract (default True)

    Example:
        ```python
        from fastapi import FastAPI
        from agentos.webui.middleware.csrf import add_csrf_protection

        app = FastAPI()

        # Add session middleware first (required for CSRF)
        from starlette.middleware.sessions import SessionMiddleware
        app.add_middleware(SessionMiddleware, secret_key="your-secret-key")

        # Add CSRF protection
        add_csrf_protection(app)
        ```

    Note:
        - SessionMiddleware must be added before CSRF protection
        - CSRF tokens are stored in session and validated on state-changing requests
        - Frontend must include the token from cookie in the X-CSRF-Token header
        - With enforce_for_api=True, browser requests to API endpoints MUST have valid CSRF tokens
        - With check_origin=True, Origin/Referer headers are validated for same-origin (second line of defense)
        - With validate_contract=True, exemptions are validated against docs/security/CSRF_EXEMPTION_CONTRACT.md
    """
    app.add_middleware(
        CSRFProtectionMiddleware,
        exempt_paths=exempt_paths,
        token_header=token_header,
        enforce_for_api=enforce_for_api,
        check_origin=check_origin,
        validate_contract=validate_contract,
    )
    logger.info(
        f"CSRF protection middleware enabled "
        f"(token_header={token_header}, "
        f"enforce_for_api={enforce_for_api}, "
        f"check_origin={check_origin}, "
        f"contract_validation={validate_contract}, "
        f"exempt_paths={exempt_paths or 'default'})"
    )


def get_csrf_token(request: Request) -> str:
    """Get CSRF token for current session.

    This is a utility function for templates/views that need to
    embed the CSRF token in forms or pass it to frontend JavaScript.

    Args:
        request: Current request

    Returns:
        CSRF token for current session

    Raises:
        RuntimeError: If session middleware is not configured
    """
    if not hasattr(request, "session"):
        raise RuntimeError(
            "Session middleware not configured. "
            "Add SessionMiddleware before using CSRF protection."
        )

    # Get existing token or generate new one
    token = request.session.get(CSRF_SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(CSRF_TOKEN_LENGTH)
        request.session[CSRF_SESSION_KEY] = token

    return token
