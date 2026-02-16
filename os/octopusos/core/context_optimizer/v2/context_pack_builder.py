from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..metrics import count_tokens
from ..rules.cli_optimizer import optimize_cli_text
from ..rules.tool_optimizer import optimize_tool_trace_text
from ..rules.ui_optimizer import optimize_ui_text
from .schema import ContextFact, ContextPack, ContextPointer, sha256_text
from .signature import (
    signature_cli,
    signature_from_pointer,
    signature_network,
    signature_tool_call,
    signature_ui,
)
from .signature_store import upsert_signature
from .semantic_validator import assert_valid


def _mk_id(prefix: str, n: int) -> str:
    return f"{prefix}_{n:04d}"


def _lines(text: str) -> list[str]:
    return text.splitlines()


def _preview(text: str, max_chars: int = 180) -> str:
    t = " ".join(text.strip().split())
    if len(t) <= max_chars:
        return t
    return t[:max_chars] + "..."


def _estimate_tokens(text: str, model: str) -> int:
    return count_tokens(text, model=model)


def build_cli_pack(
    *,
    raw_text: str,
    source_ref: Dict[str, Any],
    model: str = "gpt-4o",
    ruleset_version: str = "v2.0",
    store_signatures: bool = True,
) -> ContextPack:
    raw_sha = sha256_text(raw_text)
    v1 = optimize_cli_text(raw_text, command=str(source_ref.get("kind") or "cli_log"))
    structured = v1.get("structured") or {}
    meta = v1.get("metadata") or {}

    tool = str(structured.get("command") or source_ref.get("kind") or "unknown")
    exit_code = structured.get("exit_code")
    # Use CLI optimizer verdict (redline logic enforced there).
    verdict = str(structured.get("verdict") or "pass")
    error_lines_count = int(((structured.get("errors") or {}).get("error_lines_count") or 0))
    cli_has_error_signal = error_lines_count > 0

    # TLDR (10 lines max, pure facts, no inference).
    tldr_lines = [
        "CLI TLDR",
        f"- tool: {tool}",
        f"- verdict: {verdict}",
        f"- exit_code: {exit_code if exit_code is not None else '?'}",
        f"- warnings_count: {structured.get('warnings_count', 0)}",
        f"- failed_tests_count: {((structured.get('failed_tests') or {}).get('failed_tests_count') or 0)}",
        f"- error_lines_count: {error_lines_count}",
        f"- raw_sha256: {raw_sha}",
    ]
    tier0 = "\n".join(tldr_lines[:10]).strip() + "\n"

    pointers: List[ContextPointer] = []
    facts: List[ContextFact] = []

    # Pointers: last 200 lines, and (if errors) last error tail window.
    lines = _lines(raw_text)
    total = len(lines)
    if total:
        start = max(1, total - 200 + 1)
        ptr_id = "ptr_cli_0001"
        loc = {"line_range": [start, total], "signature": f"cli:{tool}:tail"}
        preview = _preview("\n".join(lines[-8:]))
        pointers.append(
            ContextPointer(
                id=ptr_id,
                source_kind="file",
                source_ref=dict(source_ref),
                locator=loc,
                preview=preview,
                estimated_tokens=_estimate_tokens("\n".join(lines[-200:]), model),
                hash=f"sha256:{raw_sha}",
                signature=loc.get("signature"),
            )
        )

    err_tail = ((structured.get("errors") or {}).get("error_lines_tail") or [])
    if err_tail:
        ptr_id = "ptr_cli_0002"
        loc = {"regex": r"(Traceback|ERROR|FAILED|panic)", "signature": f"cli:{tool}:errors"}
        pointers.append(
            ContextPointer(
                id=ptr_id,
                source_kind="file",
                source_ref=dict(source_ref),
                locator=loc,
                preview=_preview("\n".join(err_tail[-6:])),
                estimated_tokens=_estimate_tokens("\n".join(err_tail[-40:]), model),
                hash=f"sha256:{raw_sha}",
                signature=loc.get("signature"),
            )
        )

    # Facts template (CLI): use extracted primary_failures from cli_optimizer to avoid contradictions.
    primary_failures: List[Dict[str, Any]] = []
    for pf in (structured.get("primary_failures") or []) if isinstance(structured.get("primary_failures"), list) else []:
        if not isinstance(pf, dict):
            continue
        msg = str(pf.get("message") or "")
        top_frame = pf.get("top_frame")
        sig = signature_cli(
            tool=tool,
            exit_code=exit_code if isinstance(exit_code, int) else None,
            top_frame=str(top_frame) if top_frame else None,
            message=msg,
        )
        primary_failures.append(
            {
                "type": str(pf.get("type") or "error"),
                "signature": sig,
                "top_frame": top_frame,
                "message": msg,
                "count": int(pf.get("count") or 1),
            }
        )

    affected_paths = []
    git = (structured.get("git_status") or {}).get("changed_files") or []
    for it in git[:30]:
        p = it.get("path")
        if isinstance(p, str):
            affected_paths.append(p)

    fact_sig = signature_cli(
        tool=tool,
        exit_code=exit_code if isinstance(exit_code, int) else None,
        top_frame=str(primary_failures[0].get("top_frame")) if primary_failures and primary_failures[0].get("top_frame") else None,
        message=str(primary_failures[0].get("message") if primary_failures else verdict),
    )
    facts.append(
        ContextFact(
            id="fact_cli_0001",
            channel="cli",
            severity="error" if (verdict == "fail" or bool(primary_failures)) else "info",
            value_score=100.0 if verdict == "fail" else 85.0 if primary_failures else 40.0,
            signature=fact_sig,
            data={
                "tool": tool,
                "exit_code": exit_code,
                "verdict": verdict,
                "primary_failures": primary_failures,
                "affected_paths": affected_paths,
                "next_action_candidates": [],
            },
            evidence_ptrs=[p.id for p in pointers[:2]],
        )
    )

    # Update signature dictionary for pointers/facts (proposal pipeline uses this).
    learned = 0
    if store_signatures:
        for f in facts:
            r = upsert_signature(store_path=None, signature=f.signature, kind="cli", sample={"fact_id": f.id, "data": f.data})
            learned += 1 if r.get("is_new") else 0
        for p in pointers:
            sig = signature_from_pointer({"locator": p.locator, "signature": p.signature, "source_kind": p.source_kind, "source_ref": p.source_ref})
            r = upsert_signature(store_path=None, signature=sig, kind="cli", sample={"pointer_id": p.id, "locator": p.locator})
            learned += 1 if r.get("is_new") else 0

    pack = ContextPack(
        version="v2.0",
        generated_at_ms=int(time.time() * 1000),
        ruleset_version=ruleset_version,
        source={"kind": "cli", "ref": dict(source_ref), "raw_sha256": raw_sha},
        tier_0_tldr=tier0,
        tier_1_facts=facts,
        tier_2_excerpts=[],
        tier_3_pointers=pointers,
    )
    assert_valid(pack_to_dict(pack))
    return pack


