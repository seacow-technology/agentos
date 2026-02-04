-- Evolution Decisions Table (Phase E3)
-- Stores proposed evolution actions and their status
-- Version: v71

CREATE TABLE IF NOT EXISTS evolution_decisions (
    decision_id TEXT PRIMARY KEY,
    extension_id TEXT NOT NULL,
    action_id TEXT NOT NULL DEFAULT '*',

    -- Evolution action
    action TEXT NOT NULL CHECK (action IN ('PROMOTE', 'FREEZE', 'REVOKE', 'NONE')),
    status TEXT NOT NULL DEFAULT 'PROPOSED' CHECK (status IN ('PROPOSED', 'APPROVED', 'REJECTED', 'EXPIRED')),

    -- Context at decision time
    risk_score REAL NOT NULL,
    trust_tier TEXT NOT NULL,
    trust_trajectory TEXT NOT NULL,

    -- Decision reasoning
    explanation TEXT NOT NULL,
    causal_chain TEXT NOT NULL,  -- JSON array of causal steps
    review_level TEXT NOT NULL CHECK (review_level IN ('NONE', 'STANDARD', 'HIGH_PRIORITY', 'CRITICAL')),

    -- Supporting evidence
    evidence TEXT NOT NULL,  -- JSON object with all evidence

    -- Review tracking
    approved_by TEXT,
    approved_at TEXT,
    notes TEXT,

    -- Timestamps
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT,

    -- Indexes for common queries
    FOREIGN KEY (extension_id) REFERENCES extensions(extension_id) ON DELETE CASCADE
);

-- Index for querying decisions by extension
CREATE INDEX IF NOT EXISTS idx_evolution_decisions_extension
ON evolution_decisions(extension_id, action_id, created_at DESC);

-- Index for querying pending reviews
CREATE INDEX IF NOT EXISTS idx_evolution_decisions_status
ON evolution_decisions(status, review_level, created_at DESC);

-- Index for querying expired decisions
CREATE INDEX IF NOT EXISTS idx_evolution_decisions_expires
ON evolution_decisions(expires_at)
WHERE expires_at IS NOT NULL;

-- Evolution Audit Trail
-- Records all evolution actions and their outcomes
CREATE TABLE IF NOT EXISTS evolution_audit (
    audit_id TEXT PRIMARY KEY,
    decision_id TEXT NOT NULL,
    extension_id TEXT NOT NULL,
    action_id TEXT NOT NULL DEFAULT '*',

    -- Event type
    event_type TEXT NOT NULL CHECK (event_type IN (
        'decision_proposed',
        'decision_approved',
        'decision_rejected',
        'decision_expired',
        'action_executed',
        'action_failed'
    )),

    -- Event details
    action TEXT NOT NULL,
    actor TEXT,  -- Who performed the action
    details TEXT,  -- JSON object with event details

    -- Timestamp
    created_at TEXT NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (decision_id) REFERENCES evolution_decisions(decision_id) ON DELETE CASCADE,
    FOREIGN KEY (extension_id) REFERENCES extensions(extension_id) ON DELETE CASCADE
);

-- Index for audit queries
CREATE INDEX IF NOT EXISTS idx_evolution_audit_decision
ON evolution_audit(decision_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_evolution_audit_extension
ON evolution_audit(extension_id, event_type, created_at DESC);

-- Evolution Metrics
-- Aggregated metrics for evolution system monitoring
CREATE TABLE IF NOT EXISTS evolution_metrics (
    metric_id TEXT PRIMARY KEY,
    extension_id TEXT NOT NULL,
    action_id TEXT NOT NULL DEFAULT '*',

    -- Metric period
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,

    -- Decision counts
    total_decisions INTEGER NOT NULL DEFAULT 0,
    promote_proposed INTEGER NOT NULL DEFAULT 0,
    freeze_proposed INTEGER NOT NULL DEFAULT 0,
    revoke_proposed INTEGER NOT NULL DEFAULT 0,
    none_proposed INTEGER NOT NULL DEFAULT 0,

    -- Approval counts
    decisions_approved INTEGER NOT NULL DEFAULT 0,
    decisions_rejected INTEGER NOT NULL DEFAULT 0,
    decisions_expired INTEGER NOT NULL DEFAULT 0,

    -- Action execution counts
    actions_executed INTEGER NOT NULL DEFAULT 0,
    actions_failed INTEGER NOT NULL DEFAULT 0,

    -- Timestamps
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (extension_id) REFERENCES extensions(extension_id) ON DELETE CASCADE
);

-- Index for metrics queries
CREATE INDEX IF NOT EXISTS idx_evolution_metrics_extension
ON evolution_metrics(extension_id, period_start, period_end);

CREATE INDEX IF NOT EXISTS idx_evolution_metrics_period
ON evolution_metrics(period_start, period_end);

-- Migration metadata
INSERT INTO schema_versions (version, description, applied_at)
VALUES (
    71,
    'Evolution Decision Engine: decisions, audit, and metrics tables',
    datetime('now')
)
ON CONFLICT (version) DO NOTHING;
