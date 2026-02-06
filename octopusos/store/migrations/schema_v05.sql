-- AgentOS Store Schema v0.5
-- Content Registry: Foundation for content governance
-- Migration from v0.4 -> v0.5

-- ============================================
-- Content Registry: Unified Content Metadata
-- ============================================

CREATE TABLE IF NOT EXISTS content_registry (
    id TEXT NOT NULL,
    type TEXT NOT NULL,
    version TEXT NOT NULL,
    status TEXT DEFAULT 'draft',  -- draft|active|deprecated|frozen
    checksum TEXT NOT NULL,
    parent_version TEXT,
    change_reason TEXT,
    is_root INTEGER DEFAULT 0,  -- boolean: 1=root version, 0=evolved version
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    activated_at TIMESTAMP,
    deprecated_at TIMESTAMP,
    frozen_at TIMESTAMP,
    metadata TEXT,  -- JSON: extended metadata
    spec TEXT NOT NULL,  -- JSON: content-specific specification
    
    PRIMARY KEY (id, version),
    
    -- 🚨 RED LINE #3: Lineage constraint (enforced at database level)
    -- Either: is_root=1 AND no parent_version
    -- Or: is_root=0 AND parent_version AND change_reason
    CHECK (
        (is_root = 1 AND parent_version IS NULL) OR
        (is_root = 0 AND parent_version IS NOT NULL AND length(change_reason) > 0)
    ),
    
    -- Status must be valid
    CHECK (status IN ('draft', 'active', 'deprecated', 'frozen'))
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_content_registry_type ON content_registry(type);
CREATE INDEX IF NOT EXISTS idx_content_registry_status ON content_registry(status);
CREATE INDEX IF NOT EXISTS idx_content_registry_parent ON content_registry(parent_version);
CREATE INDEX IF NOT EXISTS idx_content_registry_lineage ON content_registry(is_root, parent_version);
CREATE INDEX IF NOT EXISTS idx_content_registry_type_status ON content_registry(type, status);

-- ============================================
-- Content Lineage: Evolution Tracking
-- ============================================

CREATE TABLE IF NOT EXISTS content_lineage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content_id TEXT NOT NULL,
    from_version TEXT NOT NULL,
    to_version TEXT NOT NULL,
    diff TEXT,  -- JSON: structured diff
    reason TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (content_id) REFERENCES content_registry(id)
);

CREATE INDEX IF NOT EXISTS idx_content_lineage_id ON content_lineage(content_id);
CREATE INDEX IF NOT EXISTS idx_content_lineage_from_to ON content_lineage(content_id, from_version, to_version);

-- ============================================
-- Content Audit Log: Content-level Audit
-- ============================================

CREATE TABLE IF NOT EXISTS content_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event TEXT NOT NULL,  -- registered|activated|deprecated|frozen|unfrozen|superseded
    content_id TEXT NOT NULL,
    version TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    operator TEXT,  -- operator (future: user/agent identifier)
    metadata TEXT,  -- JSON: additional information
    
    CHECK (event IN ('registered', 'activated', 'deprecated', 'frozen', 'unfrozen', 'superseded'))
);

CREATE INDEX IF NOT EXISTS idx_content_audit_id ON content_audit_log(content_id);
CREATE INDEX IF NOT EXISTS idx_content_audit_event ON content_audit_log(event);
CREATE INDEX IF NOT EXISTS idx_content_audit_timestamp ON content_audit_log(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_content_audit_id_version ON content_audit_log(content_id, version);

-- ============================================
-- Version Tracking
-- ============================================

INSERT OR REPLACE INTO schema_version (version) VALUES ('0.5.0');