def build_ui_pack(
    *,
    raw_text: str,
    source_ref: Dict[str, Any],
    model: str = "gpt-4o",
    ruleset_version: str = "v2.0",
    store_signatures: bool = True,
) -> ContextPack:
    raw_sha = sha256_text(raw_text)
    v1 = optimize_ui_text(raw_text)
    structured = v1.get("structured") or {}

    page_errors = structured.get("page_errors") or []
    console_summary = structured.get("console_summary") or []
    network_summary = structured.get("network_summary") or []

    tier0_lines = [
        "UI TLDR",
        f"- page_errors: {len(page_errors)}",
        f"- console_groups: {len(console_summary)}",
        f"- network_groups: {len(network_summary)}",
        f"- raw_sha256: {raw_sha}",
    ]
    tier0 = "\n".join(tier0_lines[:10]).strip() + "\n"

    pointers: List[ContextPointer] = []
    lines = _lines(raw_text)
    total = len(lines)
    if total:
        start = max(1, total - 220 + 1)
        loc = {"line_range": [start, total], "signature": "ui:tail"}
        pointers.append(
            ContextPointer(
                id="ptr_ui_0001",
                source_kind="file",
                source_ref=dict(source_ref),
                locator=loc,
                preview=_preview("\n".join(lines[-8:])),
                estimated_tokens=_estimate_tokens("\n".join(lines[-220:]), model),
                hash=f"sha256:{raw_sha}",
                signature=loc.get("signature"),
            )
        )

    facts: List[ContextFact] = []

    # Template facts: dominant root causes by signature (reuse grouped signatures as "dominant").
    dominant: List[Dict[str, Any]] = []
    for it in (console_summary[:8] if isinstance(console_summary, list) else []):
        sig = signature_ui(route=None, error_class="console", top_frame=None, message=str(it.get("signature") or ""))
        dominant.append({"route": None, "signature": sig, "count": int(it.get("count") or 0)})
    for it in (network_summary[:8] if isinstance(network_summary, list) else []):
        sig = signature_ui(route=None, error_class="network", top_frame=None, message=str(it.get("signature") or ""))
        dominant.append({"route": None, "signature": sig, "count": int(it.get("count") or 0)})

    fact_sig = signature_ui(route=None, error_class="summary", top_frame=None, message="ui_pack")
    facts.append(
        ContextFact(
            id="fact_ui_0001",
            channel="ui",
            severity="error" if page_errors else "warn" if console_summary or network_summary else "info",
            value_score=90.0 if page_errors else 60.0 if (console_summary or network_summary) else 30.0,
            signature=fact_sig,
            data={
                "page_errors": [{"route": None, "signature": signature_ui(route=None, error_class=None, top_frame=None, message=str(e)), "top_frame": None} for e in page_errors[:10]],
                "console_errors": [{"route": None, "signature": str(it.get("signature") or ""), "count": int(it.get("count") or 0)} for it in (console_summary[:15] if isinstance(console_summary, list) else [])],
                "network_failures": [{"method": None, "url_pattern": str(it.get("signature") or ""), "status": None, "count": int(it.get("count") or 0)} for it in (network_summary[:15] if isinstance(network_summary, list) else [])],
                "dominant_root_causes": dominant[:20],
            },
            evidence_ptrs=[p.id for p in pointers],
        )
    )

    learned = 0
    if store_signatures:
        for f in facts:
            r = upsert_signature(store_path=None, signature=f.signature, kind="ui", sample={"fact_id": f.id, "data": f.data})
            learned += 1 if r.get("is_new") else 0
        for p in pointers:
            sig = signature_from_pointer({"locator": p.locator, "signature": p.signature, "source_kind": p.source_kind, "source_ref": p.source_ref})
            r = upsert_signature(store_path=None, signature=sig, kind="ui", sample={"pointer_id": p.id, "locator": p.locator})
            learned += 1 if r.get("is_new") else 0

    pack = ContextPack(
        version="v2.0",
        generated_at_ms=int(time.time() * 1000),
        ruleset_version=ruleset_version,
        source={"kind": "ui", "ref": dict(source_ref), "raw_sha256": raw_sha},
        tier_0_tldr=tier0,
        tier_1_facts=facts,
        tier_2_excerpts=[],
        tier_3_pointers=pointers,
    )
    assert_valid(pack_to_dict(pack))
    return pack


