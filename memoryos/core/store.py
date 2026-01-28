"""Abstract MemoryStore interface."""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional

class MemoryStore(ABC):
    """Abstract interface for memory storage backends."""
    
    @abstractmethod
    def upsert(self, memory_item: dict) -> str:
        """Insert or update memory item."""
        pass
    
    @abstractmethod
    def get(self, memory_id: str) -> Optional[dict]:
        """Get memory by ID."""
        pass
    
    @abstractmethod
    def query(self, query: dict) -> list[dict]:
        """Query memories with filters."""
        pass
    
    @abstractmethod
    def delete(self, memory_id: str) -> bool:
        """Delete memory by ID."""
        pass
    
    @abstractmethod
    def build_context(self, project_id: str, agent_type: str, **kwargs) -> dict:
        """Build memory context."""
        pass
