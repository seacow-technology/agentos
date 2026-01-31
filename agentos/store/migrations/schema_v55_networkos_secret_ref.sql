-- Schema v55: NetworkOS Secret Reference Migration
--
-- Migration: tunnel_secrets.token → secret_ref
-- Rationale: Secrets should not be stored in plaintext in DB
-- Strategy: Add secret_ref, deprecate token, keep backward compatibility
--
-- Security Impact:
-- - Eliminates plaintext token storage in database
-- - Prevents token leakage in diagnostic exports
-- - Aligns with "zero secrets in DB" security posture
--
-- Backward Compatibility:
-- - token column preserved for 1 release cycle
-- - is_migrated flag tracks migration status
-- - Legacy code path supported until v0.next

-- ===================================================================
-- 0. Ensure tunnel_secrets table exists (backward compatibility fix)
-- ===================================================================

-- Create tunnel_secrets table if it doesn't exist
-- This handles the case where v54 was run before this table was added
CREATE TABLE IF NOT EXISTS tunnel_secrets (
    tunnel_id TEXT PRIMARY KEY,
    token TEXT,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    FOREIGN KEY (tunnel_id) REFERENCES network_tunnels(tunnel_id) ON DELETE CASCADE
);

-- Create index if it doesn't exist
CREATE INDEX IF NOT EXISTS idx_tunnel_secrets_tunnel
    ON tunnel_secrets(tunnel_id);

-- ===================================================================
-- 1. Add secret_ref column (nullable for migration period)
-- ===================================================================

-- Add secret_ref to reference secure storage
ALTER TABLE tunnel_secrets ADD COLUMN secret_ref TEXT;

-- Add migration status flag
ALTER TABLE tunnel_secrets ADD COLUMN is_migrated INTEGER DEFAULT 0;

-- ===================================================================
-- 2. Create indexes for performance
-- ===================================================================

-- Index for fast lookup by secret_ref
CREATE INDEX IF NOT EXISTS idx_tunnel_secrets_ref
    ON tunnel_secrets(secret_ref);

-- Index for finding unmigrated tunnels
CREATE INDEX IF NOT EXISTS idx_tunnel_secrets_migrated
    ON tunnel_secrets(is_migrated)
    WHERE is_migrated = 0;

-- ===================================================================
-- 3. Migration audit table
-- ===================================================================

-- Store migration notes for audit trail
CREATE TABLE IF NOT EXISTS schema_migration_notes (
    migration_version TEXT PRIMARY KEY,
    applied_at INTEGER NOT NULL,
    notes TEXT,
    security_impact TEXT
);

INSERT OR IGNORE INTO schema_migration_notes (
    migration_version,
    applied_at,
    notes,
    security_impact
)
VALUES (
    'v55',
    strftime('%s', 'now') * 1000,
    'NetworkOS: Migrated tunnel_secrets to use secret_ref instead of plaintext token storage. Backward compatibility maintained for 1 release cycle. Old token column will be removed in v0.next.',
    'CRITICAL: Eliminates plaintext token storage in database. Prevents token leakage in diagnostic exports and database dumps. Tokens now stored in encrypted secure storage (~/.agentos/secrets.json with 0600 permissions).'
);

-- ===================================================================
-- 4. Verification queries
-- ===================================================================

-- Count tunnels by migration status
SELECT 'Migration status summary:' as info;
SELECT
    CASE
        WHEN is_migrated = 1 THEN 'Migrated (secret_ref)'
        ELSE 'Legacy (plaintext token)'
    END as status,
    COUNT(*) as count
FROM tunnel_secrets
GROUP BY is_migrated;

-- Show sample of unmigrated tunnels (without exposing tokens)
SELECT 'Unmigrated tunnels (need migration):' as info;
SELECT
    tunnel_id,
    LENGTH(token) as token_length,
    created_at
FROM tunnel_secrets
WHERE is_migrated = 0
LIMIT 5;

-- ===================================================================
-- Design Notes:
-- ===================================================================
--
-- Migration Strategy:
-- 1. Schema v55 adds secret_ref column alongside existing token column
-- 2. Runtime code prioritizes secret_ref over token
-- 3. CLI provides migrate-secrets command for manual migration
-- 4. Legacy token access logs warning events
-- 5. Schema v56 (future) will drop token column after grace period
--
-- Security Model:
-- - DB stores: secret_ref (e.g., "networkos:tunnel:abc123")
-- - Secure storage stores: actual token (encrypted file)
-- - Diagnostic exports: exclude/redact tunnel_secrets table
-- - Logs: never print tokens, only redacted forms
--
-- Secret Reference Format:
-- - Pattern: "networkos:tunnel:<tunnel_id>"
-- - Example: "networkos:tunnel:cf-a1b2c3d4"
-- - Stored in: ~/.agentos/secrets.json
--
-- ===================================================================
