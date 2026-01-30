"""Data models for capability execution"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from enum import Enum


class RunnerType(str, Enum):
    """Types of capability runners"""
    EXEC_TOOL = "exec"  # exec.postman_cli, exec.curl, etc.
    ANALYZE_RESPONSE = "analyze.response"
    ANALYZE_SCHEMA = "analyze.schema"
    BROWSER_NAVIGATE = "browser.navigate"
    API_CALL = "api.call"


@dataclass
class CommandRoute:
    """
    Parsed slash command route

    This is the result from Slash Command Router (PR-D) that describes
    what capability to execute and with what parameters.
    """
    command_name: str  # e.g., "/postman"
    extension_id: str  # e.g., "tools.postman"
    action_id: str  # e.g., "get", "list", "explain"
    runner: str  # e.g., "exec.postman_cli", "analyze.response"
    args: List[str] = field(default_factory=list)  # Command arguments
    flags: Dict[str, Any] = field(default_factory=dict)  # Named flags
    description: Optional[str] = None  # Action description
    permissions: List[str] = field(default_factory=list)  # Required permissions from manifest
    metadata: Dict[str, Any] = field(default_factory=dict)  # Additional metadata


@dataclass
class ExecutionContext:
    """
    Execution context for a capability run

    Contains all necessary information and resources for executing
    a capability in a controlled environment.
    """
    session_id: str  # Chat session ID
    user_id: str  # User identifier
    extension_id: str  # Extension providing the capability
    work_dir: Path  # Working directory for execution

    # Optional context
    usage_doc: Optional[str] = None  # Content from docs/USAGE.md
    last_response: Optional[str] = None  # For analyze.response on previous output
    timeout: int = 300  # Timeout in seconds

    # Environment restrictions
    env_whitelist: List[str] = field(default_factory=lambda: [
        "PATH", "HOME", "USER", "LANG", "LC_ALL", "TMPDIR"
    ])

    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class ToolExecutionResult:
    """
    Result from executing a command-line tool

    Contains all information about the tool execution including
    output, errors, and timing information.
    """
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    command: str  # The actual command that was executed

    @property
    def output(self) -> str:
        """Get combined output (prefer stdout, fallback to stderr)"""
        return self.stdout if self.stdout else self.stderr


@dataclass
class ExecutionResult:
    """
    Result from a capability executor

    This is returned by individual executors (ExecToolExecutor, AnalyzeResponseExecutor)
    """
    success: bool
    output: str  # Main output (command stdout or LLM response)
    error: Optional[str] = None  # Error message if failed
    metadata: Dict[str, Any] = field(default_factory=dict)  # Additional info

    # Optional fields
    raw_data: Optional[Any] = None  # Raw data for further processing


@dataclass
class CapabilityResult:
    """
    Final result returned to the user

    This is what the chat interface will display to the user.
    """
    success: bool
    output: str  # Formatted output for display
    error: Optional[str] = None  # User-friendly error message
    metadata: Dict[str, Any] = field(default_factory=dict)  # Execution metadata
    artifacts: List[Path] = field(default_factory=list)  # Generated files

    # Timing
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate execution duration"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
