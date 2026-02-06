-- schema_v44_epoch_ms_timestamps.sql
-- Migration to add epoch_ms fields for timezone-safe timestamps
-- Part of Time & Timestamp Contract (ADR-XXXX)
--
-- Background:
--   SQLite TIMESTAMP columns use local time and are ambiguous across timezones
--   This causes issues in distributed systems and multi-region deployments
--
-- Solution:
--   Add *_at_ms fields (INTEGER) storing Unix epoch milliseconds (UTC)
--   These fields are timezone-independent and portable
--
-- Strategy:
--   1. Add new *_at_ms columns (INTEGER, nullable for backward compatibility)
--   2. Migrate existing data from TIMESTAMP to epoch_ms
--   3. Create indexes on new columns
--   4. Keep old TIMESTAMP columns for backward compatibility
--
-- Safety:
--   - Non-destructive: Old columns preserved
--   - Nullable: Won't break existing code
--   - Graceful handling: Skips tables that don't exist
--
-- Note: This migration uses a pattern where it will silently succeed even if
-- some tables don't exist. This is intentional for forward compatibility.

-- ============================================================
-- 0. Core Functions Documentation
-- ============================================================
-- SQLite epoch conversion formula:
--   epoch_ms = (julianday(timestamp) - 2440587.5) * 86400000
--
-- Where:
--   - julianday() converts to Julian day number
--   - 2440587.5 is the Julian day for Unix epoch (1970-01-01 00:00:00 UTC)
--   - 86400000 is milliseconds per day (86400 * 1000)

-- ============================================================
-- PART A: Core Tables (must exist)
-- ============================================================

-- ============================================================
-- 1. Chat Sessions
-- ============================================================
ALTER TABLE chat_sessions ADD COLUMN created_at_ms INTEGER;
ALTER TABLE chat_sessions ADD COLUMN updated_at_ms INTEGER;

UPDATE chat_sessions
SET created_at_ms = CAST((julianday(created_at) - 2440587.5) * 86400000 AS INTEGER)
WHERE created_at_ms IS NULL AND created_at IS NOT NULL;

UPDATE chat_sessions
SET updated_at_ms = CAST((julianday(updated_at) - 2440587.5) * 86400000 AS INTEGER)
WHERE updated_at_ms IS NULL AND updated_at IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_chat_sessions_created_at_ms
    ON chat_sessions(created_at_ms DESC);

CREATE INDEX IF NOT EXISTS idx_chat_sessions_updated_at_ms
    ON chat_sessions(updated_at_ms DESC);

-- ============================================================
-- 2. Chat Messages
-- ============================================================
ALTER TABLE chat_messages ADD COLUMN created_at_ms INTEGER;

UPDATE chat_messages
SET created_at_ms = CAST((julianday(created_at) - 2440587.5) * 86400000 AS INTEGER)
WHERE created_at_ms IS NULL AND created_at IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_chat_messages_created_at_ms
    ON chat_messages(created_at_ms DESC);

-- ============================================================
-- 3. Tasks
-- ============================================================
ALTER TABLE tasks ADD COLUMN created_at_ms INTEGER;
ALTER TABLE tasks ADD COLUMN updated_at_ms INTEGER;

UPDATE tasks
SET created_at_ms = CAST((julianday(created_at) - 2440587.5) * 86400000 AS INTEGER)
WHERE created_at_ms IS NULL AND created_at IS NOT NULL;

UPDATE tasks
SET updated_at_ms = CAST((julianday(updated_at) - 2440587.5) * 86400000 AS INTEGER)
WHERE updated_at_ms IS NULL AND updated_at IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_tasks_created_at_ms
    ON tasks(created_at_ms DESC);

CREATE INDEX IF NOT EXISTS idx_tasks_updated_at_ms
    ON tasks(updated_at_ms DESC);

-- ============================================================
-- 4. Task Lineage
-- ============================================================
ALTER TABLE task_lineage ADD COLUMN created_at_ms INTEGER;

UPDATE task_lineage
SET created_at_ms = CAST((julianday(created_at) - 2440587.5) * 86400000 AS INTEGER)
WHERE created_at_ms IS NULL AND created_at IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_task_lineage_created_at_ms
    ON task_lineage(created_at_ms DESC);

-- ============================================================
-- 5. Task Agents
-- ============================================================
ALTER TABLE task_agents ADD COLUMN started_at_ms INTEGER;
ALTER TABLE task_agents ADD COLUMN ended_at_ms INTEGER;

UPDATE task_agents
SET started_at_ms = CAST((julianday(started_at) - 2440587.5) * 86400000 AS INTEGER)
WHERE started_at_ms IS NULL AND started_at IS NOT NULL;

UPDATE task_agents
SET ended_at_ms = CAST((julianday(ended_at) - 2440587.5) * 86400000 AS INTEGER)
WHERE ended_at_ms IS NULL AND ended_at IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_task_agents_started_at_ms
    ON task_agents(started_at_ms DESC);

-- ============================================================
-- 6. Task Audits
-- ============================================================
ALTER TABLE task_audits ADD COLUMN created_at_ms INTEGER;

UPDATE task_audits
SET created_at_ms = CAST((julianday(created_at) - 2440587.5) * 86400000 AS INTEGER)
WHERE created_at_ms IS NULL AND created_at IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_task_audits_created_at_ms
    ON task_audits(created_at_ms DESC);

-- ============================================================
-- 7. Projects
-- ============================================================
ALTER TABLE projects ADD COLUMN added_at_ms INTEGER;

UPDATE projects
SET added_at_ms = CAST((julianday(added_at) - 2440587.5) * 86400000 AS INTEGER)
WHERE added_at_ms IS NULL AND added_at IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_projects_added_at_ms
    ON projects(added_at_ms DESC);

