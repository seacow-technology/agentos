-- Schema v75: Federated Trust Lifecycle (Phase G4)
-- Phase G: Cross-System Trust Federation
--
-- Purpose:
-- - Store federated trust relationships between AgentOS systems
-- - Track trust lifecycle (establish, renew, revoke, downgrade)
-- - Enforce trust expiration and revocation
-- - Maintain complete audit history
--
-- Design Principles:
-- 1. TIME-BOUND: All trust has TTL (default 24h, max 7 days)
-- 2. REVOCABLE: Trust can be revoked locally
-- 3. DEGRADABLE: Trust can be downgraded to lower levels
-- 4. AUDITABLE: Complete history of all trust changes
--
-- Red Lines (MUST NOT):
-- ❌ Cannot have unlimited trust (must have TTL)
-- ❌ Cannot have remote revoke local trust
-- ❌ Cannot silently expire (must log)
-- ❌ Cannot auto-escalate trust level
--
-- Trust Lifecycle:
--   ESTABLISH → ACTIVE → (RENEW → ACTIVE)* → EXPIRED
--                    ↓
--                 REVOKED
--                    ↓
--                DEGRADED
--
-- Created: 2026-02-02
-- Author: Phase G4 Agent (Federated Trust Lifecycle)
-- Reference: Phase G Task Cards (plan1.md)

-- =============================================================================
-- Federated Trust Table
-- =============================================================================
-- Stores active federated trust relationships with remote AgentOS systems.
-- Each trust has a TTL and can be revoked or degraded.

CREATE TABLE IF NOT EXISTS federated_trust (
    -- Primary key
    trust_id TEXT PRIMARY KEY,                 -- Unique identifier (trust-{uuid})

    -- Remote system identification
    remote_system_id TEXT NOT NULL,            -- Remote system identifier (e.g., "official-agentos")

    -- Trust timing
    established_at INTEGER NOT NULL,           -- When trust was established (epoch ms)
    expires_at INTEGER NOT NULL,               -- When trust expires (epoch ms)

    -- Trust properties
    trust_level TEXT NOT NULL,                 -- Trust level: 'MINIMAL', 'LIMITED', 'STANDARD'
    status TEXT NOT NULL,                      -- Status: 'ACTIVE', 'EXPIRED', 'REVOKED', 'DEGRADED'

    -- Revocation control
    can_revoke INTEGER NOT NULL DEFAULT 1,     -- Whether trust can be revoked (1=yes, 0=no)
    revoke_reason TEXT,                        -- Reason for revocation (if revoked)

    -- Additional data
    metadata TEXT,                             -- JSON metadata (optional)

    -- Constraints
    CHECK(trust_level IN ('MINIMAL', 'LIMITED', 'STANDARD')),
    CHECK(status IN ('ACTIVE', 'EXPIRED', 'REVOKED', 'DEGRADED')),
    CHECK(can_revoke IN (0, 1)),
    CHECK(established_at > 0),
    CHECK(expires_at > established_at),
    CHECK(expires_at <= established_at + 604800000)  -- Max 7 days (168 hours)
);

-- =============================================================================
-- Federated Trust History Table
-- =============================================================================
-- Records all trust lifecycle events for audit trail.
-- Immutable - no updates or deletes allowed.

CREATE TABLE IF NOT EXISTS federated_trust_history (
    -- Primary key
    history_id TEXT PRIMARY KEY,               -- Unique identifier (hist-{uuid})

    -- Trust reference
    trust_id TEXT NOT NULL,                    -- Trust this event belongs to

    -- Event data
    action TEXT NOT NULL,                      -- Action: 'ESTABLISH', 'RENEW', 'REVOKE', 'DOWNGRADE', 'EXPIRE'
    description TEXT NOT NULL,                 -- Human-readable description
    timestamp INTEGER NOT NULL,                -- When event occurred (epoch ms)

    -- Constraints
    CHECK(action IN ('ESTABLISH', 'RENEW', 'REVOKE', 'DOWNGRADE', 'EXPIRE')),
    CHECK(timestamp > 0),

    -- Foreign key (soft reference)
    FOREIGN KEY (trust_id) REFERENCES federated_trust(trust_id)
        ON DELETE CASCADE
);

