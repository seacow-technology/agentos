"""Extension Execution Governance Service

Provides authorization, audit, and policy enforcement for extension execution.

Wave C3: Extension Execute Real Implementation
==============================================

Security Layers:
1. Pre-execution authorization checks
2. Complete execution audit trail
3. Authorization lifecycle management
4. Policy enforcement (count limits, expiration)

Red Lines:
- All extension execution MUST check authorization
- All executions (including blocked) MUST be logged
- No silent execution without audit trail
- No bypass of authorization checks

Created: 2026-02-01
"""

import logging
import sqlite3
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from pathlib import Path

from agentos.core.time.clock import utc_now, utc_now_ms
from agentos.core.storage.paths import component_db_path

logger = logging.getLogger(__name__)


@dataclass
class AuthorizationRequest:
    """Authorization request for extension execution"""
    extension_id: str
    action_id: str
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    metadata: Optional[Dict] = None


@dataclass
class AuthorizationResult:
    """Result of authorization check"""
    allowed: bool
    auth_id: Optional[str] = None
    reason: Optional[str] = None  # Denial reason if not allowed


@dataclass
class ExecutionRecord:
    """Record of extension execution for audit trail"""
    execution_id: str
    extension_id: str
    action_id: str
    runner_type: str
    status: str
    auth_id: Optional[str] = None
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    exit_code: Optional[int] = None
    duration_ms: Optional[int] = None
    output_preview: Optional[str] = None
    error_message: Optional[str] = None
    blocked_reason: Optional[str] = None
    sandbox_mode: Optional[str] = None
    started_at: int = 0
    completed_at: Optional[int] = None


