"""
Runner Base Classes

Defines the abstract base class for capability runners and core data models.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional, Callable
import logging

logger = logging.getLogger(__name__)


# ============================================
# Data Models
# ============================================

@dataclass
class Invocation:
    """
    Invocation request for a capability runner

    Contains all necessary information to execute a capability action.
    """
    extension_id: str  # e.g., "tools.postman"
    action_id: str  # e.g., "get", "list", "explain"
    session_id: str  # Chat session ID
    user_id: str = "default"  # User identifier

    # Command arguments
    args: list = field(default_factory=list)  # Positional arguments
    flags: Dict[str, Any] = field(default_factory=dict)  # Named flags

    # Context
    metadata: Dict[str, Any] = field(default_factory=dict)  # Additional metadata
    timeout: int = 300  # Timeout in seconds

    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class RunResult:
    """
    Result from a capability run

    Contains execution status, output, and metadata.
    """
    success: bool
    output: str  # Main output (stdout or formatted result)
    error: Optional[str] = None  # Error message if failed

    # Execution metadata
    exit_code: int = 0
    duration_ms: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Timestamps
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


# ============================================
# Progress Callback Type
# ============================================

ProgressCallback = Callable[[str, int, str], None]
"""
Progress callback function

Args:
    stage: Current stage name (e.g., "VALIDATING", "EXECUTING")
    progress_pct: Progress percentage (0-100)
    message: Progress message
"""


# ============================================
# Runner Abstract Base Class
# ============================================

class Runner(ABC):
    """
    Abstract base class for capability runners

    Runners are responsible for executing specific types of capabilities
    (e.g., exec tools, analyze responses, browser navigation, API calls).

    Each runner implements the execution logic for its capability type
    and reports progress through callbacks.
    """

    @abstractmethod
    def run(
        self,
        invocation: Invocation,
        progress_cb: Optional[ProgressCallback] = None,
        declared_permissions: Optional[list] = None
    ) -> RunResult:
        """
        Execute a capability invocation

        Args:
            invocation: The invocation request with all necessary parameters
            progress_cb: Optional callback for progress updates
            declared_permissions: Permissions declared in manifest (PR-E3)

        Returns:
            RunResult with execution status and output

        Raises:
            RunnerError: If execution fails critically
            TimeoutError: If execution exceeds timeout
            PermissionError: If required permissions are not granted (PR-E3)

        Note:
            PR-E3: Implementations should check permissions before execution
            and log audit events (started, finished, denied).
        """
        pass

    @property
    @abstractmethod
    def runner_type(self) -> str:
        """
        Get the runner type identifier

        Returns:
            Runner type (e.g., "exec", "analyze.response", "browser.navigate")
        """
        pass


# ============================================
# Exceptions
# ============================================

class RunnerError(Exception):
    """Base exception for runner errors"""
    pass


class TimeoutError(RunnerError):
    """Execution timeout error"""
    pass


class ValidationError(RunnerError):
    """Invocation validation error"""
    pass


# ============================================
# Governance Integration
# ============================================

def run_with_governance(
    runner: Runner,
    invocation: Invocation,
    progress_cb: Optional[ProgressCallback] = None,
    declared_permissions: Optional[list] = None,
    require_auth: bool = True
) -> RunResult:
    """
    Run invocation with governance checks (Wave C3)

    This wrapper adds authorization checks and audit trail logging
    to any Runner execution. It enforces the governance red lines:
    1. All extensions must be pre-authorized
    2. All executions (including blocked) must be logged
    3. No silent execution without audit trail

    Authorization Priority:
    1. Session-scoped (most specific)
    2. User-scoped
    3. Global (least specific)

    Args:
        runner: Runner instance to execute
        invocation: Invocation request
        progress_cb: Progress callback
        declared_permissions: Declared permissions (for future use)
        require_auth: Whether to require authorization (default True)

    Returns:
        RunResult with execution outcome

    Red Lines:
    - If authorization fails, returns failure result with exit_code=403
    - All blocked executions are logged in extension_executions table
    - All successful executions are logged with full audit trail

    Examples:
        >>> from agentos.core.capabilities.runner_base.builtin_runner import BuiltinRunner
        >>> runner = BuiltinRunner()
        >>> invocation = Invocation(
        ...     extension_id="tools.postman",
        ...     action_id="get",
        ...     session_id="session-123",
        ...     user_id="user-456"
        ... )
        >>>
        >>> # Run with governance
        >>> result = run_with_governance(
        ...     runner=runner,
        ...     invocation=invocation,
        ...     require_auth=True
        ... )
        >>>
        >>> if result.success:
        ...     print(result.output)
        ... else:
        ...     print(f"Failed: {result.error}")
    """
    from agentos.core.capabilities.governance import (
        ExtensionGovernanceService,
        AuthorizationRequest,
    )

    governance = ExtensionGovernanceService()

    # Check authorization
    auth_result = None
    if require_auth:
        auth_request = AuthorizationRequest(
            extension_id=invocation.extension_id,
            action_id=invocation.action_id,
            session_id=invocation.session_id,
            user_id=invocation.user_id
        )

        auth_result = governance.check_authorization(auth_request)

        if not auth_result.allowed:
            # Log blocked execution
            governance.log_execution_blocked(
                extension_id=invocation.extension_id,
                action_id=invocation.action_id,
                runner_type=runner.runner_type,
                blocked_reason=auth_result.reason,
                session_id=invocation.session_id,
                user_id=invocation.user_id
            )

            # Return failure result
            logger.warning(
                f"[Governance] Blocked execution: {invocation.extension_id}/{invocation.action_id} "
                f"- Reason: {auth_result.reason}"
            )

            return RunResult(
                success=False,
                output="",
                error=f"Execution blocked: {auth_result.reason}",
                exit_code=403,
                duration_ms=0,
                metadata={"blocked": True, "reason": auth_result.reason}
            )

        # Increment execution count
        if auth_result.auth_id:
            governance.increment_execution_count(auth_result.auth_id)

    # Log execution start
    execution_id = governance.log_execution_start(
        extension_id=invocation.extension_id,
        action_id=invocation.action_id,
        runner_type=runner.runner_type,
        auth_id=auth_result.auth_id if auth_result else None,
        session_id=invocation.session_id,
        user_id=invocation.user_id,
        sandbox_mode="none",  # TODO: Implement sandbox detection
        metadata={
            "args": invocation.args,
            "flags": invocation.flags
        }
    )

    # Execute
    started_at = datetime.now()
    try:
        result = runner.run(invocation, progress_cb, declared_permissions)
    except Exception as e:
        # Log execution failure
        completed_at = datetime.now()
        duration_ms = int((completed_at - started_at).total_seconds() * 1000)

        governance.log_execution_complete(
            execution_id=execution_id,
            status="failed",
            exit_code=-1,
            duration_ms=duration_ms,
            output_preview=None,
            error_message=str(e)
        )

        # Re-raise exception
        raise

    completed_at = datetime.now()
    duration_ms = int((completed_at - started_at).total_seconds() * 1000)

    # Log execution complete
    governance.log_execution_complete(
        execution_id=execution_id,
        status="success" if result.success else "failed",
        exit_code=result.exit_code,
        duration_ms=duration_ms,
        output_preview=result.output[:1000] if result.output else None,
        error_message=result.error
    )

    return result
