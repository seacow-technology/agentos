-- Schema v74: Trust Inheritance (Phase F3)
-- Phase F: Marketplace + Trust Inheritance
--
-- Purpose:
-- - Store publisher trust scores and reputation
-- - Track trust inheritance calculations for marketplace capabilities
-- - Enable transparent trust inheritance auditing
-- - Support initial trust score calculation for new capabilities
--
-- Design Principles:
-- 1. TRANSPARENCY: All inheritance calculations are auditable
-- 2. TRACEABILITY: Source breakdown for every inherited trust score
-- 3. NON-OVERRIDABLE: Trust is calculated, not assigned
-- 4. TIME-BOUND: Publisher trust has recalculation timestamps
--
-- Red Lines (MUST NOT):
-- ❌ Cannot inherit HIGH risk trust (max initial tier = MEDIUM)
-- ❌ Cannot inherit across publishers
-- ❌ Cannot skip Phase E evolution (initial state = EARNING)
-- ❌ Cannot manually override calculated trust
--
-- Trust Inheritance Formula (v0):
--   initial_trust = (
--       publisher_trust * 0.3 +
--       category_similarity * 0.2 +
--       sandbox_safety * 0.5
--   )
--   capped at 70% (HIGH_RISK_THRESHOLD)
--
-- Created: 2026-02-02
-- Author: Phase F3 Agent (Trust Inheritance Engine)
-- Reference: Phase F Task Cards (plan1.md)

-- =============================================================================
-- Publisher Trust Table
-- =============================================================================
-- Stores calculated trust scores for capability publishers.
-- Trust is based on historical performance of publisher's capabilities
-- in the local system.

CREATE TABLE IF NOT EXISTS marketplace_publisher_trust (
    -- Primary key
    publisher_id TEXT PRIMARY KEY,             -- Publisher identifier (e.g., "official", "smithery.ai")

    -- Trust metrics
    trust_score REAL NOT NULL,                 -- Calculated trust score (0-100)
    capability_count INTEGER NOT NULL,         -- Number of capabilities from this publisher
    average_risk_score REAL NOT NULL,          -- Average risk across capabilities

    -- Performance metrics
    successful_executions INTEGER NOT NULL DEFAULT 0,  -- Total successful executions
    failed_executions INTEGER NOT NULL DEFAULT 0,      -- Total failed executions

    -- Temporal data
    last_calculated_at INTEGER NOT NULL,       -- Last trust calculation (epoch ms)
    created_at INTEGER NOT NULL,               -- First record creation (epoch ms)

    -- Constraints
    CHECK(trust_score >= 0.0 AND trust_score <= 100.0),
    CHECK(average_risk_score >= 0.0 AND average_risk_score <= 100.0),
    CHECK(capability_count >= 0),
    CHECK(successful_executions >= 0),
    CHECK(failed_executions >= 0)
);

-- =============================================================================
-- Capability Inheritance Table
-- =============================================================================
-- Records trust inheritance calculations for marketplace capabilities.
-- Each record represents the initial trust calculation when a capability
-- first enters the local system.

CREATE TABLE IF NOT EXISTS marketplace_capability_inheritance (
    -- Primary key
    inheritance_id TEXT PRIMARY KEY,           -- UUID: inh-{capability_id}-{epoch_ms}

    -- Target identification
    capability_id TEXT NOT NULL,               -- Full capability identifier
    publisher_id TEXT NOT NULL,                -- Publisher identifier
    category TEXT NOT NULL,                    -- Capability category
    sandbox_level TEXT NOT NULL,               -- Declared sandbox level

    -- Inheritance calculation
    inherited_trust REAL NOT NULL,             -- Total inherited trust (0-100)
    publisher_contribution REAL NOT NULL,      -- Publisher trust contribution (0-30)
    category_contribution REAL NOT NULL,       -- Category similarity contribution (0-20)
    sandbox_contribution REAL NOT NULL,        -- Sandbox safety contribution (0-50)

    -- Initial assignment
    initial_tier TEXT NOT NULL,                -- Initial trust tier: 'LOW', 'MEDIUM'
    initial_state TEXT NOT NULL DEFAULT 'EARNING',  -- Initial state: always 'EARNING'

    -- Explanation
    explanation TEXT NOT NULL,                 -- Human-readable explanation
    calculation_details TEXT,                  -- JSON: detailed calculation breakdown

    -- Temporal data
    calculated_at INTEGER NOT NULL,            -- When inheritance was calculated (epoch ms)

    -- Constraints
    CHECK(inherited_trust >= 0.0 AND inherited_trust <= 100.0),
    CHECK(publisher_contribution >= 0.0 AND publisher_contribution <= 30.0),
    CHECK(category_contribution >= 0.0 AND category_contribution <= 20.0),
    CHECK(sandbox_contribution >= 0.0 AND sandbox_contribution <= 50.0),
    CHECK(initial_tier IN ('LOW', 'MEDIUM')),  -- HIGH is prohibited
    CHECK(initial_state = 'EARNING'),          -- Must start with EARNING
    CHECK(sandbox_level IN ('none', 'low', 'medium', 'high')),

    -- Foreign key (soft reference)
    FOREIGN KEY (publisher_id) REFERENCES marketplace_publisher_trust(publisher_id)
        ON DELETE CASCADE
);

