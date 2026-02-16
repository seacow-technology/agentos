-- schema_v101_llm_usage_events.sql
-- Migration v0.101.0: LLM usage events
--
-- Purpose:
-- - Track every LLM invocation (cloud + local) in a single, queryable table.
-- - Support cost tracking, token usage tracking, and correlation to chat/task context.
--
-- Notes:
-- - This table is intentionally decoupled from task_runs/run_id because chat flows
--   and other subsystems may not have a run_id.
-- - All timestamps are epoch milliseconds (consistent with v44+ conventions).

CREATE TABLE IF NOT EXISTS llm_usage_events (
    event_id TEXT PRIMARY KEY,              -- ULID
    created_at_ms INTEGER NOT NULL,          -- epoch ms

    provider TEXT NOT NULL,                 -- openai|anthropic|ollama|llamacpp|...
    model TEXT,                             -- model id/name if known
    operation TEXT NOT NULL,                -- chat.generate|answers.suggest|mode.propose|tool.openai_chat|...

    -- Correlation (nullable)
    session_id TEXT,                        -- chat session
    task_id TEXT,                           -- task (if any)
    message_id TEXT,                        -- chat message id (if any)
    context_snapshot_id TEXT,               -- context_snapshots.snapshot_id (if any)

    -- Tracing (nullable)
    trace_id TEXT,
    span_id TEXT,
    parent_span_id TEXT,

    -- Usage (nullable for providers without usage reporting)
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,

    -- Cost
    cost_usd REAL,
    cost_currency TEXT NOT NULL DEFAULT 'USD',

    -- Data quality
    confidence TEXT NOT NULL DEFAULT 'HIGH', -- HIGH|LOW|ESTIMATED
    pricing_source TEXT,                    -- optional: pricing catalog/version identifier

    -- Raw provider payloads (JSON strings)
    usage_raw_json TEXT,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_llm_usage_events_time
ON llm_usage_events(created_at_ms DESC);

CREATE INDEX IF NOT EXISTS idx_llm_usage_events_session_time
ON llm_usage_events(session_id, created_at_ms DESC);

CREATE INDEX IF NOT EXISTS idx_llm_usage_events_task_time
ON llm_usage_events(task_id, created_at_ms DESC);

CREATE INDEX IF NOT EXISTS idx_llm_usage_events_message
ON llm_usage_events(message_id);

CREATE INDEX IF NOT EXISTS idx_llm_usage_events_snapshot
ON llm_usage_events(context_snapshot_id);

CREATE INDEX IF NOT EXISTS idx_llm_usage_events_provider_model_time
ON llm_usage_events(provider, model, created_at_ms DESC);

INSERT OR REPLACE INTO schema_version (version, applied_at_ms, description)
VALUES ('0.101.0', (strftime('%s', 'now') * 1000), 'LLM usage events tracking (tokens + cost + correlation)');

