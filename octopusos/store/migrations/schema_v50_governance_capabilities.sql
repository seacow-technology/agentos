-- Schema v50: Governance Capabilities
--
-- This migration adds tables for the Governance Domain (GC-001 to GC-006):
-- 1. governance_policies - Policy definitions with versioning
-- 2. governance_policy_evaluations - Audit trail of policy evaluations
-- 3. governance_overrides - Emergency override tokens
-- 4. risk_assessments - Risk score audit trail
-- 5. resource_quotas - Resource usage tracking (tokens, API calls, etc)
--
-- Design:
-- - All timestamps in epoch milliseconds (consistent with v44)
-- - Full audit trail of all governance decisions
-- - Policy versioning with evolution history
-- - Single-use override tokens
-- - Multi-tenant resource quotas

-- ===================================================================
-- Policies (GC-002, GC-006)
-- ===================================================================

CREATE TABLE IF NOT EXISTS governance_policies (
    policy_id TEXT NOT NULL,
    version TEXT NOT NULL,
    rules_json TEXT NOT NULL,           -- JSON array of PolicyRule objects
    change_reason TEXT,                 -- Why policy was created/updated
    active INTEGER NOT NULL DEFAULT 1,  -- 1=active, 0=inactive
    created_by TEXT NOT NULL,           -- Who created this version
    created_at_ms INTEGER NOT NULL,     -- When created (epoch ms)

    PRIMARY KEY (policy_id, version),

    CHECK(active IN (0, 1))
);

-- Index for loading active policies
CREATE INDEX IF NOT EXISTS idx_policy_active
ON governance_policies(policy_id, active);

-- Index for finding latest version
CREATE INDEX IF NOT EXISTS idx_policy_created
ON governance_policies(policy_id, created_at_ms DESC);

-- ===================================================================
-- Policy Evaluations (GC-002 audit)
-- ===================================================================

CREATE TABLE IF NOT EXISTS governance_policy_evaluations (
    evaluation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    policy_id TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    input_context_json TEXT NOT NULL,       -- JSON of evaluation context
    decision TEXT NOT NULL,                 -- ALLOW|DENY|ESCALATE|WARN
    rules_triggered_json TEXT,              -- JSON array of triggered rules
    confidence REAL,                        -- Confidence in decision (0.0-1.0)
    evaluated_at_ms INTEGER NOT NULL,       -- When evaluation occurred

    CHECK(decision IN ('ALLOW', 'DENY', 'ESCALATE', 'WARN'))
);

-- Index for policy audit queries
CREATE INDEX IF NOT EXISTS idx_policy_eval_policy
ON governance_policy_evaluations(policy_id, evaluated_at_ms DESC);

-- Index for time-based queries
CREATE INDEX IF NOT EXISTS idx_policy_eval_time
ON governance_policy_evaluations(evaluated_at_ms DESC);

-- ===================================================================
-- Emergency Overrides (GC-004)
-- ===================================================================

CREATE TABLE IF NOT EXISTS governance_overrides (
    override_id TEXT PRIMARY KEY,           -- Secure token (override-{random})
    admin_id TEXT NOT NULL,                 -- Admin who created override
    blocked_operation TEXT NOT NULL,        -- Description of blocked operation
    override_reason TEXT NOT NULL,          -- Justification (min 100 chars)
    expires_at_ms INTEGER NOT NULL,         -- When override expires
    used INTEGER NOT NULL DEFAULT 0,        -- 1=used, 0=unused (single-use)
    used_at_ms INTEGER,                     -- When override was used
    created_at_ms INTEGER NOT NULL,         -- When override was created

    CHECK(used IN (0, 1))
);

-- Index for admin audit
CREATE INDEX IF NOT EXISTS idx_override_admin
ON governance_overrides(admin_id, created_at_ms DESC);

-- Index for expiration cleanup
CREATE INDEX IF NOT EXISTS idx_override_expires
ON governance_overrides(expires_at_ms);

-- Index for active overrides
CREATE INDEX IF NOT EXISTS idx_override_active
ON governance_overrides(used, expires_at_ms);

-- ===================================================================
-- Risk Assessments (GC-003)
-- ===================================================================