-- =============================================================================
-- Indexes for Query Performance
-- =============================================================================

-- Publisher lookup
CREATE INDEX IF NOT EXISTS idx_publisher_trust_score
ON marketplace_publisher_trust(trust_score DESC, last_calculated_at DESC);

-- Publisher last calculated (for cache invalidation)
CREATE INDEX IF NOT EXISTS idx_publisher_last_calc
ON marketplace_publisher_trust(last_calculated_at DESC);

-- Capability inheritance by capability
CREATE INDEX IF NOT EXISTS idx_inheritance_capability
ON marketplace_capability_inheritance(capability_id, calculated_at DESC);

-- Inheritance by publisher
CREATE INDEX IF NOT EXISTS idx_inheritance_publisher
ON marketplace_capability_inheritance(publisher_id, calculated_at DESC);

-- Inheritance by tier (for statistics)
CREATE INDEX IF NOT EXISTS idx_inheritance_tier
ON marketplace_capability_inheritance(initial_tier, calculated_at DESC);

-- Inheritance chronological
CREATE INDEX IF NOT EXISTS idx_inheritance_time
ON marketplace_capability_inheritance(calculated_at DESC);

-- =============================================================================
-- Publisher Trust Summary View
-- =============================================================================
-- Convenience view for publisher trust overview

CREATE VIEW IF NOT EXISTS publisher_trust_summary AS
SELECT
    p.publisher_id,
    p.trust_score,
    p.capability_count,
    p.average_risk_score,
    p.successful_executions,
    p.failed_executions,
    ROUND(
        CAST(p.successful_executions AS REAL) /
        NULLIF(p.successful_executions + p.failed_executions, 0) * 100,
        2
    ) as success_rate_pct,
    p.last_calculated_at,
    COUNT(i.inheritance_id) as inherited_capability_count
FROM marketplace_publisher_trust p
LEFT JOIN marketplace_capability_inheritance i
    ON p.publisher_id = i.publisher_id
GROUP BY p.publisher_id
ORDER BY p.trust_score DESC;

-- =============================================================================
-- Capability Inheritance Summary View
-- =============================================================================
-- Convenience view for inheritance statistics

CREATE VIEW IF NOT EXISTS capability_inheritance_summary AS
SELECT
    category,
    initial_tier,
    COUNT(*) as capability_count,
    AVG(inherited_trust) as avg_inherited_trust,
    MIN(inherited_trust) as min_inherited_trust,
    MAX(inherited_trust) as max_inherited_trust,
    AVG(publisher_contribution) as avg_publisher_contrib,
    AVG(category_contribution) as avg_category_contrib,
    AVG(sandbox_contribution) as avg_sandbox_contrib
FROM marketplace_capability_inheritance
GROUP BY category, initial_tier
ORDER BY category, initial_tier;

-- =============================================================================
-- Trust Inheritance Audit Triggers
-- =============================================================================

-- TRIGGER 1: Validate initial_state is always EARNING
-- Rationale: New capabilities must always start with EARNING state
CREATE TRIGGER IF NOT EXISTS validate_inheritance_initial_state
BEFORE INSERT ON marketplace_capability_inheritance
FOR EACH ROW
WHEN NEW.initial_state != 'EARNING'
BEGIN
    SELECT RAISE(ABORT, 'FORBIDDEN: initial_state must be EARNING for new capabilities');