class ExtensionGovernanceService:
    """
    Extension Execution Governance Service

    Provides:
    1. Pre-execution authorization checks
    2. Execution audit trail logging
    3. Authorization lifecycle management
    4. Policy enforcement

    Authorization Priority (checked in order):
    1. Session-scoped authorization (most specific)
    2. User-scoped authorization
    3. Global authorization (least specific)

    Usage:
        >>> service = ExtensionGovernanceService()
        >>>
        >>> # Create authorization
        >>> auth_id = service.create_authorization(
        ...     extension_id="tools.postman",
        ...     action_id="get",
        ...     authorized_by="user-123",
        ...     scope="session",
        ...     scope_id="session-456"
        ... )
        >>>
        >>> # Check authorization before execution
        >>> request = AuthorizationRequest(
        ...     extension_id="tools.postman",
        ...     action_id="get",
        ...     session_id="session-456"
        ... )
        >>> result = service.check_authorization(request)
        >>> if result.allowed:
        ...     # Execute extension
        ...     exec_id = service.log_execution_start(...)
        ...     # ... execution ...
        ...     service.log_execution_complete(exec_id, "success")
        ... else:
        ...     # Block execution
        ...     service.log_execution_blocked(...)
    """

    def __init__(self, db_path: Optional[str] = None):
        """Initialize governance service

        Args:
            db_path: Database path (default: component_db_path('agentos'))
        """
        if db_path is None:
            db_path = str(component_db_path('agentos'))
        self.db_path = db_path

    # ==========================================================================
    # Authorization Management
    # ==========================================================================

    def create_authorization(
        self,
        extension_id: str,
        action_id: str,
        authorized_by: str,
        scope: str = "session",
        scope_id: Optional[str] = None,
        expires_at: Optional[int] = None,
        max_executions: Optional[int] = None,
        metadata: Optional[Dict] = None
    ) -> str:
        """
        Create an authorization for extension execution

        Args:
            extension_id: Extension to authorize (e.g., "tools.postman")
            action_id: Action to authorize (or '*' for all actions)
            authorized_by: Who granted authorization
            scope: Authorization scope ('user', 'session', 'global')
            scope_id: Scope identifier (user_id or session_id)
            expires_at: Expiration timestamp (epoch ms, None = never expires)
            max_executions: Maximum execution count (None = unlimited)
            metadata: Additional metadata

        Returns:
            auth_id: Authorization identifier

        Examples:
            >>> # Session-scoped authorization for specific action
            >>> auth_id = service.create_authorization(
            ...     extension_id="tools.postman",
            ...     action_id="get",
            ...     authorized_by="user-123",
            ...     scope="session",
            ...     scope_id="session-456"
            ... )

            >>> # Global authorization with execution limit
            >>> auth_id = service.create_authorization(
            ...     extension_id="tools.github",
            ...     action_id="*",  # All actions
            ...     authorized_by="admin",
            ...     scope="global",
            ...     max_executions=100
            ... )

            >>> # Time-limited authorization (expires in 1 hour)
            >>> import time
            >>> expires_at = int((time.time() + 3600) * 1000)
            >>> auth_id = service.create_authorization(
            ...     extension_id="tools.database",
            ...     action_id="query",
            ...     authorized_by="user-123",
            ...     scope="user",
            ...     scope_id="user-123",
            ...     expires_at=expires_at
            ... )
        """
        # Generate UUID v7-style ID with better uniqueness
        import random
        now_obj = utc_now()
        random_suffix = random.randint(1000, 9999)
        auth_id = f"auth-{now_obj.strftime('%Y%m%d%H%M%S')}-{now_obj.microsecond:06d}-{random_suffix}"

        now = utc_now_ms()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO extension_authorizations
                (auth_id, extension_id, action_id, authorized_by,
                 scope, scope_id, expires_at, max_executions,
                 execution_count, status, metadata, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 'active', ?, ?, ?)
            """, (
                auth_id,
                extension_id,
                action_id,
                authorized_by,
                scope,
                scope_id,
                expires_at,
                max_executions,
                json.dumps(metadata) if metadata else None,
                now,
                now
            ))
            conn.commit()

        logger.info(
            f"[Governance] Created authorization: {auth_id} "
            f"for {extension_id}/{action_id} (scope={scope})"
        )

        return auth_id

    def check_authorization(
        self,
        request: AuthorizationRequest
    ) -> AuthorizationResult:
        """
        Check if extension execution is authorized

        Checks in priority order:
        1. Session-scoped authorization (if session_id provided)
        2. User-scoped authorization (if user_id provided)
        3. Global authorization

        Validates:
        - Authorization status is 'active'
        - Not expired (expires_at > now)
        - Execution count limit not reached

        Args:
            request: Authorization request

        Returns:
            AuthorizationResult with decision and reason

        Examples:
            >>> # Check session authorization
            >>> request = AuthorizationRequest(
            ...     extension_id="tools.postman",
            ...     action_id="get",
            ...     session_id="session-456"
            ... )
            >>> result = service.check_authorization(request)
            >>> if result.allowed:
            ...     print(f"Authorized: {result.auth_id}")
            ... else:
            ...     print(f"Blocked: {result.reason}")
        """
        now = utc_now_ms()

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Check session-scoped authorization first
            if request.session_id:
                cursor.execute("""
                    SELECT auth_id, execution_count, max_executions
                    FROM extension_authorizations
                    WHERE extension_id = ?
                      AND (action_id = ? OR action_id = '*')
                      AND scope = 'session'
                      AND scope_id = ?
                      AND status = 'active'
                      AND (expires_at IS NULL OR expires_at > ?)
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (request.extension_id, request.action_id, request.session_id, now))

                row = cursor.fetchone()
                if row:
                    # Check execution count limit
                    if row['max_executions'] is not None:
                        if row['execution_count'] >= row['max_executions']:
                            return AuthorizationResult(
                                allowed=False,
                                reason=f"Execution limit reached: {row['execution_count']}/{row['max_executions']}"
                            )

                    return AuthorizationResult(
                        allowed=True,
                        auth_id=row['auth_id']
                    )

            # Check user-scoped authorization
            if request.user_id:
                cursor.execute("""
                    SELECT auth_id, execution_count, max_executions
                    FROM extension_authorizations
                    WHERE extension_id = ?
                      AND (action_id = ? OR action_id = '*')
                      AND scope = 'user'
                      AND scope_id = ?
                      AND status = 'active'
                      AND (expires_at IS NULL OR expires_at > ?)
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (request.extension_id, request.action_id, request.user_id, now))

                row = cursor.fetchone()
                if row:
                    # Check execution count limit
                    if row['max_executions'] is not None:
                        if row['execution_count'] >= row['max_executions']:
                            return AuthorizationResult(
                                allowed=False,
                                reason=f"Execution limit reached: {row['execution_count']}/{row['max_executions']}"
                            )

                    return AuthorizationResult(
                        allowed=True,
                        auth_id=row['auth_id']
                    )

            # Check global authorization
            cursor.execute("""
                SELECT auth_id, execution_count, max_executions
                FROM extension_authorizations
                WHERE extension_id = ?
                  AND (action_id = ? OR action_id = '*')
                  AND scope = 'global'
                  AND status = 'active'
                  AND (expires_at IS NULL OR expires_at > ?)
                ORDER BY created_at DESC
                LIMIT 1
            """, (request.extension_id, request.action_id, now))

            row = cursor.fetchone()
            if row:
                # Check execution count limit
                if row['max_executions'] is not None:
                    if row['execution_count'] >= row['max_executions']:
                        return AuthorizationResult(
                            allowed=False,
                            reason=f"Execution limit reached: {row['execution_count']}/{row['max_executions']}"
                        )

                return AuthorizationResult(
                    allowed=True,
                    auth_id=row['auth_id']
                )

        # No authorization found
        return AuthorizationResult(
            allowed=False,
            reason=f"No active authorization found for {request.extension_id}/{request.action_id}"
        )

    def increment_execution_count(self, auth_id: str):
        """Increment execution count for an authorization

        Args:
            auth_id: Authorization identifier

        Note:
            Should be called after successful authorization check
            to track usage against max_executions limit.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE extension_authorizations
                SET execution_count = execution_count + 1,
                    updated_at = ?
                WHERE auth_id = ?
            """, (utc_now_ms(), auth_id))
            conn.commit()

    def revoke_authorization(self, auth_id: str):
        """Revoke an authorization

        Args:
            auth_id: Authorization to revoke

        Note:
            Sets status to 'revoked', preventing future executions.
            Does not affect executions that already started.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE extension_authorizations
                SET status = 'revoked',
                    updated_at = ?
                WHERE auth_id = ?
            """, (utc_now_ms(), auth_id))
            conn.commit()

        logger.info(f"[Governance] Revoked authorization: {auth_id}")

    # ==========================================================================
    # Execution Audit Trail
    # ==========================================================================

    def log_execution_start(
        self,
        extension_id: str,
        action_id: str,
        runner_type: str,
        auth_id: Optional[str] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        sandbox_mode: str = "none",
        metadata: Optional[Dict] = None
    ) -> str:
        """
        Log the start of extension execution

        Args:
            extension_id: Extension being executed
            action_id: Action being executed
            runner_type: Runner type ('builtin', 'shell', 'simulated')
            auth_id: Authorization ID used (if any)
            session_id: Session context
            user_id: User context
            sandbox_mode: Sandbox mode ('none', 'restricted', 'isolated')
            metadata: Additional metadata (args, flags, etc.)

        Returns:
            execution_id: Execution record identifier

        Note:
            Must be paired with log_execution_complete() after execution.
        """
        import random
        now_obj = utc_now()
        random_suffix = random.randint(1000, 9999)
        execution_id = f"exec-{now_obj.strftime('%Y%m%d%H%M%S')}-{now_obj.microsecond:06d}-{random_suffix}"

        now = utc_now_ms()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO extension_executions
                (execution_id, extension_id, action_id, runner_type,
                 auth_id, session_id, user_id, status, sandbox_mode,
                 metadata, started_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'running', ?, ?, ?, ?)
            """, (
                execution_id,
                extension_id,
                action_id,
                runner_type,
                auth_id,
                session_id,
                user_id,
                sandbox_mode,
                json.dumps(metadata) if metadata else None,
                now,
                now
            ))
            conn.commit()

        logger.info(
            f"[Governance] Execution started: {execution_id} "
            f"({extension_id}/{action_id} via {runner_type})"
        )

        return execution_id

    def log_execution_complete(
        self,
        execution_id: str,
        status: str,
        exit_code: Optional[int] = None,
        duration_ms: Optional[int] = None,
        output_preview: Optional[str] = None,
        error_message: Optional[str] = None
    ):
        """
        Log the completion of extension execution

        Args:
            execution_id: Execution record ID
            status: Final status ('success' or 'failed')
            exit_code: Exit code (0=success)
            duration_ms: Execution duration in milliseconds
            output_preview: First 1000 chars of output
            error_message: Error details if failed

        Note:
            Output preview is automatically truncated to 1000 characters
            to prevent excessive database growth.
        """
        now = utc_now_ms()

        # Truncate output preview to 1000 chars
        if output_preview and len(output_preview) > 1000:
            output_preview = output_preview[:1000] + "... (truncated)"

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE extension_executions
                SET status = ?,
                    exit_code = ?,
                    duration_ms = ?,
                    output_preview = ?,
                    error_message = ?,
                    completed_at = ?
                WHERE execution_id = ?
            """, (
                status,
                exit_code,
                duration_ms,
                output_preview,
                error_message,
                now,
                execution_id
            ))
            conn.commit()

        logger.info(
            f"[Governance] Execution completed: {execution_id} "
            f"(status={status}, exit_code={exit_code}, duration={duration_ms}ms)"
        )

    def log_execution_blocked(
        self,
        extension_id: str,
        action_id: str,
        runner_type: str,
        blocked_reason: str,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> str:
        """
        Log a blocked execution attempt

        Args:
            extension_id: Extension that was blocked
            action_id: Action that was blocked
            runner_type: Runner type
            blocked_reason: Reason for blocking
            session_id: Session context
            user_id: User context

        Returns:
            execution_id: Execution record identifier

        Note:
            Critical for audit trail - all blocked attempts must be logged.
        """
        import random
        now_obj = utc_now()
        random_suffix = random.randint(1000, 9999)
        execution_id = f"exec-{now_obj.strftime('%Y%m%d%H%M%S')}-{now_obj.microsecond:06d}-{random_suffix}"

        now = utc_now_ms()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO extension_executions
                (execution_id, extension_id, action_id, runner_type,
                 session_id, user_id, status, blocked_reason,
                 started_at, completed_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 'blocked', ?, ?, ?, ?)
            """, (
                execution_id,
                extension_id,
                action_id,
                runner_type,
                session_id,
                user_id,
                blocked_reason,
                now,
                now,
                now
            ))
            conn.commit()

        logger.warning(
            f"[Governance] Execution blocked: {execution_id} "
            f"({extension_id}/{action_id}) - Reason: {blocked_reason}"
        )

        return execution_id

    # ==========================================================================
    # Queries
    # ==========================================================================

    def get_execution_history(
        self,
        extension_id: Optional[str] = None,
        session_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get execution history

        Args:
            extension_id: Filter by extension (optional)
            session_id: Filter by session (optional)
            limit: Maximum number of records

        Returns:
            List of execution records (ordered by started_at DESC)

        Examples:
            >>> # Get all recent executions
            >>> history = service.get_execution_history(limit=100)

            >>> # Get executions for specific extension
            >>> history = service.get_execution_history(
            ...     extension_id="tools.postman",
            ...     limit=50
            ... )

            >>> # Get executions for specific session
            >>> history = service.get_execution_history(
            ...     session_id="session-456",
            ...     limit=20
            ... )
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            query = """
                SELECT execution_id, extension_id, action_id, runner_type,
                       status, exit_code, duration_ms, sandbox_mode,
                       started_at, completed_at, blocked_reason, error_message
                FROM extension_executions
                WHERE 1=1
            """
            params = []

            if extension_id:
                query += " AND extension_id = ?"
                params.append(extension_id)

            if session_id:
                query += " AND session_id = ?"
                params.append(session_id)

            query += " ORDER BY started_at DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)

            return [dict(row) for row in cursor.fetchall()]

    def get_authorizations(
        self,
        extension_id: Optional[str] = None,
        scope: Optional[str] = None,
        status: str = "active"
    ) -> List[Dict[str, Any]]:
        """
        Get authorizations

        Args:
            extension_id: Filter by extension (optional)
            scope: Filter by scope (optional)
            status: Filter by status (default: 'active')

        Returns:
            List of authorization records

        Examples:
            >>> # Get all active authorizations
            >>> auths = service.get_authorizations()

            >>> # Get authorizations for specific extension
            >>> auths = service.get_authorizations(
            ...     extension_id="tools.postman",
            ...     status="active"
            ... )

            >>> # Get session-scoped authorizations
            >>> auths = service.get_authorizations(
            ...     scope="session",
            ...     status="active"
            ... )
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            query = """
                SELECT auth_id, extension_id, action_id, authorized_by,
                       scope, scope_id, expires_at, max_executions,
                       execution_count, status, created_at
                FROM extension_authorizations
                WHERE status = ?
            """
            params = [status]

            if extension_id:
                query += " AND extension_id = ?"
                params.append(extension_id)

            if scope:
                query += " AND scope = ?"
                params.append(scope)

            query += " ORDER BY created_at DESC"

            cursor.execute(query, params)

            return [dict(row) for row in cursor.fetchall()]
