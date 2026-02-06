-- Schema v52: Agent Capability Authorization
-- AgentOS v3 Task #27: 重构Agent定义为Capability授权模型
--
-- Design Philosophy:
-- - Agent ≠ Capability
-- - Agent只是一组被授权的Capability调用者
-- - 权力在系统，授权给Agent
-- - Tier系统控制基础权限
-- - Escalation机制处理权限不足

-- ===================================================================
-- 1. Agent Profiles Table
-- ===================================================================

-- Stores agent capability profiles
CREATE TABLE IF NOT EXISTS agent_profiles (
    agent_id TEXT PRIMARY KEY,
    agent_type TEXT NOT NULL,                    -- decision_maker|executor|analyzer|...
    tier INTEGER NOT NULL DEFAULT 1,             -- 0=untrusted, 1=read, 2=propose, 3=trusted
    allowed_capabilities_json TEXT NOT NULL,     -- JSON array of allowed capability patterns
    forbidden_capabilities_json TEXT,            -- JSON array of forbidden capability patterns
    default_capability_level TEXT NOT NULL DEFAULT 'read',  -- read|propose|write
    escalation_policy TEXT NOT NULL DEFAULT 'deny',         -- deny|request_approval|temporary_grant|log_only
    created_at_ms INTEGER NOT NULL,              -- When profile created (epoch ms)
    updated_at_ms INTEGER NOT NULL,              -- Last update time (epoch ms)

    CHECK (tier IN (0, 1, 2, 3)),
    CHECK (default_capability_level IN ('read', 'propose', 'write', 'admin')),
    CHECK (escalation_policy IN ('deny', 'request_approval', 'temporary_grant', 'log_only'))
);

-- Index for tier-based queries
CREATE INDEX IF NOT EXISTS idx_agent_profile_tier
    ON agent_profiles(tier);

-- Index for agent type queries
CREATE INDEX IF NOT EXISTS idx_agent_profile_type
    ON agent_profiles(agent_type);

-- ===================================================================
-- 2. Agent Tier History Table
-- ===================================================================

-- Tracks agent tier transitions (upgrades only)
CREATE TABLE IF NOT EXISTS agent_tier_history (
    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    from_tier INTEGER NOT NULL,                  -- Previous tier (0-3)
    to_tier INTEGER NOT NULL,                    -- New tier (0-3)
    changed_by TEXT NOT NULL,                    -- Who made the change
    reason TEXT NOT NULL,                        -- Reason for tier change
    changed_at_ms INTEGER NOT NULL,              -- When changed (epoch ms)

    CHECK (from_tier IN (0, 1, 2, 3)),
    CHECK (to_tier IN (0, 1, 2, 3)),
    CHECK (to_tier > from_tier),                 -- Only upgrades allowed

    FOREIGN KEY (agent_id) REFERENCES agent_profiles(agent_id)
);

-- Index for agent tier history queries
CREATE INDEX IF NOT EXISTS idx_tier_history_agent
    ON agent_tier_history(agent_id, changed_at_ms DESC);

-- Index for recent tier changes
CREATE INDEX IF NOT EXISTS idx_tier_history_time
    ON agent_tier_history(changed_at_ms DESC);

-- ===================================================================
-- 3. Escalation Requests Table
-- ===================================================================

-- Stores capability escalation requests
CREATE TABLE IF NOT EXISTS escalation_requests (
    request_id TEXT PRIMARY KEY,                 -- Unique request ID (escalation-{hex})
    agent_id TEXT NOT NULL,                      -- Agent requesting capability
    requested_capability TEXT NOT NULL,          -- Capability requested
    reason TEXT NOT NULL,                        -- Reason for request (min 10 chars)
    status TEXT NOT NULL DEFAULT 'pending',      -- pending|approved|denied|expired|cancelled

    requested_at_ms INTEGER NOT NULL,            -- When requested (epoch ms)
    reviewed_by TEXT,                            -- Admin who reviewed (if any)
    reviewed_at_ms INTEGER,                      -- When reviewed (if any)
    deny_reason TEXT,                            -- Reason for denial (if denied)

    CHECK (status IN ('pending', 'approved', 'denied', 'expired', 'cancelled')),
    CHECK (requested_at_ms > 0),

    FOREIGN KEY (agent_id) REFERENCES agent_profiles(agent_id)
);

-- Index for agent escalation queries
CREATE INDEX IF NOT EXISTS idx_escalation_agent
    ON escalation_requests(agent_id, requested_at_ms DESC);

