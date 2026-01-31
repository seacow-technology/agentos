-- AgentOS Store Schema v0.6
-- Task-Driven Architecture: Task as the root aggregate for full traceability
-- Migration from v0.5 -> v0.6

-- ============================================
-- Tasks: Root Aggregate for Traceability
-- ============================================

CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,  -- ULID
    session_id TEXT,  -- FK to chat_sessions (formerly task_sessions), optional
    title TEXT,
    status TEXT DEFAULT 'created',  -- Free-form string, recommended: created/planning/executing/succeeded/failed/canceled/orphan
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT,  -- user/system identifier
    metadata TEXT,  -- JSON: {orphan: true, ...}

    FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id)
);

CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_session ON tasks(session_id);
CREATE INDEX IF NOT EXISTS idx_tasks_created ON tasks(created_at DESC);

-- ============================================
-- Task Lineage: The "收编层" - Aggregates all existing IDs
-- ============================================

CREATE TABLE IF NOT EXISTS task_lineage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    kind TEXT NOT NULL,  -- Free-form string, recommended: nl_request|intent|plan|coordinator_run|dry_result|execution_request|run|tape|artifact|commit
    ref_id TEXT NOT NULL,  -- Reference to actual ID (intent_id, run_id, commit_hash, etc.)
    phase TEXT,  -- Free-form string, recommended: intent_analysis|coordination|dry_execution|execution|completed
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT,  -- JSON: additional context
    
    FOREIGN KEY (task_id) REFERENCES tasks(task_id),
    
    -- Key constraint: UNIQUE per task (allows same ref_id across multiple tasks)
    UNIQUE(task_id, kind, ref_id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_task_lineage_task ON task_lineage(task_id);
CREATE INDEX IF NOT EXISTS idx_task_lineage_kind ON task_lineage(kind);
CREATE INDEX IF NOT EXISTS idx_task_lineage_ref ON task_lineage(kind, ref_id);  -- Global reverse lookup
CREATE INDEX IF NOT EXISTS idx_task_lineage_phase ON task_lineage(phase);
CREATE INDEX IF NOT EXISTS idx_task_lineage_created ON task_lineage(created_at DESC);

-- ============================================
-- Task Sessions: Conversation/Dialog Management
-- ============================================
-- DEPRECATED: task_sessions table has been merged into chat_sessions (schema v35)
-- This table definition is kept for historical reference only.
-- All session operations should now use chat_sessions table.
-- See: agentos/store/migrations/schema_v35_merge_task_sessions.sql

-- CREATE TABLE IF NOT EXISTS task_sessions (
--     session_id TEXT PRIMARY KEY,  -- ULID
--     channel TEXT,  -- cli|api|ui
--     metadata TEXT,  -- JSON: user info, context, etc.
--     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
--     last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
-- );
--
-- CREATE INDEX IF NOT EXISTS idx_task_sessions_channel ON task_sessions(channel);
-- CREATE INDEX IF NOT EXISTS idx_task_sessions_created ON task_sessions(created_at DESC);

-- ============================================
-- Task Agents: Agent Invocation Records
-- ============================================

CREATE TABLE IF NOT EXISTS task_agents (
    invocation_id TEXT PRIMARY KEY,  -- ULID
    task_id TEXT NOT NULL,
    run_id TEXT,  -- Optional: link to specific run
    agent_key TEXT NOT NULL,  -- Registry key
    model TEXT,  -- gpt-4|claude-3|local-llama|...
    input_ref TEXT,  -- Reference to input (tape/log/blob)
    output_ref TEXT,  -- Reference to output
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP,
    status TEXT,  -- started|completed|failed
    metadata TEXT,  -- JSON: additional info
    
    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
);

CREATE INDEX IF NOT EXISTS idx_task_agents_task ON task_agents(task_id);
CREATE INDEX IF NOT EXISTS idx_task_agents_run ON task_agents(run_id);
CREATE INDEX IF NOT EXISTS idx_task_agents_agent ON task_agents(agent_key);
CREATE INDEX IF NOT EXISTS idx_task_agents_model ON task_agents(model);
CREATE INDEX IF NOT EXISTS idx_task_agents_started ON task_agents(started_at DESC);

-- ============================================
-- Task Audits: Unified Audit Trail
-- ============================================

CREATE TABLE IF NOT EXISTS task_audits (
    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    level TEXT DEFAULT 'info',  -- info|warn|error
    event_type TEXT NOT NULL,  -- Free-form: intent_created|plan_approved|run_started|commit_created|...
    payload TEXT,  -- JSON: event details
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
);

CREATE INDEX IF NOT EXISTS idx_task_audits_task ON task_audits(task_id);
CREATE INDEX IF NOT EXISTS idx_task_audits_level ON task_audits(level);
CREATE INDEX IF NOT EXISTS idx_task_audits_event ON task_audits(event_type);
CREATE INDEX IF NOT EXISTS idx_task_audits_created ON task_audits(created_at DESC);

-- ============================================
-- Version Tracking
-- ============================================

CREATE TABLE IF NOT EXISTS schema_version (
    version TEXT PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT OR REPLACE INTO schema_version (version) VALUES ('0.6.0');
