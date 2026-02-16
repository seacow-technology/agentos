from __future__ import annotations

from pathlib import Path

from octopusos.core.context_optimizer.metrics import build_token_metrics
from octopusos.core.context_optimizer.rules.cli_optimizer import optimize_cli_text


def test_cli_optimizer_real_pytest_log_reduces_tokens() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    p = repo_root / "reports" / "growth_release_gate_pytest.log"
    raw = p.read_text(encoding="utf-8", errors="replace")
    res = optimize_cli_text(raw, command="pytest")

    assert res["summary_text"].strip()
    assert res["structured"]
    assert res["metadata"].get("raw_sha256")

    m = build_token_metrics(raw, res["summary_text"], model="gpt-4o")
    assert m.optimized_tokens < m.raw_tokens


def test_cli_optimizer_raw_hash_stable() -> None:
    raw = "A\nB\nB\nB\n"
    res1 = optimize_cli_text(raw)
    res2 = optimize_cli_text(raw)
    assert res1["metadata"]["raw_sha256"] == res2["metadata"]["raw_sha256"]

