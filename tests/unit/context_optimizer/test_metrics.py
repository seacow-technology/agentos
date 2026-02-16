from __future__ import annotations

from octopusos.core.context_optimizer.metrics import count_tokens, build_token_metrics


def test_count_tokens_real_tiktoken() -> None:
    n = count_tokens("hello world", model="gpt-4o")
    assert isinstance(n, int)
    assert n > 0


def test_build_token_metrics_reduces() -> None:
    raw = "line\n" * 200 + "ERROR something bad happened\n" + ("line\n" * 200)
    opt = "ERROR something bad happened\n"
    m = build_token_metrics(raw, opt, model="gpt-4o")
    assert m.optimized_tokens < m.raw_tokens
    assert m.reduction_percent > 0