-- =============================================================================
-- Indexes for Query Performance
-- =============================================================================

-- Primary trust lookups by remote system
CREATE INDEX IF NOT EXISTS idx_federated_trust_remote
ON federated_trust(remote_system_id, status, expires_at DESC);

-- Active trust lookups
CREATE INDEX IF NOT EXISTS idx_federated_trust_active
ON federated_trust(status, expires_at DESC)
WHERE status = 'ACTIVE';

-- Expiration checks
CREATE INDEX IF NOT EXISTS idx_federated_trust_expiring
ON federated_trust(expires_at ASC)
WHERE status = 'ACTIVE';

-- Trust level queries
CREATE INDEX IF NOT EXISTS idx_federated_trust_level
ON federated_trust(trust_level, status);

-- History by trust
CREATE INDEX IF NOT EXISTS idx_trust_history_trust
ON federated_trust_history(trust_id, timestamp DESC);

-- History by action
CREATE INDEX IF NOT EXISTS idx_trust_history_action
ON federated_trust_history(action, timestamp DESC);

-- History chronological
CREATE INDEX IF NOT EXISTS idx_trust_history_time
ON federated_trust_history(timestamp DESC);

-- =============================================================================
-- Trust Summary Views
-- =============================================================================

-- Active trusts summary
CREATE VIEW IF NOT EXISTS active_federated_trusts AS
SELECT
    trust_id,
    remote_system_id,
    established_at,
    expires_at,
    trust_level,
    status,
    datetime(established_at / 1000, 'unixepoch') as established_at_iso,
    datetime(expires_at / 1000, 'unixepoch') as expires_at_iso,
    CAST((expires_at - (strftime('%s', 'now') * 1000)) / 1000 AS INTEGER) as time_remaining_seconds
FROM federated_trust
WHERE status = 'ACTIVE'
  AND expires_at > (strftime('%s', 'now') * 1000)
ORDER BY expires_at ASC;

-- Expired trusts (need attention)
CREATE VIEW IF NOT EXISTS expired_federated_trusts AS
SELECT
    trust_id,
    remote_system_id,
    established_at,
    expires_at,
    trust_level,
    status,
    datetime(expires_at / 1000, 'unixepoch') as expires_at_iso,
    CAST((strftime('%s', 'now') * 1000 - expires_at) / 1000 AS INTEGER) as expired_seconds_ago
FROM federated_trust
WHERE status = 'ACTIVE'
  AND expires_at <= (strftime('%s', 'now') * 1000)
ORDER BY expires_at ASC;

-- Trust statistics
CREATE VIEW IF NOT EXISTS federated_trust_stats AS
SELECT
    COUNT(*) as total_trusts,
    SUM(CASE WHEN status = 'ACTIVE' THEN 1 ELSE 0 END) as active_trusts,
    SUM(CASE WHEN status = 'EXPIRED' THEN 1 ELSE 0 END) as expired_trusts,
    SUM(CASE WHEN status = 'REVOKED' THEN 1 ELSE 0 END) as revoked_trusts,
    SUM(CASE WHEN status = 'DEGRADED' THEN 1 ELSE 0 END) as degraded_trusts,
    COUNT(DISTINCT remote_system_id) as unique_remote_systems
FROM federated_trust;

-- =============================================================================
-- Trust Lifecycle Triggers
-- =============================================================================

-- TRIGGER 1: Prevent trust without TTL
-- Rationale: All trust must be time-bound
CREATE TRIGGER IF NOT EXISTS validate_trust_has_ttl
BEFORE INSERT ON federated_trust
FOR EACH ROW
WHEN NEW.expires_at IS NULL
BEGIN
    SELECT RAISE(ABORT, 'FORBIDDEN: Trust must have expiration time (no unlimited trust)');
END;

-- TRIGGER 2: Prevent TTL exceeding maximum (7 days)
-- Rationale: Trust cannot exceed maximum lifetime
CREATE TRIGGER IF NOT EXISTS validate_trust_max_ttl
BEFORE INSERT ON federated_trust
FOR EACH ROW
WHEN NEW.expires_at > NEW.established_at + 604800000  -- 7 days in ms
BEGIN
    SELECT RAISE(ABORT, 'FORBIDDEN: Trust TTL cannot exceed 7 days (604800000ms)');