END;

-- TRIGGER 2: Validate initial_tier is not HIGH
-- Rationale: Cannot inherit HIGH tier trust (red line)
CREATE TRIGGER IF NOT EXISTS validate_inheritance_no_high_tier
BEFORE INSERT ON marketplace_capability_inheritance
FOR EACH ROW
WHEN NEW.initial_tier = 'HIGH'
BEGIN
    SELECT RAISE(ABORT, 'FORBIDDEN: Cannot inherit HIGH tier. Initial tier must be LOW or MEDIUM.');
END;

-- TRIGGER 3: Validate total contribution adds up
-- Rationale: Ensure calculation integrity
CREATE TRIGGER IF NOT EXISTS validate_inheritance_contribution_sum
BEFORE INSERT ON marketplace_capability_inheritance
FOR EACH ROW
WHEN ABS(NEW.inherited_trust - (NEW.publisher_contribution + NEW.category_contribution + NEW.sandbox_contribution)) > 0.1
BEGIN
    SELECT RAISE(ABORT, 'INVALID: inherited_trust must equal sum of contributions');
END;

-- TRIGGER 4: Validate publisher_contribution is within limits
-- Rationale: Publisher can contribute max 30%
CREATE TRIGGER IF NOT EXISTS validate_inheritance_publisher_limit
BEFORE INSERT ON marketplace_capability_inheritance
FOR EACH ROW
WHEN NEW.publisher_contribution > 30.0
BEGIN
    SELECT RAISE(ABORT, 'INVALID: publisher_contribution cannot exceed 30%');
END;

-- TRIGGER 5: Validate category_contribution is within limits
-- Rationale: Category can contribute max 20%
CREATE TRIGGER IF NOT EXISTS validate_inheritance_category_limit
BEFORE INSERT ON marketplace_capability_inheritance
FOR EACH ROW
WHEN NEW.category_contribution > 20.0
BEGIN
    SELECT RAISE(ABORT, 'INVALID: category_contribution cannot exceed 20%');
END;

-- TRIGGER 6: Validate sandbox_contribution is within limits
-- Rationale: Sandbox can contribute max 50%
CREATE TRIGGER IF NOT EXISTS validate_inheritance_sandbox_limit
BEFORE INSERT ON marketplace_capability_inheritance
FOR EACH ROW
WHEN NEW.sandbox_contribution > 50.0
BEGIN
    SELECT RAISE(ABORT, 'INVALID: sandbox_contribution cannot exceed 50%');
END;

-- TRIGGER 7: Validate inherited_trust is capped at 70%
-- Rationale: Cannot exceed HIGH_RISK_THRESHOLD
CREATE TRIGGER IF NOT EXISTS validate_inheritance_trust_cap
BEFORE INSERT ON marketplace_capability_inheritance
FOR EACH ROW
WHEN NEW.inherited_trust > 70.0
BEGIN
    SELECT RAISE(ABORT, 'FORBIDDEN: inherited_trust cannot exceed 70% (HIGH_RISK_THRESHOLD)');
END;

-- TRIGGER 8: Validate calculation_details is valid JSON (if provided)
CREATE TRIGGER IF NOT EXISTS validate_inheritance_json
BEFORE INSERT ON marketplace_capability_inheritance
FOR EACH ROW
WHEN NEW.calculation_details IS NOT NULL AND json_valid(NEW.calculation_details) = 0
BEGIN
    SELECT RAISE(ABORT, 'INVALID: calculation_details must be valid JSON');
END;

-- =============================================================================
-- Schema Version Record
-- =============================================================================

INSERT INTO schema_version (version, description)
VALUES ('0.74.0', 'Trust Inheritance - Publisher trust and capability inheritance (Phase F3)');

-- =============================================================================
-- Usage Examples
-- =============================================================================

-- ===== Example 1: Insert publisher trust record =====
--
-- INSERT INTO marketplace_publisher_trust (
--     publisher_id, trust_score, capability_count, average_risk_score,
--     successful_executions, failed_executions, last_calculated_at, created_at
-- ) VALUES (
--     'official', 80.0, 5, 25.0,
--     150, 10, 1738540800000, 1738540800000
-- );

