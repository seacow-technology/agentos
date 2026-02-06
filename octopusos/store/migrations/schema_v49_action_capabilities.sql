-- Schema v49: Action Capabilities and Side Effects Tracking
--
-- Description: Complete schema for Action Domain
--
-- Tables:
-- 1. action_execution_log - Full action execution records
-- 2. action_side_effects - Side effects tracking (declared vs actual)
-- 3. action_side_effects_individual - Individual side effect records
-- 4. action_rollback_history - Rollback execution history
-- 5. action_replay_log - Replay execution logs
--
-- Design Principles:
-- - Every action MUST link to a frozen decision_id
-- - Side effects MUST be declared before execution
-- - Evidence MUST be recorded for every execution
-- - All timestamps use epoch_ms (ADR-011)
-- - Rollback and replay are fully audited
--
-- Migration: v48 -> v49
-- Compatible with: AgentOS v3.0

-- ===================================================================
-- 1. Action Execution Log
-- ===================================================================

CREATE TABLE IF NOT EXISTS action_execution_log (
    execution_id TEXT PRIMARY KEY,
    action_id TEXT NOT NULL,          -- Action capability ID
    params_json TEXT NOT NULL,        -- Action parameters
    decision_id TEXT NOT NULL,        -- REQUIRED: Link to frozen decision
    agent_id TEXT NOT NULL,           -- Agent executing the action

    status TEXT NOT NULL DEFAULT 'pending',  -- pending|running|success|failure|cancelled|rolled_back
    result_json TEXT,                 -- Execution result (if success)
    error_message TEXT,               -- Error message (if failure)

    started_at_ms INTEGER NOT NULL,   -- Execution start (epoch ms)
    completed_at_ms INTEGER,          -- Execution completion (epoch ms)
    duration_ms INTEGER,              -- Execution duration (ms)

    evidence_id TEXT,                 -- Link to evidence record
    rollback_plan_json TEXT,          -- Rollback plan (if reversible)
    is_reversible INTEGER DEFAULT 0,  -- Whether action is reversible

    risk_level TEXT DEFAULT 'high',   -- low|medium|high|critical
    governance_approved INTEGER DEFAULT 0,  -- Whether governance approved

    metadata_json TEXT,               -- Additional metadata

    -- Indexes
    CHECK (status IN ('pending', 'running', 'success', 'failure', 'cancelled', 'rolled_back')),
    CHECK (risk_level IN ('low', 'medium', 'high', 'critical')),
    FOREIGN KEY (decision_id) REFERENCES decision_plans(plan_id)
);

CREATE INDEX IF NOT EXISTS idx_action_execution_decision
ON action_execution_log(decision_id);

CREATE INDEX IF NOT EXISTS idx_action_execution_agent
ON action_execution_log(agent_id, started_at_ms DESC);

CREATE INDEX IF NOT EXISTS idx_action_execution_status
ON action_execution_log(status, started_at_ms DESC);

CREATE INDEX IF NOT EXISTS idx_action_execution_action_id
ON action_execution_log(action_id, started_at_ms DESC);

CREATE INDEX IF NOT EXISTS idx_action_execution_evidence
ON action_execution_log(evidence_id);


-- ===================================================================
-- 2. Action Side Effects (Aggregate)
-- ===================================================================

CREATE TABLE IF NOT EXISTS action_side_effects (
    execution_id TEXT PRIMARY KEY,

    declared_effects_json TEXT NOT NULL DEFAULT '[]',  -- Declared side effects
    actual_effects_json TEXT NOT NULL DEFAULT '[]',    -- Actual side effects
    unexpected_effects_json TEXT,                       -- Unexpected side effects (security!)

    declared_at_ms INTEGER NOT NULL,  -- When declared (epoch ms)
    tracked_at_ms INTEGER NOT NULL,   -- When actual effects tracked (epoch ms)

    -- Indexes
    FOREIGN KEY (execution_id) REFERENCES action_execution_log(execution_id)
);

CREATE INDEX IF NOT EXISTS idx_action_side_effects_unexpected
ON action_side_effects(unexpected_effects_json)
WHERE unexpected_effects_json IS NOT NULL AND unexpected_effects_json != '[]';


-- ===================================================================
-- 3. Action Side Effects (Individual Records)
-- ===================================================================