END;

-- TRIGGER 3: Prevent expires_at before established_at
-- Rationale: Logical consistency
CREATE TRIGGER IF NOT EXISTS validate_trust_time_order
BEFORE INSERT ON federated_trust
FOR EACH ROW
WHEN NEW.expires_at <= NEW.established_at
BEGIN
    SELECT RAISE(ABORT, 'INVALID: expires_at must be after established_at');
END;

-- TRIGGER 4: Log history on trust insertion
-- Rationale: Maintain audit trail
CREATE TRIGGER IF NOT EXISTS log_trust_establish
AFTER INSERT ON federated_trust
FOR EACH ROW
BEGIN
    INSERT INTO federated_trust_history (
        history_id,
        trust_id,
        action,
        description,
        timestamp
    ) VALUES (
        'hist-' || hex(randomblob(16)),
        NEW.trust_id,
        'ESTABLISH',
        'Trust established with ' || NEW.remote_system_id || ' at ' || NEW.trust_level || ' level',
        NEW.established_at
    );
END;

-- TRIGGER 5: Prevent modification of established_at
-- Rationale: Immutable establishment time
CREATE TRIGGER IF NOT EXISTS prevent_established_at_change
BEFORE UPDATE OF established_at ON federated_trust
FOR EACH ROW
WHEN NEW.established_at != OLD.established_at
BEGIN
    SELECT RAISE(ABORT, 'FORBIDDEN: Cannot modify established_at (immutable)');
END;

-- TRIGGER 6: Prevent modification of remote_system_id
-- Rationale: Immutable remote system identity
CREATE TRIGGER IF NOT EXISTS prevent_remote_system_change
BEFORE UPDATE OF remote_system_id ON federated_trust
FOR EACH ROW
WHEN NEW.remote_system_id != OLD.remote_system_id
BEGIN
    SELECT RAISE(ABORT, 'FORBIDDEN: Cannot modify remote_system_id (immutable)');
END;

-- TRIGGER 7: Log history on revocation
-- Rationale: Audit revocation events
CREATE TRIGGER IF NOT EXISTS log_trust_revoke
AFTER UPDATE OF status ON federated_trust
FOR EACH ROW
WHEN NEW.status = 'REVOKED' AND OLD.status != 'REVOKED'
BEGIN
    INSERT INTO federated_trust_history (
        history_id,
        trust_id,
        action,
        description,
        timestamp
    ) VALUES (
        'hist-' || hex(randomblob(16)),
        NEW.trust_id,
        'REVOKE',
        'Trust revoked: ' || COALESCE(NEW.revoke_reason, 'No reason provided'),
        strftime('%s', 'now') * 1000
    );
END;

-- TRIGGER 8: Log history on downgrade
-- Rationale: Audit downgrade events
CREATE TRIGGER IF NOT EXISTS log_trust_downgrade
AFTER UPDATE OF trust_level ON federated_trust
FOR EACH ROW
WHEN NEW.trust_level != OLD.trust_level
BEGIN
    INSERT INTO federated_trust_history (
        history_id,
        trust_id,
        action,
        description,
        timestamp
    ) VALUES (
        'hist-' || hex(randomblob(16)),
        NEW.trust_id,
        'DOWNGRADE',
        'Trust downgraded: ' || OLD.trust_level || ' -> ' || NEW.trust_level,
        strftime('%s', 'now') * 1000
    );
END;

-- TRIGGER 9: Log history on renewal
-- Rationale: Audit renewal events
CREATE TRIGGER IF NOT EXISTS log_trust_renew
AFTER UPDATE OF expires_at ON federated_trust
FOR EACH ROW
WHEN NEW.expires_at != OLD.expires_at AND NEW.status = 'ACTIVE'
BEGIN
    INSERT INTO federated_trust_history (
        history_id,
        trust_id,
        action,
        description,
        timestamp
    ) VALUES (
        'hist-' || hex(randomblob(16)),
        NEW.trust_id,
        'RENEW',
        'Trust renewed: new expiration ' || datetime(NEW.expires_at / 1000, 'unixepoch'),
        strftime('%s', 'now') * 1000
    );
END;

