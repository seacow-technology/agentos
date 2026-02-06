-- Migration v0.8.0: Chat Mode + Vector Embeddings
-- Part 1: Chat Mode Support
-- Part 2: Vector Embeddings for ProjectKB

-- ============================================
-- Part 1: Chat Mode Support
-- ============================================

-- Chat Sessions: Independent chat conversations
CREATE TABLE IF NOT EXISTS chat_sessions (
    session_id TEXT PRIMARY KEY,  -- ULID
    title TEXT,  -- Session title (summary of first message or user-provided)
    task_id TEXT,  -- Optional: link to associated Task
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT,  -- JSON: {model, provider, context_budget, rag_enabled, ...}
    
    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
);

CREATE INDEX IF NOT EXISTS idx_chat_sessions_task ON chat_sessions(task_id);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_created ON chat_sessions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_updated ON chat_sessions(updated_at DESC);

-- Chat Messages: Message history for each session
CREATE TABLE IF NOT EXISTS chat_messages (
    message_id TEXT PRIMARY KEY,  -- ULID
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,  -- system|user|assistant|tool
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT,  -- JSON: {tokens_est, source, citations, command_result, ...}
    
    FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_role ON chat_messages(role);
CREATE INDEX IF NOT EXISTS idx_chat_messages_created ON chat_messages(created_at DESC);

-- ============================================
-- Part 2: Vector Embeddings for ProjectKB
-- ============================================

-- Note: kb_embeddings table already exists from v0.7.0 with different schema
-- The v0.7.0 table has: chunk_id, vector, model, dims, built_at
-- The v0.8.0 table needs: chunk_id, model, dims, vector, content_hash, built_at

-- Drop the old kb_embeddings table if it exists with old schema
DROP TABLE IF EXISTS kb_embeddings;

-- Create new kb_embeddings table with proper schema
CREATE TABLE kb_embeddings (
    chunk_id TEXT PRIMARY KEY,
    model TEXT NOT NULL,
    dims INTEGER NOT NULL,
    vector BLOB NOT NULL,  -- float32 array serialized (numpy tobytes)
    content_hash TEXT NOT NULL,
    built_at INTEGER NOT NULL,
    FOREIGN KEY (chunk_id) REFERENCES kb_chunks(chunk_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_kb_embeddings_content_hash 
ON kb_embeddings(content_hash);

CREATE INDEX IF NOT EXISTS idx_kb_embeddings_model
ON kb_embeddings(model);

-- Embedding metadata
CREATE TABLE IF NOT EXISTS kb_embedding_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at INTEGER NOT NULL
);

-- ============================================
-- Version Tracking
-- ============================================

INSERT OR REPLACE INTO schema_version (version, applied_at) 
VALUES ('0.8.0', datetime('now'));
