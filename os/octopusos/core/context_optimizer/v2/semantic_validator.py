from __future__ import annotations

from typing import Any, Dict, List, Tuple


def validate_context_pack(pack: Dict[str, Any]) -> List[str]:
    """
    Semantic consistency validator (redline checks).
    Returns list of human-readable errors; empty means pass.
    """
    errors: List[str] = []

    tier1 = pack.get("tier_1_facts") or []
    if not isinstance(tier1, list):
        errors.append("tier_1_facts must be a list")
        return errors

    for f in tier1:
        if not isinstance(f, dict):
            errors.append("fact must be an object")
            continue
        fid = str(f.get("id") or "<missing>")
        severity = str(f.get("severity") or "")
        value_score = f.get("value_score")
        signature = str(f.get("signature") or "")
        data = f.get("data") or {}

        if severity == "error":
            try:
                if float(value_score) < 50:
                    errors.append(f"{fid}: severity=error but value_score < 50")
            except Exception:
                errors.append(f"{fid}: invalid value_score")

        affected_paths = []
        if isinstance(data, dict):
            affected_paths = data.get("affected_paths") or []
        if affected_paths and not signature.strip():
            errors.append(f"{fid}: affected_paths non-empty but signature empty")

        # CLI-specific redlines when fields exist.
        if isinstance(data, dict):
            verdict = data.get("verdict")
            primary_failures = data.get("primary_failures")
            exit_code = data.get("exit_code")

            if verdict == "pass" and isinstance(primary_failures, list) and len(primary_failures) > 0:
                errors.append(f"{fid}: verdict=pass but primary_failures not empty")

            if exit_code not in (0, None) and verdict != "fail":
                errors.append(f"{fid}: exit_code!=0 but verdict!=fail")

    return errors


def assert_valid(pack: Dict[str, Any]) -> None:
    errs = validate_context_pack(pack)
    if errs:
        raise AssertionError("Semantic validation failed: " + "; ".join(errs[:8]))

