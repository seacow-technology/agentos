-- Schema v66: Extension Execution Governance
-- Wave C3: Extension Execute Real Implementation
--
-- Provides authorization, audit trail, and policy enforcement for extension execution.
--
-- Security layers:
-- 1. Pre-execution authorization checks (extension_authorizations)
-- 2. Complete execution audit trail (extension_executions)
-- 3. Authorization lifecycle management (active, revoked, expired)
-- 4. Execution count limits and expiration
--
-- Created: 2026-02-01
-- Author: Wave C3 Implementation

-- =============================================================================
-- Extension Execution Authorization Table
-- =============================================================================
-- Manages who can execute which extensions, with fine-grained control over:
-- - Scope (global, user, session)
-- - Action-level permissions (or wildcard '*' for all actions)
-- - Time-based expiration
-- - Usage count limits
-- - Revocation capability

CREATE TABLE IF NOT EXISTS extension_authorizations (
    -- Primary key
    auth_id TEXT PRIMARY KEY,              -- UUID v7-style identifier (auth-YYYYMMDDHHMMSS-NNNN)

    -- Authorization target
    extension_id TEXT NOT NULL,            -- Extension identifier (e.g., "tools.postman")
    action_id TEXT NOT NULL,               -- Action identifier (or '*' for all actions)

    -- Authorization metadata
    authorized_by TEXT NOT NULL,           -- User/Agent who granted authorization
    scope TEXT NOT NULL,                   -- 'user', 'session', 'global'
    scope_id TEXT,                         -- User ID, Session ID, or NULL for global

    -- Expiration and limits
    expires_at INTEGER,                    -- Expiration timestamp (epoch ms, NULL = never expires)
    max_executions INTEGER,                -- Maximum execution count (NULL = unlimited)
    execution_count INTEGER DEFAULT 0,     -- Current execution count

    -- Status tracking
    status TEXT NOT NULL DEFAULT 'active', -- 'active', 'revoked', 'expired'
    metadata TEXT,                         -- JSON metadata (optional)

    -- Timestamps
    created_at INTEGER NOT NULL,           -- Creation timestamp (epoch ms)
    updated_at INTEGER NOT NULL            -- Last update timestamp (epoch ms)
);

-- =============================================================================
-- Extension Execution History Table
-- =============================================================================
-- Complete audit trail of all extension executions (including blocked attempts).
-- Records every execution attempt with full context for compliance and debugging.

CREATE TABLE IF NOT EXISTS extension_executions (
    -- Primary key
    execution_id TEXT PRIMARY KEY,         -- UUID v7-style identifier (exec-YYYYMMDDHHMMSS-NNNN)

    -- Execution target
    extension_id TEXT NOT NULL,            -- Extension identifier
    action_id TEXT NOT NULL,               -- Action identifier
    runner_type TEXT NOT NULL,             -- 'builtin', 'shell', 'simulated'

    -- Authorization context
    auth_id TEXT,                          -- Authorization used (if any, NULL if blocked)
    session_id TEXT,                       -- Session context (optional)
    user_id TEXT,                          -- User who triggered (optional)

    -- Execution status
    status TEXT NOT NULL,                  -- 'pending', 'running', 'success', 'failed', 'blocked'
    exit_code INTEGER,                     -- Exit code (0=success, NULL if not applicable)
    duration_ms INTEGER,                   -- Execution duration in milliseconds

    -- Output and errors
    output_preview TEXT,                   -- First 1000 chars of output (truncated)
    error_message TEXT,                    -- Error details if failed
    blocked_reason TEXT,                   -- Reason if blocked by governance

    -- Security context
    sandbox_mode TEXT,                     -- 'none', 'restricted', 'isolated'
    metadata TEXT,                         -- JSON metadata (args, flags, etc.)

    -- Timestamps
    started_at INTEGER NOT NULL,           -- Execution start timestamp (epoch ms)
    completed_at INTEGER,                  -- Execution completion timestamp (epoch ms, NULL if running)
    created_at INTEGER NOT NULL            -- Record creation timestamp (epoch ms)
);

-- =============================================================================
-- Indexes for Performance
-- =============================================================================

-- Authorization lookups by extension and action
CREATE INDEX IF NOT EXISTS idx_ext_auth_extension
ON extension_authorizations(extension_id, action_id);

-- Authorization lookups by scope
CREATE INDEX IF NOT EXISTS idx_ext_auth_scope
ON extension_authorizations(scope, scope_id);

-- Authorization status filtering
CREATE INDEX IF NOT EXISTS idx_ext_auth_status
ON extension_authorizations(status);

-- Execution history by extension
CREATE INDEX IF NOT EXISTS idx_ext_exec_extension
ON extension_executions(extension_id, action_id);

-- Execution history by session
CREATE INDEX IF NOT EXISTS idx_ext_exec_session
ON extension_executions(session_id);

-- Execution status filtering
CREATE INDEX IF NOT EXISTS idx_ext_exec_status
ON extension_executions(status);

-- Execution history chronological ordering
CREATE INDEX IF NOT EXISTS idx_ext_exec_started
ON extension_executions(started_at DESC);

-- =============================================================================
-- Schema Version Record
-- =============================================================================

INSERT INTO schema_version (version, description)
VALUES ('v66', 'Extension execution governance (authorization + audit trail)');