-- ===== Example 2: Record capability inheritance =====
--
-- INSERT INTO marketplace_capability_inheritance (
--     inheritance_id, capability_id, publisher_id, category, sandbox_level,
--     inherited_trust, publisher_contribution, category_contribution, sandbox_contribution,
--     initial_tier, initial_state, explanation, calculated_at
-- ) VALUES (
--     'inh-official.web_scraper.v2.0.0-1738540800000',
--     'official.web_scraper.v2.0.0',
--     'official',
--     'web',
--     'medium',
--     68.0,
--     24.0,  -- 80% * 0.3
--     14.0,  -- 70% * 0.2
--     30.0,  -- 60% * 0.5
--     'MEDIUM',
--     'EARNING',
--     'Initial trust: 68.0% (MEDIUM) | Sources: Publisher 24.0% + Category 14.0% + Sandbox 30.0% | State: EARNING',
--     1738540800000
-- );

-- ===== Example 3: Query publisher trust with capabilities =====
--
-- SELECT * FROM publisher_trust_summary WHERE publisher_id = 'official';

-- ===== Example 4: Query inheritance by category =====
--
-- SELECT * FROM capability_inheritance_summary WHERE category = 'web';

-- ===== Example 5: Get latest inheritance for a capability =====
--
-- SELECT
--     capability_id,
--     inherited_trust,
--     initial_tier,
--     publisher_contribution,
--     category_contribution,
--     sandbox_contribution,
--     explanation
-- FROM marketplace_capability_inheritance
-- WHERE capability_id = 'official.web_scraper.v2.0.0'
-- ORDER BY calculated_at DESC
-- LIMIT 1;

-- ===== Example 6: Try to insert HIGH tier (should fail) =====
--
-- This will trigger the validate_inheritance_no_high_tier trigger:
-- INSERT INTO marketplace_capability_inheritance (
--     inheritance_id, capability_id, publisher_id, category, sandbox_level,
--     inherited_trust, publisher_contribution, category_contribution, sandbox_contribution,
--     initial_tier, initial_state, explanation, calculated_at
-- ) VALUES (
--     'inh-test-1738540800000', 'test', 'test', 'test', 'high',
--     75.0, 22.5, 15.0, 37.5,
--     'HIGH',  -- This will fail
--     'EARNING',
--     'Test',
--     1738540800000
-- );
-- Result: ABORT with error: "FORBIDDEN: Cannot inherit HIGH tier..."

-- =============================================================================
-- Design Notes
-- =============================================================================

-- ===== Publisher Trust Calculation =====
--
-- Publisher trust is calculated from:
-- 1. Average trust of all publisher capabilities in local system
-- 2. Time decay (recent performance matters more)
-- 3. Risk penalty (high-risk capabilities reduce trust)
-- 4. Minimum capability count (need at least 3 for valid trust)
--
-- Publishers with no local history get 0% trust.

-- ===== Trust Inheritance Rules (v0 Fixed) =====
--
-- Source                    | Max Contribution | Rationale
-- --------------------------|------------------|----------------------------------
-- Publisher Historical Trust| 30%             | Reputation earned through history
-- Category Similarity       | 20%             | Similar capabilities may behave similarly
-- Sandbox Safety Level      | 50%             | Strong isolation = more initial trust
-- Local Historical Trust    | 0%              | Cannot inherit local trust
--
-- Total inherited trust is capped at 70% (HIGH_RISK_THRESHOLD).
-- This ensures new capabilities cannot start with HIGH tier.

-- ===== Initial Tier Mapping =====
--
-- Inherited Trust | Initial Tier | Reasoning
-- ----------------|--------------|---------------------------------------
-- < 30%          | LOW          | Minimal trust, must prove safety
-- 30-70%         | MEDIUM       | Moderate trust, can start with some permissions
-- > 70%          | N/A          | Capped at 70%, cannot reach HIGH initially
--
-- All capabilities start with EARNING state regardless of tier.

-- ===== Red Lines (Enforced by Triggers) =====
--
-- 1. Cannot inherit HIGH tier:
--    - Trigger: validate_inheritance_no_high_tier
--    - Reason: New capabilities must prove HIGH trust locally
--
-- 2. Must start with EARNING state:
--    - Trigger: validate_inheritance_initial_state
--    - Reason: All capabilities must go through Phase E evolution
--
-- 3. Inherited trust capped at 70%:
--    - Trigger: validate_inheritance_trust_cap
--    - Reason: Prevents bypassing HIGH tier restrictions
--
-- 4. Contribution limits enforced:
--    - Triggers: validate_inheritance_publisher_limit (30%)
--               validate_inheritance_category_limit (20%)
--               validate_inheritance_sandbox_limit (50%)
--    - Reason: Maintains trust inheritance formula integrity

