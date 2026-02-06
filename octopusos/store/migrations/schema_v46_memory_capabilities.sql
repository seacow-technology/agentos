-- Schema v46: Memory Capability Contract
-- Task #16: Implement Memory Capability checking mechanism
-- ADR-012: Memory Capability Contract
--
-- This migration adds OS-level permission controls for Memory operations.
-- Inspired by Linux capabilities, this implements a hierarchical permission model
-- for memory access: NONE < READ < PROPOSE < WRITE < ADMIN

-- ============================================
-- Agent Capabilities Registry
-- ============================================

CREATE TABLE IF NOT EXISTS agent_capabilities (
    agent_id TEXT PRIMARY KEY,           -- Agent identifier (e.g., "chat_agent", "user:alice")
    agent_type TEXT NOT NULL,            -- Agent type classification (tier 1-4)
    memory_capability TEXT NOT NULL,     -- Capability level: none|read|propose|write|admin
    granted_by TEXT NOT NULL,            -- Who granted this capability (user_id or "system")
    granted_at_ms INTEGER NOT NULL,      -- When capability was granted (epoch milliseconds)
    reason TEXT,                         -- Human-readable reason for granting this capability
    expires_at_ms INTEGER,               -- Optional expiration time (epoch milliseconds, NULL = never expires)
    metadata TEXT,                       -- JSON: Additional metadata (e.g., scope restrictions)

    -- Constraints
    CHECK (memory_capability IN ('none', 'read', 'propose', 'write', 'admin')),
    CHECK (granted_at_ms > 0),
    CHECK (expires_at_ms IS NULL OR expires_at_ms > granted_at_ms)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_agent_cap_type
    ON agent_capabilities(agent_type);

CREATE INDEX IF NOT EXISTS idx_agent_cap_capability
    ON agent_capabilities(memory_capability);

CREATE INDEX IF NOT EXISTS idx_agent_cap_expires
    ON agent_capabilities(expires_at_ms)
    WHERE expires_at_ms IS NOT NULL;


-- ============================================
-- Memory Proposals (Pending Approval Queue)
-- ============================================

CREATE TABLE IF NOT EXISTS memory_proposals (
    proposal_id TEXT PRIMARY KEY,        -- Unique proposal ID (ulid)
    proposed_by TEXT NOT NULL,           -- Agent ID who proposed
    proposed_at_ms INTEGER NOT NULL,     -- When proposed (epoch milliseconds)
    memory_item TEXT NOT NULL,           -- JSON: Complete MemoryItem to be written
    status TEXT NOT NULL DEFAULT 'pending', -- pending|approved|rejected
    reviewed_by TEXT,                    -- Who reviewed (NULL if pending)
    reviewed_at_ms INTEGER,              -- When reviewed (NULL if pending)
    review_reason TEXT,                  -- Why approved/rejected
    resulting_memory_id TEXT,            -- Memory ID after approval (NULL if rejected)
    metadata TEXT,                       -- JSON: Additional context

    -- Constraints
    CHECK (status IN ('pending', 'approved', 'rejected')),
    CHECK (proposed_at_ms > 0),
    CHECK (
        (status = 'pending' AND reviewed_by IS NULL AND reviewed_at_ms IS NULL) OR
        (status IN ('approved', 'rejected') AND reviewed_by IS NOT NULL AND reviewed_at_ms IS NOT NULL)
    )
);

-- Indexes for proposal management
CREATE INDEX IF NOT EXISTS idx_proposal_status
    ON memory_proposals(status, proposed_at_ms DESC);

CREATE INDEX IF NOT EXISTS idx_proposal_agent
    ON memory_proposals(proposed_by, proposed_at_ms DESC);

CREATE INDEX IF NOT EXISTS idx_proposal_reviewed
    ON memory_proposals(reviewed_at_ms DESC)
    WHERE reviewed_at_ms IS NOT NULL;


-- ============================================
-- Capability Audit Trail
-- ============================================

CREATE TABLE IF NOT EXISTS agent_capability_audit (
    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    old_capability TEXT,                 -- Previous capability (NULL if first grant)
    new_capability TEXT NOT NULL,        -- New capability
    changed_by TEXT NOT NULL,            -- Who made the change
    changed_at_ms INTEGER NOT NULL,      -- When change occurred
    reason TEXT,                         -- Reason for change
    metadata TEXT                        -- JSON: Additional context
);

CREATE INDEX IF NOT EXISTS idx_cap_audit_agent
    ON agent_capability_audit(agent_id);

CREATE INDEX IF NOT EXISTS idx_cap_audit_time
    ON agent_capability_audit(changed_at_ms DESC);

CREATE INDEX IF NOT EXISTS idx_cap_audit_changer
    ON agent_capability_audit(changed_by);


-- ============================================
-- Pending Proposals View (UI Convenience)
-- ============================================

CREATE VIEW IF NOT EXISTS pending_proposals AS
SELECT
    proposal_id,
    proposed_by,
    proposed_at_ms,
    json_extract(memory_item, '$.type') as memory_type,
    json_extract(memory_item, '$.scope') as memory_scope,
    json_extract(memory_item, '$.content.key') as memory_key,
    json_extract(memory_item, '$.content.value') as memory_value
FROM memory_proposals
WHERE status = 'pending'
ORDER BY proposed_at_ms DESC;
