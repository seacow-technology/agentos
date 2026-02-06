-- schema_v38_info_need_judgments.sql
-- Migration for InfoNeed judgment history storage in MemoryOS
-- Task #22: Implement short-term memory for classification judgments

-- Create info_need_judgments table
CREATE TABLE IF NOT EXISTS info_need_judgments (
    -- Identifiers
    judgment_id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,  -- ISO 8601 format
    session_id TEXT NOT NULL,
    message_id TEXT NOT NULL UNIQUE,  -- Links to audit logs

    -- Input
    question_text TEXT NOT NULL,
    question_hash TEXT NOT NULL,  -- For deduplication

    -- Judgment process
    classified_type TEXT NOT NULL,  -- InfoNeedType enum
    confidence_level TEXT NOT NULL,  -- ConfidenceLevel enum
    decision_action TEXT NOT NULL,  -- DecisionAction enum

    -- Judgment basis (stored as JSON)
    rule_signals TEXT NOT NULL,  -- JSON: signals and patterns
    llm_confidence_score REAL NOT NULL DEFAULT 0.0,
    decision_latency_ms REAL NOT NULL DEFAULT 0.0,

    -- Outcome feedback
    outcome TEXT NOT NULL DEFAULT 'pending',  -- JudgmentOutcome enum
    user_action TEXT,  -- Specific action taken
    outcome_timestamp TEXT,  -- ISO 8601 format

    -- Context metadata
    phase TEXT NOT NULL,  -- planning/execution
    mode TEXT,  -- conversation/task/automation
    trust_tier TEXT,  -- Trust tier if external info accessed

    CONSTRAINT valid_classified_type CHECK (
        classified_type IN (
            'local_deterministic',
            'local_knowledge',
            'ambient_state',
            'external_fact_uncertain',
            'opinion'
        )
    ),
    CONSTRAINT valid_confidence_level CHECK (
        confidence_level IN ('high', 'medium', 'low')
    ),
    CONSTRAINT valid_decision_action CHECK (
        decision_action IN (
            'direct_answer',
            'local_capability',
            'require_comm',
            'suggest_comm'
        )
    ),
    CONSTRAINT valid_outcome CHECK (
        outcome IN (
            'user_proceeded',
            'user_declined',
            'system_fallback',
            'pending'
        )
    ),
    CONSTRAINT valid_phase CHECK (
        phase IN ('planning', 'execution', 'unknown')
    )
);

-- Index for session-based queries
CREATE INDEX IF NOT EXISTS idx_info_need_judgments_session_id
    ON info_need_judgments(session_id, timestamp DESC);

-- Index for type-based queries
CREATE INDEX IF NOT EXISTS idx_info_need_judgments_classified_type
    ON info_need_judgments(classified_type, timestamp DESC);

-- Index for outcome-based queries
CREATE INDEX IF NOT EXISTS idx_info_need_judgments_outcome
    ON info_need_judgments(outcome, timestamp DESC);

-- Index for deduplication (finding similar questions)
CREATE INDEX IF NOT EXISTS idx_info_need_judgments_question_hash
    ON info_need_judgments(question_hash, timestamp DESC);

-- Index for time-range queries
CREATE INDEX IF NOT EXISTS idx_info_need_judgments_timestamp
    ON info_need_judgments(timestamp DESC);

-- Composite index for common query patterns
CREATE INDEX IF NOT EXISTS idx_info_need_judgments_composite
    ON info_need_judgments(session_id, classified_type, outcome, timestamp DESC);

-- Update schema version
INSERT INTO schema_version (version, applied_at)
VALUES (
    '0.38.0',
    CURRENT_TIMESTAMP
);
