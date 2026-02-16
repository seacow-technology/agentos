from __future__ import annotations

from octopusos.core.context_optimizer.metrics import build_token_metrics
from octopusos.core.context_optimizer.rules.cli_optimizer import optimize_cli_text


def test_cli_multiple_failures_preserved() -> None:
    raw = "\n".join(
        [
            "WARNING: something is odd",
            "ERROR first: database connection failed",
            "Traceback (most recent call last):",
            "  File \"a.py\", line 1, in <module>",
            "ERROR second: timeout waiting for service",
            "Traceback (most recent call last):",
            "  File \"b.py\", line 2, in <module>",
        ]
    ) + "\n"
    res = optimize_cli_text(raw, command="pytest", exit_code=1, duration_ms=123)
    st = res["structured"]
    assert st["verdict"] == "fail"
    assert st["warnings_count"] == 1
    pf = st.get("primary_failures") or []
    msgs = [str(x.get("message") or "") for x in pf if isinstance(x, dict)]
    assert any("first" in m for m in msgs)
    assert any("second" in m for m in msgs)


def test_cli_warning_only_not_zeroed() -> None:
    raw = "\n".join([f"WARNING: w{i}" for i in range(50)]) + "\n"
    res = optimize_cli_text(raw, command="pytest", exit_code=0)
    st = res["structured"]
    assert st["verdict"] == "pass"
    assert st["warnings_count"] == 50
    # Must not collapse to empty context.
    assert res["summary_text"].strip()
    m = build_token_metrics(raw, res["summary_text"], model="gpt-4o")
    assert m.optimized_tokens > 0


def test_cli_noise_flood_preserves_long_tail_error_and_saves() -> None:
    # 1000 repeated stack traces + 1 unique error.
    repeated_block = "\n".join(
        [
            "ERROR repeated: flaky thing",
            "Traceback (most recent call last):",
            "  File \"x.py\", line 1, in <module>",
            "Exception: flaky",
        ]
    )
    raw = ("\n".join([repeated_block for _ in range(1000)]) + "\n" + "ERROR unique: real root cause\n")  # noqa: E501
    res = optimize_cli_text(raw, command="pytest", exit_code=1)
    pf = res["structured"].get("primary_failures") or []
    # repeated should be collapsed to one signature (count >> 1) and unique must exist
    counts = [int(x.get("count") or 1) for x in pf if isinstance(x, dict)]
    msgs = [str(x.get("message") or "") for x in pf if isinstance(x, dict)]
    assert any(c >= 1000 for c in counts)
    assert any("unique" in m for m in msgs)
    m = build_token_metrics(raw, res["summary_text"], model="gpt-4o")
    assert m.reduction_percent > 80

