-- Migration v0.9.0: Command History
-- Add command_history table to track all command executions

-- Command history table
CREATE TABLE IF NOT EXISTS command_history (
    id TEXT PRIMARY KEY,
    command_id TEXT NOT NULL,         -- e.g., "kb:search"
    args TEXT,                        -- JSON encoded arguments
    executed_at TEXT NOT NULL,        -- ISO 8601 timestamp
    duration_ms INTEGER,              -- Execution duration in milliseconds
    status TEXT NOT NULL,             -- success/failure/cancelled
    result_summary TEXT,              -- Human-readable summary
    error TEXT,                       -- Error message if failed
    task_id TEXT,                     -- Associated task ID (if any)
    session_id TEXT,                  -- Session ID (if any)
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_command_history_command_id ON command_history(command_id);
CREATE INDEX IF NOT EXISTS idx_command_history_executed_at ON command_history(executed_at DESC);
CREATE INDEX IF NOT EXISTS idx_command_history_status ON command_history(status);
CREATE INDEX IF NOT EXISTS idx_command_history_task_id ON command_history(task_id);

-- Pinned commands table (commands pinned by user)
CREATE TABLE IF NOT EXISTS pinned_commands (
    id TEXT PRIMARY KEY,
    history_id TEXT NOT NULL,
    pinned_at TEXT NOT NULL DEFAULT (datetime('now')),
    note TEXT,                        -- User note about why it's pinned
    FOREIGN KEY (history_id) REFERENCES command_history(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_pinned_commands_pinned_at ON pinned_commands(pinned_at DESC);

-- 更新 schema 版本（幂等操作）
INSERT OR REPLACE INTO schema_version (version, applied_at) 
VALUES ('0.9.0', datetime('now'));
