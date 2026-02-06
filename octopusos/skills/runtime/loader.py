"""Skill Loader - Loads enabled skills into memory.

This module provides the SkillLoader class which:
1. Loads all enabled skills from the registry
2. Maintains an in-memory cache for fast lookup
3. Provides skill metadata access

Design Principles:
- Load on initialization: All enabled skills loaded at startup
- Memory-efficient: Only loads manifests, not Python modules
- Fast lookup: O(1) skill_id → skill metadata

Security Notes:
- Only loads skills with status='enabled'
- Does NOT execute any skill code during loading
- Manifests are already validated by registry

Usage:
    >>> registry = SkillRegistry()
    >>> loader = SkillLoader(registry)
    >>> enabled_skills = loader.load_enabled_skills()
    >>> skill = loader.get_skill('test.skill')
"""

from typing import List, Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)


class SkillLoader:
    """Loads and manages enabled skills.

    The loader acts as a bridge between the registry (persistent storage)
    and the invoker (execution engine). It maintains an in-memory cache
    of enabled skills for fast access.

    Attributes:
        registry: SkillRegistry instance for database access
        _loaded_skills: Dict mapping skill_id to skill metadata
    """

    def __init__(self, registry):
        """Initialize loader.

        Args:
            registry: SkillRegistry instance
        """
        self.registry = registry
        self._loaded_skills: Dict[str, Dict[str, Any]] = {}

    def load_enabled_skills(self) -> List[Dict[str, Any]]:
        """Load all enabled skills from registry.

        This method queries the registry for all skills with status='enabled'
        and loads them into memory for fast access. It does NOT import or
        execute any Python code - only manifest metadata is loaded.

        Returns:
            List of skill dictionaries, each containing:
            - skill_id: Unique identifier
            - version: Semantic version
            - status: Should be 'enabled'
            - manifest_json: Parsed manifest dictionary
            - repo_hash: Git commit hash (if from GitHub)
            - imported_at: Timestamp of import
            - enabled_at: Timestamp of enable

        Security:
        - Only loads enabled skills (prevents accidental execution)
        - No code execution during load
        - Manifests already validated by registry

        Example:
            >>> loader = SkillLoader(registry)
            >>> skills = loader.load_enabled_skills()
            >>> print(f"Loaded {len(skills)} enabled skills")
        """
        try:
            skills = self.registry.list_skills(status='enabled')
            self._loaded_skills = {s['skill_id']: s for s in skills}

            logger.info(
                f"Loaded {len(skills)} enabled skills",
                extra={
                    "skill_count": len(skills),
                    "skill_ids": [s['skill_id'] for s in skills],
                }
            )

            return skills

        except Exception as e:
            logger.error(
                f"Failed to load enabled skills: {e}",
                exc_info=True,
                extra={"error": str(e)}
            )
            # Return empty list on error (fail-safe)
            self._loaded_skills = {}
            return []

    def get_skill(self, skill_id: str) -> Optional[Dict[str, Any]]:
        """Get loaded skill by ID.

        Args:
            skill_id: Skill identifier

        Returns:
            Skill dictionary if loaded, None otherwise

        Note:
            This method only returns skills that have been loaded via
            load_enabled_skills(). Skills that are imported but not
            enabled will NOT be returned.

        Example:
            >>> skill = loader.get_skill('test.skill')
            >>> if skill:
            ...     print(f"Found skill: {skill['skill_id']}")
        """
        return self._loaded_skills.get(skill_id)

    def is_enabled(self, skill_id: str) -> bool:
        """Check if skill is loaded and enabled.

        Args:
            skill_id: Skill identifier

        Returns:
            bool: True if skill is loaded (enabled), False otherwise

        Example:
            >>> if loader.is_enabled('test.skill'):
            ...     print("Skill is ready to invoke")
        """
        return skill_id in self._loaded_skills

    def reload(self) -> int:
        """Reload enabled skills from registry.

        This method refreshes the in-memory cache by re-querying the
        registry. Useful after skills are enabled/disabled.

        Returns:
            int: Number of skills loaded

        Example:
            >>> # Enable a skill
            >>> registry.update_status('test.skill', 'enabled')
            >>> # Reload to pick up changes
            >>> count = loader.reload()
            >>> print(f"Reloaded {count} skills")
        """
        skills = self.load_enabled_skills()
        return len(skills)

    def get_all_loaded_skills(self) -> Dict[str, Dict[str, Any]]:
        """Get all loaded skills.

        Returns:
            Dict mapping skill_id to skill metadata

        Example:
            >>> skills = loader.get_all_loaded_skills()
            >>> for skill_id, skill in skills.items():
            ...     print(f"- {skill_id} v{skill['version']}")
        """
        return self._loaded_skills.copy()

    def count(self) -> int:
        """Get count of loaded skills.

        Returns:
            int: Number of loaded skills
        """
        return len(self._loaded_skills)


__all__ = ["SkillLoader"]
