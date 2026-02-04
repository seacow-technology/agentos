-- Schema v73: Marketplace Registry (Phase F2)
-- AgentOS Marketplace - Capability Registration and Discovery
--
-- Design Philosophy:
-- - Registry is a LEDGER, not a store
-- - Records WHO published WHAT from WHERE
-- - NO trust scoring, NO recommendations, NO authorization
-- - Complete history preservation (immutable)
-- - Publisher identity always visible

-- ===================================================================
-- 1. Marketplace Publishers Table
-- ===================================================================

-- Stores publisher identity and metadata
CREATE TABLE IF NOT EXISTS marketplace_publishers (
    publisher_id TEXT PRIMARY KEY,               -- e.g., "official", "community.john"
    name TEXT NOT NULL,                          -- Display name
    contact TEXT,                                -- Email or contact info
    verified INTEGER NOT NULL DEFAULT 0,         -- 0=unverified, 1=verified (admin action)
    registered_at_ms INTEGER NOT NULL,           -- When publisher registered (epoch ms)
    metadata TEXT,                               -- JSON metadata (website, description, etc.)

    CHECK (verified IN (0, 1)),
    CHECK (registered_at_ms > 0)
);

-- Index for verification status queries
CREATE INDEX IF NOT EXISTS idx_marketplace_pub_verified
    ON marketplace_publishers(verified);

-- ===================================================================
-- 2. Marketplace Capabilities Table
-- ===================================================================

-- Stores capability manifests (complete history, immutable)
CREATE TABLE IF NOT EXISTS marketplace_capabilities (
    capability_id TEXT PRIMARY KEY,              -- Full ID: "publisher.name.v1.0.0"
    capability_name TEXT NOT NULL,               -- Base name: "publisher.name"
    publisher_id TEXT NOT NULL,                  -- Publisher who registered this
    capability_type TEXT NOT NULL,               -- Type/category (e.g., "web_scraper", "data_processor")
    version TEXT NOT NULL,                       -- Semantic version (e.g., "1.0.0")
    manifest_json TEXT NOT NULL,                 -- Complete manifest as JSON (converted from YAML)
    signature TEXT,                              -- Optional cryptographic signature
    status TEXT NOT NULL DEFAULT 'active',       -- active | deprecated | removed
    published_at_ms INTEGER NOT NULL,            -- When published (epoch ms)
    deprecated_at_ms INTEGER,                    -- When deprecated (NULL if active)
    removed_at_ms INTEGER,                       -- When removed (NULL if not removed)

    CHECK (status IN ('active', 'deprecated', 'removed')),
    CHECK (published_at_ms > 0),
    CHECK (deprecated_at_ms IS NULL OR deprecated_at_ms >= published_at_ms),
    CHECK (removed_at_ms IS NULL OR removed_at_ms >= published_at_ms),

    FOREIGN KEY (publisher_id) REFERENCES marketplace_publishers(publisher_id)
);

-- Composite index for capability_name + version uniqueness
CREATE UNIQUE INDEX IF NOT EXISTS idx_marketplace_cap_name_version
    ON marketplace_capabilities(capability_name, version);

-- Index for publisher-based queries (list all capabilities by publisher)
CREATE INDEX IF NOT EXISTS idx_marketplace_cap_publisher
    ON marketplace_capabilities(publisher_id, published_at_ms DESC);

-- Index for type-based queries (find all capabilities of a type)
CREATE INDEX IF NOT EXISTS idx_marketplace_cap_type
    ON marketplace_capabilities(capability_type, published_at_ms DESC);

-- Index for status-based queries (find active/deprecated capabilities)
CREATE INDEX IF NOT EXISTS idx_marketplace_cap_status
    ON marketplace_capabilities(status);

-- Index for version history queries (all versions of a capability)
CREATE INDEX IF NOT EXISTS idx_marketplace_cap_versions
    ON marketplace_capabilities(capability_name, published_at_ms DESC);

-- ===================================================================
-- 3. Marketplace Audit Log
-- ===================================================================

-- Tracks all registration and status change events
CREATE TABLE IF NOT EXISTS marketplace_audit_log (
    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    capability_id TEXT NOT NULL,                 -- Capability affected
    publisher_id TEXT NOT NULL,                  -- Publisher who owns it
    action TEXT NOT NULL,                        -- register | deprecate | remove | restore
    actor TEXT NOT NULL,                         -- Who performed the action (user_id or system)
    timestamp_ms INTEGER NOT NULL,               -- When action occurred (epoch ms)
    reason TEXT,                                 -- Human-readable reason
    metadata TEXT,                               -- JSON metadata (IP, user agent, etc.)

    CHECK (action IN ('register', 'deprecate', 'remove', 'restore')),
    CHECK (timestamp_ms > 0)
);

