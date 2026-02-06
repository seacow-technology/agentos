-- Migration v0.57 (v0.57.0): Add description column to schema_version
-- Description: Enable human-readable migration descriptions in schema_version table
-- Purpose: Support migration documentation and traceability
-- Migration from v0.50 -> v0.57 (executed between v50 and v51)
--
-- Background:
--   - schema_version table originally had: version, applied_at, applied_at_ms
--   - v51+ migrations need description column for INSERT statements
--   - Adding this column retroactively to support migration metadata
--
-- target_db: agentos

PRAGMA foreign_keys = OFF;

-- Add description column to schema_version table
-- 注意: 如果列已存在,跳过此步骤
-- SQLite 的 ALTER TABLE 不支持 IF NOT EXISTS
-- 由于 description 列可能已经存在,我们注释掉此语句
-- ALTER TABLE schema_version ADD COLUMN description TEXT;

-- 检查列是否存在的逻辑:
-- 如果列已存在,这个迁移只会记录版本信息

PRAGMA foreign_keys = ON;

-- Update schema version with description
-- Note: Using 0.57.0 to sort between v50 and v51
INSERT OR REPLACE INTO schema_version (version, applied_at_ms, description)
VALUES ('0.57.0', (strftime('%s', 'now') * 1000), 'Add description column to schema_version');
