from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple

from ..metrics import count_tokens


_SEVERITY_WEIGHT = {"error": 100.0, "warn": 60.0, "info": 20.0}


@dataclass(frozen=True)
class ItemScore:
    item_id: str
    value_score: float
    estimated_tokens: int
    ratio: float
    reasons: List[str]


def value_score(
    *,
    severity: str,
    recency_weight: float,
    uniqueness_weight: float,
    dependency_weight: float,
    actionability_weight: float,
) -> float:
    sev = _SEVERITY_WEIGHT.get(severity, 20.0)
    score = (
        0.35 * sev
        + 0.20 * float(recency_weight)
        + 0.20 * float(uniqueness_weight)
        + 0.15 * float(dependency_weight)
        + 0.10 * float(actionability_weight)
    )
    return max(0.0, min(100.0, score))


def allocate_budget_greedy(
    *,
    token_budget_total: int = 4000,
    reserve_ratio: float = 0.20,
    fixed_overhead: int = 0,
    tier0_text: str,
    facts: List[Dict[str, Any]],
    model: str = "gpt-4o",
) -> Dict[str, Any]:
    """
    Budget allocator (v2):
    - Always include tier0.
    - Select tier1 facts by (value_score / estimated_tokens) greedy.
    - Keep under base budget = total * (1 - reserve_ratio) - overhead.
    - Everything else => dropped with reason.
    """
    t_total = int(token_budget_total)
    overhead = max(0, int(fixed_overhead))
    base_limit = int(t_total * (1.0 - float(reserve_ratio))) - overhead
    base_limit = max(0, base_limit)
    expand_reserve = t_total - overhead - base_limit
    expand_reserve = max(0, expand_reserve)

    tier0_tokens = count_tokens(tier0_text or "", model=model)
    used = tier0_tokens

    scored: List[Tuple[float, int, Dict[str, Any], ItemScore]] = []
    for f in facts:
        fid = str(f.get("id") or "")
        severity = str(f.get("severity") or "info")
        vs = float(f.get("value_score") or 0.0)
        text = f.get("inject_text")
        if not isinstance(text, str) or not text.strip():
            text = _fact_to_inject_text(f)
        est = count_tokens(text, model=model)
        ratio = (vs / max(1, est))
        reasons = []
        if est == 0:
            reasons.append("zero_tokens")
        scored.append((ratio, est, f, ItemScore(item_id=fid, value_score=vs, estimated_tokens=est, ratio=ratio, reasons=reasons)))

    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)

    selected: List[Dict[str, Any]] = []
    dropped: List[Dict[str, Any]] = []
    dropped_compact: List[Dict[str, Any]] = []

    # tier0 may already exceed base_limit; still keep it (design requirement).
    for ratio, est, f, s in scored:
        if used + est <= base_limit:
            selected.append({**f, "estimated_tokens": est, "score": asdict(s)})
            used += est
        else:
            item = {**f, "estimated_tokens": est, "drop_reason": "over_budget", "score": asdict(s)}
            dropped.append(item)
            dropped_compact.append(
                {
                    "id": str(f.get("id") or ""),
                    "reason": "over_budget",
                    "estimated_tokens": int(est),
                    "value_score": float(f.get("value_score") or 0.0),
                    "signature": str(f.get("signature") or ""),
                }
            )

    return {
        "token_budget_total": t_total,
        "fixed_overhead": overhead,
        "base_limit": base_limit,
        "expand_reserve": expand_reserve,
        "tier0_tokens": tier0_tokens,
        "base_pack_tokens": used,
        "selected_items": selected,
        "dropped_items": dropped,
        "dropped_items_compact": dropped_compact,
        "generated_at_ms": int(time.time() * 1000),
        "model": model,
    }


def _fact_to_inject_text(f: Dict[str, Any]) -> str:
    # Deterministic, minimal, and still auditable.
    ch = str(f.get("channel") or "?")
    sev = str(f.get("severity") or "?")
    sig = str(f.get("signature") or "")
    data = f.get("data") or {}
    return f"[{ch}/{sev}] {sig}\n{data}\n"
