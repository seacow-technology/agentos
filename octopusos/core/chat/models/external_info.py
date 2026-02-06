"""
External Information Declaration Models

This module defines data structures for LLM to declare external information needs
during chat responses. These declarations enable the system to:
1. Capture what external info the LLM wants before allowing execution
2. Present pending requests to users for approval
3. Enforce execution phase gating based on external info requirements

Models:
- ExternalInfoAction: Enumeration of external information action types
- ExternalInfoDeclaration: Structured declaration of external info needs
"""

from __future__ import annotations
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict


class ExternalInfoAction(str, Enum):
    """
    External information action types

    Defines the types of external information operations that an LLM
    can declare as needed during conversation.
    """
    WEB_SEARCH = "web_search"           # Search the internet for information
    WEB_FETCH = "web_fetch"             # Fetch content from a specific URL
    API_CALL = "api_call"               # Call an external API
    DATABASE_QUERY = "database_query"   # Query external database
    FILE_READ = "file_read"             # Read file from filesystem
    FILE_WRITE = "file_write"           # Write file to filesystem
    COMMAND_EXEC = "command_exec"       # Execute system command
    TOOL_CALL = "tool_call"             # Call an external tool/extension


class ExternalInfoDeclaration(BaseModel):
    """
    Structured declaration of external information needs

    Represents a single declaration by the LLM of what external information
    it needs to properly answer the user's question. The system will:
    1. Capture these declarations during response generation
    2. Block execution phase transition until declarations are reviewed
    3. Present declarations to user in WebUI for approval

    Attributes:
        action: Type of external information action needed
        reason: Human-readable explanation of why this info is needed
        target: Target of the action (URL, query string, file path, etc.)
        params: Additional parameters for the action (headers, filters, etc.)
        priority: Priority level (1=critical, 2=important, 3=nice-to-have)
        estimated_cost: Estimated cost/risk level (LOW/MED/HIGH)
        alternatives: List of alternative approaches if this action is denied
    """
    action: ExternalInfoAction = Field(
        ...,
        description="Type of external information action needed"
    )

    reason: str = Field(
        ...,
        description="Human-readable explanation of why this information is needed",
        min_length=10,
        max_length=500
    )

    target: str = Field(
        ...,
        description="Target of the action (URL, query string, file path, command, etc.)",
        min_length=1,
        max_length=1000
    )

    params: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional parameters for the action (headers, filters, options, etc.)"
    )

    priority: int = Field(
        default=2,
        ge=1,
        le=3,
        description="Priority level: 1=critical, 2=important, 3=nice-to-have"
    )

    estimated_cost: str = Field(
        default="MED",
        description="Estimated cost/risk level: LOW, MED, HIGH",
        pattern="^(LOW|MED|HIGH)$"
    )

    alternatives: Optional[List[str]] = Field(
        default=None,
        description="List of alternative approaches if this action is denied"
    )

    # Pydantic v2 configuration
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "action": "web_search",
                "reason": "Need to find the latest Python 3.12 release notes to answer version-specific question",
                "target": "Python 3.12 release notes site:python.org",
                "params": {"max_results": 5},
                "priority": 1,
                "estimated_cost": "LOW",
                "alternatives": [
                    "Use cached documentation if available",
                    "Provide answer based on Python 3.11 as approximation"
                ]
            }
        }
    )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for serialization

        Returns:
            Dictionary representation of the declaration
        """
        return {
            "action": self.action.value,
            "reason": self.reason,
            "target": self.target,
            "params": self.params,
            "priority": self.priority,
            "estimated_cost": self.estimated_cost,
            "alternatives": self.alternatives
        }

    def to_user_message(self) -> str:
        """
        Convert to user-friendly message for WebUI display

        Returns:
            Human-readable string describing this declaration
        """
        action_labels = {
            ExternalInfoAction.WEB_SEARCH: "Web Search",
            ExternalInfoAction.WEB_FETCH: "Web Fetch",
            ExternalInfoAction.API_CALL: "API Call",
            ExternalInfoAction.DATABASE_QUERY: "Database Query",
            ExternalInfoAction.FILE_READ: "File Read",
            ExternalInfoAction.FILE_WRITE: "File Write",
            ExternalInfoAction.COMMAND_EXEC: "Command Execution",
            ExternalInfoAction.TOOL_CALL: "Tool Call"
        }

        priority_labels = {
            1: "Critical",
            2: "Important",
            3: "Nice-to-have"
        }

        label = action_labels.get(self.action, str(self.action))
        priority_label = priority_labels.get(self.priority, str(self.priority))

        message = f"[{label}] {self.reason}\n"
        message += f"Target: {self.target}\n"
        message += f"Priority: {priority_label} | Risk: {self.estimated_cost}"

        if self.alternatives:
            message += f"\nAlternatives: {', '.join(self.alternatives[:2])}"

        return message
