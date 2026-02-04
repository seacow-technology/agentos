-- Schema v70: Trust Trajectory
--
-- This migration adds tables for Trust Trajectory tracking (Phase E - E2):
-- 1. trust_states - Current trust state for each extension/action
-- 2. trust_transitions - Audit trail of all state transitions
-- 3. trust_trajectory_rules - Rules governing state transitions
--
-- Design Principles:
-- - States must transition sequentially (EARNING → STABLE → DEGRADING)
-- - All transitions must have audit trail with explain
-- - Time inertia prevents instant state changes
-- - No manual state overrides allowed
--
-- Red Lines:
-- - No jumping states (EARNING → DEGRADING forbidden)
-- - No instant recovery (DEGRADING → STABLE forbidden)
-- - All transitions must reference specific events

-- ===================================================================
-- Current Trust States
-- ===================================================================

CREATE TABLE IF NOT EXISTS trust_states (
    extension_id TEXT NOT NULL,
    action_id TEXT NOT NULL DEFAULT '*',
    current_state TEXT NOT NULL,                -- EARNING|STABLE|DEGRADING
    consecutive_successes INTEGER NOT NULL DEFAULT 0,
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    policy_rejections INTEGER NOT NULL DEFAULT 0,
    high_risk_events INTEGER NOT NULL DEFAULT 0,
    state_entered_at_ms INTEGER NOT NULL,       -- When current state was entered
    last_event_at_ms INTEGER NOT NULL,          -- Last event affecting state
    updated_at_ms INTEGER NOT NULL,

    PRIMARY KEY (extension_id, action_id),

    CHECK(current_state IN ('EARNING', 'STABLE', 'DEGRADING')),
    CHECK(consecutive_successes >= 0),
    CHECK(consecutive_failures >= 0),
    CHECK(policy_rejections >= 0),
    CHECK(high_risk_events >= 0)
);

-- Index for querying states by current state
CREATE INDEX IF NOT EXISTS idx_trust_states_state
ON trust_states(current_state, updated_at_ms DESC);

-- Index for degrading states (need monitoring)
CREATE INDEX IF NOT EXISTS idx_trust_states_degrading
ON trust_states(current_state, consecutive_failures DESC)
WHERE current_state = 'DEGRADING';

-- ===================================================================
-- Trust State Transitions (Audit Trail)
-- ===================================================================

CREATE TABLE IF NOT EXISTS trust_transitions (
    transition_id TEXT PRIMARY KEY,
    extension_id TEXT NOT NULL,
    action_id TEXT NOT NULL DEFAULT '*',
    old_state TEXT NOT NULL,                    -- Previous state
    new_state TEXT NOT NULL,                    -- New state
    trigger_event TEXT NOT NULL,                -- What triggered transition
    explain TEXT NOT NULL,                      -- Human-readable explanation
    risk_context_json TEXT NOT NULL,            -- Risk metrics at transition
    policy_context_json TEXT NOT NULL,          -- Policy decisions context
    created_at_ms INTEGER NOT NULL,

    CHECK(old_state IN ('EARNING', 'STABLE', 'DEGRADING')),
    CHECK(new_state IN ('EARNING', 'STABLE', 'DEGRADING')),
    CHECK(old_state != new_state)               -- No self-transitions
);

-- Index for extension history
CREATE INDEX IF NOT EXISTS idx_trust_transitions_extension
ON trust_transitions(extension_id, action_id, created_at_ms DESC);

-- Index for transition type analysis
CREATE INDEX IF NOT EXISTS idx_trust_transitions_type
ON trust_transitions(old_state, new_state, created_at_ms DESC);

-- Index for time-based queries
CREATE INDEX IF NOT EXISTS idx_trust_transitions_time
ON trust_transitions(created_at_ms DESC);

-- ===================================================================
-- Trust Trajectory Rules (v0 Fixed Rules)
-- ===================================================================

CREATE TABLE IF NOT EXISTS trust_trajectory_rules (
    rule_id TEXT PRIMARY KEY,
    from_state TEXT NOT NULL,                   -- Source state
    to_state TEXT NOT NULL,                     -- Target state
    condition_description TEXT NOT NULL,        -- Human-readable condition
    threshold_config_json TEXT NOT NULL,        -- JSON with thresholds
    priority INTEGER NOT NULL,                  -- Lower = higher priority
    active INTEGER NOT NULL DEFAULT 1,          -- 1=active, 0=inactive
    created_at_ms INTEGER NOT NULL,

    CHECK(from_state IN ('EARNING', 'STABLE', 'DEGRADING')),
    CHECK(to_state IN ('EARNING', 'STABLE', 'DEGRADING')),
    CHECK(from_state != to_state),
    CHECK(active IN (0, 1))
);

-- Index for rule lookup
CREATE INDEX IF NOT EXISTS idx_trust_rules_transition
ON trust_trajectory_rules(from_state, to_state, priority);

