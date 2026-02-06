"""
Evolution Decision Engine v0

Provides Evolution Action determination based on Trust Trajectory.
Proposes (but does not execute) trust evolution actions.

Core components:
- EvolutionEngine: Main decision engine
- EvolutionAction: Enum for action types (PROMOTE, FREEZE, REVOKE)
- EvolutionDecision: Decision model with explanation
- DecisionHistory: Historical decision tracking

Evolution Actions ARE:
- Proposals (not executions)
- Based on Trust Trajectory (not single events)
- Explainable (all decisions have reasoning)
- Auditable (all decisions logged)

Evolution Actions do NOT:
- Execute immediately (requires E4 Human Review)
- Allow silent REVOKE
- Auto-promote to HIGH risk
- Skip explanation
"""

from .models import EvolutionAction, EvolutionDecision
from .engine import EvolutionEngine
from .actions import ActionProposal, ActionConditions

__all__ = [
    "EvolutionAction",
    "EvolutionDecision",
    "EvolutionEngine",
    "ActionProposal",
    "ActionConditions",
]
