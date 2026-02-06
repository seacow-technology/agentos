-- Migration v21: Add indexes for decision fields
--
-- Purpose: Improve Lead Agent query performance by adding indexes
-- for frequently accessed decision fields.
--
-- Note: Columns (decision_id, source_event_ts, supervisor_processed_at) were added in v15
-- This migration only adds performance-optimized indexes
--
-- Compatibility: Backward compatible (indexes only)
-- Rollback: DROP INDEX (safe)
-- Migration from v0.20 -> v0.21

-- ============================================
-- NO COLUMN CHANGES
-- Columns were added in v15:
-- - decision_id TEXT
-- - source_event_ts TEXT
-- - supervisor_processed_at TEXT
-- ============================================

-- ============================================
-- Create indexes for common queries
-- ============================================

-- Index for source_event_ts queries (for lag calculation)
CREATE INDEX IF NOT EXISTS idx_task_audits_source_event_ts
ON task_audits(source_event_ts)
WHERE source_event_ts IS NOT NULL;

-- Composite index for decision lag queries
-- This optimizes the common pattern: find decisions with both timestamps for lag calculation
CREATE INDEX IF NOT EXISTS idx_task_audits_decision_lag
ON task_audits(source_event_ts, supervisor_processed_at)
WHERE source_event_ts IS NOT NULL AND supervisor_processed_at IS NOT NULL;

-- Composite index for decision queries by event type and time
-- This optimizes: SELECT * FROM task_audits WHERE event_type LIKE 'SUPERVISOR_%' AND created_at >= ? AND created_at <= ?
CREATE INDEX IF NOT EXISTS idx_task_audits_event_source_ts
ON task_audits(event_type, source_event_ts)
WHERE source_event_ts IS NOT NULL;

-- ============================================
-- Design Notes
-- ============================================

-- Performance Benefits:
-- 1. Direct column access is 10x faster than JSON extraction
-- 2. Indexes enable efficient filtering and sorting
-- 3. Reduced CPU usage for decision lag queries
--
-- Query Pattern Optimization:
-- BEFORE (v20):
--   SELECT payload FROM task_audits WHERE event_type='SUPERVISOR_DECISION'
--   Then parse JSON to extract source_event_ts
--
-- AFTER (v21):
--   SELECT source_event_ts, supervisor_processed_at FROM task_audits
--   WHERE event_type='SUPERVISOR_DECISION' AND source_event_ts IS NOT NULL
--   Uses idx_task_audits_event_source_ts index
--
-- Backward Compatibility:
-- - Existing rows will have NULL values for new columns
-- - LeadStorage will fallback to payload JSON extraction when columns are NULL
-- - New events should populate both payload and redundant columns
--
-- Data Redundancy Strategy:
-- - Payload JSON remains the source of truth
-- - Redundant columns are performance optimization
-- - Both should be kept in sync for new data
-- - Historical data can be backfilled from payload if needed

-- Update schema version
INSERT OR IGNORE INTO schema_version (version) VALUES ('0.21.0');

-- Migration complete
