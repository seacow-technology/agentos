from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import HTTPException

from octopusos.webui.api._gate_errors import gate_detail

from .capability import Capability


def trust_gate(
    *,
    capability: Capability,
    error_code: str,
    message: str,
    context: Dict[str, Any],
) -> None:
    raise HTTPException(
        status_code=409,
        detail=gate_detail(
            error_code=error_code,
            gate="trust",
            message=message,
            context=context,
            capability_id=capability.id,
            risk_tier=capability.risk_tier.value,
        ),
    )


def confirm_gate(
    *,
    capability: Capability,
    error_code: str = "CONFIRM_REQUIRED",
    message: str,
    confirm_token: str,
    context: Optional[Dict[str, Any]] = None,
) -> None:
    raise HTTPException(
        status_code=409,
        detail=gate_detail(
            error_code=error_code,
            gate="confirm",
            message=message,
            confirm_token=confirm_token,
            context=context or {},
            capability_id=capability.id,
            risk_tier=capability.risk_tier.value,
        ),
    )


def policy_gate(
    *,
    capability: Capability,
    error_code: str,
    message: str,
    context: Optional[Dict[str, Any]] = None,
) -> None:
    raise HTTPException(
        status_code=409,
        detail=gate_detail(
            error_code=error_code,
            gate="policy",
            message=message,
            context=context or {},
            capability_id=capability.id,
            risk_tier=capability.risk_tier.value,
        ),
    )