CREATE TABLE IF NOT EXISTS risk_assessments (
    assessment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    capability_id TEXT NOT NULL,            -- Capability being assessed
    agent_id TEXT NOT NULL,                 -- Agent requesting operation
    risk_score REAL NOT NULL,               -- Overall risk (0.0-1.0)
    risk_level TEXT NOT NULL,               -- LOW|MEDIUM|HIGH|CRITICAL
    factors_json TEXT NOT NULL,             -- JSON array of RiskFactor objects
    mitigation_required INTEGER NOT NULL,   -- 1=requires mitigation, 0=not required
    assessed_at_ms INTEGER NOT NULL,        -- When assessment was performed

    CHECK(risk_level IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    CHECK(mitigation_required IN (0, 1)),
    CHECK(risk_score >= 0.0 AND risk_score <= 1.0)
);

-- Index for capability risk history
CREATE INDEX IF NOT EXISTS idx_risk_capability
ON risk_assessments(capability_id, assessed_at_ms DESC);

-- Index for agent risk profile
CREATE INDEX IF NOT EXISTS idx_risk_agent
ON risk_assessments(agent_id, assessed_at_ms DESC);

-- Index for high-risk operations
CREATE INDEX IF NOT EXISTS idx_risk_high
ON risk_assessments(risk_level, assessed_at_ms DESC);

-- ===================================================================
-- Resource Quotas (GC-005)
-- ===================================================================

CREATE TABLE IF NOT EXISTS resource_quotas (
    quota_id TEXT PRIMARY KEY,              -- Unique quota identifier
    agent_id TEXT NOT NULL,                 -- Agent identifier
    resource_type TEXT NOT NULL,            -- tokens|api_calls|storage|cost_usd|compute_time
    limit_value REAL NOT NULL,              -- Maximum allowed usage
    current_usage REAL NOT NULL DEFAULT 0,  -- Current usage amount
    reset_interval_ms INTEGER,              -- How often quota resets (NULL=no reset)
    last_reset_ms INTEGER,                  -- Last time quota was reset
    updated_at_ms INTEGER NOT NULL,         -- Last update time

    CHECK(resource_type IN ('tokens', 'api_calls', 'storage', 'cost_usd', 'compute_time')),
    CHECK(limit_value >= 0),
    CHECK(current_usage >= 0)
);

-- Unique constraint: one quota per agent+resource_type
CREATE UNIQUE INDEX IF NOT EXISTS idx_quota_agent_resource
ON resource_quotas(agent_id, resource_type);

-- Index for quota checks
CREATE INDEX IF NOT EXISTS idx_quota_agent
ON resource_quotas(agent_id);

-- ===================================================================
-- Sample Data (for testing)
-- ===================================================================

-- Sample policy: Budget enforcement
INSERT OR IGNORE INTO governance_policies (
    policy_id, version, rules_json, change_reason,
    active, created_by, created_at_ms
)
VALUES (
    'budget_enforcement',
    '1.0.0',
    '[
        {
            "condition": "estimated_cost > 10.0",
            "condition_type": "threshold",
            "action": "DENY",
            "rationale": "Cost exceeds maximum allowed ($10)",
            "priority": 10
        },
        {
            "condition": "estimated_cost > 5.0",
            "condition_type": "threshold",
            "action": "ESCALATE",
            "rationale": "Cost requires approval (>$5)",
            "priority": 20
        }
    ]',
    'Initial budget policy',
    1,
    'system',
    strftime('%s', 'now') * 1000
);

-- Sample policy: High-risk operations
INSERT OR IGNORE INTO governance_policies (
    policy_id, version, rules_json, change_reason,
    active, created_by, created_at_ms
)
VALUES (
    'high_risk_approval',
    '1.0.0',
    '[
        {
            "condition": "risk_level == \"CRITICAL\"",
            "condition_type": "expression",
            "action": "DENY",
            "rationale": "Critical risk requires admin override",
            "priority": 5
        },
        {
            "condition": "risk_level == \"HIGH\" and trust_tier < \"T3\"",
            "condition_type": "expression",
            "action": "ESCALATE",
            "rationale": "High risk with low trust requires approval",
            "priority": 10
        }
    ]',
    'Initial high-risk policy',
    1,
    'system',
    strftime('%s', 'now') * 1000
);

-- Sample quota: Test agent token limit
INSERT OR IGNORE INTO resource_quotas (
    quota_id, agent_id, resource_type, limit_value,
    current_usage, reset_interval_ms, last_reset_ms, updated_at_ms
)
VALUES (
    'quota-test-agent-tokens',
    'test_agent',
    'tokens',
    100000,  -- 100k tokens
    0,
    86400000,  -- Reset daily (24h in ms)
    strftime('%s', 'now') * 1000,
    strftime('%s', 'now') * 1000
);

-- ===================================================================
-- Migration Verification
-- ===================================================================

-- Verify all tables exist
SELECT 'Schema v50 tables created:' as status;
SELECT name FROM sqlite_master
WHERE type='table'
AND name IN (
    'governance_policies',
    'governance_policy_evaluations',
    'governance_overrides',
    'risk_assessments',
    'resource_quotas'
)
ORDER BY name;

-- Verify sample data
SELECT 'Sample policies loaded:' as status;
SELECT policy_id, version, active FROM governance_policies;

SELECT 'Sample quotas loaded:' as status;
SELECT quota_id, agent_id, resource_type, limit_value FROM resource_quotas;
