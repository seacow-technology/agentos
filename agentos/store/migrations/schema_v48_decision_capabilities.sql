-- Schema v48: Decision Capabilities Domain
-- AgentOS v3 Task #23
--
-- Design Philosophy:
-- - Decision is the core differentiator of AgentOS
-- - Plans must be freezable (semantic freeze with hash)
-- - Decisions CANNOT trigger Actions directly
-- - All decisions must record rationale and evidence
-- - Support Shadow Classifier comparison
--
-- Five tables for five capabilities:
-- 1. decision_plans (DC-001, DC-002)
-- 2. decision_options (DC-003)
-- 3. decision_evaluations (DC-003)
-- 4. decision_selections (DC-004)
-- 5. decision_rationales (DC-005)

-- ===================================================================
-- 1. Decision Plans Table (DC-001, DC-002)
-- ===================================================================

-- Stores execution plans with freeze capability
CREATE TABLE IF NOT EXISTS decision_plans (
    plan_id TEXT PRIMARY KEY,                    -- Unique plan ID (ulid)
    task_id TEXT NOT NULL,                       -- Task this plan belongs to
    steps_json TEXT NOT NULL,                    -- List of PlanStep objects as JSON
    alternatives_json TEXT,                      -- List of Alternative objects as JSON
    rationale TEXT NOT NULL,                     -- Why this plan was chosen
    status TEXT NOT NULL DEFAULT 'draft',        -- draft|frozen|archived|rolled_back
    frozen_at_ms INTEGER,                        -- When frozen (NULL if not frozen)
    plan_hash TEXT,                              -- SHA-256 hash (NULL if not frozen)
    created_by TEXT NOT NULL,                    -- Agent/user who created
    created_at_ms INTEGER NOT NULL,              -- When created (epoch ms)
    updated_at_ms INTEGER,                       -- When last updated (epoch ms)
    context_snapshot_id TEXT,                    -- Context snapshot this plan is based on
    metadata TEXT,                               -- JSON metadata

    CHECK (status IN ('draft', 'frozen', 'archived', 'rolled_back')),
    CHECK (created_at_ms > 0),
    CHECK ((status = 'frozen' AND frozen_at_ms IS NOT NULL AND plan_hash IS NOT NULL) OR status != 'frozen')
);

-- Index for task-based queries
CREATE INDEX IF NOT EXISTS idx_decision_plans_task
    ON decision_plans(task_id, created_at_ms DESC);

-- Index for status-based queries
CREATE INDEX IF NOT EXISTS idx_decision_plans_status
    ON decision_plans(status, created_at_ms DESC);

-- Index for frozen plans
CREATE INDEX IF NOT EXISTS idx_decision_plans_frozen
    ON decision_plans(frozen_at_ms DESC)
    WHERE frozen_at_ms IS NOT NULL;

-- Index for plan hash verification
CREATE INDEX IF NOT EXISTS idx_decision_plans_hash
    ON decision_plans(plan_hash)
    WHERE plan_hash IS NOT NULL;

-- ===================================================================
-- 2. Decision Options Table (DC-003)
-- ===================================================================

-- Stores options for evaluation (can be reused across evaluations)
CREATE TABLE IF NOT EXISTS decision_options (
    option_id TEXT PRIMARY KEY,                  -- Unique option ID (ulid)
    decision_context_id TEXT NOT NULL,           -- Context this option belongs to
    description TEXT NOT NULL,                   -- What this option does
    estimated_cost REAL NOT NULL,                -- Estimated cost (tokens/dollars)
    estimated_time_ms INTEGER NOT NULL,          -- Estimated execution time (ms)
    risks_json TEXT,                             -- List of risk strings as JSON
    benefits_json TEXT,                          -- List of benefit strings as JSON
    created_at_ms INTEGER NOT NULL,              -- When created (epoch ms)
    metadata TEXT,                               -- JSON metadata

    CHECK (estimated_cost >= 0),
    CHECK (estimated_time_ms >= 0),
    CHECK (created_at_ms > 0)
);

-- Index for context-based queries
CREATE INDEX IF NOT EXISTS idx_decision_options_context
    ON decision_options(decision_context_id, created_at_ms DESC);

-- ===================================================================
-- 3. Decision Evaluations Table (DC-003)
-- ===================================================================