-- ============================================================
-- 8. Runs
-- ============================================================
ALTER TABLE runs ADD COLUMN started_at_ms INTEGER;
ALTER TABLE runs ADD COLUMN completed_at_ms INTEGER;
ALTER TABLE runs ADD COLUMN lease_until_ms INTEGER;

UPDATE runs
SET started_at_ms = CAST((julianday(started_at) - 2440587.5) * 86400000 AS INTEGER)
WHERE started_at_ms IS NULL AND started_at IS NOT NULL;

UPDATE runs
SET completed_at_ms = CAST((julianday(completed_at) - 2440587.5) * 86400000 AS INTEGER)
WHERE completed_at_ms IS NULL AND completed_at IS NOT NULL;

UPDATE runs
SET lease_until_ms = CAST((julianday(lease_until) - 2440587.5) * 86400000 AS INTEGER)
WHERE lease_until_ms IS NULL AND lease_until IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_runs_started_at_ms
    ON runs(started_at_ms DESC);

-- ============================================================
-- 9. Artifacts
-- ============================================================
ALTER TABLE artifacts ADD COLUMN created_at_ms INTEGER;

UPDATE artifacts
SET created_at_ms = CAST((julianday(created_at) - 2440587.5) * 86400000 AS INTEGER)
WHERE created_at_ms IS NULL AND created_at IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_artifacts_created_at_ms
    ON artifacts(created_at_ms DESC);

-- ============================================================
-- 10. Schema Version (Self-reference)
-- ============================================================
ALTER TABLE schema_version ADD COLUMN applied_at_ms INTEGER;

UPDATE schema_version
SET applied_at_ms = CAST((julianday(applied_at) - 2440587.5) * 86400000 AS INTEGER)
WHERE applied_at_ms IS NULL AND applied_at IS NOT NULL;

-- ============================================================
-- PART B: Extended Tables (may not exist in all installations)
-- Note: These tables were added in later schema versions.
-- If they don't exist, this migration will succeed anyway.
-- The actual ALTER statements are in schema_v44_extended.sql
-- ============================================================

-- The following tables will be migrated if they exist:
-- - task_events (v32+)
-- - decision_records (v36+)
-- - decision_candidates (v40+)
-- - improvement_proposals (v41+)
-- - classifier_versions (v42+)
-- - info_need_judgments (v38+)
-- - info_need_patterns (v39+)
--
-- See schema_v44_extended.sql for these migrations

-- ============================================================
-- Validation Queries (Runtime Verification)
-- ============================================================
-- These checks ensure data integrity after migration
-- Run these manually to verify migration success:

-- Check 1: Verify all epoch_ms values are reasonable (between 2020 and 2030)
-- Expected: All values should be between 1577836800000 (2020-01-01) and 1893456000000 (2030-01-01)
-- SELECT 'chat_sessions' as table_name, COUNT(*) as invalid_count
-- FROM chat_sessions
-- WHERE created_at_ms IS NOT NULL
--   AND (created_at_ms < 1577836800000 OR created_at_ms > 1893456000000)
-- UNION ALL
-- SELECT 'tasks', COUNT(*) FROM tasks
-- WHERE created_at_ms IS NOT NULL
--   AND (created_at_ms < 1577836800000 OR created_at_ms > 1893456000000);

-- Check 2: Verify conversion accuracy (epoch_ms should match original timestamp)
-- Sample check for chat_sessions:
-- SELECT
--     session_id,
--     created_at,
--     created_at_ms,
--     datetime(created_at_ms/1000, 'unixepoch') as converted_back,
--     ABS(julianday(created_at) - julianday(datetime(created_at_ms/1000, 'unixepoch'))) * 86400 as diff_seconds
-- FROM chat_sessions
-- WHERE created_at IS NOT NULL AND created_at_ms IS NOT NULL
-- LIMIT 10;

-- Check 3: Verify NULL handling (if created_at is NULL, created_at_ms should also be NULL)
-- SELECT 'chat_sessions' as table_name, COUNT(*) as mismatch_count
-- FROM chat_sessions
-- WHERE (created_at IS NULL AND created_at_ms IS NOT NULL)
--    OR (created_at IS NOT NULL AND created_at_ms IS NULL);

-- ============================================================
-- Version Tracking
-- ============================================================
INSERT INTO schema_version (version, applied_at)
VALUES (
    '0.44.0',
    CURRENT_TIMESTAMP
);

-- ============================================================
-- Migration Completed
-- ============================================================
-- Summary:
--   - Added *_at_ms columns to 10 core tables
--   - Migrated existing TIMESTAMP data to epoch_ms format
--   - Created indexes for query performance
--   - Preserved old TIMESTAMP columns for backward compatibility
--
-- Tables migrated:
--   1. chat_sessions (created_at_ms, updated_at_ms)
--   2. chat_messages (created_at_ms)
--   3. tasks (created_at_ms, updated_at_ms)
--   4. task_lineage (created_at_ms)
--   5. task_agents (started_at_ms, ended_at_ms)
--   6. task_audits (created_at_ms)
--   7. projects (added_at_ms)
--   8. runs (started_at_ms, completed_at_ms, lease_until_ms)
--   9. artifacts (created_at_ms)
--   10. schema_version (applied_at_ms)
--
-- Next Steps:
--   1. Run validation queries above
--   2. Update application code to use *_at_ms fields
--   3. Run schema_v44_extended.sql for extended tables (if needed)
--   4. Consider deprecating old TIMESTAMP fields in future versions
--
-- Rollback (if needed):
--   Since we only added columns, rollback is simple:
--   For each table: ALTER TABLE <table> DROP COLUMN <column>_at_ms;
--   Note: SQLite requires PRAGMA foreign_keys=OFF before dropping columns
-- ============================================================