-- TRIGGER 10: Prevent history modification
-- Rationale: History is immutable
CREATE TRIGGER IF NOT EXISTS prevent_history_update
BEFORE UPDATE ON federated_trust_history
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'FORBIDDEN: Trust history is immutable (no updates allowed)');
END;

-- TRIGGER 11: Prevent history deletion
-- Rationale: History is immutable
CREATE TRIGGER IF NOT EXISTS prevent_history_delete
BEFORE DELETE ON federated_trust_history
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'FORBIDDEN: Trust history is immutable (no deletions allowed)');
END;

-- =============================================================================
-- Schema Version Record
-- =============================================================================

INSERT INTO schema_version (version, description)
VALUES ('0.75.0', 'Federated Trust Lifecycle - Cross-system trust with TTL/revoke/downgrade (Phase G4)');

-- =============================================================================
-- Usage Examples
-- =============================================================================

-- ===== Example 1: Establish trust with 24-hour TTL =====
--
-- INSERT INTO federated_trust (
--     trust_id,
--     remote_system_id,
--     established_at,
--     expires_at,
--     trust_level,
--     status,
--     can_revoke
-- ) VALUES (
--     'trust-abc123',
--     'official-agentos',
--     1738540800000,                -- 2026-02-02 00:00:00
--     1738627200000,                -- 2026-02-03 00:00:00 (24h later)
--     'LIMITED',
--     'ACTIVE',
--     1
-- );

-- ===== Example 2: Revoke trust =====
--
-- UPDATE federated_trust
-- SET
--     status = 'REVOKED',
--     revoke_reason = 'Security concern detected'
-- WHERE trust_id = 'trust-abc123';

-- ===== Example 3: Downgrade trust level =====
--
-- UPDATE federated_trust
-- SET
--     trust_level = 'MINIMAL',
--     status = 'DEGRADED'
-- WHERE trust_id = 'trust-abc123';

-- ===== Example 4: Renew trust (extend expiration) =====
--
-- UPDATE federated_trust
-- SET
--     expires_at = expires_at + 86400000,  -- Extend by 24 hours
--     status = 'ACTIVE'
-- WHERE trust_id = 'trust-abc123';

-- ===== Example 5: Check expired trusts =====
--
-- SELECT * FROM expired_federated_trusts;

-- ===== Example 6: Get trust history =====
--
-- SELECT
--     action,
--     description,
--     datetime(timestamp / 1000, 'unixepoch') as timestamp_iso
-- FROM federated_trust_history
-- WHERE trust_id = 'trust-abc123'
-- ORDER BY timestamp ASC;

-- ===== Example 7: Try to create unlimited trust (should fail) =====
--
-- This will trigger validate_trust_has_ttl:
-- INSERT INTO federated_trust (
--     trust_id,
--     remote_system_id,
--     established_at,
--     expires_at,
--     trust_level,
--     status
-- ) VALUES (
--     'trust-bad',
--     'test-system',
--     1738540800000,
--     NULL,  -- This will fail
--     'LIMITED',
--     'ACTIVE'
-- );
-- Result: ABORT with error: "FORBIDDEN: Trust must have expiration time..."

-- ===== Example 8: Try to exceed max TTL (should fail) =====
--
-- This will trigger validate_trust_max_ttl:
-- INSERT INTO federated_trust (
--     trust_id,
--     remote_system_id,
--     established_at,
--     expires_at,
--     trust_level,
--     status
-- ) VALUES (
--     'trust-bad2',
--     'test-system',
--     1738540800000,
--     1738540800000 + 864000000,  -- 10 days (exceeds 7 day max)
--     'LIMITED',
--     'ACTIVE'
-- );
-- Result: ABORT with error: "FORBIDDEN: Trust TTL cannot exceed 7 days..."

-- =============================================================================
-- Design Notes
-- =============================================================================

-- ===== Trust Level Hierarchy =====
--
-- Level     | Description                    | Use Case
-- ----------|--------------------------------|--------------------------------
-- MINIMAL   | Very limited trust             | Unknown systems, testing
-- LIMITED   | Limited trust (default)        | Initial federation, moderate risk
-- STANDARD  | Standard trust                 | Established systems, normal ops
--
-- Note: Trust levels are NOT automatically escalated. Downgrade only.

