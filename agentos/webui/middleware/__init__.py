"""
WebUI Middleware

v0.3.2 Closeout - Security and privacy hardening
Task #34: XSS protection with CSP headers
Task #36: CSRF protection for Extensions interface
"""

from agentos.webui.middleware.sanitize import sanitize_response, mask_sensitive_fields
from agentos.webui.middleware.security import add_security_headers, add_xss_headers
from agentos.webui.middleware.csrf import add_csrf_protection, get_csrf_token

__all__ = [
    "sanitize_response",
    "mask_sensitive_fields",
    "add_security_headers",
    "add_xss_headers",
    "add_csrf_protection",
    "get_csrf_token",
]
