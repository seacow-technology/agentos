-- Schema v0.64.0: Context Refresh Versions
--
-- Tracks context refresh operations with versioning support for rollback/comparison.
-- Each refresh operation creates a new version record with metadata about the rebuild.

CREATE TABLE IF NOT EXISTS context_versions (
    version_id TEXT PRIMARY KEY,              -- e.g. "ctx-v-a1b2c3d4e5f6"
    session_id TEXT NOT NULL,                 -- Session being refreshed
    index_type TEXT NOT NULL,                 -- 'rag', 'memory', 'full'
    status TEXT NOT NULL,                     -- 'building', 'completed', 'failed'
    doc_count INTEGER DEFAULT 0,              -- Number of documents indexed
    chunk_count INTEGER DEFAULT 0,            -- Number of chunks created
    started_at INTEGER NOT NULL,              -- Unix epoch milliseconds
    completed_at INTEGER,                     -- Unix epoch milliseconds
    error_message TEXT,                       -- Error details if failed
    metadata TEXT,                            -- JSON: build details, comparison data

    CHECK (status IN ('building', 'completed', 'failed')),
    CHECK (index_type IN ('rag', 'memory', 'full')),
    FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id) ON DELETE CASCADE
);

-- Index for finding versions by session (most recent first)
CREATE INDEX IF NOT EXISTS idx_context_versions_session
ON context_versions(session_id, started_at DESC);

-- Index for monitoring active/failed builds
CREATE INDEX IF NOT EXISTS idx_context_versions_status
ON context_versions(status);

-- Record schema version
INSERT INTO schema_version (version, applied_at_ms, description)
VALUES ('0.64.0', (strftime('%s', 'now') * 1000), 'Context refresh versioning for RAG rebuild tracking');
