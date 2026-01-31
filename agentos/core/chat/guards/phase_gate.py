"""Phase Gate Guard - Prevents execution of Outbound/External operations during Planning phase.

This is the highest priority guard that enforces execution phase restrictions.
External communication (comm.*) operations are only allowed during execution phase,
never during planning phase.

IMPORTANT: Phase Gate only checks execution_phase, NOT conversation_mode.

- conversation_mode: Determines output style and user experience (chat/discussion/plan/development/task)
- execution_phase: Determines permission boundary (planning/execution)

The two are independent:
- Changing mode does NOT automatically change phase
- Phase must be explicitly switched by user
- Only execution_phase affects /comm command permissions

Why this guard is essential:
- Planning should be pure computation without side effects
- Prevents accidental data leakage during plan generation
- Ensures deterministic planning behavior
- Blocks timing attacks via planning-phase network calls

Bypass attempts to watch for:
- Renaming operations to avoid "comm." prefix
- Setting execution_phase to None or invalid values
- Wrapping comm operations in non-comm namespaces
- Race conditions in phase transitions

Defense measures:
- Whitelist-based approach (only "execution" allows comm.*)
- Fail-closed by default (unknown phase = blocked)
- Immutable phase context passed explicitly
- Atomic check before any external operation
"""


class PhaseGateError(Exception):
    """Raised when operation is blocked by phase gate.

    This exception indicates that an external operation was attempted
    during an inappropriate execution phase (e.g., planning).
    """
    pass


class PhaseGate:
    """Phase gate enforces execution phase restrictions.

    Rules:
    - Planning phase: No external communication (comm.*)
    - Execution phase: All operations allowed
    - Default: Block if phase unknown

    This guard implements a fail-closed security model where any
    ambiguity results in blocking the operation.

    Examples:
        >>> PhaseGate.check("comm.search", "execution")  # Allowed
        >>> PhaseGate.check("comm.search", "planning")   # Raises PhaseGateError
        >>> PhaseGate.is_allowed("comm.fetch", "planning")  # Returns False
    """

    # Valid phases
    PHASE_PLANNING = "planning"
    PHASE_EXECUTION = "execution"

    # Operations that require execution phase
    RESTRICTED_PREFIX = "comm."

    @staticmethod
    def check(operation: str, execution_phase: str):
        """Check if operation is allowed in current phase.

        This method enforces the core security policy: external communication
        operations (comm.*) are forbidden during planning phase.

        IMPORTANT: This check ONLY examines execution_phase, NOT conversation_mode.
        - conversation_mode controls output style (chat/plan/development/task)
        - execution_phase controls permission boundary (planning/execution)
        - They are independent and must be set separately

        Args:
            operation: Operation type (e.g., "comm.search", "comm.fetch")
            execution_phase: Current execution phase ("planning" or "execution")
                            NOTE: This is NOT the same as conversation_mode

        Raises:
            PhaseGateError: If operation is not allowed in current phase

        Examples:
            >>> PhaseGate.check("comm.search", "execution")  # OK
            >>> PhaseGate.check("local.query", "planning")   # OK
            >>> PhaseGate.check("comm.search", "planning")   # Raises PhaseGateError
        """
        # comm.* operations forbidden unless explicitly in execution phase
        if operation.startswith(PhaseGate.RESTRICTED_PREFIX):
            if execution_phase != PhaseGate.PHASE_EXECUTION:
                raise PhaseGateError(
                    f"Operation '{operation}' is forbidden in {execution_phase} phase. "
                    f"External communication is only allowed in execution phase."
                )

    @staticmethod
    def is_allowed(operation: str, execution_phase: str) -> bool:
        """Check if operation is allowed (non-throwing version).

        This is a convenience method for checking permissions without
        exception handling.

        Args:
            operation: Operation type (e.g., "comm.search", "comm.fetch")
            execution_phase: Current execution phase ("planning" or "execution")

        Returns:
            bool: True if operation is allowed, False otherwise

        Examples:
            >>> PhaseGate.is_allowed("comm.search", "execution")  # True
            >>> PhaseGate.is_allowed("comm.search", "planning")   # False
        """
        try:
            PhaseGate.check(operation, execution_phase)
            return True
        except PhaseGateError:
            return False

    @staticmethod
    def validate_phase(execution_phase: str) -> bool:
        """Validate that execution_phase is a recognized phase.

        Args:
            execution_phase: Phase string to validate

        Returns:
            bool: True if phase is valid, False otherwise
        """
        return execution_phase in (PhaseGate.PHASE_PLANNING, PhaseGate.PHASE_EXECUTION)