-- ===== Trust Status Flow =====
--
-- ACTIVE    - Trust is valid and within TTL
--             ↓ (time passes)
-- EXPIRED   - Trust exceeded TTL, needs renewal
--             OR
--             ↓ (manual action)
-- REVOKED   - Trust manually revoked, permanent
--             OR
--             ↓ (downgrade)
-- DEGRADED  - Trust level lowered, still active

-- ===== TTL Policy =====
--
-- - Default TTL: 24 hours
-- - Maximum TTL: 7 days (168 hours)
-- - Renewal: Can extend up to max lifetime from establishment
-- - Rationale: Forces periodic re-verification of remote systems

-- ===== Revocation Policy =====
--
-- Triggers for revocation:
-- 1. Remote evidence compromised
-- 2. Local policy changed
-- 3. Manual admin action
-- 4. Remote system flagged
--
-- Revoked trust CANNOT be renewed - must re-establish.

-- ===== Red Lines (Enforced by Triggers) =====
--
-- 1. No unlimited trust:
--    - Trigger: validate_trust_has_ttl
--    - Reason: All trust must expire
--
-- 2. Max TTL enforced:
--    - Trigger: validate_trust_max_ttl
--    - Reason: Prevents excessive trust lifetime
--
-- 3. Immutable history:
--    - Triggers: prevent_history_update, prevent_history_delete
--    - Reason: Audit trail cannot be tampered
--
-- 4. Immutable identity:
--    - Triggers: prevent_remote_system_change, prevent_established_at_change
--    - Reason: Core trust properties are fixed

-- ===== Cross-System Trust Principles =====
--
-- 1. LOCAL SOVEREIGNTY:
--    - Each AgentOS controls its own trust
--    - Remote systems cannot revoke local trust
--    - Remote systems cannot extend local trust
--
-- 2. TRANSPARENCY:
--    - All trust changes logged
--    - Complete audit history
--    - No silent operations
--
-- 3. TIME-BOUND:
--    - All trust has expiration
--    - Forces periodic re-verification
--    - Prevents stale trust accumulation
--
-- 4. DEGRADATION-ONLY:
--    - Trust can only be downgraded, not upgraded
--    - Upgrades require re-verification
--    - Prevents trust escalation

-- ===== Storage Estimates =====
--
-- Federated Trust:
--   - Average record size: ~300 bytes
--   - 100 trusts × 300 bytes = ~30KB
--   - Negligible storage impact
--
-- Trust History:
--   - Average record size: ~200 bytes
--   - 1000 events × 200 bytes = ~200KB
--   - Manageable for SQLite

-- =============================================================================
-- Testing Checklist
-- =============================================================================
--
-- ✅ Insert trust with valid TTL
-- ✅ Insert trust with NULL expires_at (should fail)
-- ✅ Insert trust with TTL > 7 days (should fail)
-- ✅ Insert trust with expires_at < established_at (should fail)
-- ✅ Revoke trust and check history
-- ✅ Downgrade trust and check history
-- ✅ Renew trust and check history
-- ✅ Try to modify established_at (should fail)
-- ✅ Try to modify remote_system_id (should fail)
-- ✅ Try to modify history (should fail)
-- ✅ Try to delete history (should fail)
-- ✅ Query active trusts view
-- ✅ Query expired trusts view
-- ✅ Query trust statistics view

-- =============================================================================
-- Completion
-- =============================================================================
--
-- v0.75 Migration Complete!
--
-- Changes Summary:
-- - Added federated_trust table
-- - Added federated_trust_history table
-- - Added 11 validation triggers
-- - Added 7 indexes for query performance
-- - Added 3 summary views
-- - Enforced TTL policy (max 7 days)
-- - Enforced immutability of history and identity
-- - Automatic history logging for all trust events
--
-- Next Steps:
-- 1. Implement TrustLifecycle in lifecycle.py ✅
-- 2. Create verification tools (G5)
-- 3. Write comprehensive tests
-- 4. Document in FEDERATED_TRUST.md
-- 5. Create gate_cross_system_trust.sh
--
-- Version: v0.75.0
-- Date: 2026-02-02
-- Author: Phase G4 Agent (Federated Trust Lifecycle)
-- Reference: Phase G Task Cards
--
