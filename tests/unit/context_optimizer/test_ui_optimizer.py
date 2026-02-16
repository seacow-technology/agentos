from __future__ import annotations

from pathlib import Path

from octopusos.core.context_optimizer.metrics import build_token_metrics
from octopusos.core.context_optimizer.rules.ui_optimizer import optimize_ui_text


def test_ui_optimizer_real_playwright_audit_reduces_tokens() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    p = repo_root / "reports" / "webui_playwright_full_audit.md"
    raw = p.read_text(encoding="utf-8", errors="replace")
    res = optimize_ui_text(raw)

    assert res["summary_text"].strip()
    assert res["structured"]
    assert res["metadata"].get("raw_sha256")

    m = build_token_metrics(raw, res["summary_text"], model="gpt-4o")
    assert m.optimized_tokens < m.raw_tokens

