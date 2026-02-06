"""
Risk Score Module v0

Provides risk scoring for extension executions based on historical audit data.
Risk scores are deterministic, explainable, and based on measurable facts.

Core components:
- RiskScorer: Main risk calculation engine
- RiskScore: Data model for risk scores
- RiskExplainer: Generates human-readable explanations
- Dimension calculators: Individual risk dimension computations

Risk Score does NOT:
- Participate in execution decisions
- Directly block executions
- It only provides input to Policy Engine (D4)

Risk Score IS:
- Deterministic (same history → same score)
- Explainable (all dimensions traceable)
- Evidence-based (not configuration-based)
"""

from .models import RiskScore
from .scorer import RiskScorer
from .explainer import RiskExplainer

__all__ = [
    "RiskScore",
    "RiskScorer",
    "RiskExplainer",
]
