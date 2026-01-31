-- Migration v36: Decision Records and Governance Tables
-- Date: 2026-01-31
-- Purpose: Add decision_records and decision_signoffs tables for BrainOS Governance (P4)
-- Gate: Gate 3 - No SQL Schema in Code

-- ============================================
-- Decision Records Table
-- ============================================

CREATE TABLE IF NOT EXISTS decision_records (
    decision_id TEXT PRIMARY KEY,
    decision_type TEXT NOT NULL,
    seed TEXT NOT NULL,
    inputs TEXT NOT NULL,
    outputs TEXT NOT NULL,
    rules_triggered TEXT NOT NULL,
    final_verdict TEXT NOT NULL,
    confidence_score REAL NOT NULL,
    timestamp TEXT NOT NULL,
    snapshot_ref TEXT,
    signed_by TEXT,
    sign_timestamp TEXT,
    sign_note TEXT,
    status TEXT NOT NULL,
    record_hash TEXT NOT NULL,

    CHECK (status IN ('PENDING', 'APPROVED', 'BLOCKED', 'SIGNED', 'FAILED'))
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_decision_records_seed
ON decision_records(seed);

CREATE INDEX IF NOT EXISTS idx_decision_records_type
ON decision_records(decision_type);

CREATE INDEX IF NOT EXISTS idx_decision_records_timestamp
ON decision_records(timestamp);

CREATE INDEX IF NOT EXISTS idx_decision_records_status
ON decision_records(status);

-- ============================================
-- Decision Signoffs Table
-- ============================================

CREATE TABLE IF NOT EXISTS decision_signoffs (
    signoff_id TEXT PRIMARY KEY,
    decision_id TEXT NOT NULL,
    signed_by TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    note TEXT NOT NULL,

    FOREIGN KEY (decision_id) REFERENCES decision_records(decision_id)
);

CREATE INDEX IF NOT EXISTS idx_decision_signoffs_decision_id
ON decision_signoffs(decision_id);

-- ============================================
-- Record Migration
-- ============================================

INSERT INTO schema_migrations (migration_id, description, status, metadata)
VALUES (
    'v36_decision_records',
    'Add decision_records and decision_signoffs tables for BrainOS Governance',
    'success',
    json_object(
        'migration_date', datetime('now'),
        'tables_added', json_array('decision_records', 'decision_signoffs'),
        'purpose', 'BrainOS Governance Layer (P4) - Decision Record System'
    )
);

-- ============================================
-- Version Tracking
-- ============================================

INSERT OR REPLACE INTO schema_version (version, applied_at)
VALUES ('0.36.0', datetime('now'));
