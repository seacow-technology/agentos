-- Schema v51: Evidence Capabilities for AgentOS v3
--
-- Complete evidence collection, linking, replay, and export system.
--
-- This schema provides the護城河 (moat) for:
-- - Regulatory compliance (SOX, GDPR, HIPAA)
-- - Legal discovery and forensics
-- - Audit trails for enterprise
-- - Time-travel debugging
-- - Rollback and replay
--
-- Design Principles:
-- 1. Evidence is IMMUTABLE (no updates after creation)
-- 2. Every Capability invocation MUST have evidence
-- 3. Evidence chains link: decision → action → memory → state_change
-- 4. Evidence integrity verified via SHA256 hash + digital signature
-- 5. All timestamps use epoch_ms (ADR-011)
--
-- Dependencies:
-- - Schema v47: Capability Registry
-- - Schema v48: Decision Capabilities
-- - Schema v49: Action Capabilities
-- - Schema v50: Governance Capabilities
-- - Schema v50z: Add description column to schema_version (executed before v51)

PRAGMA foreign_keys = ON;

-- ============================================================================
-- Evidence Log Table
-- ============================================================================

-- Primary evidence storage table
-- Stores complete evidence for every Capability invocation
CREATE TABLE IF NOT EXISTS evidence_log (
    evidence_id TEXT PRIMARY KEY,
    timestamp_ms INTEGER NOT NULL,

    -- Operation identification
    operation_type TEXT NOT NULL,  -- state|decision|action|governance
    operation_capability_id TEXT NOT NULL,
    operation_id TEXT NOT NULL,

    -- Context
    agent_id TEXT NOT NULL,
    session_id TEXT,
    project_id TEXT,
    decision_id TEXT,  -- Link to decision (if applicable)

    -- Input/Output (hashed for privacy, summary for viewing)
    input_params_hash TEXT NOT NULL,
    input_params_summary TEXT,

    output_result_hash TEXT NOT NULL,
    output_result_summary TEXT,

    -- Side Effects
    side_effects_declared_json TEXT,  -- JSON array of declared side effects
    side_effects_actual_json TEXT,    -- JSON array of actual side effects

    -- Provenance (execution environment)
    provenance_json TEXT NOT NULL,  -- {host, pid, agentos_version, python_version, user}

    -- Integrity (cryptographic verification)
    integrity_hash TEXT NOT NULL,      -- SHA256 of evidence content
    integrity_signature TEXT,          -- Optional digital signature

    -- Immutability flag (always 1)
    immutable INTEGER NOT NULL DEFAULT 1,

    -- Check constraints
    CHECK (operation_type IN ('state', 'decision', 'action', 'governance')),
    CHECK (immutable = 1),

    -- Foreign keys
    FOREIGN KEY (decision_id) REFERENCES decision_plans(plan_id)
        ON DELETE SET NULL
);

-- Indexes for evidence_log
CREATE INDEX IF NOT EXISTS idx_ev_operation
    ON evidence_log(operation_type, operation_id);

CREATE INDEX IF NOT EXISTS idx_ev_agent_time
    ON evidence_log(agent_id, timestamp_ms DESC);

CREATE INDEX IF NOT EXISTS idx_ev_decision
    ON evidence_log(decision_id);

CREATE INDEX IF NOT EXISTS idx_ev_timestamp
    ON evidence_log(timestamp_ms DESC);

CREATE INDEX IF NOT EXISTS idx_ev_capability
    ON evidence_log(operation_capability_id);


-- ============================================================================
-- Evidence Chains Tables
-- ============================================================================