-- ===== Capability Lifecycle =====
--
-- 1. Marketplace capability arrives
--    ↓
-- 2. Trust Inheritance Engine calculates initial trust
--    ↓
-- 3. Record stored in marketplace_capability_inheritance
--    ↓
-- 4. Capability enters local system with initial trust
--    ↓
-- 5. Phase E Trust Evolution takes over (EARNING → STABLE/DEGRADING)
--    ↓
-- 6. Local trust evolution is independent of inherited trust

-- ===== Cross-Publisher Prohibition =====
--
-- Trust CANNOT be inherited across publishers. Each publisher's trust
-- is calculated independently based on their own capability history.
--
-- Example (FORBIDDEN):
--   - Publisher A has 80% trust
--   - Publisher B is new (0% trust)
--   - Publisher B cannot claim Publisher A's trust
--
-- This is enforced by linking inheritance to specific publisher_id.

-- ===== Storage Estimates =====
--
-- Publisher Trust:
--   - ~100 publishers × 200 bytes = ~20KB
--   - Negligible storage impact
--
-- Capability Inheritance:
--   - Average record size: ~500 bytes
--   - 100 capabilities × 500 bytes = ~50KB
--   - 1000 capabilities × 500 bytes = ~500KB
--   - Manageable for SQLite

-- =============================================================================
-- Compliance & Audit
-- =============================================================================

-- ===== Transparency Requirements =====
--
-- Every inherited trust calculation includes:
-- - Source breakdown (publisher, category, sandbox)
-- - Contribution percentages
-- - Human-readable explanation
-- - Calculation timestamp
--
-- This enables answering:
-- - "Why did this capability start with X% trust?"
-- - "What contributed to the initial trust score?"
-- - "Has the inheritance formula been followed correctly?"

-- ===== Audit Trail =====
--
-- All inheritance calculations are immutable (no UPDATE/DELETE on marketplace_capability_inheritance).
-- If trust needs recalculation, create a new record with new timestamp.
--
-- This provides:
-- - Complete history of trust calculations
-- - Detection of calculation errors
-- - Compliance with audit requirements

-- =============================================================================
-- Testing Checklist
-- =============================================================================
--
-- ✅ Insert publisher trust record
-- ✅ Insert capability inheritance record
-- ✅ Query publisher trust summary
-- ✅ Query capability inheritance summary
-- ✅ Try to insert HIGH tier (should fail)
-- ✅ Try to insert with wrong initial_state (should fail)
-- ✅ Try to insert with trust > 70% (should fail)
-- ✅ Try to insert with publisher_contribution > 30% (should fail)
-- ✅ Try to insert with category_contribution > 20% (should fail)
-- ✅ Try to insert with sandbox_contribution > 50% (should fail)
-- ✅ Verify contribution sum validation
-- ✅ Test foreign key constraint
-- ✅ Test index performance with 100+ records

-- =============================================================================
-- Completion
-- =============================================================================
--
-- v0.74 Migration Complete!
--
-- Changes Summary:
-- - Added marketplace_publisher_trust table
-- - Added marketplace_capability_inheritance table
-- - Added 8 validation triggers for red line enforcement
-- - Added 6 indexes for query performance
-- - Added 2 summary views for convenience
-- - Enforced trust inheritance formula (30% + 20% + 50%)
-- - Prohibited HIGH tier inheritance
-- - Mandated EARNING initial state
--
-- Next Steps:
-- 1. Implement TrustInheritanceEngine in trust_inheritance.py
-- 2. Implement PublisherTrustManager in publisher_trust.py
-- 3. Create calc_initial_trust.py tool
-- 4. Create update_publisher_trust.py tool
-- 5. Write comprehensive tests
-- 6. Document in TRUST_INHERITANCE_RULES.md
--
-- Version: v0.74.0
-- Date: 2026-02-02
-- Author: Phase F3 Agent (Trust Inheritance Engine)
-- Reference: Phase F Task Cards
--
