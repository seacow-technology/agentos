"""
Path Validator - Golden Path enforcement for AgentOS v3

This module enforces the Golden Path execution model:
  State → Decision → Governance → Action → State → Evidence

Forbidden Paths (blocked):
1. Decision → Action (must freeze plan first)
2. Action → State (bypassing governance)
3. Memory.write → Action.execute (direct write without governance)
4. Evidence → * (evidence cannot call out, only be called)

Design Philosophy:
- Call stack tracking per session/task
- Validation happens BEFORE execution
- Clear error messages for violations
- Performance target: < 5ms per check
"""

import sqlite3
import json
import logging
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from contextvars import ContextVar
from datetime import datetime

from agentos.core.capability.models import (
    CapabilityDomain,
    CapabilityDefinition,
    CallStackEntry,
    PathValidationResult,
)
from agentos.core.time import utc_now_ms


logger = logging.getLogger(__name__)


# ===================================================================
# Golden Path Rules
# ===================================================================

# Which domains each domain can call
GOLDEN_PATH_RULES = {
    CapabilityDomain.STATE: {
        CapabilityDomain.DECISION,
        CapabilityDomain.GOVERNANCE,
        CapabilityDomain.EVIDENCE,
    },
    CapabilityDomain.DECISION: {
        CapabilityDomain.STATE,
        CapabilityDomain.GOVERNANCE,
        CapabilityDomain.EVIDENCE,
    },
    CapabilityDomain.ACTION: {
        CapabilityDomain.GOVERNANCE,  # Must check governance
        CapabilityDomain.EVIDENCE,    # Must record evidence
    },
    CapabilityDomain.GOVERNANCE: {
        CapabilityDomain.STATE,
        CapabilityDomain.DECISION,
        CapabilityDomain.ACTION,  # Can approve actions
        CapabilityDomain.EVIDENCE,
    },
    CapabilityDomain.EVIDENCE: {
        CapabilityDomain.EVIDENCE,  # Can only call itself
    },
}

# Explicitly forbidden paths
FORBIDDEN_PATHS = {
    ("decision", "action"),  # Decision cannot directly trigger Action
    ("action", "state"),     # Action cannot directly modify State
    ("evidence", "state"),   # Evidence cannot call State
    ("evidence", "decision"), # Evidence cannot call Decision
    ("evidence", "action"),  # Evidence cannot call Action
    ("evidence", "governance"), # Evidence cannot call Governance
}


# ===================================================================
# Call Stack Context
# ===================================================================

# Thread-local call stack using contextvars (async-safe)
_call_stack_var: ContextVar[List[CallStackEntry]] = ContextVar("call_stack", default=[])
_session_id_var: ContextVar[Optional[str]] = ContextVar("session_id", default=None)


@dataclass
class PathValidationError(Exception):
    """
    Raised when a forbidden path is detected.

    Attributes:
        from_domain: Source domain
        to_domain: Target domain
        violated_rule: Which rule was violated
        call_stack: Current call stack
        reason: Explanation of violation
    """

    from_domain: CapabilityDomain
    to_domain: CapabilityDomain
    violated_rule: str
    call_stack: List[CallStackEntry]
    reason: str

    def __str__(self):
        stack_str = " → ".join([f"{entry.domain.value}" for entry in self.call_stack])
        return (
            f"Path validation failed: {self.from_domain.value} → {self.to_domain.value} is forbidden.\n"
            f"Violated rule: {self.violated_rule}\n"
            f"Reason: {self.reason}\n"
            f"Call stack: {stack_str}"
        )


