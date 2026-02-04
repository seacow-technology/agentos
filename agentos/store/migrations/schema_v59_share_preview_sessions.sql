-- Migration v0.59 (v0.59.0): Share Links and Preview Sessions Persistent Storage
-- Description: Migrate share links and preview sessions from in-memory storage to database
-- Purpose: Enable share/preview functionality to persist across restarts with TTL support
-- Migration from v0.58 -> v0.59
--
-- Background:
--   - share.py:27 had shared_previews dict (in-memory)
--   - preview.py:45 had preview_sessions dict (in-memory)
--   - Need persistent storage with TTL and access tracking
--   - Security: cryptographically secure tokens, access logs
--
-- target_db: agentos

PRAGMA foreign_keys = OFF;

-- Create share_links table
CREATE TABLE IF NOT EXISTS share_links (
    token TEXT PRIMARY KEY,
    resource_type TEXT NOT NULL,  -- 'task'|'project'|'session'|'artifact'|'code'|'preview'
    resource_id TEXT NOT NULL,
    creator_id TEXT,
    permissions TEXT,  -- JSON: ['read', 'comment', 'execute'] etc
    created_at INTEGER NOT NULL,  -- epoch milliseconds
    expires_at INTEGER,  -- epoch milliseconds, NULL = never expires
    access_count INTEGER DEFAULT 0,
    last_accessed_at INTEGER,  -- epoch milliseconds
    metadata TEXT,  -- JSON: additional fields
    CONSTRAINT valid_resource_type CHECK (resource_type IN ('task', 'project', 'session', 'artifact', 'code', 'preview'))
);

-- Create indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_share_links_resource ON share_links(resource_type, resource_id);
CREATE INDEX IF NOT EXISTS idx_share_links_expires ON share_links(expires_at);
CREATE INDEX IF NOT EXISTS idx_share_links_creator ON share_links(creator_id);
CREATE INDEX IF NOT EXISTS idx_share_links_created_at ON share_links(created_at);

-- Create preview_sessions table
CREATE TABLE IF NOT EXISTS preview_sessions (
    session_id TEXT PRIMARY KEY,
    share_token TEXT,  -- FK to share_links if session created from share
    resource_type TEXT NOT NULL,  -- 'html'|'code'|'artifact'
    resource_id TEXT,  -- Original resource ID if applicable
    html_content TEXT,  -- HTML content for preview
    preset TEXT DEFAULT 'html-basic',  -- 'html-basic'|'three-webgl-umd'
    deps_injected TEXT,  -- JSON: list of injected dependencies
    snippet_id TEXT,  -- Optional snippet ID
    viewer_id TEXT,  -- Anonymous or authenticated viewer
    created_at INTEGER NOT NULL,  -- epoch milliseconds
    expires_at INTEGER NOT NULL,  -- epoch milliseconds
    last_activity_at INTEGER NOT NULL,  -- epoch milliseconds
    metadata TEXT,  -- JSON: additional fields
    FOREIGN KEY (share_token) REFERENCES share_links(token) ON DELETE SET NULL
);

-- Create indexes for preview sessions
CREATE INDEX IF NOT EXISTS idx_preview_sessions_expires ON preview_sessions(expires_at);
CREATE INDEX IF NOT EXISTS idx_preview_sessions_share_token ON preview_sessions(share_token);
CREATE INDEX IF NOT EXISTS idx_preview_sessions_viewer ON preview_sessions(viewer_id);
CREATE INDEX IF NOT EXISTS idx_preview_sessions_created_at ON preview_sessions(created_at);

-- Create share_access_logs table for security audit
CREATE TABLE IF NOT EXISTS share_access_logs (
    id TEXT PRIMARY KEY,
    share_token TEXT NOT NULL,
    accessed_at INTEGER NOT NULL,  -- epoch milliseconds
    viewer_ip TEXT,
    viewer_agent TEXT,
    action TEXT NOT NULL,  -- 'view'|'download'|'comment'|'execute'
    session_id TEXT,  -- Preview session ID if applicable
    metadata TEXT,  -- JSON: additional context
    FOREIGN KEY (share_token) REFERENCES share_links(token) ON DELETE CASCADE
);

-- Create indexes for access logs
CREATE INDEX IF NOT EXISTS idx_share_access_logs_token ON share_access_logs(share_token);
CREATE INDEX IF NOT EXISTS idx_share_access_logs_accessed_at ON share_access_logs(accessed_at);
CREATE INDEX IF NOT EXISTS idx_share_access_logs_action ON share_access_logs(action);

PRAGMA foreign_keys = ON;

-- Update schema version
INSERT OR REPLACE INTO schema_version (version, applied_at_ms, description)
VALUES ('0.59.0', (strftime('%s', 'now') * 1000), 'Share links and preview sessions persistent storage');
