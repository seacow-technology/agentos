-- schema_v45_memory_conflict_resolution.sql
-- Migration for Memory conflict resolution strategy
-- Task #12: Implement Memory conflict resolution strategy
--
-- This migration adds fields to support intelligent conflict resolution:
-- - superseded_by: Points to the memory_id that replaces this one
-- - supersedes: Points to the memory_id that this one replaces
-- - version: Version number for same-key memories
-- - is_active: Whether this memory is currently active (not superseded)
-- - superseded_at: Timestamp when this memory was superseded

-- Add conflict resolution fields to memory_items
ALTER TABLE memory_items ADD COLUMN superseded_by TEXT DEFAULT NULL;
ALTER TABLE memory_items ADD COLUMN supersedes TEXT DEFAULT NULL;
ALTER TABLE memory_items ADD COLUMN version INTEGER DEFAULT 1;
ALTER TABLE memory_items ADD COLUMN is_active INTEGER DEFAULT 1;  -- SQLite uses INTEGER for boolean (1=true, 0=false)
ALTER TABLE memory_items ADD COLUMN superseded_at TEXT DEFAULT NULL;  -- ISO 8601 timestamp

-- Create indexes for conflict resolution queries
CREATE INDEX IF NOT EXISTS idx_memory_is_active
    ON memory_items(is_active, scope, type);

CREATE INDEX IF NOT EXISTS idx_memory_superseded_by
    ON memory_items(superseded_by);

CREATE INDEX IF NOT EXISTS idx_memory_supersedes
    ON memory_items(supersedes);

CREATE INDEX IF NOT EXISTS idx_memory_version
    ON memory_items(scope, type, version DESC);

-- Create composite index for conflict detection
-- This index helps find existing active memories with same (scope, type, key)
CREATE INDEX IF NOT EXISTS idx_memory_conflict_detection
    ON memory_items(scope, type, is_active, json_extract(content, '$.key'));

-- Update schema version
INSERT INTO schema_version (version, applied_at)
VALUES (
    '0.45.0',
    CURRENT_TIMESTAMP
);
