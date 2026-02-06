"""Content Lifecycle Service - Content management with state machine enforcement

This service provides content lifecycle management:
1. State transition management (draft -> active -> deprecated/frozen)
2. Version activation with automatic deprecation
3. Integration with ContentRepo for data access

State transitions:
- draft -> active (via activate)
- active -> deprecated (via deprecate or when new version activated)
- active/deprecated -> frozen (via freeze)
- frozen: immutable (no further transitions)

Created for Agent-DB-Content integration
"""

import json
import logging
from typing import Optional, List, Tuple

from agentos.store.content_store import ContentRepo, ContentItem

logger = logging.getLogger(__name__)


class ContentLifecycleError(Exception):
    """Base error for content lifecycle operations"""
    pass


class ContentNotFoundError(ContentLifecycleError):
    """Content item not found"""
    pass


class ContentStateError(ContentLifecycleError):
    """Invalid state transition"""
    pass


class ContentLifecycleService:
    """Content lifecycle management with state machine enforcement

    State transitions:
    - draft -> active (via activate)
    - active -> deprecated (via deprecate or when new version activated)
    - active/deprecated -> frozen (via freeze)
    - frozen: immutable (no further transitions)
    """

    def __init__(self, repo: ContentRepo):
        """Initialize service

        Args:
            repo: ContentRepo instance
        """
        self.repo = repo

    def list_items(
        self,
        content_type: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> Tuple[List[ContentItem], int]:
        """List content items with filtering

        Args:
            content_type: Filter by content type
            status: Filter by status
            search: Search in name/tags
            limit: Page size
            offset: Page offset

        Returns:
            Tuple of (items, total_count)
        """
        return self.repo.list(
            content_type=content_type,
            status=status,
            q=search,
            limit=limit,
            offset=offset
        )

    def get_item(self, item_id: str) -> ContentItem:
        """Get single content item

        Args:
            item_id: Content ID

        Returns:
            ContentItem

        Raises:
            ContentNotFoundError: Item not found
        """
        item = self.repo.get(item_id)
        if not item:
            raise ContentNotFoundError(f"Content item {item_id} not found")
        return item

    def register(
        self,
        content_type: str,
        name: str,
        version: str,
        source_uri: Optional[str] = None,
        metadata: Optional[dict] = None,
        release_notes: Optional[str] = None
    ) -> ContentItem:
        """Register new content (initial status: draft)

        Args:
            content_type: Content type (agent/workflow/skill/tool)
            name: Content name
            version: Initial version number
            source_uri: Source URI or hash
            metadata: Additional metadata
            release_notes: Release notes

        Returns:
            Created ContentItem
        """
        import uuid

        item = ContentItem(
            id=str(uuid.uuid4()),
            content_type=content_type,
            name=name,
            version=version,
            status="draft",
            source_uri=source_uri,
            metadata_json=json.dumps(metadata) if metadata else None,
            release_notes=release_notes
        )

        return self.repo.create(item)

    def activate(self, item_id: str) -> ContentItem:
        """Activate content version (draft -> active)

        - Automatically deprecates previous active version of same (type, name)
        - Only draft items can be activated

        Args:
            item_id: Content ID

        Returns:
            Updated ContentItem

        Raises:
            ContentNotFoundError: Item not found
            ContentStateError: Item not in draft state or is frozen
        """
        item = self.get_item(item_id)

        if item.status == "frozen":
            raise ContentStateError(f"Cannot activate frozen content {item_id}")

        if item.status != "draft":
            raise ContentStateError(
                f"Can only activate draft content. Current status: {item.status}"
            )

        # Use repo's set_active (handles transaction)
        return self.repo.set_active(item.content_type, item.name, item.version)

    def deprecate(self, item_id: str) -> ContentItem:
        """Deprecate content version (active -> deprecated)

        Args:
            item_id: Content ID

        Returns:
            Updated ContentItem

        Raises:
            ContentNotFoundError: Item not found
            ContentStateError: Item not in active state or is frozen
        """
        item = self.get_item(item_id)

        if item.status == "frozen":
            raise ContentStateError(f"Cannot deprecate frozen content {item_id}")

        if item.status != "active":
            raise ContentStateError(
                f"Can only deprecate active content. Current status: {item.status}"
            )

        return self.repo.update_status(item_id, "deprecated")

    def freeze(self, item_id: str) -> ContentItem:
        """Freeze content version (any -> frozen, immutable)

        Args:
            item_id: Content ID

        Returns:
            Updated ContentItem

        Raises:
            ContentNotFoundError: Item not found
            ContentStateError: Already frozen
        """
        item = self.get_item(item_id)

        if item.status == "frozen":
            raise ContentStateError(f"Content {item_id} is already frozen")

        return self.repo.update_status(item_id, "frozen")

