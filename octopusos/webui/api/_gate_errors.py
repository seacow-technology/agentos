"""Gate error helpers.

We use 409/403 responses as "gates" for governance UX:
- trust gate: NEEDS_TRUST / FINGERPRINT_MISMATCH
- confirm gate: CONFIRM_REQUIRED (+ confirm_token)
- policy gate: BLOCKED_BY_POLICY / ADMIN_TOKEN_REQUIRED / etc.

This module provides a stable, structured HTTPException.detail shape while
remaining backward compatible with existing fields.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


def gate_detail(
    *,
    error_code: str,
    gate: str,
    message: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    confirm_token: Optional[str] = None,
    capability_id: Optional[str] = None,
    risk_tier: Optional[str] = None,
    **extra: Any,
) -> Dict[str, Any]:
    # Keep existing ad-hoc fields (host/port/fingerprint/etc) at top level for
    # backward compatibility, while adding a stable `gate/context` envelope.
    detail: Dict[str, Any] = {
        "error_code": error_code,
        "gate": gate,
    }
    if message:
        detail["message"] = message
    if confirm_token:
        detail["confirm_token"] = confirm_token
    if capability_id:
        detail["capability_id"] = capability_id
    if risk_tier:
        detail["risk_tier"] = risk_tier
    if context:
        detail["context"] = context
        for k, v in context.items():
            # Do not overwrite explicitly provided top-level keys.
            if k not in detail:
                detail[k] = v
    for k, v in extra.items():
        if v is not None and k not in detail:
            detail[k] = v
    return detail

