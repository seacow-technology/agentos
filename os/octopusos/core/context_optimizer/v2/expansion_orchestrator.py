from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from ..metrics import count_tokens
from .pointer_resolver import resolve_pointer


def orchestrate_expansion(
    *,
    expansion_request: Dict[str, Any],
    pointers_by_id: Dict[str, Dict[str, Any]],
    repo_root: Path,
    model: str = "gpt-4o",
    token_budget_total: int = 4000,
    reserve_ratio: float = 0.20,
    fixed_overhead: int = 0,
    base_pack_tokens: int,
    per_request_max_tokens: int = 350,
    max_requests: int = 3,
    seen_pointer_ids: Optional[Set[str]] = None,
    seen_signatures: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    """
    Expansion orchestrator (governed):
    - only accepts structured JSON request
    - allowlist enforced by pointer_resolver
    - budget-first: expansion can only spend expand_reserve
    - dedupe by pointer_id and signature (per run)
    """
    need = bool(expansion_request.get("need_more_detail"))
    reqs = expansion_request.get("requests") if isinstance(expansion_request.get("requests"), list) else []
    reqs = reqs[: int(max_requests)]

    t_total = int(token_budget_total)
    overhead = max(0, int(fixed_overhead))
    base_limit = int(t_total * (1.0 - float(reserve_ratio))) - overhead
    base_limit = max(0, base_limit)
    expand_reserve = max(0, (t_total - overhead - base_limit))

    already_p = set(seen_pointer_ids or set())
    already_s = set(seen_signatures or set())

    used = 0
    expanded: List[Dict[str, Any]] = []
    dropped: List[Dict[str, Any]] = []

    if not need:
        return {
            "expanded": [],
            "dropped": [],
            "budget": {
                "total": t_total,
                "base_limit": base_limit,
                "expand_reserve": expand_reserve,
                "requested": 0,
                "used": 0,
                "remaining": expand_reserve,
            },
            "generated_at_ms": int(time.time() * 1000),
        }

    for item in reqs:
        if not isinstance(item, dict):
            continue
        pid = str(item.get("pointer_id") or "").strip()
        reason = str(item.get("reason") or "").strip()
        max_t = int(item.get("max_tokens") or per_request_max_tokens)
        max_t = min(int(per_request_max_tokens), max(1, max_t))
        if not pid or pid not in pointers_by_id:
            dropped.append({"pointer_id": pid, "reason": reason, "drop_reason": "unknown_pointer"})
            continue
        if pid in already_p:
            dropped.append({"pointer_id": pid, "reason": reason, "drop_reason": "duplicate_pointer"})
            continue

        pointer = pointers_by_id[pid]
        sig = str(pointer.get("locator", {}).get("signature") or pointer.get("signature") or "").strip()
        if sig and sig in already_s:
            dropped.append({"pointer_id": pid, "reason": reason, "drop_reason": "duplicate_signature", "signature": sig})
            continue

        if used >= expand_reserve:
            dropped.append({"pointer_id": pid, "reason": reason, "drop_reason": "over_budget_reserve"})
            continue

        allowed_remaining = expand_reserve - used
        take = min(max_t, allowed_remaining)
        try:
            resolved = resolve_pointer(pointer, repo_root=repo_root, model=model, max_tokens=take)
        except Exception as e:
            dropped.append({"pointer_id": pid, "reason": reason, "drop_reason": "resolver_error", "error": str(e)[:200]})
            continue
        rtoks = int(resolved.get("tokens") or 0)
        if used + rtoks > expand_reserve:
            dropped.append({"pointer_id": pid, "reason": reason, "drop_reason": "over_budget_reserve_after_count"})
            continue

        used += rtoks
        already_p.add(pid)
        if sig:
            already_s.add(sig)
        expanded.append(
            {
                "pointer_id": pid,
                "content_excerpt": resolved.get("content_excerpt") or "",
                "content_hash": resolved.get("content_hash") or "",
                "tokens": rtoks,
                "signature": sig or resolved.get("signature"),
                "reason": reason,
            }
        )

    return {
        "expanded": expanded,
        "dropped": dropped,
        "budget": {
            "total": t_total,
            "base_limit": base_limit,
            "expand_reserve": expand_reserve,
            "requested": sum(int((it or {}).get("max_tokens") or 0) for it in reqs if isinstance(it, dict)),
            "used": used,
            "remaining": max(0, expand_reserve - used),
        },
        "generated_at_ms": int(time.time() * 1000),
        "seen_pointer_ids": sorted(already_p),
        "seen_signatures": sorted(already_s),
    }