CREATE TABLE IF NOT EXISTS action_side_effects_individual (
    side_effect_id INTEGER PRIMARY KEY AUTOINCREMENT,
    execution_id TEXT NOT NULL,

    effect_type TEXT NOT NULL,        -- Side effect type (enum value)
    was_declared INTEGER NOT NULL,    -- Whether this was declared
    details_json TEXT,                -- Side effect details

    timestamp_ms INTEGER NOT NULL,    -- When occurred (epoch ms)
    severity TEXT NOT NULL DEFAULT 'medium',  -- low|medium|high|critical

    -- Indexes
    FOREIGN KEY (execution_id) REFERENCES action_execution_log(execution_id)
);

CREATE INDEX IF NOT EXISTS idx_side_effects_individual_execution
ON action_side_effects_individual(execution_id, timestamp_ms);

CREATE INDEX IF NOT EXISTS idx_side_effects_individual_type
ON action_side_effects_individual(effect_type);

CREATE INDEX IF NOT EXISTS idx_side_effects_individual_undeclared
ON action_side_effects_individual(was_declared)
WHERE was_declared = 0;


-- ===================================================================
-- 4. Action Rollback History
-- ===================================================================

CREATE TABLE IF NOT EXISTS action_rollback_history (
    rollback_id TEXT PRIMARY KEY,
    original_execution_id TEXT NOT NULL,  -- Original execution being rolled back
    rollback_execution_id TEXT,           -- Execution ID of rollback action

    rollback_plan_json TEXT NOT NULL,     -- Rollback plan used
    rollback_status TEXT NOT NULL DEFAULT 'pending',  -- pending|success|failure|partial|not_applicable
    rollback_reason TEXT NOT NULL,        -- Why rollback was initiated

    initiated_by TEXT NOT NULL,           -- Agent/user who initiated
    initiated_at_ms INTEGER NOT NULL,     -- When initiated (epoch ms)
    completed_at_ms INTEGER,              -- When completed (epoch ms)

    result_json TEXT,                     -- Rollback result
    error_message TEXT,                   -- Error message (if failure)

    -- Indexes
    CHECK (rollback_status IN ('pending', 'success', 'failure', 'partial', 'not_applicable')),
    FOREIGN KEY (original_execution_id) REFERENCES action_execution_log(execution_id),
    FOREIGN KEY (rollback_execution_id) REFERENCES action_execution_log(execution_id)
);

CREATE INDEX IF NOT EXISTS idx_rollback_original
ON action_rollback_history(original_execution_id, initiated_at_ms DESC);

CREATE INDEX IF NOT EXISTS idx_rollback_status
ON action_rollback_history(rollback_status);

CREATE INDEX IF NOT EXISTS idx_rollback_initiated_by
ON action_rollback_history(initiated_by, initiated_at_ms DESC);


-- ===================================================================
-- 5. Action Replay Log
-- ===================================================================

CREATE TABLE IF NOT EXISTS action_replay_log (
    replay_id TEXT PRIMARY KEY,
    original_execution_id TEXT NOT NULL,  -- Original execution being replayed
    replay_mode TEXT NOT NULL,            -- dry_run|actual|compare

    original_result_json TEXT,            -- Original execution result
    replay_result_json TEXT,              -- Replay execution result
    differences_json TEXT,                -- Differences found

    replayed_by TEXT NOT NULL,            -- Agent who initiated replay
    replayed_at_ms INTEGER NOT NULL,      -- When replayed (epoch ms)
    duration_ms INTEGER,                  -- Replay duration (ms)

    -- Indexes
    CHECK (replay_mode IN ('dry_run', 'actual', 'compare')),
    FOREIGN KEY (original_execution_id) REFERENCES action_execution_log(execution_id)
);

CREATE INDEX IF NOT EXISTS idx_replay_original
ON action_replay_log(original_execution_id, replayed_at_ms DESC);

CREATE INDEX IF NOT EXISTS idx_replay_mode
ON action_replay_log(replay_mode);

CREATE INDEX IF NOT EXISTS idx_replay_by
ON action_replay_log(replayed_by, replayed_at_ms DESC);


-- ===================================================================
-- 6. Evidence Records (if not exists from Evidence Domain)
-- ===================================================================

