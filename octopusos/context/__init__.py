"""
Context module for AgentOS

Manages session-level context state including:
- Memory namespace binding
- RAG index binding
- Context refresh tracking
- State persistence

Sprint B Task #8 implementation
"""

from agentos.context.manager import ContextManager, ContextState

__all__ = ["ContextManager", "ContextState"]
