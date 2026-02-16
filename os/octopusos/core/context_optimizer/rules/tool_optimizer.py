from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def _json_load_best_effort(text: str) -> Optional[Any]:
    try:
        return json.loads(text)
    except Exception:
        return None


def field_allowlist(obj: Any, allow: Dict[str, Any]) -> Any:
    """
    Recursively allowlist fields in JSON-like dicts.
    - allow keys map to True (keep as-is) or nested allowlists.
    """
    if obj is None:
        return None
    if isinstance(obj, list):
        return [field_allowlist(x, allow) for x in obj]
    if not isinstance(obj, dict):
        return obj
    out: Dict[str, Any] = {}
    for k, rule in allow.items():
        if k not in obj:
            continue
        if rule is True:
            out[k] = obj[k]
        elif isinstance(rule, dict):
            out[k] = field_allowlist(obj[k], rule)
    return out


def remove_metadata_noise(obj: Any) -> Any:
    """
    Remove common noisy metadata keys from JSON-like dicts.
    """
    if isinstance(obj, list):
        return [remove_metadata_noise(x) for x in obj]
    if not isinstance(obj, dict):
        return obj
    drop_keys = {
        "timestamp",
        "created_at",
        "updated_at",
        "ts",
        "seq",
        "span_id",
        "trace_id",
        "request_id",
        "id",
        "uuid",
        "pid",
        "runtime",
    }
    out: Dict[str, Any] = {}
    for k, v in obj.items():
        if k in drop_keys:
            continue
        out[k] = remove_metadata_noise(v)
    return out


def _truncate_large_strings(obj: Any, *, max_len: int = 400, head_len: int = 180) -> Any:
    """
    Replace large strings with a short excerpt marker to avoid token blowups.
    """
    if isinstance(obj, list):
        return [_truncate_large_strings(x, max_len=max_len, head_len=head_len) for x in obj]
    if isinstance(obj, dict):
        return {k: _truncate_large_strings(v, max_len=max_len, head_len=head_len) for k, v in obj.items()}
    if isinstance(obj, str) and len(obj) > max_len:
        head = obj[:head_len].replace("\n", "\\n")
        sha = hashlib.sha256(obj.encode("utf-8", errors="replace")).hexdigest()[:12]
        return f"{head}... <truncated len={len(obj)} sha256={sha}>"
    return obj


def _find_first_key(obj: Any, keys: set[str]) -> Optional[Any]:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in keys:
                return v
        for v in obj.values():
            hit = _find_first_key(v, keys)
            if hit is not None:
                return hit
    if isinstance(obj, list):
        for v in obj:
            hit = _find_first_key(v, keys)
            if hit is not None:
                return hit
    return None


def collapse_repeated_calls(text: str, *, max_kept: int = 200) -> Tuple[str, Dict[str, Any]]:
    """
    Collapse repeated tool/MCP calls by signature.
    Works for JSON-lines-ish logs and plain text call dumps.
    """
    lines = text.splitlines()
    buckets: Dict[str, List[str]] = defaultdict(list)

    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        sig = s
        sig = re.sub(r"\\b\\d{4}-\\d{2}-\\d{2}[ T]\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?Z?\\b", "<ts>", sig)
        sig = re.sub(r"\\b[0-9a-f]{8,}\\b", "<id>", sig)
        sig = re.sub(r"\\b\\d+\\b", "<n>", sig)
        buckets[sig].append(ln)

    # Emit top signatures then a tail of unique lines.
    items = sorted(buckets.items(), key=lambda kv: len(kv[1]), reverse=True)
    out_lines: List[str] = []
    kept = 0
    collapsed_groups = 0

    for sig, group in items:
        if kept >= max_kept:
            break
        if len(group) <= 1:
            continue
        collapsed_groups += 1
        out_lines.append(f"- x{len(group)}: {sig}")
        out_lines.append(f"  example: {group[0].strip()}")
        kept += 2

    # Do not include raw tails here; raw context must remain separate.

    removed_est = max(0, len(lines) - len(out_lines))
    return "\n".join(out_lines).strip() + "\n", {
        "collapsed_groups": collapsed_groups,
        "raw_lines": len(lines),
        "optimized_lines": len(out_lines),
        "lines_removed_est": removed_est,
    }


def _parse_json_lines(text: str, *, max_lines: int = 800) -> List[Any]:
    objs: List[Any] = []
    for ln in text.splitlines()[:max_lines]:
        s = ln.strip()
        if not s:
            continue
        try:
            objs.append(json.loads(s))
        except Exception:
            continue
    return objs


def _signature_for_event(obj: Any) -> str:
    if not isinstance(obj, dict):
        return type(obj).__name__
    t = obj.get("type")
    tool = _find_first_key(obj, {"tool", "tool_name", "capability_id", "name"})
    op = obj.get("operation") or obj.get("op")
    parts = [str(x) for x in [t, tool, op] if x]
    return " / ".join(parts) if parts else "event"


