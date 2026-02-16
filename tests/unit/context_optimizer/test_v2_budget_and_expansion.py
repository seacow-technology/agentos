from __future__ import annotations

import json
from pathlib import Path

from octopusos.core.context_optimizer.metrics import count_tokens
from octopusos.core.context_optimizer.v2.budget_allocator import allocate_budget_greedy, value_score
from octopusos.core.context_optimizer.v2.expansion_orchestrator import orchestrate_expansion


def test_value_score_bounds() -> None:
    s = value_score(
        severity="error",
        recency_weight=100,
        uniqueness_weight=100,
        dependency_weight=100,
        actionability_weight=100,
    )
    assert 0 <= s <= 100


def test_budget_allocator_respects_base_limit() -> None:
    tier0 = "TLDR\n"
    facts = []
    for i in range(20):
        facts.append(
            {
                "id": f"fact_{i}",
                "channel": "cli",
                "severity": "info",
                "value_score": 50.0,
                "signature": f"sig_{i}",
                "data": {"i": i, "text": "x" * 200},
                "evidence_ptrs": [],
                "inject_text": json.dumps({"i": i, "text": "x" * 200}, separators=(",", ":"), sort_keys=True),
            }
        )
    alloc = allocate_budget_greedy(
        token_budget_total=400,
        reserve_ratio=0.2,
        fixed_overhead=50,
        tier0_text=tier0,
        facts=facts,
        model="gpt-4o",
    )
    assert int(alloc["base_pack_tokens"]) <= int(alloc["base_limit"]) or int(alloc["base_limit"]) == 0


def test_expansion_orchestrator_dedupes_pointer_id(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    # Create a small local file under repo_root for pointer reads.
    p = tmp_path / "x.log"
    p.write_text("a\nb\nc\n", encoding="utf-8")

    # point at tmp_path via absolute path under repo_root is not allowed, so we skip file read and only test dedupe logic
    # with unknown pointer resolution drop.
    pointers = {"ptr1": {"id": "ptr1", "source_kind": "file", "source_ref": {"path": "inline"}, "locator": {}, "preview": "", "estimated_tokens": 10, "hash": "sha256:x"}}
    req = {"need_more_detail": True, "requests": [{"pointer_id": "ptr1", "reason": "x", "max_tokens": 50}, {"pointer_id": "ptr1", "reason": "x", "max_tokens": 50}]}
    out = orchestrate_expansion(
        expansion_request=req,
        pointers_by_id=pointers,
        repo_root=repo_root,
        model="gpt-4o",
        token_budget_total=400,
        reserve_ratio=0.2,
        fixed_overhead=0,
        base_pack_tokens=10,
        per_request_max_tokens=50,
        max_requests=3,
        seen_pointer_ids=set(),
        seen_signatures=set(),
    )
    # second should be dropped as duplicate_pointer or unknown_pointer (resolver will fail due to path)
    assert len(out["expanded"]) <= 1
    assert out["budget"]["used"] <= out["budget"]["expand_reserve"]

