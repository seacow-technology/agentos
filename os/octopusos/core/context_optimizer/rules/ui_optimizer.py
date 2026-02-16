from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from typing import Any, Dict, List, Tuple


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def _normalize_signature(line: str) -> str:
    s = line.strip()
    # Remove obvious dynamic bits: timestamps, long hex ids, numbers.
    s = re.sub(r"\b\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?\b", "<ts>", s)
    s = re.sub(r"\b0x[0-9a-fA-F]+\b", "<hex>", s)
    s = re.sub(r"\b[0-9a-f]{8,}\b", "<id>", s)
    s = re.sub(r"\b\d+\b", "<n>", s)
    s = re.sub(r"\s+", " ", s)
    return s


def deduplicate_stack_traces(text: str, *, max_frames: int = 12) -> Tuple[str, Dict[str, Any]]:
    """
    Collapse repeated stack traces by signature, keep only top frames.
    """
    lines = text.splitlines()
    out: List[str] = []
    removed = 0

    # Simple: detect blocks that look like stack traces (indented "at ..." lines).
    i = 0
    seen_blocks = set()
    while i < len(lines):
        ln = lines[i]
        if re.match(r"^\s*(at\s+|Traceback\b)", ln):
            block: List[str] = [ln]
            i += 1
            while i < len(lines) and (lines[i].startswith(" ") or lines[i].startswith("\t")):
                block.append(lines[i])
                i += 1
            sig = "\n".join(_normalize_signature(x) for x in block[:max_frames])
            if sig in seen_blocks:
                removed += len(block)
                continue
            seen_blocks.add(sig)
            out.extend(block[:max_frames])
            if len(block) > max_frames:
                out.append(f"... ({len(block) - max_frames} more frames)")
            continue
        out.append(ln)
        i += 1

    return "\n".join(out) + ("\n" if text.endswith("\n") else ""), {"stacktrace_removed_lines": removed}


def group_console_by_signature(text: str, *, top_k: int = 30) -> List[Dict[str, Any]]:
    """
    Extract console lines and group them by a normalized signature.
    Supports typical audit markdown logs that embed `Console:` sections or `[ERROR]/[WARN]` markers.
    """
    lines = text.splitlines()
    console_lines: List[str] = []
    for ln in lines:
        if re.search(r"\bconsole\b", ln, flags=re.IGNORECASE) and re.search(r"\berror|warn", ln, flags=re.IGNORECASE):
            console_lines.append(ln)
        if re.search(r"\[(ERROR|WARN)\]", ln):
            console_lines.append(ln)

    buckets: Dict[str, List[str]] = defaultdict(list)
    for ln in console_lines:
        sig = _normalize_signature(ln)
        buckets[sig].append(ln)

    items = sorted(buckets.items(), key=lambda kv: len(kv[1]), reverse=True)[:top_k]
    return [{"signature": sig, "count": len(v), "examples": v[:3]} for sig, v in items]


def group_network_failures(text: str, *, top_k: int = 30) -> List[Dict[str, Any]]:
    lines = text.splitlines()
    net_lines = [ln for ln in lines if re.search(r"\b(4xx|5xx|WS|WebSocket|network)\b", ln, flags=re.IGNORECASE)]
    buckets: Dict[str, List[str]] = defaultdict(list)
    for ln in net_lines:
        sig = _normalize_signature(ln)
        buckets[sig].append(ln)
    items = sorted(buckets.items(), key=lambda kv: len(kv[1]), reverse=True)[:top_k]
    return [{"signature": sig, "count": len(v), "examples": v[:3]} for sig, v in items]


def extract_error_roots(text: str, *, max_items: int = 40) -> List[str]:
    """
    Pull likely root-cause lines.
    """
    roots: List[str] = []
    for ln in text.splitlines():
        if re.search(r"\b(blocked|failed|error)\b", ln, flags=re.IGNORECASE):
            roots.append(ln.strip())
        if re.search(r"\bCSRF\b", ln):
            roots.append(ln.strip())
    # De-dupe preserving order.
    seen = set()
    out: List[str] = []
    for r in roots:
        sig = _normalize_signature(r)
        if sig in seen:
            continue
        seen.add(sig)
        out.append(r)
        if len(out) >= max_items:
            break
    return out


def optimize_ui_text(raw_text: str) -> Dict[str, Any]:
    """
    UI/Playwright optimizer:
    - groups repeated console/network noise
    - collapses stack traces
    - extracts root causes
    """
    raw_sha = _sha256_text(raw_text)

    deduped_trace, trace_meta = deduplicate_stack_traces(raw_text)
    console_summary = group_console_by_signature(deduped_trace)
    network_summary = group_network_failures(deduped_trace)
    error_roots = extract_error_roots(deduped_trace)

    summary_lines: List[str] = []
    summary_lines.append("## UI / Playwright Summary")
    if error_roots:
        summary_lines.append("- error_roots:")
        for r in error_roots[:20]:
            summary_lines.append(f"  - {r}")

    if console_summary:
        summary_lines.append("")
        summary_lines.append("## Console (Grouped)")
        for item in console_summary[:12]:
            summary_lines.append(f"- x{item['count']}: {item['signature']}")
            for ex in item.get("examples", [])[:2]:
                summary_lines.append(f"  - {ex}")

    if network_summary:
        summary_lines.append("")
        summary_lines.append("## Network (Grouped)")
        for item in network_summary[:12]:
            summary_lines.append(f"- x{item['count']}: {item['signature']}")
            for ex in item.get("examples", [])[:2]:
                summary_lines.append(f"  - {ex}")

    structured: Dict[str, Any] = {
        "console_summary": console_summary,
        "network_summary": network_summary,
        "page_errors": error_roots,
    }
    metadata: Dict[str, Any] = {
        "raw_sha256": raw_sha,
        **trace_meta,
    }
    return {
        "console_summary": console_summary,
        "network_summary": network_summary,
        "page_errors": error_roots,
        "summary_text": "\n".join(summary_lines).strip() + "\n",
        "structured": structured,
        "metadata": metadata,
    }

