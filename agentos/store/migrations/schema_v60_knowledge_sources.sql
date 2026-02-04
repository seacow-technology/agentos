-- Migration v0.60 (v0.60.0): Knowledge Sources Persistent Storage
-- Description: Create knowledge_sources table for RAG data source configuration
-- Purpose: Migrate knowledge data sources from in-memory dict to persistent storage
-- Migration from v0.59 -> v0.60
--
-- Background:
--   - Previously, data sources were stored in _data_sources_store dict (memory only)
--   - Need persistent storage for data source configuration across restarts
--   - Support multiple source types: local, web, api, database
--   - Include audit trail for source changes
--
-- target_db: agentos

PRAGMA foreign_keys = OFF;

-- Create knowledge_sources table
CREATE TABLE IF NOT EXISTS knowledge_sources (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    source_type TEXT NOT NULL,  -- 'local'|'web'|'api'|'database'|'directory'|'file'|'git'
    uri TEXT NOT NULL,
    auth_config TEXT,  -- JSON: {api_key, username, password, etc} - should be encrypted in production
    options TEXT,  -- JSON: {refresh_interval, filters, recursive, file_types, etc}
    status TEXT NOT NULL DEFAULT 'active',  -- active|inactive|error|pending|indexed|failed
    created_at INTEGER NOT NULL,  -- epoch milliseconds
    updated_at INTEGER NOT NULL,  -- epoch milliseconds
    last_indexed_at INTEGER,  -- epoch milliseconds
    chunk_count INTEGER DEFAULT 0,
    metadata TEXT,  -- JSON: additional fields
    CONSTRAINT valid_status CHECK (status IN ('active', 'inactive', 'error', 'pending', 'indexed', 'failed'))
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_knowledge_sources_type ON knowledge_sources(source_type);
CREATE INDEX IF NOT EXISTS idx_knowledge_sources_status ON knowledge_sources(status);
CREATE INDEX IF NOT EXISTS idx_knowledge_sources_created_at ON knowledge_sources(created_at);

-- Create audit log table for knowledge source changes
-- Note: Audit entries are preserved even after source deletion (no CASCADE)
CREATE TABLE IF NOT EXISTS knowledge_source_audit (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    action TEXT NOT NULL,  -- 'create'|'update'|'delete'
    changed_fields TEXT,  -- JSON: list of field names that changed
    old_values TEXT,  -- JSON: snapshot of old values
    new_values TEXT,  -- JSON: snapshot of new values
    timestamp INTEGER NOT NULL,  -- epoch milliseconds
    metadata TEXT  -- JSON: user_id, session_id, etc
    -- No foreign key constraint to preserve audit log after deletion
);

-- Index for audit queries
CREATE INDEX IF NOT EXISTS idx_knowledge_source_audit_source_id ON knowledge_source_audit(source_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_source_audit_timestamp ON knowledge_source_audit(timestamp);
CREATE INDEX IF NOT EXISTS idx_knowledge_source_audit_action ON knowledge_source_audit(action);

PRAGMA foreign_keys = ON;

-- Update schema version with description
INSERT OR REPLACE INTO schema_version (version, applied_at_ms, description)
VALUES ('0.60.0', (strftime('%s', 'now') * 1000), 'Knowledge Sources persistent storage and audit');
