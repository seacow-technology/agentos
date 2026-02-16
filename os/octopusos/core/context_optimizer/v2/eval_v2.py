from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

from ..metrics import build_token_metrics, count_tokens
from ..pipeline import _pick_real_cli_input, _pick_real_tool_input, _pick_real_ui_input
from .budget_allocator import allocate_budget_greedy
from .context_pack_builder import (
    build_cli_pack,
    build_tool_pack,
    build_ui_pack,
    injection_text_from_pack,
    pack_to_dict,
)
from .expansion_orchestrator import orchestrate_expansion
from .proposals import generate_optimizer_proposals
from .semantic_validator import validate_context_pack


def _count_memory_kb_tokens(*, model: str = "gpt-4o", limit_memory: int = 20, limit_kb: int = 20) -> Dict[str, Any]:
    """
    Real token accounting (no optimization) for memory/KB snapshots from local octopusos db.
    This is a coarse but auditable approximation until injection plumbing is wired.
    """
    import sqlite3

    db = Path.home() / ".octopusos" / "store" / "octopusos" / "db.sqlite"
    if not db.exists():
        return {"memory_tokens": 0, "kb_tokens": 0, "db_path": str(db), "queries": [], "note": "db_missing"}

    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=30000;")
        queries = []

        mem_q = f"select id, content from memory_items where is_active = 1 order by updated_at desc limit {int(limit_memory)}"
        kb_q = f"select chunk_id, content from kb_chunks order by created_at desc limit {int(limit_kb)}"
        queries.extend([mem_q, kb_q])

        mem_rows = conn.execute(mem_q).fetchall()
        kb_rows = conn.execute(kb_q).fetchall()

        mem_text = "\n\n".join(str(r["content"] or "") for r in mem_rows)
        kb_text = "\n\n".join(str(r["content"] or "") for r in kb_rows)

        return {
            "memory_tokens": count_tokens(mem_text, model=model) if mem_text.strip() else 0,
            "kb_tokens": count_tokens(kb_text, model=model) if kb_text.strip() else 0,
            "db_path": str(db),
            "queries": queries,
            "memory_items_count": len(mem_rows),
            "kb_chunks_count": len(kb_rows),
        }
    finally:
        conn.close()


def _save_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def _scenario_sources(repo_root: Path) -> list[tuple[str, str, str]]:
    # For true "real-world" sampling, we use existing real logs/artifacts on disk.
    # Returns (scenario, channel_kind, human_label)
    return [
        ("cli_heavy", "cli", "CLI heavy real log"),
        ("ui_heavy", "ui", "UI heavy real report"),
        ("tool_heavy", "tool", "Tool heavy real trace"),
    ]


def _make_pack(repo_root: Path, channel: str, raw_text: str, src: Dict[str, Any], model: str) -> Dict[str, Any]:
    if channel == "cli":
        pack = build_cli_pack(raw_text=raw_text, source_ref=src, model=model)
    elif channel == "ui":
        pack = build_ui_pack(raw_text=raw_text, source_ref=src, model=model)
    elif channel == "tool":
        pack = build_tool_pack(raw_text=raw_text, source_ref=src, model=model)
    else:
        raise ValueError(channel)
    return pack_to_dict(pack)


