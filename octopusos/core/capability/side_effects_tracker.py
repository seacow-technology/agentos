"""
Side Effects Tracker - Track and validate side effects from capability invocations

This module:
1. Records all side effects produced during execution
2. Compares declared vs actual side effects
3. Detects unexpected side effects (security risk)
4. Provides audit trail of mutations

Design Philosophy:
- Track everything (writes, network calls, mutations)
- Detect divergence from declared side effects
- Alert on unexpected behavior
- Performance: Async tracking, minimal overhead
"""

import logging
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime

from agentos.core.capability.models import (
    CapabilityDefinition,
    SideEffectType,
)
from agentos.core.capability.registry import CapabilityRegistry, get_capability_registry
from agentos.core.time import utc_now_ms


logger = logging.getLogger(__name__)


@dataclass
class SideEffectRecord:
    """
    Record of a side effect that occurred during execution.

    Attributes:
        capability_id: Capability that produced the side effect
        side_effect_type: Type of side effect
        agent_id: Agent that triggered it
        operation: Specific operation
        details: Additional details (e.g., file path, URL)
        timestamp_ms: When it occurred
        declared: Whether this was declared in capability definition
    """

    capability_id: str
    side_effect_type: SideEffectType
    agent_id: str
    operation: str
    details: Optional[Dict] = None
    timestamp_ms: int = field(default_factory=utc_now_ms)
    declared: bool = True  # Was this side effect expected?


@dataclass
class SideEffectSummary:
    """
    Summary of side effects for an execution session.

    Attributes:
        session_id: Session/task identifier
        total_side_effects: Total count
        declared_side_effects: Side effects that were declared
        unexpected_side_effects: Side effects NOT declared (security concern)
        by_type: Count by side effect type
        by_capability: Count by capability
    """

    session_id: str
    total_side_effects: int = 0
    declared_side_effects: int = 0
    unexpected_side_effects: int = 0
    by_type: Dict[str, int] = field(default_factory=dict)
    by_capability: Dict[str, int] = field(default_factory=dict)
    records: List[SideEffectRecord] = field(default_factory=list)


class UnexpectedSideEffectError(Exception):
    """
    Raised when an unexpected side effect is detected.

    This indicates a capability is doing something it didn't declare,
    which is a security violation.
    """

    def __init__(
        self,
        capability_id: str,
        unexpected_effect: SideEffectType,
        declared_effects: List[SideEffectType],
    ):
        self.capability_id = capability_id
        self.unexpected_effect = unexpected_effect
        self.declared_effects = declared_effects

        declared_str = ", ".join([e.value for e in declared_effects]) or "none"
        super().__init__(
            f"Unexpected side effect detected!\n"
            f"Capability: {capability_id}\n"
            f"Unexpected effect: {unexpected_effect.value}\n"
            f"Declared effects: {declared_str}\n"
            f"This is a security violation - capability is doing more than declared."
        )


