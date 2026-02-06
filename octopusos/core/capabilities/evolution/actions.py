"""
Evolution Action Conditions and Proposals

Defines the conditions that trigger each evolution action.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
from .models import EvolutionAction, ReviewLevel


@dataclass
class ActionConditions:
    """
    Conditions required to trigger an evolution action.

    Attributes:
        action: Evolution action
        risk_threshold: Risk score threshold
        trajectory_state: Required trust trajectory state
        min_executions: Minimum execution count
        min_stable_days: Minimum stable days
        max_violations: Maximum allowed violations
        requires_sandbox_clean: Whether sandbox must be violation-free
    """
    action: EvolutionAction
    risk_threshold: Optional[float] = None
    trajectory_state: Optional[str] = None
    min_executions: Optional[int] = None
    min_stable_days: Optional[int] = None
    max_violations: Optional[int] = None
    requires_sandbox_clean: bool = False

    def check(self, evidence: Dict) -> bool:
        """
        Check if conditions are met based on evidence.

        Args:
            evidence: Evidence dictionary with metrics

        Returns:
            True if all conditions are met
        """
        # Check risk threshold
        if self.risk_threshold is not None:
            risk_score = evidence.get("risk_score", 100)
            if self.action == EvolutionAction.PROMOTE:
                # For PROMOTE, risk must be below threshold
                if risk_score >= self.risk_threshold:
                    return False
            elif self.action == EvolutionAction.REVOKE:
                # For REVOKE, risk must be above threshold
                if risk_score < self.risk_threshold:
                    return False

        # Check trajectory state
        if self.trajectory_state is not None:
            current_trajectory = evidence.get("trust_trajectory", "")
            if current_trajectory != self.trajectory_state:
                return False

        # Check minimum executions
        if self.min_executions is not None:
            executions = evidence.get("total_executions", 0)
            if executions < self.min_executions:
                return False

        # Check minimum stable days
        if self.min_stable_days is not None:
            stable_days = evidence.get("stable_days", 0)
            if stable_days < self.min_stable_days:
                return False

        # Check maximum violations
        if self.max_violations is not None:
            violations = evidence.get("violations", 999)
            if violations > self.max_violations:
                return False

        # Check sandbox clean requirement
        if self.requires_sandbox_clean:
            sandbox_violations = evidence.get("sandbox_violations", 0)
            if sandbox_violations > 0:
                return False

        return True

    def get_unmet_reasons(self, evidence: Dict) -> List[str]:
        """
        Get list of reasons why conditions are not met.

        Args:
            evidence: Evidence dictionary

        Returns:
            List of unmet condition descriptions
        """
        reasons = []

        if self.risk_threshold is not None:
            risk_score = evidence.get("risk_score", 100)
            if self.action == EvolutionAction.PROMOTE:
                if risk_score >= self.risk_threshold:
                    reasons.append(
                        f"Risk score {risk_score:.2f} >= threshold {self.risk_threshold:.2f}"
                    )
            elif self.action == EvolutionAction.REVOKE:
                if risk_score < self.risk_threshold:
                    reasons.append(
                        f"Risk score {risk_score:.2f} < threshold {self.risk_threshold:.2f}"
                    )

        if self.trajectory_state is not None:
            current_trajectory = evidence.get("trust_trajectory", "")
            if current_trajectory != self.trajectory_state:
                reasons.append(
                    f"Trajectory '{current_trajectory}' != required '{self.trajectory_state}'"
                )

        if self.min_executions is not None:
            executions = evidence.get("total_executions", 0)
            if executions < self.min_executions:
                reasons.append(
                    f"Only {executions} executions, need {self.min_executions}"
                )

        if self.min_stable_days is not None:
            stable_days = evidence.get("stable_days", 0)
            if stable_days < self.min_stable_days:
                reasons.append(
                    f"Only {stable_days} stable days, need {self.min_stable_days}"
                )

        if self.max_violations is not None:
            violations = evidence.get("violations", 999)
            if violations > self.max_violations:
                reasons.append(
                    f"Too many violations: {violations} > {self.max_violations}"
                )

        if self.requires_sandbox_clean:
            sandbox_violations = evidence.get("sandbox_violations", 0)
            if sandbox_violations > 0:
                reasons.append(
                    f"Sandbox violations detected: {sandbox_violations}"
                )

        return reasons


# Predefined action conditions (v0 rules)
PROMOTE_CONDITIONS = ActionConditions(
    action=EvolutionAction.PROMOTE,
    risk_threshold=30.0,  # Must be LOW risk
    trajectory_state="STABLE",  # Must be STABLE trajectory
    min_executions=50,  # At least 50 successful executions
    min_stable_days=30,  # Stable for 30+ days
    max_violations=0,  # Zero violations
    requires_sandbox_clean=True  # Clean sandbox record
)

FREEZE_CONDITIONS = ActionConditions(
    action=EvolutionAction.FREEZE,
    trajectory_state="DEGRADING",  # Degrading trajectory
    max_violations=5  # Max 5 violations
)

REVOKE_CONDITIONS = ActionConditions(
    action=EvolutionAction.REVOKE,
    risk_threshold=70.0,  # HIGH risk
    max_violations=0,  # Any of these triggers revoke:
)

# Additional revoke triggers (any one triggers revoke)
REVOKE_TRIGGERS = {
    "sandbox_violation": "Sandbox violation detected",
    "policy_denial": "Multiple policy denials (3+ in 24h)",
    "human_flag": "Human-flagged for review",
    "trust_degraded": "Trust trajectory degraded to CRITICAL"
}


@dataclass
class ActionProposal:
    """
    Proposed evolution action with supporting evidence.

    Attributes:
        action: Proposed action
        conditions: Conditions that apply
        conditions_met: Whether conditions are met
        unmet_reasons: Reasons why conditions are not met
        review_level: Required review level
        evidence: Supporting evidence
    """
    action: EvolutionAction
    conditions: ActionConditions
    conditions_met: bool
    unmet_reasons: List[str]
    review_level: ReviewLevel
    evidence: Dict

    def to_dict(self) -> Dict:
        """
        Convert proposal to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "action": self.action.value,
            "conditions_met": self.conditions_met,
            "unmet_reasons": self.unmet_reasons,
            "review_level": self.review_level.value,
            "evidence": self.evidence,
            "description": self.action.get_description(),
            "consequences": self.action.get_consequences()
        }


