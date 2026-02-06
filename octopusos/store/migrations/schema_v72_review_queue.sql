-- Evolution Review Queue (Phase E4)
-- Human review queue for evolution decisions
-- Version: v72

-- Evolution Reviews Table
-- Records human review requests and decisions
CREATE TABLE IF NOT EXISTS evolution_reviews (
    review_id TEXT PRIMARY KEY,
    decision_id TEXT NOT NULL,
    extension_id TEXT NOT NULL,
    action_id TEXT NOT NULL DEFAULT '*',

    -- Evolution action being reviewed
    action TEXT NOT NULL CHECK (action IN ('PROMOTE', 'FREEZE', 'REVOKE', 'NONE')),

    -- Review status
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED', 'TIMEOUT')),

    -- Context at submission time
    risk_score REAL NOT NULL,
    trust_tier TEXT NOT NULL,
    trust_trajectory TEXT NOT NULL,

    -- Decision context (JSON)
    context TEXT NOT NULL,  -- Full context from E3 decision (evidence, causal_chain, etc.)

    -- Review tracking
    submitted_at TEXT NOT NULL DEFAULT (datetime('now')),
    reviewed_at TEXT,
    reviewer TEXT,  -- Human reviewer identifier
    reason TEXT,  -- Approval/rejection reason (REQUIRED)

    -- Timeout configuration
    timeout_at TEXT NOT NULL,  -- When this review auto-rejects (default 24h)

    -- Audit trail
    submitted_by TEXT NOT NULL DEFAULT 'system',  -- Who submitted for review

    -- Foreign keys
    FOREIGN KEY (decision_id) REFERENCES evolution_decisions(decision_id) ON DELETE CASCADE,
    FOREIGN KEY (extension_id) REFERENCES extensions(extension_id) ON DELETE CASCADE
);

-- Index for listing pending reviews
CREATE INDEX IF NOT EXISTS idx_evolution_reviews_pending
ON evolution_reviews(status, submitted_at DESC)
WHERE status = 'PENDING';

-- Index for timeout processing
CREATE INDEX IF NOT EXISTS idx_evolution_reviews_timeout
ON evolution_reviews(timeout_at, status)
WHERE status = 'PENDING';

-- Index for history queries
CREATE INDEX IF NOT EXISTS idx_evolution_reviews_extension
ON evolution_reviews(extension_id, action_id, submitted_at DESC);

-- Index for decision lookups
CREATE INDEX IF NOT EXISTS idx_evolution_reviews_decision
ON evolution_reviews(decision_id);

-- Evolution Review Audit
-- Tracks all review state changes
CREATE TABLE IF NOT EXISTS evolution_review_audit (
    audit_id TEXT PRIMARY KEY,
    review_id TEXT NOT NULL,
    decision_id TEXT NOT NULL,

    -- Event type
    event_type TEXT NOT NULL CHECK (event_type IN (
        'review_submitted',
        'review_approved',
        'review_rejected',
        'review_timeout',
        'review_cancelled'
    )),

    -- Event details
    actor TEXT,  -- Who performed the action
    reason TEXT,  -- Reason for action
    details TEXT,  -- JSON with additional details

    -- Timestamp
    created_at TEXT NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (review_id) REFERENCES evolution_reviews(review_id) ON DELETE CASCADE,
    FOREIGN KEY (decision_id) REFERENCES evolution_decisions(decision_id) ON DELETE CASCADE
);

-- Index for audit queries
CREATE INDEX IF NOT EXISTS idx_evolution_review_audit_review
ON evolution_review_audit(review_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_evolution_review_audit_decision
ON evolution_review_audit(decision_id, created_at DESC);

-- Migration metadata
INSERT INTO schema_versions (version, description, applied_at)
VALUES (
    72,
    'Evolution Review Queue: Human review interface for trust evolution',
    datetime('now')
)
ON CONFLICT (version) DO NOTHING;
