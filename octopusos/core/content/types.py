"""Content Type Registry - manages registered content types."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from agentos.core.content.schema_loader import ContentSchemaLoader


@dataclass
class ContentTypeDescriptor:
    """Descriptor for a registered content type."""

    type_id: str
    schema_ref: str
    description: str
    lifecycle_hooks: Optional[dict[str, str]] = None
    metadata: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "type_id": self.type_id,
            "schema_ref": self.schema_ref,
            "description": self.description,
            "lifecycle_hooks": self.lifecycle_hooks or {},
            "metadata": self.metadata or {},
        }


class ContentTypeRegistry:
    """Registry for content types.

    Manages the set of allowed content types and their schemas.
    Built-in types (agent, workflow, command, rule, policy, memory, fact) are pre-registered.
    Additional types can be registered dynamically.
    """

    _instance: "ContentTypeRegistry | None" = None
    _types: dict[str, ContentTypeDescriptor] = {}

    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """Initialize with built-in types."""
        self._types = {}
        self._schema_loader = ContentSchemaLoader()

        # Pre-register built-in types
        self._register_builtin_types()

    def _register_builtin_types(self):
        """Register built-in content types."""

        # 1. policy - execution policy (existing)
        self.register_type(
            type_id="policy",
            schema_ref="execution_policy.schema.json",
            description="Execution policy defining risk tolerance, resource budgets, and safety constraints",
            metadata={
                "category": "governance",
                "is_builtin": True,
                "exists_in": "policy_lineage",
            },
        )

        # 2. memory - memory item (existing)
        self.register_type(
            type_id="memory",
            schema_ref="memory_item.schema.json",
            description="Memory item storing organizational knowledge, conventions, and constraints",
            metadata={
                "category": "knowledge",
                "is_builtin": True,
                "exists_in": "memory_items",
            },
        )

        # 3. fact - fact pack (existing)
        self.register_type(
            type_id="fact",
            schema_ref="factpack.schema.json",
            description="Fact pack containing project scan results and structural information",
            metadata={
                "category": "knowledge",
                "is_builtin": True,
                "exists_in": "artifacts",
            },
        )

        # 4. agent - agent definition (available in v0.7+)
        self.register_type(
            type_id="agent",
            schema_ref="content/agent.schema.json",
            description="Agent definition representing organizational roles with responsibilities and constraints",
            metadata={
                "category": "execution",
                "is_builtin": True,
            },
        )

        # 5. workflow - workflow definition (available in v0.6+)
        self.register_type(
            type_id="workflow",
            schema_ref="content/workflow.schema.json",
            description="Workflow definition for multi-step orchestration",
            metadata={
                "category": "execution",
                "is_builtin": True,
            },
        )

        # 6. command - command definition (available in v0.8+)
        self.register_type(
            type_id="command",
            schema_ref="content/command.schema.json",
            description="Command definitions for organizational operations (v0.8)",
            metadata={
                "category": "execution",
                "is_builtin": True,
            },
        )

        # 7. rule - governance rule (available in v0.9+)
        self.register_type(
            type_id="rule",
            schema_ref="content/rule.schema.json",
            description="Governance rule for project quality and compliance (v0.9)",
            metadata={
                "category": "governance",
                "is_builtin": True,
            },
        )

    def register_type(
        self,
        type_id: str,
        schema_ref: str,
        description: str,
        lifecycle_hooks: Optional[dict[str, str]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> ContentTypeDescriptor:
        """Register a new content type.

        Args:
            type_id: Unique type identifier (lowercase, underscore separated)
            schema_ref: Path to type-specific JSON schema
            description: Human-readable description
            lifecycle_hooks: Optional lifecycle hooks (callbacks)
            metadata: Optional additional metadata

        Returns:
            ContentTypeDescriptor

        Raises:
            ValueError: If type_id already registered or invalid
        """
        # Validate type_id format
        if not type_id or not type_id.replace("_", "").isalnum() or type_id[0].isdigit():
            raise ValueError(f"Invalid type_id: {type_id} (must be lowercase alphanumeric with underscores)")

        # Check if already registered
        if type_id in self._types:
            existing = self._types[type_id]
            # Allow re-registration of built-in types during initialization
            if not (metadata and metadata.get("is_builtin")):
                raise ValueError(f"Content type already registered: {type_id}")

        # Create descriptor
        descriptor = ContentTypeDescriptor(
            type_id=type_id,
            schema_ref=schema_ref,
            description=description,
            lifecycle_hooks=lifecycle_hooks,
            metadata=metadata,
        )

        self._types[type_id] = descriptor
        return descriptor

    def get_type(self, type_id: str) -> ContentTypeDescriptor:
        """Get a registered content type.

        Args:
            type_id: Type identifier

        Returns:
            ContentTypeDescriptor

        Raises:
            KeyError: If type not registered
        """
        if type_id not in self._types:
            raise KeyError(f"Content type not registered: {type_id}")
        return self._types[type_id]

    def list_types(self, include_placeholders: bool = True) -> list[ContentTypeDescriptor]:
        """List all registered content types.

        Args:
            include_placeholders: If False, exclude placeholder types (not yet implemented)

        Returns:
            List of ContentTypeDescriptor
        """
        types = list(self._types.values())
        if not include_placeholders:
            types = [t for t in types if not (t.metadata and t.metadata.get("placeholder"))]
        return types

    def is_registered(self, type_id: str) -> bool:
        """Check if a content type is registered.

        Args:
            type_id: Type identifier

        Returns:
            True if registered, False otherwise
        """
        return type_id in self._types

    def is_placeholder(self, type_id: str) -> bool:
        """Check if a content type is a placeholder (not yet implemented).

        Args:
            type_id: Type identifier

        Returns:
            True if placeholder, False otherwise

        Raises:
            KeyError: If type not registered
        """
        descriptor = self.get_type(type_id)
        return bool(descriptor.metadata and descriptor.metadata.get("placeholder"))

    def validate_type_exists(self, type_id: str) -> bool:
        """Validate that a content type is registered and not a placeholder.

        Args:
            type_id: Type identifier

        Returns:
            True if valid and usable

        Raises:
            ValueError: If type not registered or is placeholder
        """
        if not self.is_registered(type_id):
            raise ValueError(f"Content type not registered: {type_id}")

        if self.is_placeholder(type_id):
            descriptor = self.get_type(type_id)
            available_in = descriptor.metadata.get("available_in", "future version")
            raise ValueError(
                f"Content type '{type_id}' is a placeholder (available in {available_in}). "
                f"Cannot register content of this type yet."
            )

        return True
