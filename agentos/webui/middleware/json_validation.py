"""
JSON Validation Middleware

This middleware intercepts HTTP requests with JSON payloads and validates
that they contain valid JSON. Invalid JSON (including NaN, Infinity, etc.)
is rejected with a 400 Bad Request instead of allowing it to propagate as
a 500 Internal Server Error.

Addresses: M-1 from BACKLOG_REMAINING.md
"""

import json
import logging
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class JSONValidationMiddleware(BaseHTTPMiddleware):
    """
    Middleware to validate JSON payloads in POST/PUT/PATCH requests.

    This prevents invalid JSON values (NaN, Infinity, -Infinity) from
    causing 500 errors and instead returns a proper 400 Bad Request.

    Security Benefits:
    - Prevents information leakage via stack traces
    - Provides clear error messages to clients
    - Stops invalid data at the API boundary
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Intercept requests and validate JSON payloads.

        Args:
            request: The incoming HTTP request
            call_next: The next middleware/route handler

        Returns:
            Response from the next handler or error response
        """
        # Only validate JSON for methods that typically have request bodies
        if request.method in ["POST", "PUT", "PATCH"]:
            # Check if the request has a JSON content type
            content_type = request.headers.get("content-type", "")

            if "application/json" in content_type.lower():
                try:
                    # Read the request body
                    body = await request.body()

                    if body:
                        # Attempt to parse the JSON
                        # This will raise JSONDecodeError for invalid JSON
                        # including NaN, Infinity, and -Infinity
                        json.loads(body.decode("utf-8"))

                        # IMPORTANT: Reset the request body so it can be read again
                        # by FastAPI's body parsing
                        async def receive():
                            return {"type": "http.request", "body": body}

                        request._receive = receive

                except json.JSONDecodeError as e:
                    # Invalid JSON - return 400 Bad Request
                    logger.warning(
                        f"Invalid JSON in {request.method} {request.url.path}: {e}",
                        extra={
                            "method": request.method,
                            "path": request.url.path,
                            "error": str(e),
                            "line": e.lineno,
                            "column": e.colno,
                        }
                    )

                    # M-02: Use unified ErrorEnvelope format
                    from datetime import datetime, timezone

                    def _format_timestamp() -> str:
                        """Format current time as ISO 8601 UTC with Z suffix"""
                        return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')

                    return JSONResponse(
                        status_code=400,
                        content={
                            "ok": False,
                            "error_code": "INVALID_JSON",
                            "message": "Invalid JSON in request body",
                            "details": {
                                "hint": f"JSON parsing error at line {e.lineno}, column {e.colno}: {e.msg}",
                                "line": e.lineno,
                                "column": e.colno,
                                "parse_error": e.msg,
                            },
                            "timestamp": _format_timestamp()
                        }
                    )

                except UnicodeDecodeError as e:
                    # Invalid UTF-8 encoding
                    logger.warning(
                        f"Invalid UTF-8 encoding in {request.method} {request.url.path}: {e}",
                        extra={
                            "method": request.method,
                            "path": request.url.path,
                            "error": str(e),
                        }
                    )

                    # M-02: Use unified ErrorEnvelope format
                    from datetime import datetime, timezone

                    def _format_timestamp() -> str:
                        """Format current time as ISO 8601 UTC with Z suffix"""
                        return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')

                    return JSONResponse(
                        status_code=400,
                        content={
                            "ok": False,
                            "error_code": "INVALID_ENCODING",
                            "message": "Invalid UTF-8 encoding in request body",
                            "details": {
                                "hint": "Request body must be valid UTF-8 encoded text"
                            },
                            "timestamp": _format_timestamp()
                        }
                    )

                except Exception as e:
                    # Unexpected error - log and continue
                    logger.error(
                        f"Unexpected error in JSON validation middleware: {e}",
                        exc_info=True
                    )
                    # Allow the request to proceed - let the application handle it

        # Continue to the next middleware/handler
        response = await call_next(request)
        return response


def add_json_validation_middleware(app):
    """
    Add JSON validation middleware to the FastAPI application.

    This should be added early in the middleware chain to catch
    invalid JSON before it reaches the application logic.

    Usage:
        from agentos.webui.middleware.json_validation import add_json_validation_middleware
        add_json_validation_middleware(app)

    Args:
        app: FastAPI application instance
    """
    app.add_middleware(JSONValidationMiddleware)
    logger.info("JSON validation middleware enabled (protects against NaN/Infinity)")