def build_tool_pack(
    *,
    raw_text: str,
    source_ref: Dict[str, Any],
    model: str = "gpt-4o",
    ruleset_version: str = "v2.0",
    store_signatures: bool = True,
) -> ContextPack:
    raw_sha = sha256_text(raw_text)
    v1 = optimize_tool_trace_text(raw_text)
    structured = v1.get("structured") or {}
    meta = v1.get("metadata") or {}

    # Detect error signal in raw trace without guessing semantics.
    raw_lower = raw_text.lower()
    tool_has_error_signal = ("[error]" in raw_lower) or ("error" in raw_lower and "failed" in raw_lower) or ("traceback" in raw_lower)

    tier0 = "\n".join(
        [
            "TOOL TLDR",
            f"- format: {meta.get('format')}",
            f"- error_signal: {bool(tool_has_error_signal)}",
            f"- raw_sha256: {raw_sha}",
        ]
    ).strip() + "\n"

    pointers: List[ContextPointer] = []
    # For tool-heavy, pointers are sqlite queries into session_run_events (read-only).
    # We generate at least 5 pointers by slicing the tail window into ranges.
    if source_ref.get("source_kind") == "sqlite":
        db_path = str(source_ref.get("path") or "")
        # By default, resolve by query windows (seq ranges) are stable for replay if run_id stable;
        # in practice we only have created_at tail, so we pin by last N rows query.
        for i in range(1, 6):
            ptr_id = f"ptr_tool_{i:04d}"
            limit = 10 * i
            loc = {
                "table": "session_run_events",
                "query": f"select session_id, run_id, seq, created_at, event_json from session_run_events order by created_at desc limit {limit}",
                "signature": f"tool:session_run_events:tail{limit}",
            }
            pointers.append(
                ContextPointer(
                    id=ptr_id,
                    source_kind="sqlite",
                    source_ref={"path": db_path},
                    locator=loc,
                    preview=f"session_run_events tail {limit}",
                    estimated_tokens=min(5000, 200 * i),
                    hash=f"sha256:{raw_sha}",
                    signature=loc.get("signature"),
                )
            )

    facts: List[ContextFact] = []
    top_sigs = (structured.get("top_signatures") or []) if isinstance(structured.get("top_signatures"), list) else []

    fact_sig = signature_tool_call(capability="mcp", action="trace", status="ok", side_effect=str(top_sigs[:1]))
    facts.append(
        ContextFact(
            id="fact_tool_0001",
            channel="tool",
            severity="error" if tool_has_error_signal else "info",
            value_score=85.0 if tool_has_error_signal else 55.0,
            signature=fact_sig,
            data={
                "calls": [],
                "side_effects": [],
                "retries_deduped": None,
                "unknown_fields_dropped": None,
                "top_signatures": top_sigs[:30],
            },
            evidence_ptrs=[p.id for p in pointers[:3]],
        )
    )

    learned = 0
    if store_signatures:
        for f in facts:
            r = upsert_signature(store_path=None, signature=f.signature, kind="tool", sample={"fact_id": f.id, "data": f.data})
            learned += 1 if r.get("is_new") else 0
        for p in pointers:
            sig = signature_from_pointer({"locator": p.locator, "signature": p.signature, "source_kind": p.source_kind, "source_ref": p.source_ref})
            r = upsert_signature(store_path=None, signature=sig, kind="tool", sample={"pointer_id": p.id, "locator": p.locator})
            learned += 1 if r.get("is_new") else 0

    pack = ContextPack(
        version="v2.0",
        generated_at_ms=int(time.time() * 1000),
        ruleset_version=ruleset_version,
        source={"kind": "tool", "ref": dict(source_ref), "raw_sha256": raw_sha},
        tier_0_tldr=tier0,
        tier_1_facts=facts,
        tier_2_excerpts=[],
        tier_3_pointers=pointers,
    )
    assert_valid(pack_to_dict(pack))
    return pack


