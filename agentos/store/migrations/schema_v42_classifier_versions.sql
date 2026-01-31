-- schema_v42_classifier_versions.sql
-- Migration for ClassifierVersion management infrastructure
-- Task #10: Implement Classifier Version Management Tool
--
-- NOTE: classifier_versions table is created in v40 (Task #28)
-- This migration adds supporting tables for version management
-- v43 will merge v40 + v42 requirements into unified table structure

-- Version rollback history table
-- Tracks all rollback operations for audit purposes
CREATE TABLE IF NOT EXISTS version_rollback_history (
    rollback_id TEXT PRIMARY KEY,

    -- Rollback details
    from_version_id TEXT NOT NULL,  -- Version being rolled back from
    to_version_id TEXT NOT NULL,    -- Version being restored

    -- Reason and metadata
    reason TEXT NOT NULL,
    performed_by TEXT NOT NULL,
    performed_at TEXT NOT NULL,
    metadata TEXT NOT NULL DEFAULT '{}',  -- JSON

    CONSTRAINT valid_rollback_id CHECK (rollback_id LIKE 'rollback-%'),
    FOREIGN KEY (from_version_id) REFERENCES classifier_versions(version_id),
    FOREIGN KEY (to_version_id) REFERENCES classifier_versions(version_id)
);

-- Indexes for rollback history
CREATE INDEX IF NOT EXISTS idx_rollback_history_performed_at
    ON version_rollback_history(performed_at DESC);

CREATE INDEX IF NOT EXISTS idx_rollback_history_from_version
    ON version_rollback_history(from_version_id, performed_at DESC);

CREATE INDEX IF NOT EXISTS idx_rollback_history_to_version
    ON version_rollback_history(to_version_id, performed_at DESC);

-- Update schema version
INSERT INTO schema_version (version, applied_at)
VALUES (
    '0.42.0',
    CURRENT_TIMESTAMP
);