class SideEffectsTracker:
    """
    Side effects tracker for capability invocations.

    This class:
    1. Records side effects as they occur
    2. Validates against declared side effects
    3. Detects unexpected behavior
    4. Provides session-level summaries

    Usage:
        tracker = SideEffectsTracker()

        # Start tracking session
        tracker.start_session("task-123")

        # Record side effect
        tracker.record_side_effect(
            capability_id="action.file.write",
            side_effect_type=SideEffectType.FILE_SYSTEM_WRITE,
            agent_id="executor_agent",
            operation="write_file",
            details={"path": "/tmp/output.txt"}
        )

        # Get summary
        summary = tracker.get_session_summary("task-123")
        print(f"Total side effects: {summary.total_side_effects}")
        print(f"Unexpected: {summary.unexpected_side_effects}")

        # End session
        tracker.end_session("task-123")
    """

    def __init__(self, registry: Optional[CapabilityRegistry] = None):
        """
        Initialize side effects tracker.

        Args:
            registry: CapabilityRegistry instance (default: use global)
        """
        self.registry = registry or get_capability_registry()
        self._sessions: Dict[str, List[SideEffectRecord]] = {}
        self._strict_mode = True  # Raise on unexpected side effects
        logger.debug("SideEffectsTracker initialized")

    # ===================================================================
    # Session Management
    # ===================================================================

    def start_session(self, session_id: str):
        """
        Start tracking side effects for a session.

        Args:
            session_id: Unique session identifier (task_id, etc.)
        """
        self._sessions[session_id] = []
        logger.debug(f"Started side effects tracking for session: {session_id}")

    def end_session(self, session_id: str) -> SideEffectSummary:
        """
        End tracking and get summary.

        Args:
            session_id: Session identifier

        Returns:
            SideEffectSummary for the session
        """
        summary = self.get_session_summary(session_id)

        # Clean up session data
        if session_id in self._sessions:
            del self._sessions[session_id]

        logger.debug(
            f"Ended side effects tracking for session {session_id}: "
            f"total={summary.total_side_effects}, unexpected={summary.unexpected_side_effects}"
        )

        return summary

    def get_session_records(self, session_id: str) -> List[SideEffectRecord]:
        """Get all side effect records for a session"""
        return self._sessions.get(session_id, [])

    # ===================================================================
    # Side Effect Recording
    # ===================================================================

    def record_side_effect(
        self,
        capability_id: str,
        side_effect_type: SideEffectType,
        agent_id: str,
        operation: str,
        details: Optional[Dict] = None,
        session_id: Optional[str] = None,
    ):
        """
        Record a side effect that occurred.

        This should be called immediately after a side effect happens,
        e.g., after writing a file, making a network call, etc.

        Args:
            capability_id: Capability that produced the side effect
            side_effect_type: Type of side effect
            agent_id: Agent that triggered it
            operation: Specific operation name
            details: Additional context (file path, URL, etc.)
            session_id: Optional session ID (if not set, recorded globally)

        Raises:
            UnexpectedSideEffectError: If side effect not declared and strict_mode=True
        """
        # Check if side effect was declared
        cap_def = self.registry.get_capability(capability_id)
        if cap_def is None:
            logger.warning(f"Recording side effect for unknown capability: {capability_id}")
            declared = False
        else:
            declared = side_effect_type in cap_def.produces_side_effects

        # Create record
        record = SideEffectRecord(
            capability_id=capability_id,
            side_effect_type=side_effect_type,
            agent_id=agent_id,
            operation=operation,
            details=details,
            timestamp_ms=utc_now_ms(),
            declared=declared,
        )

        # Store in session
        if session_id and session_id in self._sessions:
            self._sessions[session_id].append(record)

        # Log
        if not declared:
            logger.warning(
                f"UNEXPECTED SIDE EFFECT: {capability_id} produced {side_effect_type.value} "
                f"(not declared in definition)"
            )

            # Raise in strict mode
            if self._strict_mode and cap_def:
                raise UnexpectedSideEffectError(
                    capability_id=capability_id,
                    unexpected_effect=side_effect_type,
                    declared_effects=cap_def.produces_side_effects,
                )
        else:
            logger.debug(
                f"Recorded side effect: {capability_id} → {side_effect_type.value} "
                f"(declared: {declared})"
            )

    # ===================================================================
    # Validation
    # ===================================================================

    def validate_declared_effects(
        self, capability_id: str, actual_effects: List[SideEffectType]
    ) -> Tuple[bool, List[SideEffectType]]:
        """
        Validate that actual side effects match declared ones.

        Args:
            capability_id: Capability to check
            actual_effects: Side effects that actually occurred

        Returns:
            (all_declared, unexpected_effects)
        """
        cap_def = self.registry.get_capability(capability_id)
        if cap_def is None:
            return False, actual_effects

        declared_set = set(cap_def.produces_side_effects)
        actual_set = set(actual_effects)

        unexpected = actual_set - declared_set
        return (len(unexpected) == 0, list(unexpected))

    def get_undeclared_effects(self, session_id: str) -> List[SideEffectRecord]:
        """
        Get all undeclared (unexpected) side effects for a session.

        Args:
            session_id: Session identifier

        Returns:
            List of undeclared side effect records
        """
        records = self.get_session_records(session_id)
        return [record for record in records if not record.declared]

    # ===================================================================
    # Statistics & Summaries
    # ===================================================================

    def get_session_summary(self, session_id: str) -> SideEffectSummary:
        """
        Get summary of side effects for a session.

        Args:
            session_id: Session identifier

        Returns:
            SideEffectSummary with aggregated metrics
        """
        records = self.get_session_records(session_id)

        summary = SideEffectSummary(session_id=session_id, records=records)

        for record in records:
            summary.total_side_effects += 1

            if record.declared:
                summary.declared_side_effects += 1
            else:
                summary.unexpected_side_effects += 1

            # Count by type
            effect_type = record.side_effect_type.value
            summary.by_type[effect_type] = summary.by_type.get(effect_type, 0) + 1

            # Count by capability
            cap_id = record.capability_id
            summary.by_capability[cap_id] = summary.by_capability.get(cap_id, 0) + 1

        return summary

    def get_capability_effects(self, capability_id: str) -> List[SideEffectType]:
        """
        Get declared side effects for a capability.

        Args:
            capability_id: Capability to check

        Returns:
            List of declared side effects
        """
        cap_def = self.registry.get_capability(capability_id)
        if cap_def is None:
            return []
        return cap_def.produces_side_effects

    def has_side_effect_type(
        self, capability_id: str, side_effect_type: SideEffectType
    ) -> bool:
        """
        Check if capability declares a specific side effect type.

        Args:
            capability_id: Capability to check
            side_effect_type: Side effect type to check

        Returns:
            True if capability declares this side effect
        """
        cap_def = self.registry.get_capability(capability_id)
        if cap_def is None:
            return False
        return side_effect_type in cap_def.produces_side_effects

    # ===================================================================
    # Context Managers
    # ===================================================================

    class TrackedExecution:
        """
        Context manager for tracking side effects during execution.

        Usage:
            with tracker.track_execution("task-123", "action.file.write"):
                # ... perform operation ...
                tracker.record_side_effect(...)
            # Summary is automatically generated on exit
        """

        def __init__(self, tracker: "SideEffectsTracker", session_id: str, capability_id: str):
            self.tracker = tracker
            self.session_id = session_id
            self.capability_id = capability_id

        def __enter__(self):
            if self.session_id not in self.tracker._sessions:
                self.tracker.start_session(self.session_id)
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            if exc_type is None:
                # Normal exit - log summary
                summary = self.tracker.get_session_summary(self.session_id)
                if summary.unexpected_side_effects > 0:
                    logger.warning(
                        f"Execution of {self.capability_id} produced "
                        f"{summary.unexpected_side_effects} unexpected side effects"
                    )
            return False  # Don't suppress exceptions

    def track_execution(self, session_id: str, capability_id: str) -> "TrackedExecution":
        """
        Create context manager for tracking execution.

        Args:
            session_id: Session identifier
            capability_id: Capability being executed

        Returns:
            TrackedExecution context manager
        """
        return self.TrackedExecution(self, session_id, capability_id)

    # ===================================================================
    # Configuration
    # ===================================================================

    def set_strict_mode(self, enabled: bool):
        """
        Enable/disable strict mode.

        In strict mode, unexpected side effects raise UnexpectedSideEffectError.
        In permissive mode, they are logged as warnings.

        Args:
            enabled: Whether to enable strict mode
        """
        self._strict_mode = enabled
        logger.info(f"Strict mode {'enabled' if enabled else 'disabled'}")

    def is_strict_mode(self) -> bool:
        """Check if strict mode is enabled"""
        return self._strict_mode


# Global singleton
_tracker_instance: Optional[SideEffectsTracker] = None


def get_side_effects_tracker(
    registry: Optional[CapabilityRegistry] = None,
) -> SideEffectsTracker:
    """
    Get global side effects tracker singleton.

    Args:
        registry: Optional CapabilityRegistry instance

    Returns:
        Singleton SideEffectsTracker instance
    """
    global _tracker_instance
    if _tracker_instance is None:
        _tracker_instance = SideEffectsTracker(registry=registry)
    return _tracker_instance
