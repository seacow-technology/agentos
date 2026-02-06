-- Migration v0.11.0: Context Governance (Phase B.1)
-- Part 1: Artifacts (summary/requirements/decision)
-- Part 2: Context Snapshots (token budget tracking)
-- Part 3: Context Snapshot Items (for diff capability)

-- ============================================
-- Part 1: Chat Artifacts - Summary and Decisions
-- ============================================

-- Chat Artifacts: Structured outputs from chat sessions (summary, requirements, decisions)
-- These are NOT chat messages but derived artifacts with lineage
-- NOTE: Renamed from 'artifacts' to avoid conflict with v01's run_artifacts table
CREATE TABLE IF NOT EXISTS chat_artifacts (
    artifact_id TEXT PRIMARY KEY,  -- ULID
    artifact_type TEXT NOT NULL,  -- summary|requirements|decision|plan|analysis
    session_id TEXT,  -- Optional: associated chat session
    task_id TEXT,  -- Optional: associated task
    title TEXT,
    content TEXT NOT NULL,  -- Main content (text)
    content_json TEXT,  -- Optional: structured content (JSON)
    version INTEGER NOT NULL DEFAULT 1,  -- Artifact version (for iterative refinement)
    created_at INTEGER NOT NULL,  -- Unix epoch milliseconds
    created_by TEXT NOT NULL DEFAULT 'system',  -- system|user|agent
    metadata TEXT,  -- JSON: {model, tokens, derived_from_msg_ids, replace_strategy, ...}

    FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id) ON DELETE CASCADE,
    FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_chat_artifacts_session_type
ON chat_artifacts(session_id, artifact_type, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_chat_artifacts_task_type
ON chat_artifacts(task_id, artifact_type, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_chat_artifacts_type_created
ON chat_artifacts(artifact_type, created_at DESC);

-- ============================================
-- Part 2: Context Snapshots - Budget Tracking
-- ============================================

-- Context Snapshots: Record of context assembly for each send
-- Enables: budget tracking, diff, audit, cost attribution
CREATE TABLE IF NOT EXISTS context_snapshots (
    snapshot_id TEXT PRIMARY KEY,  -- ULID
    session_id TEXT NOT NULL,
    created_at INTEGER NOT NULL,  -- Unix epoch milliseconds
    reason TEXT NOT NULL,  -- send|dry_run|audit|summary_trigger
    provider TEXT,  -- local|cloud|null (not sent yet)
    model TEXT,  -- qwen2.5:14b|gpt-4o-mini|...
    
    -- Budget and usage
    budget_tokens INTEGER NOT NULL,
    total_tokens_est INTEGER NOT NULL,
    
    -- Token breakdown by source
    tokens_system INTEGER NOT NULL DEFAULT 0,
    tokens_window INTEGER NOT NULL DEFAULT 0,
    tokens_rag INTEGER NOT NULL DEFAULT 0,
    tokens_memory INTEGER NOT NULL DEFAULT 0,
    tokens_summary INTEGER NOT NULL DEFAULT 0,
    tokens_policy INTEGER NOT NULL DEFAULT 0,
    
    -- Quick reference (for fast export)
    composition_json TEXT NOT NULL,  -- {window_msg_ids:[], summary_artifact_ids:[], rag_chunk_ids:[], memory_ids:[], ...}
    assembled_hash TEXT,  -- SHA256 of final messages (for dedup)
    metadata TEXT,  -- JSON: {usage_ratio, watermark, trigger_summary, ...}
    
    FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_context_snapshots_session_time 
ON context_snapshots(session_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_context_snapshots_reason 
ON context_snapshots(reason, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_context_snapshots_usage 
ON context_snapshots(total_tokens_est DESC);

-- ============================================
-- Part 3: Context Snapshot Items - Diff Capability
-- ============================================

-- Context Snapshot Items: Detailed composition for diff
-- This enables "what changed?" queries between snapshots
CREATE TABLE IF NOT EXISTS context_snapshot_items (
    snapshot_id TEXT NOT NULL,
    item_type TEXT NOT NULL,  -- window_msg|rag_chunk|memory|summary|policy
    item_id TEXT NOT NULL,  -- message_id|chunk_id|memory_id|artifact_id|policy_id
    tokens_est INTEGER NOT NULL DEFAULT 0,
    rank INTEGER NOT NULL DEFAULT 0,  -- Order/priority (for RAG topK, window order)
    metadata TEXT,  -- JSON: {score, reason, ...}
    
    PRIMARY KEY(snapshot_id, item_type, item_id),
    FOREIGN KEY (snapshot_id) REFERENCES context_snapshots(snapshot_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_snapshot_items_snapshot_type 
ON context_snapshot_items(snapshot_id, item_type);

CREATE INDEX IF NOT EXISTS idx_snapshot_items_item 
ON context_snapshot_items(item_type, item_id);

-- ============================================
-- Schema Metadata
-- ============================================

-- Record schema capabilities for introspection
CREATE TABLE IF NOT EXISTS schema_capabilities (
    capability TEXT PRIMARY KEY,
    version TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,  -- 0=disabled, 1=enabled
    description TEXT,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT OR REPLACE INTO schema_capabilities (capability, version, description) VALUES
    ('context_governance', '0.11.0', 'Context budget tracking and diff capability'),
    ('chat_artifacts', '0.11.0', 'Structured chat artifacts with lineage (summary, requirements, decisions)'),
    ('context_snapshots', '0.11.0', 'Token usage tracking per context assembly'),
    ('context_diff', '0.11.0', 'Snapshot comparison for explainability');

-- ============================================
-- Version Tracking
-- ============================================

INSERT OR REPLACE INTO schema_version (version, applied_at) 
VALUES ('0.11.0', datetime('now'));
