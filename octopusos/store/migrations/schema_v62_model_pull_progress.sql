-- Schema v62: Model Pull Progress - Persistent Storage
-- Task #15 (Wave A5): Migrate model pull progress from memory to database
--
-- Design Goals:
-- - Replace in-memory _pull_progress dict with persistent storage
-- - Survive service restarts and recover progress state
-- - Audit trail for all model download operations
-- - Support progress tracking, cleanup, and historical queries
--
-- References:
-- - agentos/webui/api/models.py (line 41) - Original memory storage
-- - KnowledgeSourceRepo pattern (schema_v60)
-- - TwilioSessionRepo pattern (schema_v61)

-- ===================================================================
-- 1. Model Pull Progress Table
-- ===================================================================

-- Core progress tracking for model downloads (Ollama pull operations)
CREATE TABLE IF NOT EXISTS model_pull_progress (
    model_name TEXT PRIMARY KEY,                      -- Model name (e.g., "llama3.2:3b")
    pull_id TEXT UNIQUE NOT NULL,                     -- Pull operation ID (format: "pull_{uuid}")

    -- Status tracking
    status TEXT NOT NULL DEFAULT 'pulling',           -- pulling, completed, failed, canceled
    progress_pct REAL NOT NULL DEFAULT 0.0,           -- Progress percentage (0.0 - 100.0)

    -- Byte tracking
    total_bytes INTEGER,                              -- Total download size (NULL if unknown)
    completed_bytes INTEGER DEFAULT 0,                -- Bytes downloaded so far

    -- Timestamps (epoch_ms for consistency with v44+)
    started_at INTEGER NOT NULL,                      -- Pull start time (epoch_ms)
    updated_at INTEGER NOT NULL,                      -- Last update time (epoch_ms)
    completed_at INTEGER,                             -- Pull completion time (epoch_ms, NULL if not done)

    -- Current operation details
    current_step TEXT,                                -- Current step description (e.g., "Downloading: 45%")

    -- Error handling
    error_message TEXT,                               -- Error message if status = 'failed'

    -- Additional metadata (JSON-encoded)
    metadata TEXT,                                    -- JSON: {provider, digest, layers, etc}

    CHECK (status IN ('pulling', 'completed', 'failed', 'canceled')),
    CHECK (progress_pct >= 0.0 AND progress_pct <= 100.0)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_model_pull_progress_status
    ON model_pull_progress(status);

CREATE INDEX IF NOT EXISTS idx_model_pull_progress_updated_at
    ON model_pull_progress(updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_model_pull_progress_pull_id
    ON model_pull_progress(pull_id);

-- Index for active pulls (for cleanup queries)
CREATE INDEX IF NOT EXISTS idx_model_pull_progress_active
    ON model_pull_progress(status, started_at DESC)
    WHERE status IN ('pulling');

-- ===================================================================
-- 2. Schema Version Update
-- ===================================================================

-- Record migration
INSERT INTO schema_version (version, description, applied_at)
VALUES ('0.62.0', 'Model Pull Progress - Persistent Storage', strftime('%s', 'now') * 1000);
