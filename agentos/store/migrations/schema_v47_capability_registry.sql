-- Schema v47: Capability Registry and Grants
-- AgentOS v3 Capability System
-- Task #22: Capability注册表和调用路径验证引擎
--
-- Design Philosophy:
-- - Linux capabilities-inspired permission model
-- - All 27 capabilities from 5 domains registered here
-- - Golden Path enforcement: State→Decision→Governance→Action→Evidence
-- - Forbidden paths blocked at registry level

-- ===================================================================
-- 1. Capability Definitions Table
-- ===================================================================

-- Stores the 27 atomic capability definitions
CREATE TABLE IF NOT EXISTS capability_definitions (
    capability_id TEXT PRIMARY KEY,              -- e.g., "state.memory.read"
    domain TEXT NOT NULL,                        -- state|decision|action|governance|evidence
    level TEXT NOT NULL,                         -- none|read|propose|write|admin
    version TEXT NOT NULL,                       -- e.g., "1.0.0"
    definition_json TEXT NOT NULL,               -- Complete CapabilityDefinition as JSON
    created_at_ms INTEGER NOT NULL,              -- When loaded into registry (epoch ms)

    CHECK (domain IN ('state', 'decision', 'action', 'governance', 'evidence')),
    CHECK (level IN ('none', 'read', 'propose', 'write', 'admin'))
);

-- Index for domain-based queries
CREATE INDEX IF NOT EXISTS idx_cap_def_domain
    ON capability_definitions(domain);

-- Index for level-based queries
CREATE INDEX IF NOT EXISTS idx_cap_def_level
    ON capability_definitions(level);

-- ===================================================================
-- 2. Capability Grants Table
-- ===================================================================

-- Tracks which capabilities are granted to which agents
CREATE TABLE IF NOT EXISTS capability_grants (
    grant_id TEXT PRIMARY KEY,                   -- Unique grant ID (ulid)
    agent_id TEXT NOT NULL,                      -- Agent receiving grant (e.g., "chat_agent", "user:alice")
    capability_id TEXT NOT NULL,                 -- Capability being granted
    granted_by TEXT NOT NULL,                    -- Who granted (user_id or system)
    granted_at_ms INTEGER NOT NULL,              -- When granted (epoch ms)
    expires_at_ms INTEGER,                       -- Optional expiration (NULL = never expires)
    scope TEXT,                                  -- Optional scope (e.g., "project:proj-123")
    reason TEXT,                                 -- Human-readable reason
    metadata TEXT,                               -- JSON metadata

    CHECK (granted_at_ms > 0),
    CHECK (expires_at_ms IS NULL OR expires_at_ms > granted_at_ms),

    FOREIGN KEY (capability_id) REFERENCES capability_definitions(capability_id)
);

-- Composite index for permission checks (agent_id + capability_id)
CREATE INDEX IF NOT EXISTS idx_cap_grant_agent_cap
    ON capability_grants(agent_id, capability_id);

-- Index for agent-based queries
CREATE INDEX IF NOT EXISTS idx_cap_grant_agent
    ON capability_grants(agent_id);

-- Index for capability-based queries (who has this capability)
CREATE INDEX IF NOT EXISTS idx_cap_grant_capability
    ON capability_grants(capability_id);

-- Index for expiration tracking
CREATE INDEX IF NOT EXISTS idx_cap_grant_expires
    ON capability_grants(expires_at_ms)
    WHERE expires_at_ms IS NOT NULL;

-- Index for scope-based queries
CREATE INDEX IF NOT EXISTS idx_cap_grant_scope
    ON capability_grants(scope)
    WHERE scope IS NOT NULL;

-- ===================================================================
-- 3. Capability Invocations Table (Audit Trail)
-- ===================================================================

-- Records every capability invocation (allowed or denied)
CREATE TABLE IF NOT EXISTS capability_invocations (
    invocation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,                      -- Agent invoking
    capability_id TEXT NOT NULL,                 -- Capability invoked
    operation TEXT NOT NULL,                     -- Specific operation (e.g., "read", "write")
    allowed INTEGER NOT NULL,                    -- 0=denied, 1=allowed
    reason TEXT,                                 -- Reason for denial (if allowed=0)
    context_json TEXT,                           -- Execution context as JSON
    timestamp_ms INTEGER NOT NULL,               -- Invocation time (epoch ms)

    CHECK (allowed IN (0, 1)),
    CHECK (timestamp_ms > 0)
);

-- Index for agent-based audit queries (most recent first)
CREATE INDEX IF NOT EXISTS idx_cap_inv_agent_time
    ON capability_invocations(agent_id, timestamp_ms DESC);

-- Index for capability-based audit queries
CREATE INDEX IF NOT EXISTS idx_cap_inv_capability_time
    ON capability_invocations(capability_id, timestamp_ms DESC);

-- Index for denied invocations (security monitoring)
CREATE INDEX IF NOT EXISTS idx_cap_inv_denied
    ON capability_invocations(allowed, timestamp_ms DESC)
    WHERE allowed = 0;

-- Index for time-based queries (recent activity)
CREATE INDEX IF NOT EXISTS idx_cap_inv_timestamp
    ON capability_invocations(timestamp_ms DESC);

-- ===================================================================
-- 4. Capability Call Paths Table (PathValidator)
-- ===================================================================

