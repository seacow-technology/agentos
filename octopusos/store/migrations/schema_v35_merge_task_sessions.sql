-- Migration v35: Merge task_sessions into chat_sessions
-- Date: 2026-01-31
-- Purpose: Eliminate duplicate session tables, unify to single session system
-- Gate: Gate 2 - No Duplicate Tables

-- ============================================
-- Step 1: Extend chat_sessions schema (if needed)
-- ============================================

-- Add missing fields from task_sessions to chat_sessions
-- These columns are needed to store data from task_sessions table
-- Note: If task_sessions table doesn't exist (fresh migration), these columns
-- will still be added for future compatibility

-- Add channel column (stores communication channel: cli|api|ui)
ALTER TABLE chat_sessions ADD COLUMN channel TEXT;

-- Add last_activity column (tracks last interaction time)
ALTER TABLE chat_sessions ADD COLUMN last_activity TIMESTAMP;

-- ============================================
-- Step 2: Migrate data from task_sessions to chat_sessions
-- ============================================

-- Create task_sessions table placeholder if it doesn't exist (for fresh migrations)
CREATE TABLE IF NOT EXISTS task_sessions (
    session_id TEXT PRIMARY KEY,
    channel TEXT,
    created_at TIMESTAMP,
    last_activity TIMESTAMP,
    metadata TEXT
);

-- Migrate task_sessions records to chat_sessions
-- Strategy: INSERT OR IGNORE to avoid conflicts
-- Map fields: channel, created_at, last_activity, metadata
-- If task_sessions is empty (fresh migration), no data will be migrated
INSERT OR IGNORE INTO chat_sessions (
    session_id,
    title,
    task_id,
    created_at,
    updated_at,
    channel,
    last_activity,
    metadata
)
SELECT
    session_id,
    'Migrated Task Session' as title,  -- Default title for migrated sessions
    json_extract(metadata, '$.task_id') as task_id,  -- Extract task_id from metadata if exists
    created_at,
    last_activity as updated_at,  -- Map last_activity to updated_at
    channel,
    last_activity,
    metadata
FROM task_sessions
WHERE session_id NOT IN (SELECT session_id FROM chat_sessions);

-- ============================================
-- Step 3: Update task references
-- ============================================

-- Note: tasks.session_id foreign key currently points to task_sessions
-- After this migration, it will logically point to chat_sessions
-- SQLite doesn't allow modifying foreign keys without recreating the table,
-- but since we're keeping the session_id values intact and they exist in both tables,
-- the referential integrity is maintained.

-- The foreign key constraint will be updated in a future schema revision
-- when we have a maintenance window to rebuild the tasks table.

-- For now, we just ensure all session_ids in tasks table exist in chat_sessions
-- (which they do, since we migrated all task_sessions data to chat_sessions)

-- ============================================
-- Step 4: Archive task_sessions table
-- ============================================

-- Rename task_sessions to task_sessions_legacy for backup
ALTER TABLE task_sessions RENAME TO task_sessions_legacy;

-- Drop indexes on legacy table (they're no longer needed)
-- These indexes may not exist in fresh migrations, so we use IF EXISTS
DROP INDEX IF EXISTS idx_task_sessions_channel;
DROP INDEX IF EXISTS idx_task_sessions_created;

-- ============================================
-- Step 5: Record migration
-- ============================================

INSERT INTO schema_migrations (migration_id, description, status, metadata)
VALUES (
    'v35_merge_task_sessions',
    'Merge task_sessions into chat_sessions unified session system',
    'success',
    json_object(
        'migration_date', datetime('now'),
        'task_sessions_count', (SELECT COUNT(*) FROM task_sessions_legacy),
        'chat_sessions_count', (SELECT COUNT(*) FROM chat_sessions),
        'migrated_count', (SELECT COUNT(*) FROM chat_sessions WHERE json_extract(metadata, '$.migrated_from_task_sessions') IS NOT NULL)
    )
);

-- ============================================
-- Version Tracking
-- ============================================

INSERT OR REPLACE INTO schema_version (version, applied_at)
VALUES ('0.35.0', datetime('now'));
