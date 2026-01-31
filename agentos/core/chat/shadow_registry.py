"""
Shadow Classifier Registry

This module provides a centralized registry for managing shadow classifier versions.
The registry handles registration, activation, deactivation, and retrieval of
shadow classifiers for parallel evaluation.

Thread-Safety: The registry uses asyncio locks for concurrent access safety.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from agentos.core.chat.shadow_classifier import BaseShadowClassifier

logger = logging.getLogger(__name__)


class ShadowClassifierRegistry:
    """
    Registry for managing shadow classifier versions.

    Responsibilities:
    - Register and unregister shadow classifiers
    - Activate/deactivate classifiers for parallel evaluation
    - Version validation and metadata tracking
    - Thread-safe concurrent access

    Usage:
        registry = ShadowClassifierRegistry()
        registry.register(shadow_classifier_v2a)
        registry.activate("v2-shadow-expand-keywords")
        active_shadows = registry.get_active_shadows()
    """

    def __init__(self):
        """Initialize shadow classifier registry."""
        self._registry: Dict[str, BaseShadowClassifier] = {}
        self._active_shadows: List[str] = []
        self._lock = asyncio.Lock()
        logger.info("Initialized ShadowClassifierRegistry")

    def register(self, classifier: BaseShadowClassifier) -> None:
        """
        Register a shadow classifier.

        Args:
            classifier: Shadow classifier to register

        Raises:
            ValueError: If version already registered or invalid version type
        """
        version_id = classifier.version.version_id

        # Validate version not already registered
        if version_id in self._registry:
            raise ValueError(
                f"Shadow classifier {version_id} already registered"
            )

        # Validate version type is "shadow"
        if classifier.version.version_type != "shadow":
            raise ValueError(
                f"Only shadow classifiers can be registered, got version_type='{classifier.version.version_type}'"
            )

        # Register classifier
        self._registry[version_id] = classifier
        logger.info(
            f"Registered shadow classifier: {version_id} - {classifier.version.change_description}"
        )

    def unregister(self, version_id: str) -> None:
        """
        Unregister a shadow classifier.

        Args:
            version_id: Version ID to unregister

        Raises:
            ValueError: If version not found
        """
        if version_id not in self._registry:
            raise ValueError(f"Shadow classifier {version_id} not found")

        # Deactivate if currently active
        if version_id in self._active_shadows:
            self.deactivate(version_id)

        # Remove from registry
        del self._registry[version_id]
        logger.info(f"Unregistered shadow classifier: {version_id}")

    def activate(self, version_id: str) -> None:
        """
        Activate a shadow classifier for parallel evaluation.

        Args:
            version_id: Version ID to activate

        Raises:
            ValueError: If version not found
        """
        if version_id not in self._registry:
            raise ValueError(f"Shadow classifier {version_id} not found")

        if version_id not in self._active_shadows:
            self._active_shadows.append(version_id)
            logger.info(
                f"Activated shadow classifier: {version_id} "
                f"(total active: {len(self._active_shadows)})"
            )
        else:
            logger.debug(f"Shadow classifier {version_id} already active")

    def deactivate(self, version_id: str) -> None:
        """
        Deactivate a shadow classifier.

        Args:
            version_id: Version ID to deactivate
        """
        if version_id in self._active_shadows:
            self._active_shadows.remove(version_id)
            logger.info(
                f"Deactivated shadow classifier: {version_id} "
                f"(total active: {len(self._active_shadows)})"
            )
        else:
            logger.debug(f"Shadow classifier {version_id} not active")

    def get_active_shadows(self) -> List[BaseShadowClassifier]:
        """
        Get all currently active shadow classifiers.

        Returns:
            List of active shadow classifier instances
        """
        active_classifiers = [
            self._registry[vid]
            for vid in self._active_shadows
            if vid in self._registry
        ]
        return active_classifiers

    def get_classifier(self, version_id: str) -> Optional[BaseShadowClassifier]:
        """
        Get a specific shadow classifier by version ID.

        Args:
            version_id: Version ID to retrieve

        Returns:
            Shadow classifier instance or None if not found
        """
        return self._registry.get(version_id)

    def list_all_versions(self) -> List[str]:
        """
        List all registered shadow classifier version IDs.

        Returns:
            List of version IDs
        """
        return list(self._registry.keys())

    def get_version_info(self, version_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a shadow classifier version.

        Args:
            version_id: Version ID to query

        Returns:
            Dictionary with version metadata or None if not found
        """
        classifier = self._registry.get(version_id)
        if not classifier:
            return None

        return {
            "version_id": version_id,
            "version_type": classifier.version.version_type,
            "change_description": classifier.version.change_description,
            "created_at": classifier.version.created_at.isoformat(),
            "is_active": version_id in self._active_shadows,
            "detailed_changes": classifier.get_change_description(),
        }

    def get_all_version_info(self) -> List[Dict[str, Any]]:
        """
        Get information about all registered shadow classifiers.

        Returns:
            List of version info dictionaries
        """
        return [
            self.get_version_info(version_id)
            for version_id in self._registry.keys()
        ]

    def is_active(self, version_id: str) -> bool:
        """
        Check if a shadow classifier is currently active.

        Args:
            version_id: Version ID to check

        Returns:
            True if active, False otherwise
        """
        return version_id in self._active_shadows

    def count_active(self) -> int:
        """
        Count number of active shadow classifiers.

        Returns:
            Number of active shadows
        """
        return len(self._active_shadows)

    def count_total(self) -> int:
        """
        Count total number of registered shadow classifiers.

        Returns:
            Total number of registered shadows
        """
        return len(self._registry)

    async def activate_batch(self, version_ids: List[str]) -> Dict[str, bool]:
        """
        Activate multiple shadow classifiers at once.

        Args:
            version_ids: List of version IDs to activate

        Returns:
            Dictionary mapping version_id to success status
        """
        async with self._lock:
            results = {}
            for version_id in version_ids:
                try:
                    self.activate(version_id)
                    results[version_id] = True
                except ValueError as e:
                    logger.warning(f"Failed to activate {version_id}: {e}")
                    results[version_id] = False
            return results

    async def deactivate_all(self) -> int:
        """
        Deactivate all shadow classifiers.

        Returns:
            Number of classifiers deactivated
        """
        async with self._lock:
            count = len(self._active_shadows)
            self._active_shadows.clear()
            logger.info(f"Deactivated all {count} shadow classifiers")
            return count

    def clear_registry(self) -> None:
        """
        Clear the entire registry (for testing/reset).

        Warning: This removes all registered shadow classifiers.
        """
        self._active_shadows.clear()
        self._registry.clear()
        logger.warning("Cleared entire shadow classifier registry")


# Global singleton registry
_shadow_registry: Optional[ShadowClassifierRegistry] = None


def get_shadow_registry() -> ShadowClassifierRegistry:
    """
    Get the global shadow classifier registry singleton.

    Returns:
        Global ShadowClassifierRegistry instance
    """
    global _shadow_registry
    if _shadow_registry is None:
        _shadow_registry = ShadowClassifierRegistry()
    return _shadow_registry


def reset_shadow_registry() -> None:
    """
    Reset the global shadow registry (for testing).

    Warning: This destroys the current registry and creates a new one.
    """
    global _shadow_registry
    _shadow_registry = None
    logger.info("Reset global shadow classifier registry")
