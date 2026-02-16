from __future__ import annotations

import json
from pathlib import Path

from octopusos.core.context_optimizer.metrics import build_token_metrics
from octopusos.core.context_optimizer.rules.tool_optimizer import optimize_tool_trace_text


def test_tool_optimizer_json_trace_reduces_tokens() -> None:
    # Real-ish event shape (kept local to the test, but still processed by real tokenizer).
    raw_obj = {
        "type": "message.delta",
        "session_id": "01TEST",
        "run_id": "run_test",
        "seq": 123,
        "created_at": 1770000000,
        "event_json": {
            "type": "tool.call",
            "tool": "playwright",
            "request": {"url": "https://example.com", "timeout_ms": 30000, "headers": {"x": "y"}},
            "response": {"status": 200, "body": {"title": "Example Domain", "headers": {"server": "nginx"}}},
            "metadata": {"trace_id": "abcd" * 20, "timestamp": "2026-02-10T00:00:00Z"},
        },
    }
    raw = json.dumps(raw_obj, ensure_ascii=False)
    res = optimize_tool_trace_text(raw)
    assert res["summary_text"].strip()
    assert res["metadata"].get("raw_sha256")

    m = build_token_metrics(raw, res["summary_text"], model="gpt-4o")
    assert m.optimized_tokens < m.raw_tokens

