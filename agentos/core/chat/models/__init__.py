"""Data models for Chat Mode"""

# Import from models_base to maintain backward compatibility
from agentos.core.chat.models_base import (
    ConversationMode,
    ChatSession,
    ChatMessage,
    ChatResponse
)

# Import external info models
from agentos.core.chat.models.external_info import (
    ExternalInfoAction,
    ExternalInfoDeclaration
)

# Import decision candidate models (v3 Shadow Classifier System)
from agentos.core.chat.models.decision_candidate import (
    DecisionRole,
    DecisionCandidate,
    DecisionSet,
    ClassifierVersion,
    validate_shadow_isolation,
)

__all__ = [
    # Base models
    "ConversationMode",
    "ChatSession",
    "ChatMessage",
    "ChatResponse",
    # External info models
    "ExternalInfoAction",
    "ExternalInfoDeclaration",
    # Decision candidate models (v3)
    "DecisionRole",
    "DecisionCandidate",
    "DecisionSet",
    "ClassifierVersion",
    "validate_shadow_isolation",
]
