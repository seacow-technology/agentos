from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, Optional


def _norm(s: str) -> str:
    s = s.strip()
    s = re.sub(r"\b\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?\b", "<ts>", s)
    s = re.sub(r"\b0x[0-9a-fA-F]+\b", "<hex>", s)
    s = re.sub(r"\b[0-9a-f]{8,}\b", "<id>", s)
    s = re.sub(r"\b\d+\b", "<n>", s)
    s = re.sub(r"\s+", " ", s)
    return s


def signature_cli(*, tool: str, exit_code: Optional[int], top_frame: Optional[str], message: str) -> str:
    parts = ["cli", tool or "unknown", f"exit={exit_code}" if exit_code is not None else "exit=?"]
    if top_frame:
        parts.append(_norm(top_frame)[:120])
    parts.append(_norm(message)[:180])
    base = " | ".join(parts)
    h = hashlib.sha256(base.encode("utf-8", errors="replace")).hexdigest()[:16]
    return f"cli:{tool}:{h}"


def signature_ui(*, route: Optional[str], error_class: Optional[str], top_frame: Optional[str], message: str) -> str:
    parts = ["ui", route or "*", error_class or "*"]
    if top_frame:
        parts.append(_norm(top_frame)[:120])
    parts.append(_norm(message)[:180])
    base = " | ".join(parts)
    h = hashlib.sha256(base.encode("utf-8", errors="replace")).hexdigest()[:16]
    return f"ui:{h}"


def signature_network(*, method: str, url_pattern: str, status: Optional[int]) -> str:
    base = f"net | {method.upper()} | {_norm(url_pattern)[:160]} | {status if status is not None else '?'}"
    h = hashlib.sha256(base.encode("utf-8", errors="replace")).hexdigest()[:16]
    return f"net:{h}"


def signature_tool_call(*, capability: str, action: str, status: str, side_effect: Optional[str] = None) -> str:
    base = f"tool | {capability} | {action} | {status} | {_norm(side_effect or '')[:160]}"
    h = hashlib.sha256(base.encode("utf-8", errors="replace")).hexdigest()[:16]
    return f"tool:{capability}:{h}"


def signature_from_pointer(pointer: Dict[str, Any]) -> str:
    # Stable across runs for same "kind of issue" but still tied to locator signature when present.
    sig = str(pointer.get("locator", {}).get("signature") or pointer.get("signature") or "").strip()
    if sig:
        return _norm(sig)[:220]
    base = f"{pointer.get('source_kind')}|{pointer.get('source_ref')}|{pointer.get('locator')}"
    h = hashlib.sha256(base.encode("utf-8", errors="replace")).hexdigest()[:16]
    return f"ptr:{h}"

