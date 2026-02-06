"""
Log entry data model.

This module contains the LogEntry model which is shared between
the logging system and the API layer.
"""

from pydantic import BaseModel
from typing import Optional, Dict, Any


class LogEntry(BaseModel):
    """Log entry model"""
    id: str
    level: str  # "debug" | "info" | "warn" | "error"
    timestamp: str
    task_id: Optional[str] = None
    session_id: Optional[str] = None
    span_id: Optional[str] = None
    message: str
    metadata: Dict[str, Any] = {}
