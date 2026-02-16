from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

import json

from octopusos.core.context_optimizer.metrics import build_token_metrics
from octopusos.core.context_optimizer.rules.cli_optimizer import optimize_cli_text
from octopusos.core.context_optimizer.v2.budget_allocator import allocate_budget_greedy
from octopusos.core.context_optimizer.v2.context_pack_builder import build_cli_pack, pack_to_dict
from octopusos.core.context_optimizer.v2.eval_v2 import run_v2_and_se_evaluation
from octopusos.core.context_optimizer.v2.signature_store import signatures_total

router = APIRouter(prefix="/api/context_optimizer", tags=["context_optimizer"])


class CliOptimizeRequest(BaseModel):
    text: str = Field(..., description="Raw CLI output text")
    model: str = Field(default="gpt-4o", description="Tokenizer model for token metrics")
    command: Optional[str] = None
    exit_code: Optional[int] = None
    duration_ms: Optional[int] = None


class CliOptimizeResponse(BaseModel):
    summary_text: str
    structured: Dict[str, Any]
    metadata: Dict[str, Any]
    raw_tokens: int
    optimized_tokens: int
    reduction_percent: float
    raw_sha256: str


@router.post("/cli", response_model=CliOptimizeResponse)
def optimize_cli(payload: CliOptimizeRequest) -> Dict[str, Any]:
    res = optimize_cli_text(
        payload.text,
        command=payload.command,
        exit_code=payload.exit_code,
        duration_ms=payload.duration_ms,
    )
    summary_text = str(res.get("summary_text") or "")
    metrics = build_token_metrics(payload.text, summary_text, model=payload.model)
    meta = dict(res.get("metadata") or {})
    raw_sha = str(meta.get("raw_sha256") or "")
    return {
        "summary_text": summary_text,
        "structured": dict(res.get("structured") or {}),
        "metadata": meta,
        "raw_tokens": metrics.raw_tokens,
        "optimized_tokens": metrics.optimized_tokens,
        "reduction_percent": metrics.reduction_percent,
        "raw_sha256": raw_sha,
    }


class V2CliPackRequest(BaseModel):
    text: str
    model: str = "gpt-4o"
    token_budget_total: int = 4000
    reserve_ratio: float = 0.20
    fixed_overhead: int = 1200


@router.post("/v2/cli_pack")
def v2_cli_pack(payload: V2CliPackRequest) -> Dict[str, Any]:
    # source_ref.path is not available from browser, so mark as "inline".
    src_ref = {"source_kind": "file", "path": "inline", "kind": "cli_inline"}
    before_n = signatures_total()
    v1 = optimize_cli_text(payload.text, command="cli_inline")
    pack = build_cli_pack(raw_text=payload.text, source_ref=src_ref, model=payload.model)
    pack_d = pack_to_dict(pack)
    after_n = signatures_total()
    learned = max(0, after_n - before_n)

    alloc = allocate_budget_greedy(
        token_budget_total=payload.token_budget_total,
        reserve_ratio=payload.reserve_ratio,
        fixed_overhead=payload.fixed_overhead,
        tier0_text=pack_d.get("tier_0_tldr") or "",
        facts=[
            {**f, "inject_text": json.dumps(f.get("data") or {}, ensure_ascii=False, separators=(",", ":"), sort_keys=True)}
            for f in (pack_d.get("tier_1_facts") or [])
            if isinstance(f, dict)
        ],
        model=payload.model,
    )

    raw_tokens = build_token_metrics(payload.text, payload.text, model=payload.model).raw_tokens
    base_pack_tokens = int(alloc.get("base_pack_tokens") or 0)
    total_injected = base_pack_tokens  # expansion is not executed in this endpoint.
    saved = max(0, raw_tokens - total_injected)
    saved_percent = 0.0 if raw_tokens <= 0 else (saved / raw_tokens) * 100.0

    md = v1.get("metadata") or {}
    dropped_summary = {
        "lines_removed": int(md.get("dedup_removed_lines") or 0) + int(md.get("progress_removed_lines") or 0),
        "duplicate_lines_removed": int(md.get("dedup_removed_lines") or 0),
        "progress_lines_removed": int(md.get("progress_removed_lines") or 0),
        "unique_lines": int(md.get("dedup_unique_lines") or 0),
        "total_lines": int(md.get("lines_raw") or 0),
        "dropped_facts_over_budget": len(alloc.get("dropped_items_compact") or []),
    }

    return {
        "pack": pack_d,
        "selection": alloc,
        "summary": {
            "Raw Context": raw_tokens,
            "Base Pack Used": base_pack_tokens,
            "Expansion Used": 0,
            "Total Injected": total_injected,
            "Budget Total": payload.token_budget_total,
            "Saved Tokens": saved,
            "Saved Percent": round(saved_percent, 3),
            "Ruleset Version": pack_d.get("ruleset_version"),
            "Signatures Learned": learned,
            "Dropped Summary": dropped_summary,
        },
    }


@router.post("/v2/run_eval")
def v2_run_eval() -> Dict[str, Any]:
    # Server-side evaluation over real on-disk artifacts.
    repo_root = Path(__file__).resolve().parents[3]
    out = run_v2_and_se_evaluation(repo_root=repo_root)
    return {"ok": True, "reports_dir": str(repo_root / "reports" / "token_optimization"), "result": out}
