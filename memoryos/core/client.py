"""MemoryClient - API boundary for accessing MemoryOS."""

from __future__ import annotations
from typing import Optional
from memoryos.core.store import MemoryStore

class MemoryClient:
    """Client for accessing MemoryOS (local or remote)."""
    
    def __init__(self, store: MemoryStore):
        self.store = store
    
    def upsert(self, memory_item: dict) -> str:
        """Insert or update memory item."""
        return self.store.upsert(memory_item)
    
    def get(self, memory_id: str) -> Optional[dict]:
        """Get memory by ID."""
        return self.store.get(memory_id)
    
    def query(self, query: dict) -> list[dict]:
        """Query memories."""
        return self.store.query(query)
    
    def build_context(self, project_id: str, agent_type: str, **kwargs) -> dict:
        """Build memory context."""
        return self.store.build_context(project_id, agent_type, **kwargs)
