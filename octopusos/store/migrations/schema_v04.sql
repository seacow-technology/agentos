-- AgentOS Store Schema v0.4
-- Memory Governance: Retention Policy, Decay, GC, Audit
-- Migration from v0.2 -> v0.4

-- ============================================
-- Memory Governance: Add Lifecycle Fields
-- ============================================

-- Add retention policy and decay tracking fields to memory_items
ALTER TABLE memory_items ADD COLUMN last_used_at TIMESTAMP;
ALTER TABLE memory_items ADD COLUMN use_count INTEGER DEFAULT 0;
ALTER TABLE memory_items ADD COLUMN retention_type TEXT DEFAULT 'project';  -- temporary|project|permanent
ALTER TABLE memory_items ADD COLUMN expires_at TIMESTAMP;
ALTER TABLE memory_items ADD COLUMN auto_cleanup INTEGER DEFAULT 1;  -- boolean (1=true, 0=false)

-- ============================================
-- Memory Audit Log
-- ============================================

CREATE TABLE IF NOT EXISTS memory_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event TEXT NOT NULL,  -- created|updated|deleted|merged|promoted|decayed
    memory_id TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT,  -- JSON: {reason, old_value, new_value, etc}
    FOREIGN KEY (memory_id) REFERENCES memory_items(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_memory_audit_memory_id ON memory_audit_log(memory_id);
CREATE INDEX IF NOT EXISTS idx_memory_audit_event ON memory_audit_log(event);
CREATE INDEX IF NOT EXISTS idx_memory_audit_timestamp ON memory_audit_log(timestamp DESC);

-- ============================================
-- GC Metadata Table
-- ============================================

CREATE TABLE IF NOT EXISTS memory_gc_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    status TEXT NOT NULL,  -- running|completed|failed
    memories_decayed INTEGER DEFAULT 0,
    memories_deleted INTEGER DEFAULT 0,
    memories_promoted INTEGER DEFAULT 0,
    error TEXT,
    metadata TEXT  -- JSON: {decay_rate, cleanup_threshold, etc}
);

CREATE INDEX IF NOT EXISTS idx_memory_gc_runs_started ON memory_gc_runs(started_at DESC);

-- ============================================
-- Indexes for Performance (Retention Queries)
-- ============================================

CREATE INDEX IF NOT EXISTS idx_memory_retention_type ON memory_items(retention_type);
CREATE INDEX IF NOT EXISTS idx_memory_expires_at ON memory_items(expires_at);
CREATE INDEX IF NOT EXISTS idx_memory_last_used ON memory_items(last_used_at);
CREATE INDEX IF NOT EXISTS idx_memory_use_count ON memory_items(use_count DESC);
CREATE INDEX IF NOT EXISTS idx_memory_confidence_decay ON memory_items(confidence, last_used_at);

-- ============================================
-- Migration: Set Default Values
-- ============================================

-- Set last_used_at to created_at for existing records
UPDATE memory_items
SET last_used_at = created_at
WHERE last_used_at IS NULL;

-- Set retention_type based on scope heuristic
UPDATE memory_items
SET retention_type = CASE
    WHEN scope = 'global' THEN 'permanent'
    WHEN scope IN ('project', 'repo') THEN 'project'
    WHEN scope IN ('task', 'agent') THEN 'temporary'
    ELSE 'project'
END
WHERE retention_type = 'project';  -- default value

-- Set expires_at for temporary memories (7 days from now)
UPDATE memory_items
SET expires_at = datetime('now', '+7 days')
WHERE retention_type = 'temporary' AND expires_at IS NULL;

-- ============================================
-- Audit: Record Migration Event
-- ============================================

INSERT INTO memory_audit_log (event, memory_id, metadata)
SELECT 'migrated', id, json_object(
    'from_version', '0.2',
    'to_version', '0.4',
    'retention_type', retention_type,
    'expires_at', expires_at
)
FROM memory_items;

-- ============================================
-- Version Tracking
-- ============================================

CREATE TABLE IF NOT EXISTS schema_version (
    version TEXT PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT OR REPLACE INTO schema_version (version) VALUES ('0.4.0');