-- Stores evaluation results (scored and ranked options)
CREATE TABLE IF NOT EXISTS decision_evaluations (
    evaluation_id TEXT PRIMARY KEY,              -- Unique evaluation ID (ulid)
    decision_context_id TEXT NOT NULL,           -- Context for this evaluation
    options_json TEXT NOT NULL,                  -- List of Option objects as JSON
    scores_json TEXT NOT NULL,                   -- Dict of option_id -> score
    ranked_options_json TEXT NOT NULL,           -- List of option_ids ranked best to worst
    recommendation TEXT NOT NULL,                -- Recommended option_id (top ranked)
    recommendation_rationale TEXT,               -- Why this option is recommended
    confidence REAL NOT NULL,                    -- Confidence in evaluation (0-100)
    evaluated_by TEXT NOT NULL,                  -- Agent/classifier that performed evaluation
    evaluated_at_ms INTEGER NOT NULL,            -- When evaluated (epoch ms)
    metadata TEXT,                               -- JSON metadata

    CHECK (confidence >= 0 AND confidence <= 100),
    CHECK (evaluated_at_ms > 0)
);

-- Index for context-based queries
CREATE INDEX IF NOT EXISTS idx_decision_evaluations_context
    ON decision_evaluations(decision_context_id, evaluated_at_ms DESC);

-- Index for time-based queries
CREATE INDEX IF NOT EXISTS idx_decision_evaluations_time
    ON decision_evaluations(evaluated_at_ms DESC);

-- Index for evaluator-based queries (Shadow Classifier comparison)
CREATE INDEX IF NOT EXISTS idx_decision_evaluations_evaluator
    ON decision_evaluations(evaluated_by, evaluated_at_ms DESC);

-- ===================================================================
-- 4. Decision Selections Table (DC-004)
-- ===================================================================

-- Stores final decisions (selected option with rationale)
CREATE TABLE IF NOT EXISTS decision_selections (
    decision_id TEXT PRIMARY KEY,                -- Unique decision ID (ulid)
    evaluation_id TEXT NOT NULL,                 -- Evaluation this decision is based on
    selected_option_id TEXT NOT NULL,            -- Option that was selected
    selected_option_json TEXT NOT NULL,          -- Full Option object as JSON
    rationale TEXT NOT NULL,                     -- Detailed rationale for selection
    alternatives_rejected_json TEXT,             -- List of Option objects that were rejected
    rejection_reasons_json TEXT,                 -- Dict of option_id -> rejection reason
    confidence_level TEXT NOT NULL,              -- very_low|low|medium|high|very_high
    decided_by TEXT NOT NULL,                    -- Who made the decision (user/agent)
    decided_at_ms INTEGER NOT NULL,              -- When decision was made (epoch ms)
    evidence_id TEXT,                            -- Evidence record ID (for audit)
    metadata TEXT,                               -- JSON metadata

    CHECK (confidence_level IN ('very_low', 'low', 'medium', 'high', 'very_high')),
    CHECK (decided_at_ms > 0),

    FOREIGN KEY (evaluation_id) REFERENCES decision_evaluations(evaluation_id)
);

-- Index for evaluation-based queries
CREATE INDEX IF NOT EXISTS idx_decision_selections_evaluation
    ON decision_selections(evaluation_id);

-- Index for decider-based queries
CREATE INDEX IF NOT EXISTS idx_decision_selections_decided_by
    ON decision_selections(decided_by, decided_at_ms DESC);

-- Index for time-based queries
CREATE INDEX IF NOT EXISTS idx_decision_selections_time
    ON decision_selections(decided_at_ms DESC);

-- Index for evidence linkage
CREATE INDEX IF NOT EXISTS idx_decision_selections_evidence
    ON decision_selections(evidence_id)
    WHERE evidence_id IS NOT NULL;

-- ===================================================================
-- 5. Decision Rationales Table (DC-005)
-- ===================================================================

-- Stores extended rationale for decisions (with evidence refs)
CREATE TABLE IF NOT EXISTS decision_rationales (
    rationale_id TEXT PRIMARY KEY,               -- Unique rationale ID (ulid)
    decision_id TEXT NOT NULL,                   -- Decision this rationale belongs to
    rationale TEXT NOT NULL,                     -- Detailed explanation
    evidence_refs_json TEXT,                     -- List of evidence IDs as JSON
    created_by TEXT NOT NULL,                    -- Who created this rationale
    created_at_ms INTEGER NOT NULL,              -- When created (epoch ms)
    metadata TEXT,                               -- JSON metadata

    CHECK (created_at_ms > 0),

    FOREIGN KEY (decision_id) REFERENCES decision_selections(decision_id)
);