-- Index for pending requests
CREATE INDEX IF NOT EXISTS idx_escalation_pending
    ON escalation_requests(status, requested_at_ms ASC)
    WHERE status = 'pending';

-- Index for reviewer queries
CREATE INDEX IF NOT EXISTS idx_escalation_reviewer
    ON escalation_requests(reviewed_by, reviewed_at_ms DESC)
    WHERE reviewed_by IS NOT NULL;

-- ===================================================================
-- 4. Extend capability_grants Table
-- ===================================================================

-- Add escalation_request_id column to capability_grants (if not exists)
-- This links temporary grants to their escalation requests

-- Note: This uses ALTER TABLE which requires checking if column exists
-- SQLite doesn't support IF NOT EXISTS for ALTER TABLE, so we use a workaround

-- Check if column exists using pragma
SELECT CASE
    WHEN COUNT(*) > 0 THEN 'Column already exists'
    ELSE 'Adding column'
END as status
FROM pragma_table_info('capability_grants')
WHERE name = 'escalation_request_id';

-- If column doesn't exist, add it
-- (This will fail silently if it already exists, which is fine)
ALTER TABLE capability_grants ADD COLUMN escalation_request_id TEXT;

-- Create index for escalation tracking
CREATE INDEX IF NOT EXISTS idx_grant_escalation
    ON capability_grants(escalation_request_id)
    WHERE escalation_request_id IS NOT NULL;

-- ===================================================================
-- 5. Views for Convenience
-- ===================================================================

-- Active agent profiles with tier info
CREATE VIEW IF NOT EXISTS v_agent_profiles_with_tier AS
SELECT
    p.agent_id,
    p.agent_type,
    p.tier,
    CASE p.tier
        WHEN 0 THEN 'Untrusted'
        WHEN 1 THEN 'Read-Only'
        WHEN 2 THEN 'Propose'
        WHEN 3 THEN 'Trusted'
    END as tier_name,
    p.allowed_capabilities_json,
    p.forbidden_capabilities_json,
    p.escalation_policy,
    h.from_tier as previous_tier,
    h.changed_at_ms as last_tier_change_ms
FROM agent_profiles p
LEFT JOIN (
    SELECT agent_id, from_tier, changed_at_ms,
           ROW_NUMBER() OVER (PARTITION BY agent_id ORDER BY changed_at_ms DESC) as rn
    FROM agent_tier_history
) h ON p.agent_id = h.agent_id AND h.rn = 1;

-- Pending escalation requests summary
CREATE VIEW IF NOT EXISTS v_pending_escalations AS
SELECT
    r.request_id,
    r.agent_id,
    p.agent_type,
    p.tier as agent_tier,
    r.requested_capability,
    r.reason,
    r.requested_at_ms,
    (strftime('%s', 'now') * 1000 - r.requested_at_ms) / 1000.0 as age_seconds
FROM escalation_requests r
JOIN agent_profiles p ON r.agent_id = p.agent_id
WHERE r.status = 'pending'
ORDER BY r.requested_at_ms ASC;

-- Agent capability summary (grants + profile)
CREATE VIEW IF NOT EXISTS v_agent_capability_summary AS
SELECT
    p.agent_id,
    p.agent_type,
    p.tier,
    COUNT(g.grant_id) as active_grants,
    GROUP_CONCAT(g.capability_id, ', ') as granted_capabilities,
    COUNT(DISTINCT e.request_id) as pending_escalations
FROM agent_profiles p
LEFT JOIN active_capability_grants g ON p.agent_id = g.agent_id
LEFT JOIN escalation_requests e ON p.agent_id = e.agent_id AND e.status = 'pending'
GROUP BY p.agent_id, p.agent_type, p.tier
ORDER BY p.agent_id;

-- Tier transition statistics
CREATE VIEW IF NOT EXISTS v_tier_transition_stats AS
SELECT
    from_tier,
    to_tier,
    COUNT(*) as transition_count,
    AVG((changed_at_ms - LAG(changed_at_ms) OVER (PARTITION BY agent_id ORDER BY changed_at_ms)) / 1000.0 / 86400.0) as avg_days_between
FROM agent_tier_history
GROUP BY from_tier, to_tier
ORDER BY from_tier, to_tier;

-- ===================================================================
-- 6. Sample Data (for testing)
-- ===================================================================

