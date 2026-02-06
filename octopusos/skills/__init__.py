"""SkillOS: Skill Management System for AgentOS.

This module provides the core infrastructure for managing skills:
- Skill manifest parsing and validation
- Skill registry (database-backed storage)
- Skill lifecycle management

Design Principles:
1. Independent database: ~/.agentos/store/skill/db.sqlite
2. Strict validation: Structural, type, and semantic checks
3. Import ≠ Enable: Imported skills default to imported_disabled status
"""

from agentos.skills.manifest import (
    SkillManifest,
    load_manifest,
    validate_manifest,
    normalize_manifest,
)
from agentos.skills.registry import SkillRegistry

__all__ = [
    "SkillManifest",
    "load_manifest",
    "validate_manifest",
    "normalize_manifest",
    "SkillRegistry",
]
