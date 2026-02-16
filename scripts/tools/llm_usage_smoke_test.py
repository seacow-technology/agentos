#!/usr/bin/env python3
import os
import sqlite3
import tempfile
from pathlib import Path


def main() -> int:
    fd, p = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    db_path = Path(p)

    from octopusos.store.migrator import auto_migrate

    auto_migrate(db_path)

    os.environ["OCTOPUSOS_DB_PATH"] = str(db_path)
    os.environ["OCTOPUSOS_LLM_PRICING_JSON"] = (
        '{"openai":{"gpt-4o-mini":{"input_per_1m":0.15,"output_per_1m":0.60,"source":"smoke"}}}'
    )

    # Ensure registry_db uses the temp DB.
    from octopusos.core.db import registry_db

    registry_db._DB_PATH = None  # type: ignore[attr-defined]
    if hasattr(registry_db._thread_local, "connection"):  # type: ignore[attr-defined]
        registry_db._thread_local.connection = None  # type: ignore[attr-defined]

    from octopusos.core.llm.usage_events import LLMUsageEvent, record_llm_usage_event
    from octopusos.store import get_db

    event_id = record_llm_usage_event(
        LLMUsageEvent(
            provider="openai",
            model="gpt-4o-mini",
            operation="smoke.chat.generate",
            session_id="sess_smoke",
            prompt_tokens=123,
            completion_tokens=45,
            total_tokens=168,
            confidence="HIGH",
        )
    )

    conn = get_db()
    row = conn.execute(
        "SELECT event_id, provider, model, operation, prompt_tokens, completion_tokens, total_tokens, cost_usd, pricing_source "
        "FROM llm_usage_events WHERE event_id = ?",
        (event_id,),
    ).fetchone()
    print("DB:", str(db_path))
    print(dict(row) if row else None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

