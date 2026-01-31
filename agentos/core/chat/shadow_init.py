"""
Shadow Classifier Initialization

This module provides initialization functions for setting up shadow classifiers
at system startup. It registers all available shadow classifier versions and
configures which ones are active for parallel evaluation.
"""

import logging
from typing import Dict, Any, Optional

from agentos.core.chat.shadow_classifier import (
    ShadowClassifierV2ExpandKeywords,
    ShadowClassifierV2AdjustThreshold,
)
from agentos.core.chat.shadow_registry import get_shadow_registry

logger = logging.getLogger(__name__)


def initialize_shadow_classifiers(config: Optional[Dict[str, Any]] = None) -> None:
    """
    Initialize all shadow classifiers.

    This function:
    1. Creates instances of all shadow classifier versions
    2. Registers them with the global registry
    3. Activates configured versions for parallel evaluation

    Args:
        config: Optional configuration dictionary
            - enabled: bool, whether shadow evaluation is enabled
            - active_versions: List[str], versions to activate
            - max_concurrent_shadows: int, max shadows to run in parallel

    Example config:
        {
            "enabled": True,
            "active_versions": ["v2-shadow-expand-keywords"],
            "max_concurrent_shadows": 2
        }
    """
    if config is None:
        config = {}

    # Check if shadow evaluation is enabled
    if not config.get("enabled", True):
        logger.info("Shadow classifier evaluation is disabled")
        return

    registry = get_shadow_registry()

    # Register shadow v2.a (expanded keywords)
    try:
        shadow_v2a = ShadowClassifierV2ExpandKeywords()
        registry.register(shadow_v2a)
        logger.info(
            f"Registered shadow classifier: {shadow_v2a.version.version_id}"
        )
    except Exception as e:
        logger.error(f"Failed to register shadow v2.a: {e}")

    # Register shadow v2.b (adjusted thresholds)
    try:
        shadow_v2b = ShadowClassifierV2AdjustThreshold()
        registry.register(shadow_v2b)
        logger.info(
            f"Registered shadow classifier: {shadow_v2b.version.version_id}"
        )
    except Exception as e:
        logger.error(f"Failed to register shadow v2.b: {e}")

    # Activate configured versions
    active_versions = config.get("active_versions", ["v2-shadow-expand-keywords"])
    for version_id in active_versions:
        try:
            registry.activate(version_id)
            logger.info(f"Activated shadow classifier: {version_id}")
        except ValueError as e:
            logger.warning(f"Failed to activate {version_id}: {e}")

    # Log summary
    total_registered = registry.count_total()
    total_active = registry.count_active()
    logger.info(
        f"Shadow classifier initialization complete: "
        f"{total_active}/{total_registered} active"
    )


def get_shadow_config_defaults() -> Dict[str, Any]:
    """
    Get default shadow classifier configuration.

    Returns:
        Default configuration dictionary
    """
    return {
        "enabled": True,
        "active_versions": [
            "v2-shadow-expand-keywords"  # Most conservative shadow
        ],
        "max_concurrent_shadows": 2,
        "evaluation_timeout_ms": 500,
    }


def reconfigure_shadows(config: Dict[str, Any]) -> None:
    """
    Reconfigure shadow classifiers at runtime.

    This function allows dynamic reconfiguration without restarting
    the system. It deactivates all current shadows and activates
    the newly configured ones.

    Args:
        config: New configuration dictionary
    """
    registry = get_shadow_registry()

    # Deactivate all current shadows
    for version_id in registry.list_all_versions():
        if registry.is_active(version_id):
            registry.deactivate(version_id)

    # Activate new configuration
    active_versions = config.get("active_versions", [])
    for version_id in active_versions:
        try:
            registry.activate(version_id)
            logger.info(f"Reconfigured: Activated shadow {version_id}")
        except ValueError as e:
            logger.warning(f"Reconfiguration warning: {e}")

    logger.info(
        f"Shadow classifier reconfiguration complete: "
        f"{registry.count_active()} active"
    )
