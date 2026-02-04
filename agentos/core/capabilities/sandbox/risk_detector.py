"""Risk Level Detection for Extensions

Phase D1: Determine risk level for extensions to decide sandbox requirements.
"""

import logging
from typing import Optional

from agentos.core.capabilities.capability_models import RiskLevel

logger = logging.getLogger(__name__)


def get_extension_risk_level(extension_id: str) -> RiskLevel:
    """
    Get risk level for an extension

    This determines whether an extension requires sandbox execution.

    Risk Level Logic:
    1. Check extension manifest for declared risk_level
    2. Check trust tier from registry
    3. Use default based on extension type

    Args:
        extension_id: Extension identifier

    Returns:
        RiskLevel: Risk level for the extension

    Examples:
        >>> risk = get_extension_risk_level("tools.postman")
        >>> if risk == RiskLevel.HIGH:
        ...     print("Requires sandbox")

    Note:
        For MVP (Phase D1), we use a simple heuristic:
        - Extensions with "untrusted" in name → HIGH
        - Extensions with "local" or "builtin" → LOW
        - Default → MED

        Future phases (D3) will integrate with Trust Tier system.
    """
    # MVP Phase D1: Use heuristic-based risk detection
    # Future phases (D3) will integrate with Trust Tier system

    # Check for untrusted patterns (HIGH risk)
    if "untrusted" in extension_id.lower():
        logger.debug(f"[Risk] {extension_id} → HIGH (untrusted)")
        return RiskLevel.HIGH

    # Check for low-risk patterns (builtin/local)
    low_risk_patterns = ["builtin", "local"]
    for pattern in low_risk_patterns:
        if pattern in extension_id.lower():
            logger.debug(f"[Risk] {extension_id} → LOW (pattern: {pattern})")
            return RiskLevel.LOW

    # Check for high-risk patterns
    high_risk_patterns = ["remote", "cloud", "external", "third-party"]
    for pattern in high_risk_patterns:
        if pattern in extension_id.lower():
            logger.debug(f"[Risk] {extension_id} → HIGH (pattern: {pattern})")
            return RiskLevel.HIGH

    # Default to MED (conservative)
    logger.debug(f"[Risk] {extension_id} → MED (default)")
    return RiskLevel.MED


def requires_sandbox(extension_id: str) -> bool:
    """
    Determine if extension requires sandbox execution

    Red Line: HIGH and CRITICAL risk levels MUST use sandbox

    Args:
        extension_id: Extension identifier

    Returns:
        bool: True if sandbox is required

    Examples:
        >>> if requires_sandbox("tools.untrusted"):
        ...     print("Must execute in sandbox")
    """
    risk_level = get_extension_risk_level(extension_id)
    requires = risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)

    if requires:
        logger.info(
            f"[Sandbox] {extension_id} requires sandbox (risk={risk_level.value})"
        )

    return requires
