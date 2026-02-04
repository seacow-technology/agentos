-- Schema v68: Trust Tier Determination
-- Phase D3: Trust Tier tables for tier calculation and history tracking
--
-- Purpose:
-- - Track trust tier changes over time
-- - Cache current tier for performance
-- - Enable tier evolution analysis
--
-- Design Principles:
-- 1. Tier is calculated result, not configuration
-- 2. All tier changes must be traceable
-- 3. Same extension can have different tiers over time

-- Trust Tier History Table
-- Records all tier changes for audit trail and evolution analysis
CREATE TABLE IF NOT EXISTS trust_tier_history (
    record_id TEXT PRIMARY KEY,           -- Unique record identifier (UUID)
    extension_id TEXT NOT NULL,           -- Extension identifier
    action_id TEXT NOT NULL,              -- Action identifier ("*" for all)
    old_tier TEXT,                        -- Previous tier (NULL for initial)
    new_tier TEXT NOT NULL,               -- New tier (LOW/MEDIUM/HIGH)
    risk_score REAL NOT NULL,             -- Risk score that triggered the tier
    reason TEXT,                          -- Human-readable reason
    created_at INTEGER NOT NULL           -- Timestamp (epoch milliseconds)
);

-- Indexes for tier history queries
CREATE INDEX IF NOT EXISTS idx_trust_tier_history_extension
ON trust_tier_history(extension_id, action_id);

CREATE INDEX IF NOT EXISTS idx_trust_tier_history_created
ON trust_tier_history(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_trust_tier_history_tier_changes
ON trust_tier_history(old_tier, new_tier)
WHERE old_tier IS NOT NULL;

-- Trust Tier Current State Table
-- Caches current tier for fast lookups without recalculation
CREATE TABLE IF NOT EXISTS trust_tier_current (
    extension_id TEXT NOT NULL,           -- Extension identifier
    action_id TEXT NOT NULL,              -- Action identifier
    tier TEXT NOT NULL,                   -- Current tier (LOW/MEDIUM/HIGH)
    risk_score REAL NOT NULL,             -- Current risk score
    updated_at INTEGER NOT NULL,          -- Last update timestamp (epoch milliseconds)
    PRIMARY KEY (extension_id, action_id)
);

-- Index for tier lookups
CREATE INDEX IF NOT EXISTS idx_trust_tier_current_tier
ON trust_tier_current(tier);

-- Schema version tracking
-- Note: schema_version table should already exist
INSERT INTO schema_version (version, description)
VALUES (
    '0.68.0',
    'Trust Tier determination tables: tier history and current state cache'
);