-- Index for active rules
CREATE INDEX IF NOT EXISTS idx_trust_rules_active
ON trust_trajectory_rules(active, priority)
WHERE active = 1;

-- ===================================================================
-- Initial Rules (v0 Fixed Configuration)
-- ===================================================================

-- Rule 1: EARNING → STABLE (Promotion)
-- Condition: N consecutive successes, no policy rejections
INSERT INTO trust_trajectory_rules (
    rule_id,
    from_state,
    to_state,
    condition_description,
    threshold_config_json,
    priority,
    active,
    created_at_ms
)
VALUES (
    'rule_earning_to_stable',
    'EARNING',
    'STABLE',
    'Promote to STABLE after consistent success with no policy violations',
    '{
        "min_consecutive_successes": 10,
        "max_policy_rejections": 0,
        "min_time_in_state_hours": 0
    }',
    10,
    1,
    strftime('%s', 'now') * 1000
);

-- Rule 2: STABLE → DEGRADING (High-Risk Failure)
-- Condition: Any high-risk failure or policy rejection
INSERT INTO trust_trajectory_rules (
    rule_id,
    from_state,
    to_state,
    condition_description,
    threshold_config_json,
    priority,
    active,
    created_at_ms
)
VALUES (
    'rule_stable_to_degrading',
    'STABLE',
    'DEGRADING',
    'Degrade trust on high-risk failure or policy violation',
    '{
        "max_consecutive_failures": 0,
        "max_policy_rejections": 0,
        "max_high_risk_events": 0
    }',
    5,
    1,
    strftime('%s', 'now') * 1000
);

-- Rule 3: DEGRADING → EARNING (Recovery Path)
-- Condition: Risk stabilized, recent successes, time passed
INSERT INTO trust_trajectory_rules (
    rule_id,
    from_state,
    to_state,
    condition_description,
    threshold_config_json,
    priority,
    active,
    created_at_ms
)
VALUES (
    'rule_degrading_to_earning',
    'DEGRADING',
    'EARNING',
    'Begin earning trust back after demonstrating recovery',
    '{
        "min_consecutive_successes": 5,
        "max_consecutive_failures": 0,
        "max_policy_rejections": 0,
        "min_time_in_state_hours": 0
    }',
    10,
    1,
    strftime('%s', 'now') * 1000
);

-- ===================================================================
-- Sample Data (for testing)
-- ===================================================================

-- Sample: Extension starting in EARNING state
INSERT OR IGNORE INTO trust_states (
    extension_id,
    action_id,
    current_state,
    consecutive_successes,
    consecutive_failures,
    policy_rejections,
    high_risk_events,
    state_entered_at_ms,
    last_event_at_ms,
    updated_at_ms
)
VALUES (
    'test_extension',
    '*',
    'EARNING',
    3,
    0,
    0,
    0,
    strftime('%s', 'now') * 1000 - 86400000,  -- 1 day ago
    strftime('%s', 'now') * 1000,
    strftime('%s', 'now') * 1000
);

-- ===================================================================
-- Validation Constraints
-- ===================================================================

-- Create trigger to prevent forbidden state jumps
CREATE TRIGGER IF NOT EXISTS prevent_state_jumping
BEFORE INSERT ON trust_transitions
BEGIN
    -- EARNING can only go to STABLE
    SELECT CASE
        WHEN NEW.old_state = 'EARNING' AND NEW.new_state != 'STABLE'
        THEN RAISE(ABORT, 'EARNING can only transition to STABLE')
    END;

    -- STABLE can only go to DEGRADING
    SELECT CASE
        WHEN NEW.old_state = 'STABLE' AND NEW.new_state != 'DEGRADING'
        THEN RAISE(ABORT, 'STABLE can only transition to DEGRADING')
    END;

    -- DEGRADING can only go to EARNING
    SELECT CASE
        WHEN NEW.old_state = 'DEGRADING' AND NEW.new_state != 'EARNING'
        THEN RAISE(ABORT, 'DEGRADING can only transition to EARNING (no jumping to STABLE)')
    END;
END;

-- ===================================================================
-- Migration Verification
-- ===================================================================

-- Verify all tables exist
SELECT 'Schema v70 tables created:' as status;
SELECT name FROM sqlite_master
WHERE type='table'
AND name IN (
    'trust_states',
    'trust_transitions',
    'trust_trajectory_rules'
)
ORDER BY name;

-- Verify rules loaded
SELECT 'Trust trajectory rules loaded:' as status;
SELECT rule_id, from_state, to_state, active FROM trust_trajectory_rules;

-- Verify sample data
SELECT 'Sample trust states loaded:' as status;
SELECT extension_id, action_id, current_state, consecutive_successes FROM trust_states;

-- Verify trigger exists
SELECT 'State transition triggers:' as status;
SELECT name FROM sqlite_master WHERE type='trigger' AND name = 'prevent_state_jumping';