def summarize_side_effects(obj: Any) -> Dict[str, Any]:
    """
    Best-effort extraction of side effects from common event shapes.
    """
    out: Dict[str, Any] = {}
    if not isinstance(obj, dict):
        return out
    # Common: event_json with type and payload/content.
    t = obj.get("type")
    out["type"] = t
    # Try to capture referenced artifacts/paths quickly.
    s = json.dumps(obj, ensure_ascii=False)[:200000]
    paths = re.findall(r"([A-Za-z0-9_./-]{5,}\\.(?:log|json|txt|md))", s)
    if paths:
        uniq = []
        seen = set()
        for p in paths:
            if p in seen:
                continue
            seen.add(p)
            uniq.append(p)
            if len(uniq) >= 30:
                break
        out["referenced_artifacts"] = uniq
    return out


def optimize_tool_trace_text(raw_text: str) -> Dict[str, Any]:
    """
    Tool/MCP trace optimizer:
    - drops noisy metadata for JSON payloads (best effort)
    - collapses repeated calls/heartbeats/polling
    - outputs an auditable summary
    """
    raw_sha = _sha256_text(raw_text)

    parsed = _json_load_best_effort(raw_text)
    structured: Dict[str, Any] = {}
    metadata: Dict[str, Any] = {"raw_sha256": raw_sha}

    if parsed is not None:
        cleaned = _truncate_large_strings(remove_metadata_noise(parsed))
        structured["side_effects"] = summarize_side_effects(cleaned)

        # Identify tool/capability name best-effort.
        tool = _find_first_key(cleaned, {"tool", "tool_name", "capability_id", "name"})
        structured["tool"] = tool

        # Keep only a compact allowlist and then summarize into a small text blob (not pretty JSON).
        allow = {
            "type": True,
            "session_id": True,
            "run_id": True,
            "event_json": True,
            "payload": True,
            "data": True,
            "tool": True,
            "tool_name": True,
            "capability_id": True,
            "operation": True,
            "request": True,
            "response": True,
            "error": True,
            "errors": True,
            "status": True,
        }
        allowlisted = field_allowlist(cleaned, allow)
        compact = _truncate_large_strings(allowlisted, max_len=260, head_len=140)

        summary_lines: List[str] = []
        summary_lines.append("Tool Trace Summary")
        if tool is not None:
            summary_lines.append(f"- tool: {tool}")
        if isinstance(compact, dict) and "type" in compact:
            summary_lines.append(f"- type: {compact.get('type')}")
        se = structured.get("side_effects") or {}
        refs = se.get("referenced_artifacts") if isinstance(se, dict) else None
        if isinstance(refs, list) and refs:
            summary_lines.append("- referenced_artifacts:")
            for p in refs[:20]:
                summary_lines.append(f"  - {p}")

        # Keep a tiny JSON excerpt for auditability (still truncated).
        excerpt = json.dumps(compact, ensure_ascii=False)
        if len(excerpt) > 1200:
            excerpt = excerpt[:1200] + "... <excerpt truncated>"
        summary_lines.append("- excerpt_json:")
        summary_lines.append(excerpt)

        metadata["format"] = "json"
        return {
            "summary_text": "\n".join(summary_lines).strip() + "\n",
            "structured": structured,
            "metadata": metadata,
        }

    # JSON-lines support (common for traces).
    jsonl = _parse_json_lines(raw_text)
    if jsonl:
        cleaned_events = [_truncate_large_strings(remove_metadata_noise(x)) for x in jsonl]
        sig_counts: Dict[str, int] = defaultdict(int)
        for ev in cleaned_events:
            sig_counts[_signature_for_event(ev)] += 1

        top = sorted(sig_counts.items(), key=lambda kv: kv[1], reverse=True)[:40]
        summary_lines: List[str] = []
        summary_lines.append("Tool Trace Summary (jsonl)")
        summary_lines.append(f"- events_total: {len(cleaned_events)}")
        summary_lines.append("- grouped:")
        for sig, n in top[:20]:
            summary_lines.append(f"  - x{n}: {sig}")

        refs: List[str] = []
        seen = set()
        for ev in cleaned_events:
            se = summarize_side_effects(ev)
            for p in (se.get("referenced_artifacts") or []) if isinstance(se, dict) else []:
                if p in seen:
                    continue
                seen.add(p)
                refs.append(p)
                if len(refs) >= 30:
                    break
            if len(refs) >= 30:
                break
        if refs:
            summary_lines.append("- referenced_artifacts:")
            for p in refs[:20]:
                summary_lines.append(f"  - {p}")

        excerpt = json.dumps(cleaned_events[0], ensure_ascii=False)
        if len(excerpt) > 1200:
            excerpt = excerpt[:1200] + "... <excerpt truncated>"
        summary_lines.append("- first_event_excerpt:")
        summary_lines.append(excerpt)

        metadata["format"] = "jsonl"
        metadata["events_parsed"] = len(cleaned_events)
        return {
            "summary_text": "\n".join(summary_lines).strip() + "\n",
            "structured": {"top_signatures": top},
            "metadata": metadata,
        }

    # Plain-text fallback.
    collapsed, meta2 = collapse_repeated_calls(raw_text)
    metadata.update(meta2)
    metadata["format"] = "text"
    return {
        "summary_text": collapsed,
        "structured": structured,
        "metadata": metadata,
    }
