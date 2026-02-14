from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from octopusos.core.capability.models import RiskLevel
from octopusos.core.capability.registry import CapabilityRegistry

from .risk import RiskTier


@dataclass(frozen=True)
class Capability:
    """Execution capability view.

    Execution surfaces use stable aliases (e.g. "ssh.exec") in audit/logs and
    gate responses. The single source of truth is the v3 CapabilityRegistry.
    """

    id: str
    risk_tier: RiskTier
    requires_trust: bool = False
    requires_confirm: bool = False


def _risk_tier_from_v3(risk_level: Optional[RiskLevel]) -> RiskTier:
    if risk_level == RiskLevel.CRITICAL:
        return RiskTier.CRITICAL
    if risk_level == RiskLevel.HIGH:
        return RiskTier.HIGH
    if risk_level == RiskLevel.MEDIUM:
        return RiskTier.MEDIUM
    return RiskTier.LOW


def get_capability(capability_id: str) -> Capability:
    """Resolve an execution capability from the v3 CapabilityRegistry.

    `capability_id` here is the execution alias (e.g. "ssh.exec").
    """

    alias = str(capability_id or "").strip()
    if not alias:
        return Capability(id="", risk_tier=RiskTier.LOW)

    registry = CapabilityRegistry.get_instance()
    cap_def = registry.get_execution_definition(alias)
    if cap_def is None:
        # Unknown capabilities default to LOW so we don't accidentally over-block.
        return Capability(id=alias, risk_tier=RiskTier.LOW)

    meta = registry.get_execution_meta(alias)
    return Capability(
        id=alias,
        risk_tier=_risk_tier_from_v3(cap_def.risk_level),
        requires_trust=bool(meta.get("requires_trust", False)),
        requires_confirm=bool(meta.get("requires_confirm", False)),
    )
