"""Execution policy for controlling agent behavior."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class PolicyViolation(RuntimeError):
    """Exception raised when policy is violated."""
    pass


class ExecutionMode(str, Enum):
    """Execution modes."""
    INTERACTIVE = "interactive"
    SEMI_AUTO = "semi_auto"
    FULL_AUTO = "full_auto"


@dataclass(frozen=True)
class ExecutionPolicy:
    """Execution policy that controls agent question/risk behavior."""

@dataclass(frozen=True)
class ExecutionPolicy:
    """Execution policy that controls agent question/risk behavior."""

    mode: str
    _question_budget: int = 0
    risk_profile: str = "safe"
    auto_fallback: bool = False
    require_verification: bool = True
    max_retries: int = 3
    question_rules: dict = None
    constraints: dict = None
    # PR-0131-2026-1: Token Budget & Cost Governance
    token_budget: dict = None  # {"max_total_tokens": int, "max_prompt_tokens": int, "max_completion_tokens": int}

    def __post_init__(self):
        """Initialize computed fields."""
        # Use object.__setattr__ because dataclass is frozen
        if self.question_rules is None:
            object.__setattr__(self, 'question_rules', {})
        if self.constraints is None:
            object.__setattr__(self, 'constraints', {})
        if self.token_budget is None:
            object.__setattr__(self, 'token_budget', {})

        # Compute derived fields
        object.__setattr__(self, 'allowed_question_types',
                          self.question_rules.get('allowed_types', self._get_default_allowed_types()))
        object.__setattr__(self, 'require_evidence',
                          self.question_rules.get('require_evidence', True))
        object.__setattr__(self, 'min_evidence_count',
                          self.question_rules.get('min_evidence_count', 1))

    @property
    def question_budget(self) -> int:
        """
        Get question budget (enforced invariant: full_auto = 0).
        
        Returns:
            Question budget (0 for full_auto mode)
        """
        if self.mode == "full_auto" or self.mode == ExecutionMode.FULL_AUTO:
            return 0
        return max(0, self._question_budget)

    def with_question_budget(self, n: int) -> ExecutionPolicy:
        """
        Create new policy with different question budget.
        
        Args:
            n: New question budget
            
        Returns:
            New ExecutionPolicy instance
            
        Raises:
            PolicyViolation: If trying to set non-zero budget in full_auto mode
        """
        if (self.mode == "full_auto" or self.mode == ExecutionMode.FULL_AUTO) and n != 0:
            raise PolicyViolation(
                "Cannot set non-zero question_budget in full_auto mode (Invariant #2)"
            )
        
        return ExecutionPolicy(
            mode=self.mode,
            _question_budget=n,
            risk_profile=self.risk_profile,
            auto_fallback=self.auto_fallback,
            require_verification=self.require_verification,
            max_retries=self.max_retries,
            question_rules=self.question_rules,
            constraints=self.constraints,
            token_budget=self.token_budget
        )

    def __init__(self, mode: str, config: Optional[dict] = None):
        """
        Initialize execution policy (compatibility constructor).

        Args:
            mode: Execution mode (interactive|semi_auto|full_auto)
            config: Policy configuration dict
        """
        config = config or {}
        
        # Question budget
        if mode == "full_auto":
            question_budget = 0
        elif mode == "semi_auto":
            question_budget = config.get("question_budget", 3)
        else:  # interactive
            question_budget = config.get("question_budget", 999)
        
        # Initialize frozen dataclass fields
        object.__setattr__(self, 'mode', mode)
        object.__setattr__(self, '_question_budget', question_budget)
        object.__setattr__(self, 'risk_profile', config.get("risk_profile", "safe"))
        object.__setattr__(self, 'auto_fallback', config.get("auto_fallback", False))
        object.__setattr__(self, 'require_verification', config.get("require_verification", True))
        object.__setattr__(self, 'max_retries', config.get("max_retries", 3))
        object.__setattr__(self, 'question_rules', config.get("question_rules", {}))
        object.__setattr__(self, 'constraints', config.get("constraints", {}))
        object.__setattr__(self, 'token_budget', config.get("token_budget", {}))

        # Call post_init manually
        self.__post_init__()

    def _get_default_allowed_types(self) -> list[str]:
        """Get default allowed question types based on mode."""
        if self.mode == "full_auto":
            return []
        elif self.mode == "semi_auto":
            return ["blocker"]
        else:  # interactive
            return ["clarification", "blocker", "decision_needed"]

    def can_ask_question(self, question_type: str, evidence_refs: list[str]) -> bool:
        """
        Check if a question can be asked.

        Args:
            question_type: Type of question (clarification|blocker|decision_needed)
            evidence_refs: Evidence references supporting the question

        Returns:
            True if question is allowed, False otherwise
        """
        # Check mode
        if self.mode == "full_auto":
            return False

        # Check question type
        if question_type not in self.allowed_question_types:
            return False

        # Check evidence requirement
        if self.require_evidence and len(evidence_refs) < self.min_evidence_count:
            return False

        return True

    def handle_question_rejected(self, question: dict) -> str:
        """
        Handle rejected question.

        Args:
            question: Question dict with type, text, evidence, etc.

        Returns:
            Action to take: "FALLBACK" or "BLOCKED"
        """
        if self.auto_fallback:
            return "FALLBACK"
        return "BLOCKED"

    def get_risk_constraints(self) -> dict:
        """Get risk-based constraints."""
        from agentos.core.policy.risk_profiles import RISK_PROFILES

        profile = RISK_PROFILES.get(self.risk_profile, RISK_PROFILES["safe"])

        # Merge with custom constraints
        constraints = profile.copy()
        constraints.update(self.constraints)

        return constraints

    def validate_operation(self, operation: str, context: dict) -> tuple[bool, str]:
        """
        Validate if an operation is allowed.

        Args:
            operation: Operation to validate (e.g., "rm -rf /tmp/file")
            context: Context dict (e.g., {"files_count": 10})

        Returns:
            (is_allowed, reason)
        """
        constraints = self.get_risk_constraints()

        # Check forbidden operations
        forbidden = constraints.get("forbidden_operations", [])
        for pattern in forbidden:
            if pattern in operation:
                return False, f"Forbidden operation: {pattern}"

        # Check max files per commit
        max_files = constraints.get("max_files_per_commit", 999)
        files_count = context.get("files_count", 0)
        if files_count > max_files:
            return False, f"Too many files ({files_count} > {max_files})"

        # Check destructive operations
        if not constraints.get("allow_destructive", False):
            destructive_patterns = ["rm ", "DELETE ", "DROP ", "TRUNCATE "]
            for pattern in destructive_patterns:
                if pattern in operation:
                    return False, f"Destructive operation not allowed: {pattern}"

        return True, "OK"

    def to_dict(self) -> dict:
        """Convert policy to dict."""
        return {
            "schema_version": "1.0.0",
            "mode": self.mode,
            "question_budget": self.question_budget,
            "risk_profile": self.risk_profile,
            "auto_fallback": self.auto_fallback,
            "require_verification": self.require_verification,
            "max_retries": self.max_retries,
            "question_rules": {
                "allowed_types": self.allowed_question_types,
                "require_evidence": self.require_evidence,
                "min_evidence_count": self.min_evidence_count,
            },
            "constraints": self.constraints,
            "token_budget": self.token_budget,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ExecutionPolicy":
        """Create policy from dict."""
        mode = data.get("mode", "interactive")
        config = {
            "question_budget": data.get("question_budget"),
            "risk_profile": data.get("risk_profile", "safe"),
            "auto_fallback": data.get("auto_fallback", False),
            "require_verification": data.get("require_verification", True),
            "max_retries": data.get("max_retries", 3),
            "question_rules": data.get("question_rules", {}),
            "constraints": data.get("constraints", {}),
        }
        return cls(mode, config)
