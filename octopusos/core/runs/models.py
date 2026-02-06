"""
Run Data Models

Defines run states, progress stages, and run records.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any


class RunStatus(str, Enum):
    """
    Run execution status

    Lifecycle:
    PENDING -> RUNNING -> SUCCEEDED/FAILED/TIMEOUT/CANCELED
    """
    PENDING = "PENDING"  # Created but not started
    RUNNING = "RUNNING"  # Currently executing
    SUCCEEDED = "SUCCEEDED"  # Completed successfully
    FAILED = "FAILED"  # Failed with error
    TIMEOUT = "TIMEOUT"  # Timed out
    CANCELED = "CANCELED"  # Canceled by user


class ProgressStage(str, Enum):
    """
    Standard progress stages for capability execution

    Each stage has a typical progress percentage range:
    - VALIDATING: 0-10%
    - LOADING: 10-20%
    - EXECUTING: 20-90%
    - FINALIZING: 90-95%
    - DONE: 100%
    """
    VALIDATING = "VALIDATING"  # Validating inputs and permissions
    LOADING = "LOADING"  # Loading extension resources
    EXECUTING = "EXECUTING"  # Main execution phase
    FINALIZING = "FINALIZING"  # Post-processing and cleanup
    DONE = "DONE"  # Execution complete

    @property
    def typical_progress(self) -> int:
        """Get typical progress percentage for this stage"""
        return {
            ProgressStage.VALIDATING: 5,
            ProgressStage.LOADING: 15,
            ProgressStage.EXECUTING: 60,
            ProgressStage.FINALIZING: 90,
            ProgressStage.DONE: 100,
        }[self]


@dataclass
class RunRecord:
    """
    Run execution record

    Tracks the full lifecycle of a capability execution including
    status, progress, output, and timing information.
    """
    # Identity
    run_id: str  # Unique run identifier
    extension_id: str  # Extension being executed
    action_id: str  # Action being executed

    # Status
    status: RunStatus
    progress_pct: int = 0  # Progress percentage (0-100)

    # Progress tracking
    stages: List[Dict[str, Any]] = field(default_factory=list)  # Stage history
    current_stage: Optional[str] = None  # Current stage name

    # Output
    stdout: str = ""  # Standard output
    stderr: str = ""  # Standard error
    error: Optional[str] = None  # Error message if failed

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)  # Additional metadata

    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None

    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate execution duration in seconds"""
        if self.started_at and self.ended_at:
            return (self.ended_at - self.started_at).total_seconds()
        return None

    @property
    def is_terminal(self) -> bool:
        """Check if run is in a terminal state"""
        return self.status in [
            RunStatus.SUCCEEDED,
            RunStatus.FAILED,
            RunStatus.TIMEOUT,
            RunStatus.CANCELED
        ]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            "run_id": self.run_id,
            "extension_id": self.extension_id,
            "action_id": self.action_id,
            "status": self.status.value,
            "progress_pct": self.progress_pct,
            "stages": self.stages,
            "current_stage": self.current_stage,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "error": self.error,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "duration_seconds": self.duration_seconds,
        }