-- Evidence chains table
-- Stores complete chains of related evidence
CREATE TABLE IF NOT EXISTS evidence_chains (
    chain_id TEXT PRIMARY KEY,
    links_json TEXT NOT NULL,  -- JSON array of links
    created_at_ms INTEGER NOT NULL,
    created_by TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chain_created
    ON evidence_chains(created_at_ms DESC);


-- Evidence chain links table
-- Individual links in evidence chains (for querying)
CREATE TABLE IF NOT EXISTS evidence_chain_links (
    link_id INTEGER PRIMARY KEY AUTOINCREMENT,
    chain_id TEXT NOT NULL,
    from_type TEXT NOT NULL,  -- decision|action|memory|state
    from_id TEXT NOT NULL,
    to_type TEXT NOT NULL,
    to_id TEXT NOT NULL,
    relationship TEXT NOT NULL,  -- caused_by|resulted_in|modified|triggered|approved_by

    -- Check constraints
    CHECK (from_type IN ('decision', 'action', 'memory', 'state', 'governance')),
    CHECK (to_type IN ('decision', 'action', 'memory', 'state', 'governance')),
    CHECK (relationship IN ('caused_by', 'resulted_in', 'modified', 'triggered', 'approved_by')),

    -- Foreign keys
    FOREIGN KEY (chain_id) REFERENCES evidence_chains(chain_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_link_chain
    ON evidence_chain_links(chain_id);

CREATE INDEX IF NOT EXISTS idx_link_from
    ON evidence_chain_links(from_type, from_id);

CREATE INDEX IF NOT EXISTS idx_link_to
    ON evidence_chain_links(to_type, to_id);


-- ============================================================================
-- Evidence Replay Tables
-- ============================================================================

-- Evidence replay log table
-- Tracks all evidence replay operations (for debugging and validation)
CREATE TABLE IF NOT EXISTS evidence_replay_log (
    replay_id TEXT PRIMARY KEY,
    evidence_id TEXT NOT NULL,
    replay_mode TEXT NOT NULL,  -- read_only|validate

    -- Comparison results
    original_output_hash TEXT NOT NULL,
    replayed_output_hash TEXT,
    matches INTEGER,  -- 0|1|NULL (NULL if not compared)

    -- Metadata
    replayed_by TEXT NOT NULL,
    replayed_at_ms INTEGER NOT NULL,

    -- Check constraints
    CHECK (replay_mode IN ('read_only', 'validate')),
    CHECK (matches IS NULL OR matches IN (0, 1)),

    -- Foreign keys
    FOREIGN KEY (evidence_id) REFERENCES evidence_log(evidence_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_replay_evidence
    ON evidence_replay_log(evidence_id);

CREATE INDEX IF NOT EXISTS idx_replay_time
    ON evidence_replay_log(replayed_at_ms DESC);


-- ============================================================================
-- Evidence Export Tables
-- ============================================================================

-- Evidence exports table
-- Tracks exported evidence packages (for compliance and audit)
CREATE TABLE IF NOT EXISTS evidence_exports (
    export_id TEXT PRIMARY KEY,
    query_json TEXT NOT NULL,  -- JSON of ExportQuery
    format TEXT NOT NULL,       -- json|pdf|csv|html

    -- File metadata
    file_path TEXT NOT NULL,
    file_size_bytes INTEGER NOT NULL,
    file_hash TEXT NOT NULL,    -- SHA256 of export file

    -- Metadata
    exported_by TEXT NOT NULL,
    exported_at_ms INTEGER NOT NULL,
    expires_at_ms INTEGER,      -- When export file expires (NULL = never)

    -- Check constraints
    CHECK (format IN ('json', 'pdf', 'csv', 'html'))
);

CREATE INDEX IF NOT EXISTS idx_export_by
    ON evidence_exports(exported_by, exported_at_ms DESC);

CREATE INDEX IF NOT EXISTS idx_export_expires
    ON evidence_exports(expires_at_ms);


-- ============================================================================
-- Evidence Verification Views
-- ============================================================================

-- View for evidence with integrity check status
CREATE VIEW IF NOT EXISTS evidence_integrity_view AS
SELECT
    e.evidence_id,
    e.timestamp_ms,
    e.operation_type,
    e.operation_capability_id,
    e.agent_id,
    e.integrity_hash,
    e.integrity_signature,
    CASE
        WHEN e.integrity_signature IS NOT NULL THEN 'signed'
        ELSE 'unsigned'
    END AS signature_status,
    e.immutable
FROM evidence_log e;


-- View for evidence chains with entity counts
CREATE VIEW IF NOT EXISTS evidence_chain_summary AS
SELECT
    c.chain_id,
    c.created_at_ms,
    c.created_by,
    COUNT(l.link_id) AS link_count,
    COUNT(DISTINCT l.from_type || ':' || l.from_id) AS source_entity_count,
    COUNT(DISTINCT l.to_type || ':' || l.to_id) AS target_entity_count
FROM evidence_chains c
LEFT JOIN evidence_chain_links l ON c.chain_id = l.chain_id
GROUP BY c.chain_id;


-- View for evidence replay statistics
CREATE VIEW IF NOT EXISTS evidence_replay_stats AS
SELECT
    e.evidence_id,
    e.operation_type,
    e.operation_capability_id,
    COUNT(r.replay_id) AS total_replays,
    SUM(CASE WHEN r.replay_mode = 'read_only' THEN 1 ELSE 0 END) AS read_only_replays,
    SUM(CASE WHEN r.replay_mode = 'validate' THEN 1 ELSE 0 END) AS validate_replays,
    SUM(CASE WHEN r.matches = 1 THEN 1 ELSE 0 END) AS matching_replays,
    SUM(CASE WHEN r.matches = 0 THEN 1 ELSE 0 END) AS non_matching_replays
FROM evidence_log e
LEFT JOIN evidence_replay_log r ON e.evidence_id = r.evidence_id
GROUP BY e.evidence_id;


-- ============================================================================
-- Evidence Audit Triggers
-- ============================================================================

-- Trigger to prevent evidence modification
CREATE TRIGGER IF NOT EXISTS prevent_evidence_modification
BEFORE UPDATE ON evidence_log
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'Evidence is immutable and cannot be modified');
END;


-- Trigger to prevent evidence deletion (except cascades)
CREATE TRIGGER IF NOT EXISTS prevent_evidence_deletion
BEFORE DELETE ON evidence_log
FOR EACH ROW
WHEN OLD.immutable = 1
BEGIN
    SELECT RAISE(ABORT, 'Evidence cannot be deleted (immutable=1)');
END;


-- ============================================================================
-- Evidence Statistics Functions
-- ============================================================================

-- NOTE: SQLite doesn't support user-defined functions in DDL.
--       These would be implemented in application code.
--
-- get_evidence_stats():
--   - Total evidence count
--   - Evidence by operation_type
--   - Evidence by agent
--   - Average chain length
--   - Replay match rate
--   - Export counts by format


-- ============================================================================
-- Schema Version Update
-- ============================================================================

-- Update schema version to v51
INSERT OR REPLACE INTO schema_version (version, applied_at_ms, description)
VALUES (
    '0.51.0',
    (strftime('%s', 'now') * 1000),
    'Evidence Capabilities: evidence_log, evidence_chains, evidence_replay_log, evidence_exports'
);


-- ============================================================================
-- Comments and Documentation
-- ============================================================================

-- Evidence Log Table:
--   - Stores ALL capability invocations with complete evidence
--   - IMMUTABLE (no updates allowed)
--   - Cryptographic integrity (SHA256 + signatures)
--   - Privacy-preserving (hashed inputs/outputs with summaries)
--
-- Evidence Chains:
--   - Links related operations: decision → action → memory → state
--   - Bidirectional traversal (forward and backward)
--   - Supports multi-hop queries
--
-- Evidence Replay:
--   - Read-only replay (simulation, no side effects)
--   - Validate mode (re-execute, requires ADMIN)
--   - Comparison and diff generation
--
-- Evidence Export:
--   - Multiple formats (JSON, PDF, CSV, HTML)
--   - Audit-ready reports
--   - Automatic expiration and cleanup
--
-- Performance Notes:
--   - Indexes optimized for common queries
--   - Views for aggregated statistics
--   - Triggers enforce immutability
--   - Foreign key cascades for cleanup
--
-- Compliance Features:
--   - Complete audit trail (who, what, when, why)
--   - Cryptographic verification (tamper-proof)
--   - Time-travel debugging (replay)
--   - Export for legal discovery (PDF reports)


-- ============================================================================
-- End of Schema v51
-- ============================================================================
