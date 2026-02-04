"""
Knowledge module - RAG and knowledge base management

This module provides:
- KnowledgeSourceRepo: Persistent storage for data source configuration
- KnowledgeService: Health checks and diagnostics for knowledge sources
- SourceBridge: Bridge layer connecting knowledge_sources and kb_sources/kb_chunks
- SyncResult: Result object for synchronization operations
"""

from .source_repo import KnowledgeSourceRepo
from .knowledge_service import KnowledgeService
from .source_bridge import SourceBridge, SyncResult

__all__ = ["KnowledgeSourceRepo", "KnowledgeService", "SourceBridge", "SyncResult"]
