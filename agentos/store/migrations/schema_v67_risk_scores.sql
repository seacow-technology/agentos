-- Schema v67: Risk Score Storage
-- Phase D2: Risk Score v0 (History-based)
--
-- Stores calculated risk scores for extensions to enable:
-- 1. Historical risk tracking over time
-- 2. Trend analysis and anomaly detection
-- 3. Fast risk lookups without recalculation
-- 4. Audit trail of risk assessments
--
-- Created: 2026-02-02
-- Author: Phase D2 Implementation

-- =============================================================================
-- Risk Score History Table
-- =============================================================================
-- Records historical risk scores calculated for extensions.
-- Each calculation is timestamped and includes all dimension details.

CREATE TABLE IF NOT EXISTS risk_scores (
    -- Primary key
    score_id TEXT PRIMARY KEY,                 -- UUID v7-style identifier (risk-YYYYMMDDHHMMSS-NNNN)

    -- Target
    extension_id TEXT NOT NULL,                -- Extension identifier
    action_id TEXT NOT NULL,                   -- Action identifier (or '*' for all actions)

    -- Risk score
    score REAL NOT NULL,                       -- Risk score value (0-100)
    level TEXT NOT NULL,                       -- Risk level: 'LOW', 'MEDIUM', 'HIGH'

    -- Dimension breakdown
    dimensions TEXT NOT NULL,                  -- JSON: dimension name -> normalized value (0-1)
    explanation TEXT,                          -- Human-readable explanation

    -- Calculation metadata
    window_days INTEGER NOT NULL,              -- Historical window used (days)
    sample_size INTEGER NOT NULL,              -- Number of executions analyzed
    calculated_at INTEGER NOT NULL,            -- Calculation timestamp (epoch ms)

    -- Record metadata
    created_at INTEGER NOT NULL                -- Record creation timestamp (epoch ms)
);

-- =============================================================================
-- Indexes for Performance
-- =============================================================================

-- Lookup by extension and action
CREATE INDEX IF NOT EXISTS idx_risk_scores_extension
ON risk_scores(extension_id, action_id);

-- Chronological ordering
CREATE INDEX IF NOT EXISTS idx_risk_scores_calculated
ON risk_scores(calculated_at DESC);

-- Risk level filtering
CREATE INDEX IF NOT EXISTS idx_risk_scores_level
ON risk_scores(level);

-- =============================================================================
-- Schema Version Record
-- =============================================================================

INSERT INTO schema_version (version, description)
VALUES ('0.67.0', 'Risk score storage for extension governance (Phase D2)');