-- Index for decision-based queries
CREATE INDEX IF NOT EXISTS idx_decision_rationales_decision
    ON decision_rationales(decision_id, created_at_ms ASC);

-- ===================================================================
-- 6. Views for Convenience
-- ===================================================================

-- Active plans (draft + frozen, excluding archived)
CREATE VIEW IF NOT EXISTS active_decision_plans AS
SELECT
    plan_id,
    task_id,
    status,
    frozen_at_ms,
    plan_hash,
    created_by,
    created_at_ms,
    updated_at_ms
FROM decision_plans
WHERE status IN ('draft', 'frozen')
ORDER BY created_at_ms DESC;

-- Frozen plans ready for execution
CREATE VIEW IF NOT EXISTS frozen_plans AS
SELECT
    plan_id,
    task_id,
    plan_hash,
    frozen_at_ms,
    created_by
FROM decision_plans
WHERE status = 'frozen'
ORDER BY frozen_at_ms DESC;

-- Recent decisions with confidence
CREATE VIEW IF NOT EXISTS recent_decisions AS
SELECT
    ds.decision_id,
    ds.evaluation_id,
    ds.selected_option_id,
    ds.confidence_level,
    ds.decided_by,
    ds.decided_at_ms,
    de.decision_context_id,
    de.evaluated_by,
    de.confidence as evaluation_confidence,
    datetime(ds.decided_at_ms / 1000, 'unixepoch') as decided_at_iso
FROM decision_selections ds
JOIN decision_evaluations de ON ds.evaluation_id = de.evaluation_id
ORDER BY ds.decided_at_ms DESC
LIMIT 1000;

-- Decision statistics by context
CREATE VIEW IF NOT EXISTS decision_stats_by_context AS
SELECT
    de.decision_context_id,
    COUNT(DISTINCT ds.decision_id) as total_decisions,
    AVG(de.confidence) as avg_evaluation_confidence,
    COUNT(CASE WHEN ds.confidence_level IN ('high', 'very_high') THEN 1 END) as high_confidence_decisions,
    COUNT(CASE WHEN ds.confidence_level IN ('low', 'very_low') THEN 1 END) as low_confidence_decisions,
    MIN(ds.decided_at_ms) as first_decision_ms,
    MAX(ds.decided_at_ms) as last_decision_ms
FROM decision_evaluations de
LEFT JOIN decision_selections ds ON de.evaluation_id = ds.evaluation_id
GROUP BY de.decision_context_id
ORDER BY total_decisions DESC;

-- Plan freeze statistics
CREATE VIEW IF NOT EXISTS plan_freeze_stats AS
SELECT
    task_id,
    COUNT(*) as total_plans,
    COUNT(CASE WHEN status = 'draft' THEN 1 END) as draft_plans,
    COUNT(CASE WHEN status = 'frozen' THEN 1 END) as frozen_plans,
    COUNT(CASE WHEN status = 'archived' THEN 1 END) as archived_plans,
    COUNT(CASE WHEN status = 'rolled_back' THEN 1 END) as rolled_back_plans,
    MIN(created_at_ms) as first_plan_ms,
    MAX(created_at_ms) as last_plan_ms
FROM decision_plans
GROUP BY task_id
ORDER BY total_plans DESC;

-- ===================================================================
-- 7. Update Schema Version
-- ===================================================================

-- Record schema version
-- Note: description column is added in v50.5, so we don't use it here
INSERT INTO schema_version (version, applied_at)
VALUES (
    '0.48.0',
    CURRENT_TIMESTAMP
);

-- ===================================================================
-- Performance Notes:
-- - decision_plans table indexed by task_id, status, and frozen_at_ms
-- - decision_evaluations indexed by context and evaluator (Shadow Classifier support)
-- - decision_selections indexed by evaluation_id and evidence_id
-- - Plan hash verification: O(1) lookup by plan_hash
-- - Expected performance: Plan freeze < 10ms, Evaluation < 200ms
-- ===================================================================

-- ===================================================================
-- Integration Notes:
-- - Evidence IDs link to evidence.record capability (Domain 5)
-- - Context snapshots link to state.context service (Domain 1)
-- - PathValidator enforces Decision → Action blocking
-- - Plans can be executed by action.execute only when frozen
-- ===================================================================
