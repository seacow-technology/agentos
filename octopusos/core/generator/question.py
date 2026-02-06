"""Question definition and handling for agent execution."""

from enum import Enum
from typing import Optional


class QuestionType(str, Enum):
    """Question types for agent execution."""
    CLARIFICATION = "clarification"
    BLOCKER = "blocker"
    DECISION_NEEDED = "decision_needed"


class Question:
    """Represents a question from the agent during execution."""

    def __init__(
        self,
        question_type: str,
        question_text: str,
        evidence_refs: list,
        impact: str,
        suggested_answers: Optional[list] = None,
    ):
        """
        Initialize question.

        Args:
            question_type: Type of question (clarification|blocker|decision_needed)
            question_text: The actual question text
            evidence_refs: Evidence IDs from FactPack/MemoryPack supporting this question
            impact: Description of what happens if question is not answered
            suggested_answers: Optional list of suggested answers
        """
        self.question_type = question_type
        self.question_text = question_text
        self.evidence_refs = evidence_refs
        self.impact = impact
        self.suggested_answers = suggested_answers or []

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "question_type": self.question_type,
            "question_text": self.question_text,
            "evidence_refs": self.evidence_refs,
            "impact": self.impact,
            "suggested_answers": self.suggested_answers,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Question":
        """Create Question from dictionary."""
        return cls(
            question_type=data["question_type"],
            question_text=data["question_text"],
            evidence_refs=data["evidence_refs"],
            impact=data["impact"],
            suggested_answers=data.get("suggested_answers", []),
        )

    def validate(self) -> tuple[bool, list[str]]:
        """
        Validate question structure.

        Returns:
            (is_valid, errors)
        """
        errors = []

        # Check required fields
        if not self.question_type:
            errors.append("question_type is required")
        elif self.question_type not in ["clarification", "blocker", "decision_needed"]:
            errors.append(f"Invalid question_type: {self.question_type}")

        if not self.question_text:
            errors.append("question_text is required")

        if not self.evidence_refs:
            errors.append("evidence_refs is required (at least one evidence)")

        if not self.impact:
            errors.append("impact is required")

        return len(errors) == 0, errors


def create_blocker_question(
    question_text: str,
    evidence_refs: list,
    impact: str,
    suggested_answers: Optional[list] = None,
) -> Question:
    """Create a blocker question (for semi_auto mode)."""
    return Question(
        question_type="blocker",
        question_text=question_text,
        evidence_refs=evidence_refs,
        impact=impact,
        suggested_answers=suggested_answers,
    )


def create_clarification_question(
    question_text: str,
    evidence_refs: list,
    impact: str,
    suggested_answers: Optional[list] = None,
) -> Question:
    """Create a clarification question (for interactive mode)."""
    return Question(
        question_type="clarification",
        question_text=question_text,
        evidence_refs=evidence_refs,
        impact=impact,
        suggested_answers=suggested_answers,
    )


def create_decision_question(
    question_text: str,
    evidence_refs: list,
    impact: str,
    suggested_answers: Optional[list] = None,
) -> Question:
    """Create a decision question (for interactive mode)."""
    return Question(
        question_type="decision_needed",
        question_text=question_text,
        evidence_refs=evidence_refs,
        impact=impact,
        suggested_answers=suggested_answers,
    )