-- Index for capability audit trail
CREATE INDEX IF NOT EXISTS idx_marketplace_audit_cap
    ON marketplace_audit_log(capability_id, timestamp_ms DESC);

-- Index for publisher audit trail
CREATE INDEX IF NOT EXISTS idx_marketplace_audit_publisher
    ON marketplace_audit_log(publisher_id, timestamp_ms DESC);

-- Index for time-based queries (recent activity)
CREATE INDEX IF NOT EXISTS idx_marketplace_audit_timestamp
    ON marketplace_audit_log(timestamp_ms DESC);

-- ===================================================================
-- 4. Views for Convenience
-- ===================================================================

-- Active capabilities only
CREATE VIEW IF NOT EXISTS active_marketplace_capabilities AS
SELECT
    capability_id,
    capability_name,
    publisher_id,
    capability_type,
    version,
    manifest_json,
    published_at_ms,
    datetime(published_at_ms / 1000, 'unixepoch') as published_at_iso
FROM marketplace_capabilities
WHERE status = 'active'
ORDER BY capability_name, published_at_ms DESC;

-- Publisher capability summary
CREATE VIEW IF NOT EXISTS marketplace_publisher_summary AS
SELECT
    p.publisher_id,
    p.name as publisher_name,
    p.verified,
    COUNT(c.capability_id) as total_capabilities,
    SUM(CASE WHEN c.status = 'active' THEN 1 ELSE 0 END) as active_capabilities,
    MIN(c.published_at_ms) as first_publish_ms,
    MAX(c.published_at_ms) as last_publish_ms
FROM marketplace_publishers p
LEFT JOIN marketplace_capabilities c ON p.publisher_id = c.publisher_id
GROUP BY p.publisher_id, p.name, p.verified
ORDER BY p.verified DESC, p.publisher_id;

-- Recent registrations (monitoring view)
CREATE VIEW IF NOT EXISTS recent_marketplace_registrations AS
SELECT
    c.capability_id,
    c.capability_name,
    c.publisher_id,
    p.name as publisher_name,
    p.verified as publisher_verified,
    c.capability_type,
    c.version,
    c.published_at_ms,
    datetime(c.published_at_ms / 1000, 'unixepoch') as published_at_iso
FROM marketplace_capabilities c
JOIN marketplace_publishers p ON c.publisher_id = p.publisher_id
ORDER BY c.published_at_ms DESC
LIMIT 100;

-- ===================================================================
-- 5. Marketplace Governance Actions (Phase F5)
-- ===================================================================

-- Tracks all governance actions (delist, flag, suspend)
-- Marketplace can GOVERN but CANNOT authorize or trust
CREATE TABLE IF NOT EXISTS marketplace_governance_actions (
    action_id INTEGER PRIMARY KEY AUTOINCREMENT,
    action_type TEXT NOT NULL,                   -- delist | suspend | restore
    target_type TEXT NOT NULL,                   -- capability | publisher
    target_id TEXT NOT NULL,                     -- Capability ID or Publisher ID
    reason TEXT NOT NULL,                        -- Human-readable reason for action
    admin_id TEXT NOT NULL,                      -- Admin who performed action
    created_at_ms INTEGER NOT NULL,              -- When action occurred (epoch ms)
    metadata TEXT,                               -- JSON metadata (context, evidence, etc.)

    CHECK (action_type IN ('delist', 'suspend', 'restore')),
    CHECK (target_type IN ('capability', 'publisher')),
    CHECK (created_at_ms > 0)
);

-- Index for target lookups (find all actions on a capability/publisher)
CREATE INDEX IF NOT EXISTS idx_governance_target
    ON marketplace_governance_actions(target_type, target_id, created_at_ms DESC);

-- Index for admin audit trail
CREATE INDEX IF NOT EXISTS idx_governance_admin
    ON marketplace_governance_actions(admin_id, created_at_ms DESC);

-- ===================================================================
-- 6. Marketplace Capability Flags (Phase F5)
-- ===================================================================

-- Tracks risk flags on capabilities
-- Marketplace can FLAG but cannot TRUST or AUTHORIZE
CREATE TABLE IF NOT EXISTS marketplace_flags (
    flag_id INTEGER PRIMARY KEY AUTOINCREMENT,
    capability_id TEXT NOT NULL,                 -- Capability being flagged
    flag_type TEXT NOT NULL,                     -- security | policy | malicious | suspicious
    severity TEXT NOT NULL,                      -- low | medium | high | critical
    description TEXT NOT NULL,                   -- Detailed description of issue
    flagged_at_ms INTEGER NOT NULL,              -- When flag was created (epoch ms)
    resolved_at_ms INTEGER,                      -- When flag was resolved (NULL if active)
    admin_id TEXT NOT NULL,                      -- Admin who created flag
    metadata TEXT,                               -- JSON metadata (evidence, references, etc.)

    CHECK (flag_type IN ('security', 'policy', 'malicious', 'suspicious')),
    CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    CHECK (flagged_at_ms > 0),
    CHECK (resolved_at_ms IS NULL OR resolved_at_ms >= flagged_at_ms)
);