def pack_to_dict(pack: ContextPack) -> Dict[str, Any]:
    return {
        "version": pack.version,
        "generated_at_ms": pack.generated_at_ms,
        "ruleset_version": pack.ruleset_version,
        "source": pack.source,
        "tier_0_tldr": pack.tier_0_tldr,
        "tier_1_facts": [
            {
                "id": f.id,
                "channel": f.channel,
                "severity": f.severity,
                "value_score": float(f.value_score),
                "signature": f.signature,
                "data": f.data,
                "evidence_ptrs": list(f.evidence_ptrs),
            }
            for f in pack.tier_1_facts
        ],
        "tier_2_excerpts": [
            {"id": e.id, "pointer_id": e.pointer_id, "excerpt": e.excerpt, "hash": e.hash} for e in pack.tier_2_excerpts
        ],
        "tier_3_pointers": [
            {
                "id": p.id,
                "source_kind": p.source_kind,
                "source_ref": p.source_ref,
                "locator": p.locator,
                "preview": p.preview,
                "estimated_tokens": int(p.estimated_tokens),
                "hash": p.hash,
                "signature": p.signature,
            }
            for p in pack.tier_3_pointers
        ],
    }


def injection_text_from_pack(pack: ContextPack) -> str:
    """
    Default injection order (frozen):
    1. tier0
    2. tier1 facts (compact)
    (tier2 excluded by default)
    """
    lines: List[str] = []
    lines.append(pack.tier_0_tldr.strip())
    for f in pack.tier_1_facts:
        lines.append(f"- [{f.channel}/{f.severity}] {f.signature}")
        # keep JSON stable and short
        lines.append(json.dumps(f.data, ensure_ascii=False, separators=(",", ":"), sort_keys=True)[:2400])
    return "\n".join(lines).strip() + "\n"
