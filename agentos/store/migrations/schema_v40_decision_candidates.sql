-- schema_v40_decision_candidates.sql
-- Migration for DecisionCandidate and DecisionSet tables
-- Task #28: v3 decision candidate data model and storage

-- Classifier versions table (Shadow Evaluation 语义层)
-- NOTE: This will be merged with version management fields in v43
CREATE TABLE IF NOT EXISTS classifier_versions (
    version_id TEXT PRIMARY KEY,
    version_type TEXT NOT NULL CHECK(version_type IN ('active', 'shadow')),
    change_description TEXT,
    created_at TEXT NOT NULL,
    promoted_from TEXT,  -- If promoted from shadow to active
    deprecated_at TEXT,
    metadata TEXT,  -- JSON for additional metadata

    CONSTRAINT valid_version_type CHECK (version_type IN ('active', 'shadow'))
);

-- Decision candidates table
CREATE TABLE IF NOT EXISTS decision_candidates (
    candidate_id TEXT PRIMARY KEY,
    decision_role TEXT NOT NULL CHECK(decision_role IN ('active', 'shadow')),
    version_id TEXT NOT NULL,

    -- Input
    question_text TEXT NOT NULL,
    question_hash TEXT NOT NULL,
    context TEXT NOT NULL,  -- JSON
    phase TEXT NOT NULL,
    mode TEXT,

    -- Classification result
    info_need_type TEXT NOT NULL,
    confidence_level TEXT NOT NULL,
    decision_action TEXT NOT NULL,
    reason_codes TEXT NOT NULL,  -- JSON array

    -- Signals
    rule_signals TEXT NOT NULL,  -- JSON
    llm_confidence_score REAL,

    -- Relationships
    timestamp TEXT NOT NULL,
    message_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    decision_set_id TEXT NOT NULL,

    -- Shadow-specific
    shadow_metadata TEXT,  -- JSON

    -- Legacy compatibility
    latency_ms REAL,

    CONSTRAINT valid_decision_role CHECK (decision_role IN ('active', 'shadow')),
    CONSTRAINT valid_confidence_score CHECK (
        llm_confidence_score IS NULL OR
        (llm_confidence_score >= 0.0 AND llm_confidence_score <= 1.0)
    ),
    CONSTRAINT valid_latency CHECK (
        latency_ms IS NULL OR latency_ms >= 0.0
    ),
    FOREIGN KEY (version_id) REFERENCES classifier_versions(version_id)
);

-- Decision sets table
CREATE TABLE IF NOT EXISTS decision_sets (
    decision_set_id TEXT PRIMARY KEY,
    message_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    question_text TEXT NOT NULL,
    question_hash TEXT NOT NULL,
    active_candidate_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    context_snapshot TEXT NOT NULL,  -- JSON

    FOREIGN KEY (active_candidate_id) REFERENCES decision_candidates(candidate_id)
);

-- Indexes for efficient queries

-- Candidate indexes
CREATE INDEX IF NOT EXISTS idx_candidates_message
    ON decision_candidates(message_id);

CREATE INDEX IF NOT EXISTS idx_candidates_session
    ON decision_candidates(session_id);

CREATE INDEX IF NOT EXISTS idx_candidates_role
    ON decision_candidates(decision_role);

CREATE INDEX IF NOT EXISTS idx_candidates_version
    ON decision_candidates(version_id);

CREATE INDEX IF NOT EXISTS idx_candidates_timestamp
    ON decision_candidates(timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_candidates_question_hash
    ON decision_candidates(question_hash);

CREATE INDEX IF NOT EXISTS idx_candidates_decision_set
    ON decision_candidates(decision_set_id);

CREATE INDEX IF NOT EXISTS idx_candidates_info_need_type
    ON decision_candidates(info_need_type);

-- DecisionSet indexes
CREATE INDEX IF NOT EXISTS idx_sets_message
    ON decision_sets(message_id);

CREATE INDEX IF NOT EXISTS idx_sets_session
    ON decision_sets(session_id);

CREATE INDEX IF NOT EXISTS idx_sets_timestamp
    ON decision_sets(timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_sets_question_hash
    ON decision_sets(question_hash);

-- ClassifierVersion indexes (basic, will be extended in v43)
CREATE INDEX IF NOT EXISTS idx_versions_type
    ON classifier_versions(version_type);

CREATE INDEX IF NOT EXISTS idx_versions_created
    ON classifier_versions(created_at DESC);

-- Update schema version
INSERT INTO schema_version (version, applied_at)
VALUES (
    '0.40.0',
    CURRENT_TIMESTAMP
);
