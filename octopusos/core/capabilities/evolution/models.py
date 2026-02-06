"""
Evolution Decision Data Models

Defines the data structures for evolution decisions and actions.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, Optional, List


class EvolutionAction(Enum):
    """
    Evolution Action enumeration.

    Actions represent proposed trust evolution:
    - PROMOTE: Upgrade trust level
    - FREEZE: Maintain current level, increase scrutiny
    - REVOKE: Downgrade trust level
    - NONE: No action needed
    """
    PROMOTE = "PROMOTE"
    FREEZE = "FREEZE"
    REVOKE = "REVOKE"
    NONE = "NONE"

    def get_description(self) -> str:
        """
        Get human-readable description of action.

        Returns:
            Action description
        """
        descriptions = {
            EvolutionAction.PROMOTE: "Upgrade trust: reduce approval frequency, relax execution window",
            EvolutionAction.FREEZE: "Freeze trust: maintain level but increase scrutiny",
            EvolutionAction.REVOKE: "Revoke trust: downgrade level, require re-approval",
            EvolutionAction.NONE: "No action needed: current trust level appropriate"
        }
        return descriptions[self]

    def get_consequences(self) -> List[str]:
        """
        Get list of action consequences.

        Returns:
            List of consequence strings
        """
        consequences = {
            EvolutionAction.PROMOTE: [
                "Lower human approval frequency",
                "Wider execution time window",
                "Allow higher tier requests"
            ],
            EvolutionAction.FREEZE: [
                "Block new permission grants",
                "Maintain existing capabilities",
                "Mandatory sandbox for all executions"
            ],
            EvolutionAction.REVOKE: [
                "All automatic execution disabled",
                "Must restart Phase D (Trust Building)",
                "Requires full human review"
            ],
            EvolutionAction.NONE: []
        }
        return consequences[self]

    def requires_human_review(self) -> bool:
        """
        Whether this action requires human review.

        Returns:
            True if REVOKE or PROMOTE
        """
        return self in [EvolutionAction.REVOKE, EvolutionAction.PROMOTE]


class ReviewLevel(Enum):
    """
    Human review requirement levels.
    """
    NONE = "NONE"
    STANDARD = "STANDARD"
    HIGH_PRIORITY = "HIGH_PRIORITY"
    CRITICAL = "CRITICAL"


@dataclass
class EvolutionDecision:
    """
    Evolution decision result with reasoning and context.

    Attributes:
        decision_id: Unique decision identifier
        extension_id: Extension identifier
        action_id: Action identifier
        action: Proposed evolution action
        risk_score: Current risk score
        trust_tier: Current trust tier
        trust_trajectory: Current trust trajectory state
        explanation: Human-readable explanation
        causal_chain: Decision → Action causal chain
        review_level: Required human review level
        conditions_met: List of conditions that triggered this decision
        evidence: Supporting evidence for decision
        created_at: Decision timestamp
        expires_at: When this decision expires (if applicable)
    """
    decision_id: str
    extension_id: str
    action_id: str
    action: EvolutionAction
    risk_score: float
    trust_tier: str
    trust_trajectory: str
    explanation: str
    causal_chain: List[str]
    review_level: ReviewLevel
    conditions_met: List[str]
    evidence: Dict
    created_at: datetime
    expires_at: Optional[datetime] = None

    def to_dict(self) -> Dict:
        """
        Convert decision to API-friendly dictionary.

        Returns:
            Dictionary with all decision details
        """
        return {
            "decision_id": self.decision_id,
            "extension_id": self.extension_id,
            "action_id": self.action_id,
            "action": self.action.value,
            "risk_score": round(self.risk_score, 2),
            "trust_tier": self.trust_tier,
            "trust_trajectory": self.trust_trajectory,
            "explanation": self.explanation,
            "causal_chain": self.causal_chain,
            "review_level": self.review_level.value,
            "conditions_met": self.conditions_met,
            "evidence": self.evidence,
            "consequences": self.action.get_consequences(),
            "requires_review": self.action.requires_human_review(),
            "meta": {
                "created_at": int(self.created_at.timestamp() * 1000),
                "expires_at": int(self.expires_at.timestamp() * 1000) if self.expires_at else None
            }
        }

    def is_safe_for_auto_execution(self) -> bool:
        """
        Whether this decision can be auto-executed without human review.

        Returns:
            True only for NONE and FREEZE actions
        """
        return self.action in [EvolutionAction.NONE, EvolutionAction.FREEZE]

    def get_summary(self) -> str:
        """
        Get one-line summary of decision.

        Returns:
            Brief summary string
        """
        return f"{self.action.value}: {self.explanation.split('.')[0]}"


@dataclass
class DecisionRecord:
    """
    Historical record of an evolution decision.

    Attributes:
        record_id: Unique record identifier
        decision_id: Decision identifier
        extension_id: Extension identifier
        action_id: Action identifier
        action: Evolution action
        status: Decision status (PROPOSED, APPROVED, REJECTED, EXPIRED)
        risk_score: Risk score at decision time
        trust_tier: Trust tier at decision time
        trust_trajectory: Trust trajectory at decision time
        explanation: Decision explanation
        approved_by: Who approved (if applicable)
        approved_at: When approved (if applicable)
        created_at: Decision timestamp
    """
    record_id: str
    decision_id: str
    extension_id: str
    action_id: str
    action: str
    status: str  # PROPOSED, APPROVED, REJECTED, EXPIRED
    risk_score: float
    trust_tier: str
    trust_trajectory: str
    explanation: str
    approved_by: Optional[str]
    approved_at: Optional[datetime]
    created_at: datetime

    def to_dict(self) -> Dict:
        """
        Convert record to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "record_id": self.record_id,
            "decision_id": self.decision_id,
            "extension_id": self.extension_id,
            "action_id": self.action_id,
            "action": self.action,
            "status": self.status,
            "risk_score": round(self.risk_score, 2),
            "trust_tier": self.trust_tier,
            "trust_trajectory": self.trust_trajectory,
            "explanation": self.explanation,
            "approved_by": self.approved_by,
            "approved_at": int(self.approved_at.timestamp() * 1000) if self.approved_at else None,
            "created_at": int(self.created_at.timestamp() * 1000)
        }
