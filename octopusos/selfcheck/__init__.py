"""
Self-check module for AgentOS

Provides comprehensive system health checks for:
- Runtime (version, paths, permissions)
- Providers (local & cloud)
- Context (memory, RAG, session binding)
- Chat pipeline

Sprint B Task #7 implementation
"""

from agentos.selfcheck.runner import SelfCheckRunner

__all__ = ["SelfCheckRunner"]