CREATE TABLE IF NOT EXISTS evidence_records (
    evidence_id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,        -- Type of entity (e.g., 'action_execution')
    entity_id TEXT NOT NULL,          -- Entity ID
    event_type TEXT NOT NULL,         -- Event type (e.g., 'action.executed')

    data_json TEXT NOT NULL,          -- Evidence data
    created_at_ms INTEGER NOT NULL,   -- When created (epoch ms)

    checksum TEXT,                    -- Data integrity checksum
    signature TEXT,                   -- Cryptographic signature (optional)

    -- Indexes
    UNIQUE (entity_type, entity_id, event_type, created_at_ms)
);

CREATE INDEX IF NOT EXISTS idx_evidence_entity
ON evidence_records(entity_type, entity_id);

CREATE INDEX IF NOT EXISTS idx_evidence_event
ON evidence_records(event_type, created_at_ms DESC);


-- ===================================================================
-- Data Integrity Views
-- ===================================================================

-- View: Executions with side effect compliance
CREATE VIEW IF NOT EXISTS v_action_compliance AS
SELECT
    ael.execution_id,
    ael.action_id,
    ael.agent_id,
    ael.status,
    ael.started_at_ms,
    ase.declared_effects_json,
    ase.actual_effects_json,
    ase.unexpected_effects_json,
    CASE
        WHEN ase.unexpected_effects_json IS NULL OR ase.unexpected_effects_json = '[]' THEN 1
        ELSE 0
    END AS is_compliant
FROM action_execution_log ael
LEFT JOIN action_side_effects ase ON ael.execution_id = ase.execution_id;

-- View: Rollback success rate
CREATE VIEW IF NOT EXISTS v_rollback_stats AS
SELECT
    COUNT(*) AS total_rollbacks,
    SUM(CASE WHEN rollback_status = 'success' THEN 1 ELSE 0 END) AS successful_rollbacks,
    SUM(CASE WHEN rollback_status = 'failure' THEN 1 ELSE 0 END) AS failed_rollbacks,
    SUM(CASE WHEN rollback_status = 'not_applicable' THEN 1 ELSE 0 END) AS irreversible_actions,
    ROUND(
        SUM(CASE WHEN rollback_status = 'success' THEN 1.0 ELSE 0 END) * 100.0 / COUNT(*),
        2
    ) AS success_rate_percent
FROM action_rollback_history;

-- View: Replay comparison results
CREATE VIEW IF NOT EXISTS v_replay_results AS
SELECT
    replay_id,
    original_execution_id,
    replay_mode,
    CASE
        WHEN differences_json IS NULL OR differences_json = '{}' THEN 1
        ELSE 0
    END AS results_match,
    replayed_by,
    replayed_at_ms
FROM action_replay_log;


-- ===================================================================
-- Migration Metadata
-- ===================================================================

-- Note: description column is added in v50.5, and applied_at_ms is added in v44
-- v49 should use applied_at_ms (from v44), but not description yet
INSERT INTO schema_version (version, applied_at_ms)
VALUES (
    49,
    strftime('%s', 'now') * 1000
)
ON CONFLICT(version) DO UPDATE SET
    applied_at_ms = excluded.applied_at_ms;


-- ===================================================================
-- Verification Queries
-- ===================================================================

-- Count tables
SELECT 'action_execution_log' AS table_name, COUNT(*) AS row_count FROM action_execution_log
UNION ALL
SELECT 'action_side_effects', COUNT(*) FROM action_side_effects
UNION ALL
SELECT 'action_side_effects_individual', COUNT(*) FROM action_side_effects_individual
UNION ALL
SELECT 'action_rollback_history', COUNT(*) FROM action_rollback_history
UNION ALL
SELECT 'action_replay_log', COUNT(*) FROM action_replay_log;


-- ===================================================================
-- Sample Data (for testing)
-- ===================================================================

-- Insert sample action execution (commented out for production)
-- INSERT INTO action_execution_log (
--     execution_id, action_id, params_json, decision_id, agent_id,
--     status, started_at_ms, risk_level, governance_approved
-- ) VALUES (
--     'exec-sample-001',
--     'action.execute.local',
--     '{"command": "echo test"}',
--     'decision-sample-001',
--     'system_agent',
--     'success',
--     strftime('%s', 'now') * 1000,
--     'low',
--     1
-- );
