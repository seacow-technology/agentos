"""Content Activation Gate - enforces activation rules and lineage constraints.

🚨 RED LINE #3: All content must have explainable lineage before activation.
"""

from typing import Optional

from agentos.core.content.registry import ContentRegistry


class LineageRequiredError(Exception):
    """RED LINE VIOLATION: Content without explainable lineage.

    All content must either:
    1. Be a root version (is_root=true, no parent)
    2. Be an evolved version (parent_version + change_reason)

    Orphan content (no parent, not root) cannot be activated.
    """

    pass


class LineageError(Exception):
    """Lineage validation error (invalid parent, missing reason, etc.)."""

    pass


class ContentActivationGate:
    """Content Activation Gate - enforces activation rules.

    This gate ensures that:
    1. Content passes schema validation
    2. Content has valid lineage (RED LINE #3)
    3. No conflicting active versions exist
    4. Frozen content cannot be modified
    """

    def __init__(self, registry: Optional[ContentRegistry] = None):
        """Initialize activation gate.

        Args:
            registry: ContentRegistry instance (creates new if None)
        """
        self.registry = registry or ContentRegistry()

    def activate(self, content_id: str, version: str) -> bool:
        """Activate content (with lineage enforcement).

        Args:
            content_id: Content ID
            version: Content version

        Returns:
            True if activated

        Raises:
            ValueError: If validation fails
            LineageRequiredError: If lineage is not explainable (RED LINE #3)
        """
        # 1. Check content exists
        content = self.registry.get(content_id, version)
        if not content:
            raise ValueError(f"Content not found: {content_id} v{version}")

        # 2. Check current status
        if content["status"] == "active":
            return True  # Already active
        if content["status"] == "frozen":
            raise ValueError(f"Cannot activate frozen content: {content_id} v{version}")
        if content["status"] == "deprecated":
            raise ValueError(f"Cannot activate deprecated content: {content_id} v{version}")

        # 3. 🚨 RED LINE #3: Lineage enforcement
        if not self._has_explainable_lineage(content):
            raise LineageRequiredError(
                f"RED LINE VIOLATION: Content {content_id} v{version} cannot be activated. "
                f"All content must have explainable lineage:\n"
                f"  - Root version: is_root=true, no parent_version\n"
                f"  - Evolved version: parent_version + change_reason (non-empty)\n"
                f"Current content: is_root={content['metadata'].get('is_root')}, "
                f"parent_version={content['metadata'].get('parent_version')}, "
                f"change_reason={bool(content['metadata'].get('change_reason'))}"
            )

        # 4. Check for conflicting active versions
        self._check_no_active_conflict(content_id, version)

        # 5. Activate
        self.registry.update_status(content_id, version, "active")

        return True

    def deactivate(self, content_id: str, version: str) -> bool:
        """Deactivate content (mark as deprecated).

        Args:
            content_id: Content ID
            version: Content version

        Returns:
            True if deactivated
        """
        content = self.registry.get(content_id, version)
        if not content:
            raise ValueError(f"Content not found: {content_id} v{version}")

        if content["status"] == "frozen":
            raise ValueError(f"Cannot deactivate frozen content: {content_id} v{version}")

        self.registry.update_status(content_id, version, "deprecated")
        return True

    def freeze(self, content_id: str, version: str) -> bool:
        """Freeze content (make immutable).

        Args:
            content_id: Content ID
            version: Content version

        Returns:
            True if frozen
        """
        content = self.registry.get(content_id, version)
        if not content:
            raise ValueError(f"Content not found: {content_id} v{version}")

        self.registry.update_status(content_id, version, "frozen")
        return True

    def unfreeze(self, content_id: str, version: str) -> bool:
        """Unfreeze content (allow modifications).

        Args:
            content_id: Content ID
            version: Content version

        Returns:
            True if unfrozen
        """
        content = self.registry.get(content_id, version)
        if not content:
            raise ValueError(f"Content not found: {content_id} v{version}")

        if content["status"] != "frozen":
            raise ValueError(f"Content is not frozen: {content_id} v{version}")

        # Revert to draft status
        self.registry.update_status(content_id, version, "draft")
        return True

    def _has_explainable_lineage(self, content: dict) -> bool:
        """Check if content has explainable lineage (RED LINE #3).

        Args:
            content: Content dict

        Returns:
            True if lineage is explainable

        Raises:
            LineageError: If lineage is invalid (malformed)
        """
        metadata = content.get("metadata", {})
        is_root = metadata.get("is_root", False)
        parent_version = metadata.get("parent_version")
        change_reason = metadata.get("change_reason", "").strip()

        # Case 1: Root version
        if is_root:
            if parent_version is not None:
                raise LineageError(
                    f"Root content cannot have parent_version: {content['id']} v{content['version']}"
                )
            return True

        # Case 2: Evolved version
        if not parent_version:
            return False  # No parent and not root → orphan → reject

        if not change_reason:
            raise LineageError(
                f"Content {content['id']} v{content['version']} has parent {parent_version} "
                f"but missing change_reason. All evolutions must explain WHY."
            )

        # Case 3: Validate parent exists
        parent_content = self.registry.get(content["id"], parent_version)
        if not parent_content:
            raise LineageError(
                f"Parent version not found: {content['id']} v{parent_version}. "
                f"Cannot activate content with missing parent."
            )

        return True

    def _check_no_active_conflict(self, content_id: str, version: str):
        """Check that no other version of this content is active.

        Args:
            content_id: Content ID
            version: Content version to activate

        Raises:
            ValueError: If another version is already active
        """
        all_versions = self.registry.list(limit=1000)
        active_versions = [
            c for c in all_versions if c["id"] == content_id and c["status"] == "active"
        ]

        if active_versions:
            conflicting = active_versions[0]
            if conflicting["version"] != version:
                raise ValueError(
                    f"Cannot activate {content_id} v{version}: "
                    f"another version (v{conflicting['version']}) is already active. "
                    f"Deactivate it first or use supersede operation."
                )
