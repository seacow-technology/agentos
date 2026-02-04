-- Schema v0.63.0: Brain Cache Table (SQLite fallback)
--
-- Provides persistent cache storage for Brain subgraph queries when Redis is unavailable.
-- This table is only used by SQLite cache backend.

CREATE TABLE IF NOT EXISTS brain_cache (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    expires_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_brain_cache_expires
ON brain_cache(expires_at);

-- Note: Cleanup of expired entries is done by SQLiteBrainCache.cleanup_expired()
-- Manual cleanup query (optional):
-- DELETE FROM brain_cache WHERE expires_at < (strftime('%s', 'now') * 1000);

INSERT INTO schema_version (version, applied_at_ms, description)
VALUES ('0.63.0', (strftime('%s', 'now') * 1000), 'Brain cache table for SQLite fallback');
