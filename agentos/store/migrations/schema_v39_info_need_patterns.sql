-- schema_v39_info_need_patterns.sql
-- Migration for InfoNeed pattern nodes in BrainOS
-- Task #23: Implement BrainOS decision pattern nodes

-- InfoNeed judgment pattern nodes
CREATE TABLE IF NOT EXISTS info_need_patterns (
    pattern_id TEXT PRIMARY KEY,
    pattern_type TEXT NOT NULL,  -- PatternType enum

    -- Pattern features (stored as JSON)
    question_features TEXT NOT NULL,  -- JSON: non-semantic features

    -- Classification mapping
    classification_type TEXT NOT NULL,  -- InfoNeedType enum
    confidence_level TEXT NOT NULL,  -- ConfidenceLevel enum

    -- Statistical data
    occurrence_count INTEGER NOT NULL DEFAULT 0,
    success_count INTEGER NOT NULL DEFAULT 0,
    failure_count INTEGER NOT NULL DEFAULT 0,
    avg_confidence_score REAL NOT NULL DEFAULT 0.0,
    avg_latency_ms REAL NOT NULL DEFAULT 0.0,
    success_rate REAL NOT NULL DEFAULT 0.0,

    -- Time metadata
    first_seen TEXT NOT NULL,  -- ISO 8601 format
    last_seen TEXT NOT NULL,  -- ISO 8601 format
    last_updated TEXT NOT NULL,  -- ISO 8601 format

    -- Version control
    pattern_version INTEGER NOT NULL DEFAULT 1,

    CONSTRAINT valid_pattern_type CHECK (
        pattern_type IN (
            'question_keyword_pattern',
            'rule_signal_pattern',
            'llm_confidence_pattern',
            'combined_pattern'
        )
    ),
    CONSTRAINT valid_classification_type CHECK (
        classification_type IN (
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
    CONSTRAINT valid_counts CHECK (
        occurrence_count >= 0 AND
        success_count >= 0 AND
        failure_count >= 0 AND
        success_count + failure_count <= occurrence_count
    ),
    CONSTRAINT valid_scores CHECK (
        avg_confidence_score >= 0.0 AND avg_confidence_score <= 1.0 AND
        avg_latency_ms >= 0.0 AND
        success_rate >= 0.0 AND success_rate <= 1.0
    )
);

-- Decision signal nodes
CREATE TABLE IF NOT EXISTS decision_signals (
    signal_id TEXT PRIMARY KEY,
    signal_type TEXT NOT NULL,  -- SignalType enum
    signal_value TEXT NOT NULL,  -- Signal value (keyword, pattern, etc.)

    -- Effectiveness metrics
    effectiveness_score REAL NOT NULL DEFAULT 0.0,
    true_positive_count INTEGER NOT NULL DEFAULT 0,
    false_positive_count INTEGER NOT NULL DEFAULT 0,
    true_negative_count INTEGER NOT NULL DEFAULT 0,
    false_negative_count INTEGER NOT NULL DEFAULT 0,

    -- Time metadata
    created_at TEXT NOT NULL,  -- ISO 8601 format
    last_updated TEXT NOT NULL,  -- ISO 8601 format

    CONSTRAINT valid_signal_type CHECK (
        signal_type IN (
            'keyword',
            'length',
            'tense',
            'interrogative',
            'sentiment',
            'structure'
        )
    ),
    CONSTRAINT valid_effectiveness CHECK (
        effectiveness_score >= 0.0 AND effectiveness_score <= 1.0
    ),
    CONSTRAINT valid_signal_counts CHECK (
        true_positive_count >= 0 AND
        false_positive_count >= 0 AND
        true_negative_count >= 0 AND
        false_negative_count >= 0
    ),
    UNIQUE(signal_type, signal_value)
);

-- Pattern-signal relationship links
CREATE TABLE IF NOT EXISTS pattern_signal_links (
    link_id TEXT PRIMARY KEY,
    pattern_id TEXT NOT NULL,
    signal_id TEXT NOT NULL,
    weight REAL NOT NULL DEFAULT 1.0,

    CONSTRAINT valid_weight CHECK (weight >= 0.0),
    FOREIGN KEY (pattern_id) REFERENCES info_need_patterns(pattern_id) ON DELETE CASCADE,
    FOREIGN KEY (signal_id) REFERENCES decision_signals(signal_id) ON DELETE CASCADE,
    UNIQUE(pattern_id, signal_id)
);

-- Pattern evolution history
CREATE TABLE IF NOT EXISTS pattern_evolution (
    evolution_id TEXT PRIMARY KEY,
    from_pattern_id TEXT NOT NULL,
    to_pattern_id TEXT NOT NULL,
    evolution_type TEXT NOT NULL,  -- EvolutionType enum
    reason TEXT NOT NULL,
    timestamp TEXT NOT NULL,  -- ISO 8601 format
    triggered_by TEXT,  -- Job name, manual, etc.

    CONSTRAINT valid_evolution_type CHECK (
        evolution_type IN ('refined', 'split', 'merged', 'deprecated')
    ),
    FOREIGN KEY (from_pattern_id) REFERENCES info_need_patterns(pattern_id) ON DELETE CASCADE,
    FOREIGN KEY (to_pattern_id) REFERENCES info_need_patterns(pattern_id) ON DELETE CASCADE
);

-- Indexes for efficient queries

-- Index for type-based queries
CREATE INDEX IF NOT EXISTS idx_info_need_patterns_type
    ON info_need_patterns(classification_type, occurrence_count DESC);

-- Index for occurrence-based queries
CREATE INDEX IF NOT EXISTS idx_info_need_patterns_occurrence
    ON info_need_patterns(occurrence_count DESC);

-- Index for success rate queries
CREATE INDEX IF NOT EXISTS idx_info_need_patterns_success_rate
    ON info_need_patterns(success_rate DESC);

-- Index for time-based queries
CREATE INDEX IF NOT EXISTS idx_info_need_patterns_last_seen
    ON info_need_patterns(last_seen DESC);

-- Index for signal type queries
CREATE INDEX IF NOT EXISTS idx_decision_signals_type
    ON decision_signals(signal_type);

-- Index for signal effectiveness queries
CREATE INDEX IF NOT EXISTS idx_decision_signals_effectiveness
    ON decision_signals(effectiveness_score DESC);

-- Index for pattern-signal links
CREATE INDEX IF NOT EXISTS idx_pattern_signal_links_pattern
    ON pattern_signal_links(pattern_id);

CREATE INDEX IF NOT EXISTS idx_pattern_signal_links_signal
    ON pattern_signal_links(signal_id);

-- Index for evolution history
CREATE INDEX IF NOT EXISTS idx_pattern_evolution_from
    ON pattern_evolution(from_pattern_id, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_pattern_evolution_to
    ON pattern_evolution(to_pattern_id, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_pattern_evolution_timestamp
    ON pattern_evolution(timestamp DESC);

-- Update schema version
INSERT INTO schema_version (version, applied_at)
VALUES (
    '0.39.0',
    CURRENT_TIMESTAMP
);
