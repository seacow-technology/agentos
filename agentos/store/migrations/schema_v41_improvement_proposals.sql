-- schema_v41_improvement_proposals.sql
-- Migration for ImprovementProposal tables
-- Task #7: Implement ImprovementProposal data model

-- Improvement proposals table
CREATE TABLE IF NOT EXISTS improvement_proposals (
    proposal_id TEXT PRIMARY KEY,

    -- Scope and change details
    scope TEXT NOT NULL,
    change_type TEXT NOT NULL,
    description TEXT NOT NULL,

    -- Evidence (stored as JSON)
    evidence TEXT NOT NULL,  -- JSON: ProposalEvidence

    -- Recommendation
    recommendation TEXT NOT NULL,
    reasoning TEXT NOT NULL,

    -- Affected components
    affected_version_id TEXT NOT NULL,
    shadow_version_id TEXT,

    -- Lifecycle management
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    reviewed_by TEXT,
    reviewed_at TEXT,
    review_notes TEXT,
    implemented_at TEXT,

    -- Metadata
    metadata TEXT NOT NULL DEFAULT '{}',  -- JSON

    -- Constraints
    CONSTRAINT valid_proposal_id CHECK (proposal_id LIKE 'BP-%'),
    CONSTRAINT valid_change_type CHECK (
        change_type IN (
            'expand_keyword',
            'adjust_threshold',
            'add_signal',
            'remove_signal',
            'refine_rule',
            'promote_shadow'
        )
    ),
    CONSTRAINT valid_recommendation CHECK (
        recommendation IN (
            'Promote to v2',
            'Reject',
            'Defer',
            'Test in staging'
        )
    ),
    CONSTRAINT valid_status CHECK (
        status IN ('pending', 'accepted', 'rejected', 'deferred', 'implemented')
    ),
    CONSTRAINT reviewed_proposals_have_reviewer CHECK (
        status = 'pending' OR (
            reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL
        )
    ),
    CONSTRAINT implemented_proposals_have_timestamp CHECK (
        status != 'implemented' OR implemented_at IS NOT NULL
    ),
    FOREIGN KEY (affected_version_id) REFERENCES classifier_versions(version_id)
);

-- Proposal history table (audit trail)
CREATE TABLE IF NOT EXISTS proposal_history (
    history_id TEXT PRIMARY KEY,
    proposal_id TEXT NOT NULL,

    -- Change details
    action TEXT NOT NULL,  -- 'created', 'accepted', 'rejected', 'deferred', 'implemented'
    actor TEXT,  -- User who performed the action
    timestamp TEXT NOT NULL,

    -- State snapshot (before the change)
    previous_status TEXT,
    new_status TEXT,
    notes TEXT,

    CONSTRAINT valid_action CHECK (
        action IN ('created', 'accepted', 'rejected', 'deferred', 'implemented', 'modified')
    ),
    FOREIGN KEY (proposal_id) REFERENCES improvement_proposals(proposal_id) ON DELETE CASCADE
);

-- Indexes for efficient queries

-- Index for status-based queries
CREATE INDEX IF NOT EXISTS idx_proposals_status
    ON improvement_proposals(status, created_at DESC);

-- Index for version-based queries
CREATE INDEX IF NOT EXISTS idx_proposals_affected_version
    ON improvement_proposals(affected_version_id, created_at DESC);

-- Index for shadow version queries
CREATE INDEX IF NOT EXISTS idx_proposals_shadow_version
    ON improvement_proposals(shadow_version_id)
    WHERE shadow_version_id IS NOT NULL;

-- Index for pending proposals
CREATE INDEX IF NOT EXISTS idx_proposals_pending
    ON improvement_proposals(created_at DESC)
    WHERE status = 'pending';

-- Index for reviewed proposals
CREATE INDEX IF NOT EXISTS idx_proposals_reviewed
    ON improvement_proposals(reviewed_at DESC)
    WHERE reviewed_at IS NOT NULL;

-- Index for change type queries
CREATE INDEX IF NOT EXISTS idx_proposals_change_type
    ON improvement_proposals(change_type, status);

-- Index for proposal history
CREATE INDEX IF NOT EXISTS idx_proposal_history_proposal
    ON proposal_history(proposal_id, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_proposal_history_timestamp
    ON proposal_history(timestamp DESC);

-- Update schema version
INSERT INTO schema_version (version, applied_at)
VALUES (
    '0.41.0',
    CURRENT_TIMESTAMP
);
