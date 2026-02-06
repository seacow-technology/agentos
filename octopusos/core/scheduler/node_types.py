"""TaskGraph node types for different operations."""

from enum import Enum

class TaskNodeType(Enum):
    """Task node types."""
    SCAN = "scan"
    GENERATE = "generate"
    APPLY = "apply"
    VERIFY = "verify"
    REVIEW = "review"
    LEARN = "learn"
    HEAL = "heal"

class TaskNode:
    """Enhanced task node with type and metadata."""
    
    def __init__(
        self,
        task_id: str,
        node_type: TaskNodeType,
        metadata: dict
    ):
        self.task_id = task_id
        self.node_type = node_type
        self.metadata = metadata
        self.estimated_tokens = metadata.get("estimated_tokens", 1000)
        self.estimated_cost = metadata.get("estimated_cost", 0.01)
