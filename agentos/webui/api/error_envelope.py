"""
API Error Envelope - Unified error response format for M-02 API Contract Consistency

This module provides a standardized error response structure and exception handlers
to ensure consistent error formatting across all AgentOS WebUI API endpoints.

Created for BACKLOG M-02: Error Response Format Unification
"""

from datetime import datetime, timezone
from typing import Dict, Any, Optional
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import logging
from agentos.core.time import utc_now


logger = logging.getLogger(__name__)


def _format_timestamp() -> str:
    """Format current time as ISO 8601 UTC with Z suffix"""
    return utc_now().strftime('%Y-%m-%dT%H:%M:%S.%fZ')


class ErrorEnvelope:
    """
    Unified error response envelope

    Ensures all error responses follow the same structure:
    {
        "ok": false,
        "error_code": "VALIDATION_ERROR",
        "message": "Request validation failed",
        "details": {...},
        "timestamp": "2024-01-31T12:34:56.789Z"
    }
    """

    @staticmethod
    def format_error(
        error_code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        status_code: int = 400
    ) -> Dict[str, Any]:
        """
        Format an error response with consistent structure

        Args:
            error_code: Machine-readable error code (e.g., "VALIDATION_ERROR", "NOT_FOUND")
            message: Human-readable error message
            details: Additional error details (optional)
            status_code: HTTP status code (not included in response body, used for context)

        Returns:
            Standardized error response dictionary with compatibility aliases:
            - reason_code (alias for error_code, backwards compatibility)
            - hint (top-level, extracted from details.hint if present)
        """
        details = details or {}

        # Build response with new standard fields
        response = {
            "ok": False,
            "error_code": error_code,
            "message": message,
            "details": details,
            "timestamp": _format_timestamp()
        }

        # Backwards compatibility: Add alias fields
        response["reason_code"] = error_code  # Alias for error_code

        # Extract hint from details to top-level (if present)
        if "hint" in details:
            response["hint"] = details["hint"]

        return response

    @staticmethod
    def format_success(
        data: Any,
        message: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Format a success response with consistent structure

        Args:
            data: Response data
            message: Optional success message

        Returns:
            Standardized success response dictionary
        """
        response = {
            "ok": True,
            "data": data,
            "timestamp": _format_timestamp()
        }

        if message:
            response["message"] = message

        return response


def register_error_handlers(app: FastAPI) -> None:
    """
    Register global error handlers for consistent error responses

    This should be called during application startup to ensure all
    exceptions are handled consistently.

    Args:
        app: FastAPI application instance
    """

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """
        Handle Pydantic validation errors

        Converts FastAPI/Pydantic validation errors into our standard format
        """
        errors = exc.errors()

        # Format validation errors for better readability
        formatted_errors = []
        for error in errors:
            formatted_errors.append({
                "field": " -> ".join(str(loc) for loc in error["loc"]),
                "message": error["msg"],
                "type": error["type"]
            })

        logger.warning(
            f"Validation error on {request.method} {request.url.path}: {formatted_errors}"
        )

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=ErrorEnvelope.format_error(
                error_code="VALIDATION_ERROR",
                message="Request validation failed",
                details={"errors": formatted_errors},
                status_code=422
            )
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        """
        Handle HTTPException with unified format

        If the exception detail is already in our format, pass it through.
        Otherwise, wrap it in our standard envelope.
        """
        detail = exc.detail

        # Check if detail is already in our standard format
        if isinstance(detail, dict) and "error_code" in detail:
            # Already formatted - ensure timestamp is present
            if "timestamp" not in detail:
                detail["timestamp"] = _format_timestamp()
            return JSONResponse(
                status_code=exc.status_code,
                content=detail
            )

        # Map HTTP status codes to error codes
        error_code_map = {
            400: "BAD_REQUEST",
            401: "UNAUTHORIZED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            405: "METHOD_NOT_ALLOWED",
            409: "CONFLICT",
            422: "VALIDATION_ERROR",
            429: "RATE_LIMITED",
            500: "INTERNAL_ERROR",
            502: "BAD_GATEWAY",
            503: "SERVICE_UNAVAILABLE",
            504: "GATEWAY_TIMEOUT"
        }

        error_code = error_code_map.get(exc.status_code, "HTTP_ERROR")

        logger.warning(
            f"HTTP exception on {request.method} {request.url.path}: "
            f"status={exc.status_code}, detail={detail}"
        )

        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorEnvelope.format_error(
                error_code=error_code,
                message=str(detail) if detail else "An error occurred",
                details=None,
                status_code=exc.status_code
            )
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """
        Catch-all handler for unhandled exceptions

        Ensures even unexpected errors return a consistent format.
        Integrates with Sentry if available.
        """
        # Always log the full error with stack trace
        logger.error(
            f"Unhandled exception on {request.method} {request.url.path}",
            exc_info=exc
        )

        # Report to Sentry if available and enabled
        try:
            import sentry_sdk
            import os
            SENTRY_ENABLED = os.getenv("SENTRY_ENABLED", "true").lower() == "true"
            if SENTRY_ENABLED:
                sentry_sdk.capture_exception(exc)
        except ImportError:
            pass  # Sentry not installed
        except Exception as e:
            logger.warning(f"Failed to report exception to Sentry: {e}")

        # Get environment and debug settings
        import os
        is_debug = os.getenv("AGENTOS_DEBUG", "false").lower() == "true"
        environment = os.getenv("AGENTOS_ENV", "development").lower()

        # In production, don't expose internal error details
        if environment == "production" or not is_debug:
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content=ErrorEnvelope.format_error(
                    error_code="INTERNAL_ERROR",
                    message="Internal server error",
                    details={"hint": "An unexpected error occurred. Please contact support if the issue persists."},
                    status_code=500
                )
            )

        # Development mode: Return detailed error information for debugging
        import traceback

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorEnvelope.format_error(
                error_code="INTERNAL_ERROR",
                message=f"{type(exc).__name__}: {str(exc)}",
                details={
                    "hint": "An unexpected error occurred. See debug_info below (DEBUG mode).",
                    "debug_info": {
                        "exception_type": type(exc).__name__,
                        "exception_message": str(exc),
                        "traceback": traceback.format_exc(),
                        "request_path": str(request.url.path),
                        "request_method": request.method
                    }
                },
                status_code=500
            )
        )

    logger.info("Registered unified error handlers (M-02)")


# Convenience exception classes for common patterns

class APIError(Exception):
    """
    Base API error with support for unified error envelope

    Example:
        raise APIError(
            error_code="TASK_NOT_FOUND",
            message="Task does not exist",
            details={"task_id": "123"},
            status_code=404
        )
    """

    def __init__(
        self,
        error_code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        status_code: int = 400
    ):
        self.error_code = error_code
        self.message = message
        self.details = details
        self.status_code = status_code
        super().__init__(message)

    def to_response(self) -> JSONResponse:
        """Convert to JSONResponse"""
        return JSONResponse(
            status_code=self.status_code,
            content=ErrorEnvelope.format_error(
                error_code=self.error_code,
                message=self.message,
                details=self.details,
                status_code=self.status_code
            )
        )


class ValidationError(APIError):
    """Validation error (400)"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__("VALIDATION_ERROR", message, details, 400)


class NotFoundError(APIError):
    """Resource not found (404)"""
    def __init__(self, resource: str, identifier: str, details: Optional[Dict[str, Any]] = None):
        message = f"{resource} not found: {identifier}"
        super().__init__("NOT_FOUND", message, details, 404)


class ConflictError(APIError):
    """Resource conflict (409)"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__("CONFLICT", message, details, 409)


class RateLimitError(APIError):
    """Rate limit exceeded (429)"""
    def __init__(self, message: str = "Rate limit exceeded", details: Optional[Dict[str, Any]] = None):
        super().__init__("RATE_LIMITED", message, details, 429)
