-- Migration v0.53: Rename projects.id to projects.project_id
-- Description: Fix column name mismatch between schema and API code
-- Purpose: Align projects table primary key name with API expectations
-- Migration from v0.52 -> v0.53
--
-- Background:
--   - v01 created projects table with 'id' as primary key
--   - v31 attempted to redefine with 'project_id' but CREATE IF NOT EXISTS skipped it
--   - API code expects 'project_id' column name
--   - Foreign key references use projects(id) which will auto-update
--
-- Risk:
--   - ALTER TABLE RENAME COLUMN requires SQLite 3.25.0+ (2018-09-15)
--   - Foreign key references remain valid (SQLite auto-updates them)
--
-- target_db: agentos

PRAGMA foreign_keys = OFF;

-- Rename the primary key column
ALTER TABLE projects RENAME COLUMN id TO project_id;

PRAGMA foreign_keys = ON;

-- Update schema version
INSERT OR REPLACE INTO schema_version (version, applied_at_ms, description)
VALUES ('0.53.0', (strftime('%s', 'now') * 1000), 'Rename projects.id to project_id');
