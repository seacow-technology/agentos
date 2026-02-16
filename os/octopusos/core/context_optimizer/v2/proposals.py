from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .signature_store import top_signatures


def generate_optimizer_proposals(
    *,
    output_path: Path,
    ruleset_version: str = "v2.0",
    limit: int = 50,
) -> Dict[str, Any]:
    """
    Local auditable "self-learning" (proposal-only):
    - NEW_NOISE_PATTERN: high-frequency signatures (likely repetitive noise)
    - NEW_EXTRACT_RULE: placeholders (future), based on signature kinds
    - NEW_POINTER_RULE: recommend pointer generation for frequent signatures
    """
    now_ms = int(time.time() * 1000)
    top = top_signatures(limit=limit)

    proposals: List[Dict[str, Any]] = []
    for r in top[:25]:
        sig = str(r.get("signature") or "")
        kind = str(r.get("kind") or "")
        cnt = int(r.get("count") or 0)
        if cnt >= 10:
            proposals.append(
                {
                    "type": "NEW_NOISE_PATTERN",
                    "signature": sig,
                    "kind": kind,
                    "count": cnt,
                    "suggestion": "Consider default grouping or dropping repeated entries of this signature.",
                }
            )
        if cnt >= 5:
            proposals.append(
                {
                    "type": "NEW_POINTER_RULE",
                    "signature": sig,
                    "kind": kind,
                    "count": cnt,
                    "suggestion": "Add/expand pointer locator rules for this signature to enable selective expansion.",
                }
            )

    payload = {
        "generated_at_ms": now_ms,
        "ruleset_version": ruleset_version,
        "top_signatures": top,
        "proposals": proposals,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload

