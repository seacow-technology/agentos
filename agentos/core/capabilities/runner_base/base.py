"""
Runner Base Classes

Defines the abstract base class for capability runners and core data models.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional, Callable


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
