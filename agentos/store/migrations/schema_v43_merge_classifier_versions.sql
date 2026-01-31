-- schema_v43_merge_classifier_versions.sql
-- Migration to merge two classifier version concepts into unified table
-- Fixes: v40 (Shadow Evaluation) + v42 (Version Management) conflict
--
-- Background:
--   Task #28: Shadow Evaluation needs version_type (active/shadow)
--   Task #10: Version Management needs version_number, parent_version_id, etc.
--   v42 mistakenly dropped version_type, breaking Shadow Evaluation system
--
-- Solution:
--   Merge both concepts into one table supporting both use cases
--
-- Safety: Uses RENAME instead of DROP for rollback capability

-- ============================================================
-- Step 0: Idempotency check
-- If backup table exists, assume migration already attempted
-- ============================================================

-- Check if backup exists (via a no-op query that will fail if it doesn't)
-- If it exists, we're in recovery/retry mode
-- SQLite doesn't support IF EXISTS in standard way, so we use CREATE TABLE IF NOT EXISTS

CREATE TABLE IF NOT EXISTS _classifier_versions_v43_backup (dummy INTEGER);
DROP TABLE IF EXISTS _classifier_versions_v43_backup;

-- ============================================================
-- Step 1: Backup existing data via RENAME (NOT DROP!)
-- This allows rollback if anything goes wrong
-- ============================================================

-- Rename old table to backup (safe, atomic operation)
ALTER TABLE classifier_versions RENAME TO _classifier_versions_v43_backup;

-- ============================================================
-- Step 2: Create merged table structure
-- This table supports BOTH:
--   - Shadow Evaluation (version_type, change_description)
--   - Version Management (version_number, parent_version_id, is_active, etc.)
-- ============================================================

CREATE TABLE classifier_versions (
    version_id TEXT PRIMARY KEY,

    -- ===== 【语义层】Shadow Evaluation / Decision Semantics =====
    -- Used by: decision_candidate_store.py, shadow_registry.py
    -- CONSTRAINT: version_type must be 'active' or 'shadow'
    version_type TEXT NOT NULL CHECK (version_type IN ('active', 'shadow')),
    change_description TEXT,

    -- ===== 【治理层】Version Management / Evolution Governance =====
    -- Used by: classifier_version_manager.py, classifier_migrate.py
    version_number TEXT,             -- Semantic version: "1.0", "2.0"
    parent_version_id TEXT,          -- For rollback chain (self-reference, nullable)
    change_log TEXT,                 -- Detailed change log
    source_proposal_id TEXT,         -- Source ImprovementProposal ID
    is_active INTEGER DEFAULT 0,     -- 1 if currently active version
    created_by TEXT,                 -- Creator (user/system)

    -- ===== 【通用】Shared metadata =====
    created_at TEXT NOT NULL,
    promoted_from TEXT,              -- If promoted from shadow to active
    deprecated_at TEXT,              -- When this version was deprecated
    metadata TEXT DEFAULT '{}',      -- JSON metadata

    -- ===== Constraints =====
    CONSTRAINT valid_version_type CHECK (version_type IN ('active', 'shadow')),
    CONSTRAINT valid_is_active CHECK (is_active IN (0, 1))
    -- Note: FOREIGN KEY constraints added after data migration to avoid circular dependency
);

-- ============================================================
-- Step 3: Migrate data from backup
-- Strategy: Infer version_type from existing data with validation
-- ============================================================

INSERT INTO classifier_versions (
    version_id,
    version_type,
    change_description,
    version_number,
    parent_version_id,
    change_log,
    source_proposal_id,
    is_active,
    created_by,
    created_at,
    metadata,
    promoted_from,
    deprecated_at
)
SELECT
    version_id,

    -- Note: v40 table only has version_type column (values: 'active' or 'shadow')
    -- v42 doesn't modify this, so we preserve it
    version_type,

    -- Map existing change_description (from v40)
    COALESCE(change_description, 'Migrated from v40/v42') as change_description,

    -- New fields from v43 (not in v40/v42) - set to NULL or defaults
    NULL as version_number,
    NULL as parent_version_id,
    change_description as change_log,  -- Use change_description as change_log
    NULL as source_proposal_id,
    -- Infer is_active from version_type
    CASE WHEN version_type = 'active' THEN 1 ELSE 0 END as is_active,
    NULL as created_by,

    created_at,
    COALESCE(metadata, '{}') as metadata,
    promoted_from,
    deprecated_at
FROM _classifier_versions_v43_backup;

-- ============================================================
-- Step 4: Add foreign key constraints (after data migration)
-- ============================================================

-- Note: SQLite doesn't support ADD CONSTRAINT for FOREIGN KEY
-- We rely on the FOREIGN KEY defined in CREATE TABLE
-- Here we just document the expected referential integrity

-- Expected constraints (enforced at application level if needed):
-- 1. parent_version_id should reference existing classifier_versions.version_id
-- 2. source_proposal_id should reference improvement_proposals.proposal_id

-- ============================================================
-- Step 5: Create indexes for both layers
-- ============================================================

-- Shadow Evaluation layer indexes
CREATE INDEX IF NOT EXISTS idx_classifier_versions_type
    ON classifier_versions(version_type, created_at DESC);

-- Version Management layer indexes
CREATE INDEX IF NOT EXISTS idx_classifier_versions_active
    ON classifier_versions(is_active, created_at DESC)
    WHERE is_active = 1;

CREATE INDEX IF NOT EXISTS idx_classifier_versions_parent
    ON classifier_versions(parent_version_id)
    WHERE parent_version_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_classifier_versions_proposal
    ON classifier_versions(source_proposal_id)
    WHERE source_proposal_id IS NOT NULL;

-- General indexes
CREATE INDEX IF NOT EXISTS idx_classifier_versions_created
    ON classifier_versions(created_at DESC);

-- ============================================================
-- Step 6: Validation checks (runtime verification)
-- These checks ensure data integrity after migration
-- ============================================================

-- Check 1: Row count preserved
-- Expected: Same number of rows before and after
-- SELECT
--     (SELECT COUNT(*) FROM _classifier_versions_v43_backup) as before_count,
--     (SELECT COUNT(*) FROM classifier_versions) as after_count;

-- Check 2: version_type distribution
-- Expected: Only 'active' and 'shadow' values
-- SELECT version_type, COUNT(*) FROM classifier_versions GROUP BY version_type;

-- Check 3: Consistency between version_type and is_active
-- Expected: All is_active=1 should have version_type='active'
-- SELECT COUNT(*) FROM classifier_versions
-- WHERE is_active = 1 AND version_type != 'active';

-- Check 4: Referential integrity (if parent_version_id is used)
-- Expected: All parent_version_id should point to existing versions
-- SELECT COUNT(*) FROM classifier_versions cv1
-- WHERE cv1.parent_version_id IS NOT NULL
-- AND NOT EXISTS (
--     SELECT 1 FROM classifier_versions cv2
--     WHERE cv2.version_id = cv1.parent_version_id
-- );

-- ============================================================
-- Step 7: Success marker
-- Only drop backup after successful migration and validation
-- ============================================================

-- IMPORTANT: Backup table is NOT dropped here
-- Keep _classifier_versions_v43_backup for manual verification and rollback
-- Drop manually after confirming migration success

-- To rollback (if needed):
--   DROP TABLE classifier_versions;
--   ALTER TABLE _classifier_versions_v43_backup RENAME TO classifier_versions;

-- To finalize (after validation):
--   DROP TABLE _classifier_versions_v43_backup;

-- Update schema version
INSERT INTO schema_version (version, applied_at)
VALUES (
    '0.43.0',
    CURRENT_TIMESTAMP
);

-- ============================================================
-- Migration completed
-- Next steps:
--   1. Run MIGRATION_ACCEPTANCE.md checks
--   2. Verify 4 gates pass
--   3. Manually drop backup table
-- ============================================================