-- Sample profile: Chat Agent (Tier 2 - Propose)
INSERT OR IGNORE INTO agent_profiles (
    agent_id, agent_type, tier, allowed_capabilities_json,
    forbidden_capabilities_json, escalation_policy,
    created_at_ms, updated_at_ms
)
VALUES (
    'chat_agent',
    'decision_maker',
    2,
    '["state.read", "state.memory.propose", "decision.infoneed.classify", "evidence.query"]',
    '["action.execute.*", "state.memory.write", "governance.override.*"]',
    'request_approval',
    strftime('%s', 'now') * 1000,
    strftime('%s', 'now') * 1000
);

-- Sample profile: Executor Agent (Tier 3 - Trusted)
INSERT OR IGNORE INTO agent_profiles (
    agent_id, agent_type, tier, allowed_capabilities_json,
    forbidden_capabilities_json, escalation_policy,
    created_at_ms, updated_at_ms
)
VALUES (
    'executor_agent',
    'executor',
    3,
    '["state.read", "state.write", "action.execute.local", "action.execute.network", "evidence.write"]',
    '["action.execute.cloud", "governance.override.*", "governance.policy.evolve"]',
    'request_approval',
    strftime('%s', 'now') * 1000,
    strftime('%s', 'now') * 1000
);

-- Sample profile: Analyzer Agent (Tier 1 - Read-Only)
INSERT OR IGNORE INTO agent_profiles (
    agent_id, agent_type, tier, allowed_capabilities_json,
    forbidden_capabilities_json, escalation_policy,
    created_at_ms, updated_at_ms
)
VALUES (
    'analyzer_agent',
    'analyzer',
    1,
    '["state.read", "evidence.query"]',
    '["state.write", "state.memory.propose", "action.execute.*", "governance.*"]',
    'deny',
    strftime('%s', 'now') * 1000,
    strftime('%s', 'now') * 1000
);

-- Sample tier history: Chat Agent initialization
INSERT OR IGNORE INTO agent_tier_history (
    agent_id, from_tier, to_tier, changed_by, reason, changed_at_ms
)
VALUES (
    'chat_agent',
    0,
    2,
    'system:initialization',
    'Initial agent setup with Propose tier',
    strftime('%s', 'now') * 1000
);

-- Sample tier history: Executor Agent initialization
INSERT OR IGNORE INTO agent_tier_history (
    agent_id, from_tier, to_tier, changed_by, reason, changed_at_ms
)
VALUES (
    'executor_agent',
    0,
    3,
    'system:initialization',
    'Initial agent setup with Trusted tier',
    strftime('%s', 'now') * 1000
);

-- ===================================================================
-- 7. Migration Verification
-- ===================================================================

-- Verify tables exist
SELECT 'Schema v52 tables created:' as status;
SELECT name FROM sqlite_master
WHERE type='table'
AND name IN (
    'agent_profiles',
    'agent_tier_history',
    'escalation_requests'
)
ORDER BY name;

-- Verify views exist
SELECT 'Schema v52 views created:' as status;
SELECT name FROM sqlite_master
WHERE type='view'
AND name LIKE 'v_agent%' OR name LIKE 'v_%escalation%' OR name LIKE 'v_tier%'
ORDER BY name;

-- Verify sample data
SELECT 'Sample agent profiles loaded:' as status;
SELECT agent_id, agent_type, tier FROM agent_profiles;

SELECT 'Sample tier history loaded:' as status;
SELECT agent_id, from_tier, to_tier, changed_by FROM agent_tier_history;

-- Show agent capability summary
SELECT 'Agent capability summary:' as status;
SELECT * FROM v_agent_capability_summary;

-- ===================================================================
-- Performance Notes:
-- - agent_profiles: Primary key on agent_id for O(1) lookups
-- - agent_tier_history: Indexed by (agent_id, changed_at_ms DESC) for tier queries
-- - escalation_requests: Indexed by status for pending request queries
-- - Views use indexes for efficient aggregation
-- - Expected performance: Profile lookup < 1ms, Authorization check < 10ms
-- ===================================================================

-- ===================================================================
-- Design Rationale:
-- - Separate profile table for agent configuration (immutable once created)
-- - Tier history tracks trust evolution over time
-- - Escalation requests enable runtime capability requests
-- - Forbidden capabilities take precedence over allowed (security first)
-- - Tier system enforces maximum capabilities per trust level
-- - All timestamps in epoch milliseconds (v44 contract)
-- ===================================================================
