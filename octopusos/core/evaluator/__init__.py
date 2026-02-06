"""
Intent Evaluator Engine — v0.9.3

Core module for evaluating multiple Execution Intents, detecting conflicts,
planning merges, and comparing risks.

Red Lines:
- RL-E1: No execution payload in outputs
- RL-E2: Merged intents must have complete lineage
"""

from .engine import EvaluatorEngine
from .intent_set_loader import IntentSetLoader
from .intent_normalizer import IntentNormalizer
from .conflict_detector import ConflictDetector
from .risk_comparator import RiskComparator
from .merge_planner import MergePlanner
from .evaluation_explainer import EvaluationExplainer

__all__ = [
    "EvaluatorEngine",
    "IntentSetLoader",
    "IntentNormalizer",
    "ConflictDetector",
    "RiskComparator",
    "MergePlanner",
    "EvaluationExplainer",
]

__version__ = "0.9.3"
