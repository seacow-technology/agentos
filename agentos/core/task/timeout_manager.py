"""
Task Timeout Manager

Provides wallclock-based timeout detection and handling.

Key Features:
1. Configurable timeout duration
2. Timeout detection in runner loop
3. Graceful timeout handling
4. Timeout audit logging
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any
from datetime import datetime, timezone, timedelta
import logging
from agentos.core.time import utc_now, utc_now_iso


logger = logging.getLogger(__name__)


@dataclass
class TimeoutConfig:
    """
    Task Timeout Configuration

    Attributes:
        enabled: Whether timeout is enabled
        timeout_seconds: Timeout duration in seconds (default: 3600 = 1 hour)
        warning_threshold: Warn when execution time exceeds this ratio (default: 0.8)
    """
    enabled: bool = True
    timeout_seconds: int = 3600  # 1 hour
    warning_threshold: float = 0.8  # Warn at 80% of timeout

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for metadata storage."""
        return {
            "enabled": self.enabled,
            "timeout_seconds": self.timeout_seconds,
            "warning_threshold": self.warning_threshold,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TimeoutConfig":
        """Create from dictionary."""
        return cls(
            enabled=data.get("enabled", True),
            timeout_seconds=data.get("timeout_seconds", 3600),
            warning_threshold=data.get("warning_threshold", 0.8),
        )


@dataclass
class TimeoutState:
    """
    Current timeout state for a task

    Attributes:
        execution_start_time: When execution started (ISO 8601)
        last_heartbeat: Last heartbeat timestamp
        warning_issued: Whether timeout warning has been issued
    """
    execution_start_time: Optional[str] = None
    last_heartbeat: Optional[str] = None
    warning_issued: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for metadata storage."""
        return {
            "execution_start_time": self.execution_start_time,
            "last_heartbeat": self.last_heartbeat,
            "warning_issued": self.warning_issued,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TimeoutState":
        """Create from dictionary."""
        return cls(
            execution_start_time=data.get("execution_start_time"),
            last_heartbeat=data.get("last_heartbeat"),
            warning_issued=data.get("warning_issued", False),
        )


class TimeoutManager:
    """
    Timeout Manager

    Detects and handles task execution timeouts.
    """

    def start_timeout_tracking(
        self,
        timeout_state: TimeoutState
    ) -> TimeoutState:
        """
        Start timeout tracking for a task

        Args:
            timeout_state: Current timeout state

        Returns:
            Updated timeout state with start time
        """
        now = utc_now_iso()
        timeout_state.execution_start_time = now
        timeout_state.last_heartbeat = now
        timeout_state.warning_issued = False

        logger.info(f"Started timeout tracking at {now}")
        return timeout_state

    def check_timeout(
        self,
        timeout_config: TimeoutConfig,
        timeout_state: TimeoutState
    ) -> tuple[bool, Optional[str], Optional[str]]:
        """
        Check if task execution has timed out

        Args:
            timeout_config: Timeout configuration
            timeout_state: Current timeout state

        Returns:
            (is_timeout, warning_message, timeout_message) tuple
            - is_timeout: True if execution has exceeded timeout limit
            - warning_message: Warning when approaching timeout (at warning_threshold)
            - timeout_message: Message when timeout is reached
        """
        if not timeout_config.enabled:
            return False, None, None

        if not timeout_state.execution_start_time:
            return False, None, None

        # Calculate elapsed time
        start_time = datetime.fromisoformat(timeout_state.execution_start_time)
        now = utc_now()
        elapsed_seconds = (now - start_time).total_seconds()

        # Check for timeout
        if elapsed_seconds >= timeout_config.timeout_seconds:
            message = (
                f"Task execution timed out after {elapsed_seconds:.0f}s "
                f"(limit: {timeout_config.timeout_seconds}s)"
            )
            return True, None, message

        # Check for warning threshold
        warning_threshold_seconds = timeout_config.timeout_seconds * timeout_config.warning_threshold

        if elapsed_seconds >= warning_threshold_seconds and not timeout_state.warning_issued:
            remaining = timeout_config.timeout_seconds - elapsed_seconds
            warning = (
                f"Task execution approaching timeout: {elapsed_seconds:.0f}s elapsed, "
                f"{remaining:.0f}s remaining (limit: {timeout_config.timeout_seconds}s)"
            )
            return False, warning, None

        return False, None, None

    def update_heartbeat(
        self,
        timeout_state: TimeoutState
    ) -> TimeoutState:
        """
        Update last heartbeat timestamp

        Args:
            timeout_state: Current timeout state

        Returns:
            Updated timeout state
        """
        timeout_state.last_heartbeat = utc_now_iso()
        return timeout_state

    def mark_warning_issued(
        self,
        timeout_state: TimeoutState
    ) -> TimeoutState:
        """
        Mark that timeout warning has been issued

        Args:
            timeout_state: Current timeout state

        Returns:
            Updated timeout state
        """
        timeout_state.warning_issued = True
        return timeout_state

    def get_timeout_metrics(
        self,
        timeout_state: TimeoutState
    ) -> Dict[str, Any]:
        """
        Get timeout metrics for observability

        Args:
            timeout_state: Current timeout state

        Returns:
            Dictionary with timeout metrics including:
            - execution_start_time: When execution started
            - elapsed_seconds: Time elapsed since start
            - last_heartbeat: Last heartbeat timestamp
            - warning_issued: Whether timeout warning was issued
        """
        if not timeout_state.execution_start_time:
            return {
                "execution_start_time": None,
                "elapsed_seconds": None,
                "last_heartbeat": None,
                "warning_issued": False,
            }

        start_time = datetime.fromisoformat(timeout_state.execution_start_time)
        now = utc_now()
        elapsed_seconds = (now - start_time).total_seconds()

        return {
            "execution_start_time": timeout_state.execution_start_time,
            "elapsed_seconds": elapsed_seconds,
            "last_heartbeat": timeout_state.last_heartbeat,
            "warning_issued": timeout_state.warning_issued,
        }