class PathValidator:
    """
    Path validator for Golden Path enforcement.

    This class:
    1. Maintains call stack per session/task
    2. Validates every domain transition
    3. Blocks forbidden paths
    4. Records violations for audit

    Usage:
        validator = PathValidator(db_path="...")

        # Start session
        validator.start_session("task-123")

        # Before calling capability
        validator.validate_call(
            from_domain=CapabilityDomain.STATE,
            to_domain=CapabilityDomain.DECISION,
            agent_id="chat_agent",
            capability_id="decision.plan.create",
            operation="create_plan"
        )

        # After call completes
        validator.pop_call()

        # End session
        validator.end_session()
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize path validator.

        Args:
            db_path: Path to SQLite database (default: store/registry.sqlite)
        """
        if db_path is None:
            from agentos.store import get_db_path
            db_path = get_db_path()

        self.db_path = db_path
        logger.info(f"PathValidator initialized with db: {db_path}")

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ===================================================================
    # Session Management
    # ===================================================================

    def start_session(self, session_id: str):
        """
        Start a new validation session.

        Args:
            session_id: Unique session identifier (task_id, chat_session_id, etc.)
        """
        _session_id_var.set(session_id)
        _call_stack_var.set([])
        logger.debug(f"Started path validation session: {session_id}")

    def end_session(self):
        """End current validation session"""
        session_id = _session_id_var.get()
        if session_id:
            logger.debug(f"Ended path validation session: {session_id}")
        _session_id_var.set(None)
        _call_stack_var.set([])

    def get_session_id(self) -> Optional[str]:
        """Get current session ID"""
        return _session_id_var.get()

    def get_call_stack(self) -> List[CallStackEntry]:
        """Get current call stack"""
        return _call_stack_var.get()

    # ===================================================================
    # Path Validation
    # ===================================================================

    def validate_call(
        self,
        from_domain: Optional[CapabilityDomain],
        to_domain: CapabilityDomain,
        agent_id: str,
        capability_id: str,
        operation: str,
    ) -> PathValidationResult:
        """
        Validate a domain-to-domain call.

        This is the main validation method called BEFORE executing a capability.

        Args:
            from_domain: Source domain (None if top-level call)
            to_domain: Target domain
            agent_id: Agent making the call
            capability_id: Capability being invoked
            operation: Operation name

        Returns:
            PathValidationResult with validation outcome

        Raises:
            PathValidationError: If path is forbidden
        """
        call_stack = self.get_call_stack()
        session_id = self.get_session_id()
        timestamp_ms = utc_now_ms()

        # If no from_domain, this is a top-level call (always allowed)
        if from_domain is None:
            # First call in stack
            entry = CallStackEntry(
                capability_id=capability_id,
                domain=to_domain,
                agent_id=agent_id,
                operation=operation,
                timestamp_ms=timestamp_ms,
                parent_invocation_id=None,
            )
            call_stack.append(entry)
            _call_stack_var.set(call_stack)

            return PathValidationResult(
                valid=True,
                reason=None,
                violated_rule=None,
                call_stack=call_stack,
            )

        # Check Golden Path rules
        allowed_targets = GOLDEN_PATH_RULES.get(from_domain, set())
        if to_domain not in allowed_targets:
            # Check if explicitly forbidden
            forbidden_key = (from_domain.value, to_domain.value)
            if forbidden_key in FORBIDDEN_PATHS:
                violation_reason = self._get_violation_reason(from_domain, to_domain)
                violated_rule = f"{from_domain.value}→{to_domain.value}_forbidden"

                # Log violation
                self._log_path_violation(
                    session_id=session_id,
                    call_stack=call_stack,
                    violated_rule=violated_rule,
                    violation_reason=violation_reason,
                )

                # Raise exception
                raise PathValidationError(
                    from_domain=from_domain,
                    to_domain=to_domain,
                    violated_rule=violated_rule,
                    call_stack=call_stack,
                    reason=violation_reason,
                )

        # Valid path - push to stack
        parent_invocation_id = call_stack[-1].timestamp_ms if call_stack else None
        entry = CallStackEntry(
            capability_id=capability_id,
            domain=to_domain,
            agent_id=agent_id,
            operation=operation,
            timestamp_ms=timestamp_ms,
            parent_invocation_id=parent_invocation_id,
        )
        call_stack.append(entry)
        _call_stack_var.set(call_stack)

        # Log valid path
        self._log_valid_path(session_id=session_id, call_stack=call_stack)

        return PathValidationResult(
            valid=True,
            reason=None,
            violated_rule=None,
            call_stack=call_stack,
        )

    def pop_call(self) -> Optional[CallStackEntry]:
        """
        Pop the last call from stack (after operation completes).

        Returns:
            Popped CallStackEntry, or None if stack is empty
        """
        call_stack = self.get_call_stack()
        if call_stack:
            entry = call_stack.pop()
            _call_stack_var.set(call_stack)
            return entry
        return None

    def _get_violation_reason(
        self, from_domain: CapabilityDomain, to_domain: CapabilityDomain
    ) -> str:
        """Get human-readable reason for path violation"""
        violations = {
            ("decision", "action"): (
                "Decision cannot directly trigger Action. "
                "You must first freeze the plan (decision.plan.freeze) "
                "and pass through Governance approval."
            ),
            ("action", "state"): (
                "Action cannot directly modify State. "
                "Actions must record Evidence, which then updates State "
                "through the governance layer."
            ),
            ("evidence", "state"): (
                "Evidence domain is write-only. "
                "It cannot call back to State domain. "
                "Evidence can only be queried by other domains."
            ),
            ("evidence", "decision"): (
                "Evidence domain is write-only. "
                "It cannot call Decision domain."
            ),
            ("evidence", "action"): (
                "Evidence domain is write-only. "
                "It cannot trigger Actions."
            ),
            ("evidence", "governance"): (
                "Evidence domain is write-only. "
                "It cannot call Governance."
            ),
        }

        key = (from_domain.value, to_domain.value)
        return violations.get(key, f"Path {from_domain.value}→{to_domain.value} is not allowed by Golden Path rules")

    def _log_path_violation(
        self,
        session_id: Optional[str],
        call_stack: List[CallStackEntry],
        violated_rule: str,
        violation_reason: str,
    ):
        """Log path violation to database"""
        if not session_id:
            session_id = "unknown"

        conn = self._get_connection()
        cursor = conn.cursor()

        call_stack_json = json.dumps([
            {
                "capability_id": entry.capability_id,
                "domain": entry.domain.value,
                "agent_id": entry.agent_id,
                "operation": entry.operation,
                "timestamp_ms": entry.timestamp_ms,
            }
            for entry in call_stack
        ])

        timestamp_ms = utc_now_ms()

        cursor.execute(
            """
            INSERT INTO capability_call_paths (
                session_id, call_stack_json, path_valid, violation_reason, timestamp_ms
            )
            VALUES (?, ?, 0, ?, ?)
            """,
            (session_id, call_stack_json, f"{violated_rule}: {violation_reason}", timestamp_ms),
        )

        conn.commit()
        conn.close()

        logger.warning(
            f"Path violation: session={session_id}, rule={violated_rule}, "
            f"reason={violation_reason}"
        )

    def _log_valid_path(self, session_id: Optional[str], call_stack: List[CallStackEntry]):
        """Log valid path to database (for audit/analytics)"""
        if not session_id:
            return

        conn = self._get_connection()
        cursor = conn.cursor()

        call_stack_json = json.dumps([
            {
                "capability_id": entry.capability_id,
                "domain": entry.domain.value,
                "agent_id": entry.agent_id,
                "operation": entry.operation,
                "timestamp_ms": entry.timestamp_ms,
            }
            for entry in call_stack
        ])

        timestamp_ms = utc_now_ms()

        cursor.execute(
            """
            INSERT INTO capability_call_paths (
                session_id, call_stack_json, path_valid, violation_reason, timestamp_ms
            )
            VALUES (?, ?, 1, NULL, ?)
            """,
            (session_id, call_stack_json, timestamp_ms),
        )

        conn.commit()
        conn.close()

    # ===================================================================
    # Decorators
    # ===================================================================

    @staticmethod
    def require_golden_path(
        target_domain: CapabilityDomain,
        capability_id: str,
        operation: str,
    ):
        """
        Decorator to automatically validate golden path.

        Usage:
            @PathValidator.require_golden_path(
                target_domain=CapabilityDomain.ACTION,
                capability_id="action.execute",
                operation="execute"
            )
            def execute_action(agent_id, ...):
                # This will only run if path is valid
                ...
        """
        def decorator(func):
            def wrapper(*args, **kwargs):
                # Get current domain from call stack
                validator = PathValidator()
                call_stack = validator.get_call_stack()

                from_domain = call_stack[-1].domain if call_stack else None
                agent_id = kwargs.get("agent_id") or (args[0] if args else "unknown")

                # Validate path
                validator.validate_call(
                    from_domain=from_domain,
                    to_domain=target_domain,
                    agent_id=agent_id,
                    capability_id=capability_id,
                    operation=operation,
                )

                try:
                    # Execute function
                    result = func(*args, **kwargs)
                    return result
                finally:
                    # Pop from stack after execution
                    validator.pop_call()

            return wrapper
        return decorator

    # ===================================================================
    # Query Methods
    # ===================================================================

    def get_violations(
        self, session_id: Optional[str] = None, limit: int = 100
    ) -> List[Dict]:
        """
        Get recent path violations.

        Args:
            session_id: Filter by session (optional)
            limit: Max results

        Returns:
            List of violation records
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        if session_id:
            cursor.execute(
                """
                SELECT session_id, call_stack_json, violation_reason, timestamp_ms
                FROM capability_call_paths
                WHERE path_valid = 0 AND session_id = ?
                ORDER BY timestamp_ms DESC
                LIMIT ?
                """,
                (session_id, limit),
            )
        else:
            cursor.execute(
                """
                SELECT session_id, call_stack_json, violation_reason, timestamp_ms
                FROM capability_call_paths
                WHERE path_valid = 0
                ORDER BY timestamp_ms DESC
                LIMIT ?
                """,
                (limit,),
            )

        rows = cursor.fetchall()
        conn.close()

        violations = []
        for row in rows:
            violations.append({
                "session_id": row["session_id"],
                "call_stack": json.loads(row["call_stack_json"]),
                "violation_reason": row["violation_reason"],
                "timestamp_ms": row["timestamp_ms"],
            })

        return violations

    def get_path_stats(self, session_id: Optional[str] = None) -> Dict:
        """
        Get path validation statistics.

        Args:
            session_id: Filter by session (optional)

        Returns:
            Dict with counts and metrics
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        stats = {}

        if session_id:
            # Total paths
            cursor.execute(
                "SELECT COUNT(*) as count FROM capability_call_paths WHERE session_id = ?",
                (session_id,),
            )
            stats["total_paths"] = cursor.fetchone()["count"]

            # Valid paths
            cursor.execute(
                "SELECT COUNT(*) as count FROM capability_call_paths WHERE session_id = ? AND path_valid = 1",
                (session_id,),
            )
            stats["valid_paths"] = cursor.fetchone()["count"]

            # Invalid paths
            cursor.execute(
                "SELECT COUNT(*) as count FROM capability_call_paths WHERE session_id = ? AND path_valid = 0",
                (session_id,),
            )
            stats["invalid_paths"] = cursor.fetchone()["count"]
        else:
            # Total paths
            cursor.execute("SELECT COUNT(*) as count FROM capability_call_paths")
            stats["total_paths"] = cursor.fetchone()["count"]

            # Valid paths
            cursor.execute(
                "SELECT COUNT(*) as count FROM capability_call_paths WHERE path_valid = 1"
            )
            stats["valid_paths"] = cursor.fetchone()["count"]

            # Invalid paths
            cursor.execute(
                "SELECT COUNT(*) as count FROM capability_call_paths WHERE path_valid = 0"
            )
            stats["invalid_paths"] = cursor.fetchone()["count"]

        conn.close()

        # Calculate success rate
        if stats["total_paths"] > 0:
            stats["success_rate"] = (stats["valid_paths"] / stats["total_paths"]) * 100
        else:
            stats["success_rate"] = 0.0

        return stats


# Global singleton
_validator_instance: Optional[PathValidator] = None


def get_path_validator(db_path: Optional[str] = None) -> PathValidator:
    """
    Get global path validator singleton.

    Args:
        db_path: Optional database path

    Returns:
        Singleton PathValidator instance
    """
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = PathValidator(db_path=db_path)
    return _validator_instance
