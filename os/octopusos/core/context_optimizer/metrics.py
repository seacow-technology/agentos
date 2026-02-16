from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

try:
    import tiktoken  # type: ignore
except Exception:  # pragma: no cover - optional dependency for token-accurate counts
    tiktoken = None

from .schema import TokenMetrics, TokenOptimizationReport


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def count_tokens(text: str, model: str = "gpt-4o") -> int:
    """
    Token count.

    Uses `tiktoken` when available; otherwise returns a conservative estimate so the
    app can run in minimal environments.
    """
    if tiktoken is None:
        # Rough heuristic: ~4 chars/token for English-ish text; clamp to >= 0.
        # Use UTF-8 decoding already done by Python strings.
        return max(0, (len(text) + 3) // 4)
    try:
        enc = tiktoken.encoding_for_model(model)
    except Exception:
        # Conservative fallback for unknown model strings.
        enc = tiktoken.get_encoding("o200k_base")
    return len(enc.encode(text))


def compute_reduction(raw_tokens: int, optimized_tokens: int) -> Tuple[float, float]:
    if raw_tokens <= 0:
        return 0.0, 0.0
    optimized_tokens = max(0, int(optimized_tokens))
    raw_tokens = int(raw_tokens)
    reduction_rate = max(0.0, min(1.0, (raw_tokens - optimized_tokens) / raw_tokens))
    return reduction_rate, reduction_rate * 100.0


def build_token_metrics(raw_text: str, optimized_text: str, model: str) -> TokenMetrics:
    raw_tokens = count_tokens(raw_text, model=model)
    optimized_tokens = count_tokens(optimized_text, model=model)
    reduction_rate, reduction_percent = compute_reduction(raw_tokens, optimized_tokens)
    raw_bytes = len(raw_text.encode("utf-8", errors="replace"))
    optimized_bytes = len(optimized_text.encode("utf-8", errors="replace"))
    return TokenMetrics(
        model=model,
        raw_tokens=raw_tokens,
        optimized_tokens=optimized_tokens,
        reduction_rate=reduction_rate,
        reduction_percent=reduction_percent,
        raw_bytes=raw_bytes,
        optimized_bytes=optimized_bytes,
        bytes_removed=max(0, raw_bytes - optimized_bytes),
    )


def generate_report_json(
    *,
    kind: str,
    raw_text: str,
    optimized_text: str,
    model: str,
    structured: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    output_path: Path,
    preview_chars: int = 1200,
) -> TokenOptimizationReport:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    metrics = build_token_metrics(raw_text, optimized_text, model=model)
    report = TokenOptimizationReport(
        kind=kind,
        metrics=metrics,
        structured=structured or {},
        metadata=metadata or {},
        raw_sha256=_sha256_text(raw_text),
        optimized_sha256=_sha256_text(optimized_text),
        raw_preview=raw_text[:preview_chars],
        optimized_preview=optimized_text[:preview_chars],
    )

    payload: Dict[str, Any] = asdict(report)
    # Flatten metrics for easier UI/grep.
    payload["metrics"] = asdict(metrics)

    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return report