def evaluate_promote(evidence: Dict) -> ActionProposal:
    """
    Evaluate PROMOTE action conditions.

    Args:
        evidence: Evidence dictionary

    Returns:
        ActionProposal with evaluation result
    """
    conditions_met = PROMOTE_CONDITIONS.check(evidence)
    unmet_reasons = PROMOTE_CONDITIONS.get_unmet_reasons(evidence)

    # CRITICAL: Never auto-promote to HIGH risk
    if evidence.get("trust_tier") == "HIGH" or evidence.get("risk_score", 0) >= 70:
        conditions_met = False
        unmet_reasons.append("BLOCKED: Cannot auto-promote to HIGH risk tier")

    review_level = ReviewLevel.HIGH_PRIORITY if conditions_met else ReviewLevel.NONE

    return ActionProposal(
        action=EvolutionAction.PROMOTE,
        conditions=PROMOTE_CONDITIONS,
        conditions_met=conditions_met,
        unmet_reasons=unmet_reasons,
        review_level=review_level,
        evidence=evidence
    )


def evaluate_freeze(evidence: Dict) -> ActionProposal:
    """
    Evaluate FREEZE action conditions.

    Args:
        evidence: Evidence dictionary

    Returns:
        ActionProposal with evaluation result
    """
    conditions_met = FREEZE_CONDITIONS.check(evidence)
    unmet_reasons = FREEZE_CONDITIONS.get_unmet_reasons(evidence)

    review_level = ReviewLevel.STANDARD if conditions_met else ReviewLevel.NONE

    return ActionProposal(
        action=EvolutionAction.FREEZE,
        conditions=FREEZE_CONDITIONS,
        conditions_met=conditions_met,
        unmet_reasons=unmet_reasons,
        review_level=review_level,
        evidence=evidence
    )


def evaluate_revoke(evidence: Dict) -> ActionProposal:
    """
    Evaluate REVOKE action conditions.

    Args:
        evidence: Evidence dictionary

    Returns:
        ActionProposal with evaluation result
    """
    # Check if any revoke trigger is present
    conditions_met = False
    unmet_reasons = []
    trigger_reasons = []

    # Check HIGH risk score (>= 70)
    risk_score = evidence.get("risk_score", 0)
    if risk_score >= 70.0:
        conditions_met = True
        trigger_reasons.append(f"Risk score {risk_score:.2f} >= 70.0")

    # Check additional triggers
    for trigger_key, trigger_desc in REVOKE_TRIGGERS.items():
        if evidence.get(trigger_key, False):
            conditions_met = True
            trigger_reasons.append(trigger_desc)

    # Check critical trajectory
    if evidence.get("trust_trajectory") == "CRITICAL":
        conditions_met = True
        trigger_reasons.append("Trust trajectory: CRITICAL")

    if not conditions_met:
        unmet_reasons = ["No revoke triggers detected"]

    # REVOKE always requires CRITICAL review
    review_level = ReviewLevel.CRITICAL if conditions_met else ReviewLevel.NONE

    # Include trigger reasons in evidence
    if trigger_reasons:
        evidence = {**evidence, "revoke_triggers": trigger_reasons}

    return ActionProposal(
        action=EvolutionAction.REVOKE,
        conditions=REVOKE_CONDITIONS,
        conditions_met=conditions_met,
        unmet_reasons=unmet_reasons,
        review_level=review_level,
        evidence=evidence
    )
