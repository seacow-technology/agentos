import os
import sqlite3
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest


def _make_temp_db() -> Path:
    fd, p = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    return Path(p)


def _reset_registry_db(db_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OCTOPUSOS_DB_PATH", str(db_path))
    # Reset cached db path + per-thread connection (module-level singletons)
    from octopusos.core.db import registry_db

    registry_db._DB_PATH = None  # type: ignore[attr-defined]
    if hasattr(registry_db._thread_local, "connection"):  # type: ignore[attr-defined]
        registry_db._thread_local.connection = None  # type: ignore[attr-defined]


def _migrate(db_path: Path) -> None:
    from octopusos.store.migrator import auto_migrate

    auto_migrate(db_path)


def test_record_llm_usage_event_inserts_row_and_computes_cost(monkeypatch: pytest.MonkeyPatch):
    db_path = _make_temp_db()
    _migrate(db_path)
    _reset_registry_db(db_path, monkeypatch)

    monkeypatch.setenv(
        "OCTOPUSOS_LLM_PRICING_JSON",
        '{"openai":{"gpt-4o-mini":{"input_per_1m":0.15,"output_per_1m":0.60,"source":"test"}}}',
    )

    from octopusos.core.llm.usage_events import LLMUsageEvent, record_llm_usage_event
    from octopusos.store import get_db

    event_id = record_llm_usage_event(
        LLMUsageEvent(
            provider="openai",
            model="gpt-4o-mini",
            operation="test.op",
            prompt_tokens=1000,
            completion_tokens=500,
            total_tokens=1500,
            confidence="HIGH",
        )
    )
    assert event_id

    conn = get_db()
    row = conn.execute(
        "SELECT provider, model, operation, prompt_tokens, completion_tokens, total_tokens, cost_usd, pricing_source "
        "FROM llm_usage_events WHERE event_id = ?",
        (event_id,),
    ).fetchone()
    assert row is not None
    assert row["provider"] == "openai"
    assert row["model"] == "gpt-4o-mini"
    assert row["operation"] == "test.op"
    assert row["prompt_tokens"] == 1000
    assert row["completion_tokens"] == 500
    assert row["total_tokens"] == 1500
    assert row["pricing_source"] == "test"
    # 1000 * 0.15 / 1e6 + 500 * 0.60 / 1e6 = 0.00015 + 0.0003 = 0.00045
    assert abs(float(row["cost_usd"]) - 0.00045) < 1e-9


def test_cost_computed_from_db_pricing_when_env_missing(monkeypatch: pytest.MonkeyPatch):
    db_path = _make_temp_db()
    _migrate(db_path)
    _reset_registry_db(db_path, monkeypatch)

    monkeypatch.delenv("OCTOPUSOS_LLM_PRICING_JSON", raising=False)

    from octopusos.store import get_db
    from octopusos.core.llm import pricing as pricing_mod
    from octopusos.core.llm.usage_events import LLMUsageEvent, record_llm_usage_event

    # Reset pricing cache so it re-reads DB.
    pricing_mod._DB_CACHE = None  # type: ignore[attr-defined]
    pricing_mod._DB_CACHE_AT_MS = None  # type: ignore[attr-defined]

    conn = get_db()
    now_ms = 123
    conn.execute(
        "INSERT OR REPLACE INTO llm_model_pricing "
        "(provider, model, input_per_1m, output_per_1m, currency, source, enabled, created_at_ms, updated_at_ms) "
        "VALUES (?, ?, ?, ?, 'USD', ?, 1, ?, ?)",
        ("openai", "gpt-4o-mini", 1.0, 2.0, "db-test", now_ms, now_ms),
    )
    conn.commit()

    event_id = record_llm_usage_event(
        LLMUsageEvent(
            provider="openai",
            model="gpt-4o-mini",
            operation="test.db.cost",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            confidence="HIGH",
        )
    )

    row = conn.execute(
        "SELECT cost_usd, pricing_source FROM llm_usage_events WHERE event_id = ?",
        (event_id,),
    ).fetchone()
    assert row is not None
    # 100 * 1.0 / 1e6 + 50 * 2.0 / 1e6 = 0.0001 + 0.0001 = 0.0002
    assert abs(float(row["cost_usd"]) - 0.0002) < 1e-12
    assert row["pricing_source"] == "db-test"


def test_engine_invoke_model_attaches_provider_model(monkeypatch: pytest.MonkeyPatch):
    # No DB required: just ensure metadata is enriched for audit + usage recording.
    from octopusos.core.chat.engine import ChatEngine

    class FakeAdapter:
        model = "gpt-4o-mini"

        def health_check(self):
            return True, "ok"

        def generate(self, messages, **kwargs):
            _ = messages, kwargs
            return "ok", {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15, "tokens_confidence": "HIGH"}

    monkeypatch.setattr("octopusos.core.chat.adapters.get_adapter", lambda provider, model: FakeAdapter())

    engine = ChatEngine.__new__(ChatEngine)
    context_pack = SimpleNamespace(
        messages=[{"role": "user", "content": "hi"}],
        metadata={"context_integrity_checked": True},
        snapshot_id=None,
    )

    _, md = ChatEngine._invoke_model(engine, context_pack, "cloud", None)
    assert md["provider"] == "openai"
    assert md["model"] == "gpt-4o-mini"


def test_ensure_context_snapshot_provider_model_updates_row(monkeypatch: pytest.MonkeyPatch):
    db_path = _make_temp_db()
    _migrate(db_path)
    _reset_registry_db(db_path, monkeypatch)

    from octopusos.store import get_db
    from octopusos.core.llm.usage_events import ensure_context_snapshot_provider_model

    conn = get_db()
    # Minimal rows needed for FK constraints.
    conn.execute("INSERT INTO chat_sessions (session_id, title, created_at, updated_at) VALUES (?, ?, ?, ?)", ("s1", "t", 1, 1))
    conn.execute(
        "INSERT INTO context_snapshots (snapshot_id, session_id, created_at, reason, provider, model, budget_tokens, total_tokens_est, composition_json) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("snap1", "s1", 1, "send", None, None, 10, 10, "{}"),
    )
    conn.commit()

    ensure_context_snapshot_provider_model(snapshot_id="snap1", provider="openai", model="gpt-4o-mini")

    row = conn.execute("SELECT provider, model FROM context_snapshots WHERE snapshot_id = ?", ("snap1",)).fetchone()
    assert row is not None
    assert row["provider"] == "openai"
    assert row["model"] == "gpt-4o-mini"
