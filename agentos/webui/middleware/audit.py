"""
Audit Middleware - Automatic audit logging for write operations

This middleware automatically records audit events for write operations (POST, PUT, DELETE)
to provide complete traceability of API actions.

Created for Agent-API-Contract (Wave1-A3)

Key Features:
1. Automatic audit recording for write operations
2. Captures user_id, action, target, timestamp, result
3. Extracts task_id and repo_id from request path
4. Records to task_audits table
5. Best-effort: Audit failures never block business requests warning
"""

import json
import logging
import time
from datetime import datetime
from typing import Callable, Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from agentos.core.task.audit_service import TaskAuditService
from agentos.store import get_db

logger = logging.getLogger(__name__)


class AuditMiddleware(BaseHTTPMiddleware):
    """Audit middleware for automatic write operation logging

    Records all write operations (POST, PUT, DELETE) to task_audits table.
    Extracts task_id and repo_id from request path when available.
    """

    # HTTP methods that trigger audit
    AUDIT_METHODS = {"POST", "PUT", "DELETE", "PATCH"}

    # Paths to exclude from auditing (health checks, static files, etc.)
    EXCLUDE_PATHS = {
        "/health",
        "/api/health",
        "/static",
        "/favicon.ico",
    }

    def __init__(self, app: ASGIApp):
        """Initialize audit middleware

        Args:
            app: ASGI application
        """
        super().__init__(app)

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        """Process request and record audit if needed

        Args:
            request: FastAPI request
            call_next: Next middleware/handler

        Returns:
            Response from downstream handler
        """
        # Skip audit for excluded paths
        if self._should_skip_audit(request):
            return await call_next(request)

        # Skip audit for non-write operations
        if request.method not in self.AUDIT_METHODS:
            return await call_next(request)

        # Capture request metadata
        start_time = time.time()
        request_metadata = self._extract_request_metadata(request)

        # Set log context for this request
        from agentos.core.logging.context import set_log_context, clear_log_context
        set_log_context(
            task_id=request_metadata.get("task_id"),
            session_id=request.headers.get("X-Session-ID")  # Extract session from header
        )

        try:
            # Execute request
            response = await call_next(request)
        finally:
            # Clear log context after request completes
            clear_log_context()

        # Record audit (async, best-effort)
        try:
            duration_ms = int((time.time() - start_time) * 1000)
            await self._record_audit(request, response, request_metadata, duration_ms)
        except Exception as e:
            # Log error but don't fail the request
            logger.error(f"Failed to record audit: {e}", exc_info=True)

        return response

    def _should_skip_audit(self, request: Request) -> bool:
        """Check if request should be skipped from auditing

        Args:
            request: FastAPI request

        Returns:
            True if should skip audit, False otherwise
        """
        path = request.url.path

        # Check exact path matches
        if path in self.EXCLUDE_PATHS:
            return True

        # Check prefix matches
        for exclude_path in self.EXCLUDE_PATHS:
            if path.startswith(exclude_path):
                return True

        return False

    def _extract_request_metadata(self, request: Request) -> dict:
        """Extract metadata from request

        Args:
            request: FastAPI request

        Returns:
            Metadata dictionary
        """
        # Extract user_id from headers or auth
        user_id = self._extract_user_id(request)

        # Extract task_id from path (e.g., /api/tasks/{task_id}/action)
        task_id = self._extract_task_id(request)

        # Extract repo_id from path or query params
        repo_id = self._extract_repo_id(request)

        return {
            "user_id": user_id,
            "task_id": task_id,
            "repo_id": repo_id,
            "method": request.method,
            "path": request.url.path,
            "query_params": dict(request.query_params),
        }

    def _extract_user_id(self, request: Request) -> Optional[str]:
        """Extract user ID from request

        Args:
            request: FastAPI request

        Returns:
            User ID or None
        """
        # Try X-User-Token header
        user_token = request.headers.get("X-User-Token")
        if user_token:
            return user_token

        # Try Authorization header
        auth_header = request.headers.get("Authorization")
        if auth_header:
            # Extract from Bearer token or Basic auth
            if auth_header.startswith("Bearer "):
                return auth_header[7:]
            elif auth_header.startswith("Basic "):
                return auth_header[6:]

        # Default to "anonymous"
        return "anonymous"

    def _extract_task_id(self, request: Request) -> Optional[str]:
        """Extract task_id from request path

        Args:
            request: FastAPI request

        Returns:
            Task ID or None
        """
        # Parse path for task_id (e.g., /api/tasks/{task_id}/...)
        path_parts = request.url.path.split("/")

        try:
            # Look for "tasks" in path and get next segment
            if "tasks" in path_parts:
                task_idx = path_parts.index("tasks")
                if task_idx + 1 < len(path_parts):
                    task_id = path_parts[task_idx + 1]
                    # Validate task_id format (ULID is 26 chars)
                    if len(task_id) >= 10:
                        return task_id

            # Look for "execution" in path (e.g., /api/execution/{task_id}/...)
            if "execution" in path_parts:
                exec_idx = path_parts.index("execution")
                if exec_idx + 1 < len(path_parts):
                    task_id = path_parts[exec_idx + 1]
                    if len(task_id) >= 10:
                        return task_id
        except (ValueError, IndexError):
            pass

        return None

    def _extract_repo_id(self, request: Request) -> Optional[str]:
        """Extract repo_id from request path or query params

        Args:
            request: FastAPI request

        Returns:
            Repository ID or None
        """
        # Try query params first
        repo_id = request.query_params.get("repo_id")
        if repo_id:
            return repo_id

        # Parse path for repo_id (e.g., /api/repos/{repo_id}/...)
        path_parts = request.url.path.split("/")

        try:
            if "repos" in path_parts:
                repo_idx = path_parts.index("repos")
                if repo_idx + 1 < len(path_parts):
                    return path_parts[repo_idx + 1]
        except (ValueError, IndexError):
            pass

        return None

    async def _record_audit(
        self,
        request: Request,
        response: Response,
        metadata: dict,
        duration_ms: int,
    ) -> None:
        """Record audit event to database (best-effort)

        审计失败不应该影响业务请求的返回。
        所有异常都被捕获并记录为 WARNING，不会抛出。

        Args:
            request: FastAPI request
            response: FastAPI response
            metadata: Request metadata
            duration_ms: Request duration in milliseconds
        """
        try:
            # Initialize audit service
            db = get_db()
            audit_service = TaskAuditService(db=db)

            # Determine operation status
            status = "success" if 200 <= response.status_code < 400 else "failed"

            # Determine event type
            event_type = self._determine_event_type(request, metadata)

            # Build audit payload
            payload = {
                "method": metadata["method"],
                "path": metadata["path"],
                "query_params": metadata["query_params"],
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "user_id": metadata["user_id"],
            }

            # Add error message if failed
            if status == "failed":
                payload["error_message"] = f"Request failed with status {response.status_code}"

            # Record audit
            task_id = metadata.get("task_id") or "system"
            repo_id = metadata.get("repo_id")

            # Best-effort: 使用较短超时，不阻塞业务
            audit_service.record_operation(
                task_id=task_id,
                operation=metadata["method"].lower(),
                repo_id=repo_id,
                status=status,
                event_type=event_type,
                level="info" if status == "success" else "warn",
                **payload,
            )

            logger.debug(
                f"Recorded audit: task={task_id}, event={event_type}, "
                f"status={status}, duration={duration_ms}ms"
            )

        except TimeoutError as e:
            # 超时：审计系统繁忙，记录 warning
            logger.warning(
                f"Audit timeout (system busy, audit dropped): "
                f"task={metadata.get('task_id', 'unknown')}, "
                f"path={metadata.get('path')}, "
                f"error={str(e)}"
            )
        except Exception as e:
            # 其他异常：记录详细错误，但不影响业务
            logger.warning(
                f"Audit failed (best-effort, dropped): "
                f"task={metadata.get('task_id', 'unknown')}, "
                f"path={metadata.get('path')}, "
                f"error={str(e)}"
            )
            # 开发环境下输出完整堆栈
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("Audit failure details:", exc_info=True)

    def _determine_event_type(self, request: Request, metadata: dict) -> str:
        """Determine event type from request

        Args:
            request: FastAPI request
            metadata: Request metadata

        Returns:
            Event type string
        """
        path = metadata["path"]
        method = metadata["method"]

        # Map common endpoints to event types
        if "/tasks/" in path:
            if method == "POST":
                if "/approve" in path:
                    return "task_approved"
                elif "/queue" in path:
                    return "task_queued"
                elif "/start" in path:
                    return "task_started"
                elif "/complete" in path:
                    return "task_completed"
                elif "/cancel" in path:
                    return "task_canceled"
                else:
                    return "task_created"
            elif method == "PUT":
                return "task_updated"
            elif method == "DELETE":
                return "task_deleted"

        elif "/execution/" in path:
            return "execution_action"

        elif "/repos/" in path or "/repositories/" in path:
            if method == "POST":
                return "repo_write"
            elif method == "PUT":
                return "repo_update"
            elif method == "DELETE":
                return "repo_delete"

        # Generic event type
        return f"api_{method.lower()}"


# ============================================
# Middleware Registration Helper
# ============================================

def add_audit_middleware(app):
    """Add audit middleware to FastAPI app

    Args:
        app: FastAPI application

    Example:
        from fastapi import FastAPI
        from agentos.webui.middleware.audit import add_audit_middleware

        app = FastAPI()
        add_audit_middleware(app)
    """
    app.add_middleware(AuditMiddleware)
    logger.info("Audit middleware registered")
