"""
Guardian Base Class

Defines the abstract Guardian interface that all Guardian implementations must follow.

🔒 SEMANTIC FREEZE (F-2): Guardian Workflow State
--------------------------------------------------
Guardian produces verdicts, Supervisor applies state changes

✅ Guardian CAN:
   - Read task state
   - Produce GuardianVerdictSnapshot (frozen)
   - Return PASS/FAIL/NEEDS_CHANGES status

❌ Guardian CANNOT:
   - NEVER directly modify task state
   - NEVER write to tasks table
   - NEVER call Supervisor.update_task_state()

Guarantee: Supervisor is the SOLE state writer. All state changes traced to Supervisor decisions.
Reference: ADR-004 Section F-2
"""

from abc import ABC, abstractmethod
from typing import Dict, Any

from .models import GuardianVerdictSnapshot


class Guardian(ABC):
    """
    Abstract Guardian Base Class

    All Guardian implementations must inherit from this class and implement
    the verify() method.

    Attributes:
        code: Unique identifier for this Guardian (e.g., "smoke_test", "diff")
    """

    code: str = ""

    @abstractmethod
    def verify(self, task_id: str, context: Dict[str, Any]) -> GuardianVerdictSnapshot:
        """
        Execute verification for a task

        🔒 SEMANTIC FREEZE (F-2): This method MUST only return a verdict.
        It MUST NOT modify task state or write to the database.

        Args:
            task_id: Task to verify
            context: Verification context (may include task metadata, findings, etc.)

        Returns:
            GuardianVerdictSnapshot with the verification result (frozen dataclass)

        Raises:
            Exception: If verification fails unexpectedly

        Contract:
            - Returns GuardianVerdictSnapshot (immutable)
            - NEVER modifies task state directly
            - NEVER writes to tasks/guardian_assignments/guardian_verdicts tables
        """
        raise NotImplementedError("Guardian subclasses must implement verify()")

    def __repr__(self) -> str:
        return f"<Guardian code={self.code}>"