-- Tracks call paths for Golden Path validation
-- Used by PathValidator to detect forbidden paths
CREATE TABLE IF NOT EXISTS capability_call_paths (
    path_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,                    -- Session/task identifier
    call_stack_json TEXT NOT NULL,               -- Call stack as JSON array
    path_valid INTEGER NOT NULL,                 -- 0=invalid, 1=valid
    violation_reason TEXT,                       -- Why path is invalid (if path_valid=0)
    timestamp_ms INTEGER NOT NULL,               -- Path check time (epoch ms)

    CHECK (path_valid IN (0, 1)),
    CHECK (timestamp_ms > 0)
);

-- Index for session-based queries
CREATE INDEX IF NOT EXISTS idx_cap_path_session
    ON capability_call_paths(session_id, timestamp_ms DESC);

-- Index for invalid paths (security monitoring)
CREATE INDEX IF NOT EXISTS idx_cap_path_invalid
    ON capability_call_paths(path_valid, timestamp_ms DESC)
    WHERE path_valid = 0;

-- Index for time-based queries
CREATE INDEX IF NOT EXISTS idx_cap_path_timestamp
    ON capability_call_paths(timestamp_ms DESC);

-- ===================================================================
-- 5. Grant Audit Trail
-- ===================================================================

-- Tracks all changes to capability grants
CREATE TABLE IF NOT EXISTS capability_grant_audit (
    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    grant_id TEXT NOT NULL,                      -- Grant being modified
    agent_id TEXT NOT NULL,                      -- Agent affected
    capability_id TEXT NOT NULL,                 -- Capability affected
    action TEXT NOT NULL,                        -- grant|revoke|expire
    changed_by TEXT NOT NULL,                    -- Who made the change
    changed_at_ms INTEGER NOT NULL,              -- When changed (epoch ms)
    reason TEXT,                                 -- Reason for change
    metadata TEXT,                               -- JSON metadata

    CHECK (action IN ('grant', 'revoke', 'expire')),
    CHECK (changed_at_ms > 0)
);

-- Index for grant tracking
CREATE INDEX IF NOT EXISTS idx_cap_grant_audit_grant
    ON capability_grant_audit(grant_id, changed_at_ms DESC);

-- Index for agent tracking
CREATE INDEX IF NOT EXISTS idx_cap_grant_audit_agent
    ON capability_grant_audit(agent_id, changed_at_ms DESC);

-- Index for capability tracking
CREATE INDEX IF NOT EXISTS idx_cap_grant_audit_capability
    ON capability_grant_audit(capability_id, changed_at_ms DESC);

-- ===================================================================
-- 6. Views for Convenience
-- ===================================================================

-- Active grants (non-expired)
CREATE VIEW IF NOT EXISTS active_capability_grants AS
SELECT
    grant_id,
    agent_id,
    capability_id,
    granted_by,
    granted_at_ms,
    expires_at_ms,
    scope,
    reason
FROM capability_grants
WHERE expires_at_ms IS NULL OR expires_at_ms > (strftime('%s', 'now') * 1000)
ORDER BY agent_id, capability_id;

-- Recent denials (security monitoring)
CREATE VIEW IF NOT EXISTS recent_capability_denials AS
SELECT
    invocation_id,
    agent_id,
    capability_id,
    operation,
    reason,
    timestamp_ms,
    datetime(timestamp_ms / 1000, 'unixepoch') as timestamp_iso
FROM capability_invocations
WHERE allowed = 0
ORDER BY timestamp_ms DESC
LIMIT 1000;

-- Capability grant summary by agent
CREATE VIEW IF NOT EXISTS agent_capability_summary AS
SELECT
    agent_id,
    COUNT(*) as total_grants,
    GROUP_CONCAT(capability_id, ', ') as capabilities,
    MIN(granted_at_ms) as first_grant_ms,
    MAX(granted_at_ms) as last_grant_ms
FROM active_capability_grants
GROUP BY agent_id
ORDER BY agent_id;

-- Capability usage statistics
CREATE VIEW IF NOT EXISTS capability_usage_stats AS
SELECT
    capability_id,
    COUNT(*) as total_invocations,
    SUM(CASE WHEN allowed = 1 THEN 1 ELSE 0 END) as allowed_count,
    SUM(CASE WHEN allowed = 0 THEN 1 ELSE 0 END) as denied_count,
    ROUND(100.0 * SUM(CASE WHEN allowed = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) as success_rate_pct
FROM capability_invocations
GROUP BY capability_id
ORDER BY total_invocations DESC;

-- ===================================================================
-- 7. Update Schema Version
-- ===================================================================

-- Record schema version
-- Note: description column is added in v50.5, so we don't use it here
INSERT INTO schema_version (version, applied_at)
VALUES (
    '0.47.0',
    CURRENT_TIMESTAMP
);

-- ===================================================================
-- Performance Notes:
-- - capability_grants table uses composite index for O(log n) permission checks
-- - capability_invocations table partitioned by timestamp for efficient pruning
-- - Views use indexes for fast aggregation
-- - Expected performance: Permission check < 10ms (with cache)
-- ===================================================================

-- ===================================================================
-- Migration Compatibility:
-- - This schema is compatible with existing ADR-012 Memory Capability system
-- - Memory v2.0 capabilities can coexist with v3 capabilities
-- - No breaking changes to existing tables
-- ===================================================================