def _facts_for_allocator(pack: Dict[str, Any]) -> List[Dict[str, Any]]:
    facts = []
    for f in pack.get("tier_1_facts") or []:
        if not isinstance(f, dict):
            continue
        facts.append(
            {
                **f,
                "inject_text": json.dumps(f.get("data") or {}, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
            }
        )
    return facts


def _pointers_by_id(pack: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for p in pack.get("tier_3_pointers") or []:
        if isinstance(p, dict) and isinstance(p.get("id"), str):
            out[p["id"]] = p
    return out


def _auto_expansion_request(pack: Dict[str, Any], *, max_requests: int = 3, max_tokens: int = 350) -> Dict[str, Any]:
    # Deterministic policy (frozen):
    # - If any error facts exist, request first N pointers.
    # - If any error fact lacks top_frame, force expansion (minimal info safeguard).
    facts = [f for f in (pack.get("tier_1_facts") or []) if isinstance(f, dict)]
    need = any(str(f.get("severity")) == "error" for f in facts)
    # Minimal info safeguard: severity=error and top_frame=None => MUST expand.
    for f in facts:
        if str(f.get("severity")) != "error":
            continue
        data = f.get("data") if isinstance(f.get("data"), dict) else {}
        pfs = data.get("primary_failures") if isinstance(data, dict) else None
        if isinstance(pfs, list) and any(isinstance(x, dict) and not x.get("top_frame") for x in pfs):
            need = True
            break
    pointers = [p for p in (pack.get("tier_3_pointers") or []) if isinstance(p, dict)]
    reqs = []
    for p in pointers[:max_requests]:
        reqs.append(
            {
                "pointer_id": str(p.get("id")),
                "reason": "Need precise evidence excerpt for root cause (governed expansion).",
                "max_tokens": int(max_tokens),
            }
        )
    return {"need_more_detail": bool(need), "requests": reqs}


def run_v2_and_se_evaluation(
    *,
    repo_root: Path,
    model: str = "gpt-4o",
    token_budget_total: int = 4000,
    reserve_ratio: float = 0.20,
    fixed_overhead: int = 1200,
    per_expansion_max_tokens: int = 350,
    max_requests: int = 3,
) -> Dict[str, Any]:
    out_dir = repo_root / "reports" / "token_optimization"
    out_dir.mkdir(parents=True, exist_ok=True)

    se_items: List[Dict[str, Any]] = []
    semantic_errors: List[Dict[str, Any]] = []

    # Select 3 real-world sources.
    cli_raw, cli_src = _pick_real_cli_input(repo_root)
    ui_raw, ui_src = _pick_real_ui_input(repo_root)
    tool_raw, tool_src = _pick_real_tool_input(repo_root)

    mapping = [
        ("cli_heavy", "cli", cli_raw, {"source_kind": "file", "path": cli_src.get("source_path"), **cli_src}),
        ("ui_heavy", "ui", ui_raw, {"source_kind": "file", "path": ui_src.get("source_path"), **ui_src}),
        ("tool_heavy", "tool", tool_raw, {"source_kind": "sqlite" if "sqlite" in str(tool_src.get("kind", "")) else "file", "path": str(Path.home() / ".octopusos" / "store" / "octopusos" / "db.sqlite"), **tool_src}),
    ]

    def has_error_signal(text: str) -> bool:
        # Strict signal for "root-cause exists" in raw baseline:
        # avoid matching incidental substrings like "error_message" in passing logs.
        import re
        return bool(re.search(r"\b(ERROR|FAILED|Exception|Traceback|panic)\b", text))

    # Baseline raw tokens are always on the raw input.
    for scenario, channel, raw_text, src_ref in mapping:
        pack = _make_pack(repo_root, channel, raw_text, src_ref, model)
        pack_path = out_dir / f"{scenario}_context_pack.json"
        _save_json(pack_path, pack)
        verrs = validate_context_pack(pack)
        if verrs:
            semantic_errors.append({"scenario": scenario, "errors": verrs})

        inj_text = injection_text_from_pack(
            # reconstruct lightweight; this function expects ContextPack, but for eval we replicate format:
            # (Keep stable with pack_to_dict output)
            # We'll just compute injection by recomputing via builder again for determinism.
            build_cli_pack(raw_text=raw_text, source_ref=src_ref, model=model)
            if channel == "cli"
            else build_ui_pack(raw_text=raw_text, source_ref=src_ref, model=model)
            if channel == "ui"
            else build_tool_pack(raw_text=raw_text, source_ref=src_ref, model=model)
        )

        # Pack-only budget allocation (tier0 + tier1).
        alloc = allocate_budget_greedy(
            token_budget_total=token_budget_total,
            reserve_ratio=reserve_ratio,
            fixed_overhead=fixed_overhead,
            tier0_text=str(pack.get("tier_0_tldr") or ""),
            facts=_facts_for_allocator(pack),
            model=model,
        )
        _save_json(out_dir / f"{scenario}_context_pack_selection.json", alloc)

        raw_tokens = count_tokens(raw_text, model=model)
        base_pack_tokens = int(alloc.get("base_pack_tokens") or 0)

        # Pack-only injected text: tier0 + selected facts.
        selected_inject = [str(pack.get("tier_0_tldr") or "").strip()]
        for it in alloc.get("selected_items") or []:
            if not isinstance(it, dict):
                continue
            selected_inject.append(json.dumps(it.get("data") or {}, ensure_ascii=False, separators=(",", ":"), sort_keys=True))
        base_injected_text = "\n".join(selected_inject).strip() + "\n"
        base_injected_tokens = count_tokens(base_injected_text, model=model)

        # Expansion: governed request + orchestrator.
        exp_req = _auto_expansion_request(pack, max_requests=max_requests, max_tokens=per_expansion_max_tokens)
        pointers = _pointers_by_id(pack)
        exp = orchestrate_expansion(
            expansion_request=exp_req,
            pointers_by_id=pointers,
            repo_root=repo_root,
            model=model,
            token_budget_total=token_budget_total,
            reserve_ratio=reserve_ratio,
            fixed_overhead=fixed_overhead,
            base_pack_tokens=base_injected_tokens,
            per_request_max_tokens=per_expansion_max_tokens,
            max_requests=max_requests,
            seen_pointer_ids=set(),
            seen_signatures=set(),
        )
        _save_json(out_dir / f"{scenario}_context_pack_expansions.json", exp)

        expansion_tokens = int(exp.get("budget", {}).get("used") or 0)

        facts = [f for f in (pack.get("tier_1_facts") or []) if isinstance(f, dict)]
        pack_has_error = any(str(f.get("severity")) == "error" for f in facts)
        raw_baseline_rc = has_error_signal(raw_text)

        def emit(variant: str, base_t: int, exp_t: int, rc: bool) -> None:
            total_t = base_t + exp_t
            saved_percent = 0.0 if raw_tokens <= 0 else max(0.0, (raw_tokens - total_t) / raw_tokens * 100.0)
            se_items.append(
                {
                    "scenario": scenario,
                    "variant": variant,  # raw|pack_only|pack_expansion
                    "raw_tokens": raw_tokens,
                    "base_pack_tokens": base_t,
                    "expansion_tokens": exp_t,
                    "total_tokens": total_t,
                    "saved_percent": round(saved_percent, 3),
                    "expansion_count": 0 if exp_t == 0 else len(exp.get("expanded") or []),
                    "avg_expansion_tokens": 0 if not exp.get("expanded") else round(exp_t / max(1, len(exp.get("expanded"))), 3),
                    "root_cause_identified": bool(rc),
                }
            )

        # 1) Raw full baseline
        emit("raw_full", raw_tokens, 0, raw_baseline_rc)
        # 2) Pack only (no expansion)
        emit("pack_only", base_injected_tokens, 0, pack_has_error)
        # 3) Pack + expansion (20% reserve)
        emit("pack_plus_expansion", base_injected_tokens, expansion_tokens, pack_has_error or bool(exp.get("expanded")))

    # Expansion utility scoring (effective if it changes outcome vs pack_only).
    # Also track an "ineffective streak" across runs (proposal-only behavior).
    effective = 0
    total = 0
    by_scenario: Dict[str, Dict[str, Any]] = {}
    for it in se_items:
        by_scenario.setdefault(str(it.get("scenario")), {})[str(it.get("variant"))] = it
    for sc, m in by_scenario.items():
        po = m.get("pack_only")
        pe = m.get("pack_plus_expansion")
        if not po or not pe:
            continue
        total += 1
        eff = bool((not po.get("root_cause_identified")) and pe.get("root_cause_identified"))
        # If outcome same, treat as ineffective (even if it adds context).
        pe["expansion_effective"] = bool(eff)
        effective += 1 if eff else 0

    effective_ratio = 0.0 if total == 0 else round((effective / total) * 100.0, 3)

    # v2_report.json: aggregate + proposals + pack paths.
    v2_report = {
        "generated_at_ms": int(time.time() * 1000),
        "model": model,
        "defaults": {
            "B_total": token_budget_total,
            "reserve_ratio": reserve_ratio,
            "fixed_overhead": fixed_overhead,
            "per_expansion_max_tokens": per_expansion_max_tokens,
            "max_requests": max_requests,
            "ruleset_version": "v2.0",
        },
        "se_items": se_items,
        "semantic_validation": {
            "validation_passed": len(semantic_errors) == 0,
            "semantic_conflicts": len(semantic_errors),
            "conflicts": semantic_errors[:50],
        },
        "expansion_effective_ratio_percent": effective_ratio,
    }
    _save_json(out_dir / "v2_report.json", v2_report)

    # se_report.json: one entry per scenario (as frozen contract).
    se_report = {"generated_at_ms": int(time.time() * 1000), "items": se_items}
    _save_json(out_dir / "se_report.json", se_report)

    # semantic_consistency_report.json (frozen)
    # Expansion ineffective streak tracking (proposal-only adaptive hint).
    state_path = out_dir / "expansion_utility_state.json"
    state = {"ineffective_streak": 0}
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except Exception:
            state = {"ineffective_streak": 0}
    ineffective_streak = int(state.get("ineffective_streak") or 0)
    ran_expansion = any(it.get("variant") == "pack_plus_expansion" and int(it.get("expansion_tokens") or 0) > 0 for it in se_items)
    if ran_expansion and effective_ratio == 0.0:
        ineffective_streak += 1
    else:
        ineffective_streak = 0
    state_path.write_text(json.dumps({"ineffective_streak": ineffective_streak}, indent=2), encoding="utf-8")

    semantic_report = {
        "generated_at_ms": int(time.time() * 1000),
        "validation_passed": len(semantic_errors) == 0,
        "semantic_conflicts": len(semantic_errors),
        "expansion_effective_ratio_percent": effective_ratio,
        "expansion_ineffective_streak": ineffective_streak,
        "reserve_ratio_recommendation": 0.15 if ineffective_streak >= 5 else None,
        "notes": [
            "Semantic validator currently enforces redline consistency checks only.",
            "Memory/KB token accounting is handled in aggregate_report.json v2 section.",
        ],
    }
    _save_json(out_dir / "semantic_consistency_report.json", semantic_report)

    # Update aggregate_report.json (append v2 section, keep existing keys for v1).
    def _by_variant(variant: str) -> list[dict[str, Any]]:
        return [it for it in se_items if it.get("variant") == variant]

    pack_items = _by_variant("pack_plus_expansion")
    raw_total = sum(int(it.get("raw_tokens") or 0) for it in pack_items)
    base_total = sum(int(it.get("base_pack_tokens") or 0) for it in pack_items)
    exp_total = sum(int(it.get("expansion_tokens") or 0) for it in pack_items)
    total_injected = sum(int(it.get("total_tokens") or 0) for it in pack_items)
    saved_vs_raw = max(0, raw_total - total_injected)
    saved_percent = 0.0 if raw_total <= 0 else (saved_vs_raw / raw_total) * 100.0

    memkb = _count_memory_kb_tokens(model=model)
    v2_aggregate = {
        "ruleset_version": "v2.0",
        "token_budget_total": token_budget_total,
        "reserve_ratio": reserve_ratio,
        "fixed_overhead": fixed_overhead,
        "execution_tokens": total_injected,
        "base_tokens": base_total,
        "expand_tokens": exp_total,
        "total_tokens": total_injected,
        "raw_tokens": raw_total,
        "saved_vs_raw": saved_vs_raw,
        "saved_percent": round(saved_percent, 3),
        "memory_tokens": int(memkb.get("memory_tokens") or 0),
        "kb_tokens": int(memkb.get("kb_tokens") or 0),
        "memory_token_count": int(memkb.get("memory_tokens") or 0),
        "kb_token_count": int(memkb.get("kb_tokens") or 0),
        # Placeholder: true "reasoning tokens" depend on the model's internal accounting,
        # but we expose an auditable proxy as the injected pack tokens.
        "reasoning_tokens": int(total_injected),
        "reasoning_tokens_proxy": int(total_injected),
        "memory_kb_accounting": {k: v for k, v in memkb.items() if k not in {"memory_tokens", "kb_tokens"}},
    }
    agg_path = out_dir / "aggregate_report.json"
    merged: Dict[str, Any] = {}
    if agg_path.exists():
        try:
            merged = json.loads(agg_path.read_text(encoding="utf-8"))
        except Exception:
            merged = {}
    merged["v2"] = v2_aggregate
    merged.setdefault("model", model)
    merged["generated_at_ms_v2"] = int(time.time() * 1000)
    _save_json(agg_path, merged)

    # Proposals (signature learning outputs).
    proposals = generate_optimizer_proposals(output_path=out_dir / "optimizer_proposals.json", ruleset_version="v2.0")

    return {"v2_report": v2_report, "se_report": se_report, "optimizer_proposals": proposals}


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parents[5]
    out = run_v2_and_se_evaluation(repo_root=repo_root)
    print(json.dumps(out, ensure_ascii=False, indent=2))
