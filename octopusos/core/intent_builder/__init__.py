"""Intent Builder (v0.9.4) - Natural Language to ExecutionIntent.

RED LINES:
- No execution (no subprocess/shell/exec)
- No fabrication (registry_only=true)
- full_auto => question_budget=0
- Every selection must have evidence_refs
"""

from agentos.core.intent_builder.builder import IntentBuilder
from agentos.core.intent_builder.registry_query import RegistryQueryService
from agentos.core.intent_builder.evidence import EvidenceBuilder
from agentos.core.intent_builder.questions import QuestionGenerator
from agentos.core.intent_builder.nl_parser import NLParser

__all__ = [
    "IntentBuilder",
    "RegistryQueryService",
    "EvidenceBuilder",
    "QuestionGenerator",
    "NLParser",
]
