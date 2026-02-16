-- schema_v102_llm_model_pricing.sql
-- Migration v0.102.0: Model pricing catalog
--
-- Purpose:
-- - Persist per-provider/per-model token pricing in the DB (editable from WebUI).
-- - Enable cost_usd calculation without environment variables.
--
-- Units:
-- - input_per_1m / output_per_1m: USD per 1,000,000 tokens.

CREATE TABLE IF NOT EXISTS llm_model_pricing (
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    input_per_1m REAL NOT NULL,
    output_per_1m REAL NOT NULL,
    currency TEXT NOT NULL DEFAULT 'USD',
    source TEXT,                       -- e.g. "manual", "vendor", "contract", etc.
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at_ms INTEGER NOT NULL,
    updated_at_ms INTEGER NOT NULL,

    PRIMARY KEY (provider, model),
    CHECK(currency IN ('USD')),
    CHECK(enabled IN (0, 1)),
    CHECK(input_per_1m >= 0),
    CHECK(output_per_1m >= 0)
);

CREATE INDEX IF NOT EXISTS idx_llm_model_pricing_provider
ON llm_model_pricing(provider);

CREATE INDEX IF NOT EXISTS idx_llm_model_pricing_updated
ON llm_model_pricing(updated_at_ms DESC);

INSERT OR REPLACE INTO schema_version (version, applied_at_ms, description)
VALUES ('0.102.0', (strftime('%s', 'now') * 1000), 'DB-backed LLM model pricing catalog');