-- Index for capability flag queries
CREATE INDEX IF NOT EXISTS idx_flags_capability
    ON marketplace_flags(capability_id, flagged_at_ms DESC);

-- Index for active flags only
CREATE INDEX IF NOT EXISTS idx_flags_active
    ON marketplace_flags(capability_id, resolved_at_ms)
    WHERE resolved_at_ms IS NULL;

-- Index for severity-based queries
CREATE INDEX IF NOT EXISTS idx_flags_severity
    ON marketplace_flags(severity, flagged_at_ms DESC)
    WHERE resolved_at_ms IS NULL;

-- ===================================================================
-- 7. Publisher Suspensions (Phase F5)
-- ===================================================================

-- Tracks publisher suspension status
-- Marketplace can SUSPEND but cannot revoke local capabilities
CREATE TABLE IF NOT EXISTS marketplace_publisher_suspensions (
    suspension_id INTEGER PRIMARY KEY AUTOINCREMENT,
    publisher_id TEXT NOT NULL,                  -- Publisher being suspended
    suspended_at_ms INTEGER NOT NULL,            -- When suspension occurred (epoch ms)
    reason TEXT NOT NULL,                        -- Reason for suspension
    admin_id TEXT NOT NULL,                      -- Admin who performed suspension
    restored_at_ms INTEGER,                      -- When suspension lifted (NULL if active)
    restored_by TEXT,                            -- Admin who restored publisher
    metadata TEXT,                               -- JSON metadata (evidence, notes, etc.)

    CHECK (suspended_at_ms > 0),
    CHECK (restored_at_ms IS NULL OR restored_at_ms >= suspended_at_ms),

    FOREIGN KEY (publisher_id) REFERENCES marketplace_publishers(publisher_id)
);

-- Index for publisher suspension lookups
CREATE INDEX IF NOT EXISTS idx_suspension_publisher
    ON marketplace_publisher_suspensions(publisher_id, suspended_at_ms DESC);

-- Index for active suspensions only
CREATE INDEX IF NOT EXISTS idx_suspension_active
    ON marketplace_publisher_suspensions(publisher_id, restored_at_ms)
    WHERE restored_at_ms IS NULL;

-- ===================================================================
-- 8. Governance Views (Phase F5)
-- ===================================================================

-- Active flags summary
CREATE VIEW IF NOT EXISTS active_marketplace_flags AS
SELECT
    f.flag_id,
    f.capability_id,
    f.flag_type,
    f.severity,
    f.description,
    f.flagged_at_ms,
    datetime(f.flagged_at_ms / 1000, 'unixepoch') as flagged_at_iso,
    f.admin_id
FROM marketplace_flags f
WHERE f.resolved_at_ms IS NULL
ORDER BY f.severity DESC, f.flagged_at_ms DESC;

-- Active suspensions summary
CREATE VIEW IF NOT EXISTS active_publisher_suspensions AS
SELECT
    s.suspension_id,
    s.publisher_id,
    p.name as publisher_name,
    s.reason,
    s.suspended_at_ms,
    datetime(s.suspended_at_ms / 1000, 'unixepoch') as suspended_at_iso,
    s.admin_id
FROM marketplace_publisher_suspensions s
JOIN marketplace_publishers p ON s.publisher_id = p.publisher_id
WHERE s.restored_at_ms IS NULL
ORDER BY s.suspended_at_ms DESC;

-- ===================================================================
-- 9. Update Schema Version
-- ===================================================================

-- Record schema version
INSERT INTO schema_version (version, applied_at, description)
VALUES (
    '0.73.0',
    CURRENT_TIMESTAMP,
    'Marketplace Registry: capability registration ledger with governance (Phase F5)'
);

-- ===================================================================
-- Immutability Guarantees:
-- - capability_id is PRIMARY KEY (cannot be overwritten)
-- - UNIQUE(capability_name, version) prevents version collision
-- - All changes tracked in audit log
-- - No DELETE operations in application layer (only status changes)
-- ===================================================================

-- ===================================================================
-- Trust Model:
-- - Registry does NOT score trust
-- - Registry does NOT hide publisher identity
-- - Registry does NOT recommend capabilities
-- - Trust decisions made by downstream systems (Phase F3)
-- ===================================================================

-- ===================================================================
-- Performance Notes:
-- - Composite index on (capability_name, version) for O(log n) lookups
-- - Publisher index for efficient listing
-- - Type index for discovery queries
-- - Expected performance: Query < 5ms, Register < 20ms
-- ===================================================================
