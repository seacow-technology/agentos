"""Gates module for AgentOS

This module provides gate execution and validation mechanisms.
"""

from agentos.core.gates.pause_gate import (
    PauseState,
    PauseCheckpoint,
    PauseMetadata,
    PauseGateViolation,
    enforce_pause_checkpoint,
    can_pause_at,
    create_pause_metadata,
)

from agentos.core.gates.done_gate import (
    DoneGateRunner,
    GateResult,
    GateRunResult,
)

__all__ = [
    # Pause gates
    "PauseState",
    "PauseCheckpoint",
    "PauseMetadata",
    "PauseGateViolation",
    "enforce_pause_checkpoint",
    "can_pause_at",
    "create_pause_metadata",
    # DONE gates
    "DoneGateRunner",
    "GateResult",
    "GateRunResult",
]
