-- Migration v0.33: Extensions System
-- Description: Core infrastructure for AgentOS Extension system
-- Purpose: Enable installable capability packages management
-- Migration from v0.32 -> v0.33
--
-- Background:
--   - AgentOS needs a plugin/extension system for third-party integrations
--   - Extensions are zip packages with manifest, commands, and install plans
--   - Extensions cannot import/patch AgentOS core (security boundary)
--   - All installations are managed by Core's controlled executors
--
-- Design Principles:
--   - Strict isolation: extensions have no direct system access
--   - Declarative: extensions declare capabilities, Core executes
--   - Auditable: all installation steps are tracked
--   - Sandboxed: no network/exec permissions by default
--
-- Use Cases:
--   - Install third-party tools (Postman, k6, etc.)
--   - Add slash commands (/postman, /k6)
--   - Manage extension lifecycle (enable/disable/uninstall)
--   - Configure extension settings
--
-- Reference:
--   - P2 Strategic Plan: Extension System (PR-A to PR-F)
--
-- ============================================
-- Phase 1: Create extensions Table
-- ============================================

CREATE TABLE IF NOT EXISTS extensions (
    -- Primary key
    id TEXT PRIMARY KEY,                    -- Unique extension ID (e.g., 'tools.postman')

    -- Basic metadata
    name TEXT NOT NULL,                     -- Human-readable name
    version TEXT NOT NULL,                  -- Semantic version (e.g., '0.1.0')
    description TEXT,                       -- Brief description
    icon_path TEXT,                         -- Path to icon file (relative to extension dir)

    -- Status
    installed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    enabled BOOLEAN DEFAULT TRUE,           -- Whether extension is active
    status TEXT NOT NULL,                   -- INSTALLED, INSTALLING, FAILED, UNINSTALLED

    -- Security
    sha256 TEXT NOT NULL,                   -- SHA256 hash of the zip package
    source TEXT NOT NULL,                   -- upload, url
    source_url TEXT,                        -- Original URL if installed from URL

    -- Permissions and capabilities (JSON)
    permissions_required TEXT,              -- JSON array: ["network", "exec", "filesystem.write"]
    capabilities TEXT,                      -- JSON array of capability objects

    -- Additional metadata (JSON)
    metadata TEXT,                          -- JSON object for extensibility

    -- Constraints
    CHECK(status IN ('INSTALLED', 'INSTALLING', 'FAILED', 'UNINSTALLED')),
    CHECK(source IN ('upload', 'url'))
);

-- ============================================
-- Phase 2: Create extension_installs Table
-- ============================================

CREATE TABLE IF NOT EXISTS extension_installs (
    -- Primary key
    install_id TEXT PRIMARY KEY,            -- Unique install process ID (ULID)

    -- Extension reference
    extension_id TEXT NOT NULL,

    -- Installation status
    status TEXT NOT NULL,                   -- INSTALLING, COMPLETED, FAILED, UNINSTALLING
    progress INTEGER DEFAULT 0,             -- 0-100
    current_step TEXT,                      -- Current step description

    -- Timing
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP,

    -- Error handling
    error TEXT,                             -- Error message if status = FAILED

    -- Constraints
    FOREIGN KEY (extension_id) REFERENCES extensions(id) ON DELETE CASCADE,
    CHECK(status IN ('INSTALLING', 'COMPLETED', 'FAILED', 'UNINSTALLING')),
    CHECK(progress >= 0 AND progress <= 100)
);

-- ============================================
-- Phase 3: Create extension_configs Table
-- ============================================

CREATE TABLE IF NOT EXISTS extension_configs (
    -- Primary key (one config per extension)
    extension_id TEXT PRIMARY KEY,

    -- Configuration data
    config_json TEXT,                       -- JSON object: extension-specific config
    secrets_ref TEXT,                       -- Reference to secrets storage (if needed)

    -- Metadata
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    FOREIGN KEY (extension_id) REFERENCES extensions(id) ON DELETE CASCADE
);

-- ============================================
-- Phase 4: Indexes for Performance
-- ============================================

-- Index 1: Query enabled extensions
CREATE INDEX IF NOT EXISTS idx_extensions_enabled
ON extensions(enabled)
WHERE enabled = TRUE;

-- Index 2: Query by status
CREATE INDEX IF NOT EXISTS idx_extensions_status
ON extensions(status);

-- Index 3: Query installs by extension
CREATE INDEX IF NOT EXISTS idx_extension_installs_extension_id
ON extension_installs(extension_id);

-- Index 4: Query installs by status
CREATE INDEX IF NOT EXISTS idx_extension_installs_status
ON extension_installs(status);

-- Index 5: Query recent installs
CREATE INDEX IF NOT EXISTS idx_extension_installs_started
ON extension_installs(started_at DESC);

-- ============================================
-- Phase 5: Validation Triggers
-- ============================================

-- Trigger 1: Ensure extension ID is not empty
CREATE TRIGGER IF NOT EXISTS validate_extension_id
BEFORE INSERT ON extensions
FOR EACH ROW
WHEN NEW.id IS NULL OR NEW.id = ''
BEGIN
    SELECT RAISE(ABORT, 'extensions.id cannot be empty');
END;

-- Trigger 2: Ensure version follows semantic versioning
CREATE TRIGGER IF NOT EXISTS validate_extension_version
BEFORE INSERT ON extensions
FOR EACH ROW
WHEN NEW.version NOT LIKE '_%.%._%'
BEGIN
    SELECT RAISE(ABORT, 'extensions.version must follow semantic versioning (e.g., "0.1.0")');
END;

-- Trigger 3: Ensure sha256 is valid hex string
CREATE TRIGGER IF NOT EXISTS validate_extension_sha256
BEFORE INSERT ON extensions
FOR EACH ROW
WHEN NEW.sha256 IS NULL OR LENGTH(NEW.sha256) != 64
BEGIN
    SELECT RAISE(ABORT, 'extensions.sha256 must be a 64-character hex string');
END;

-- Trigger 4: Update config timestamp on modification
CREATE TRIGGER IF NOT EXISTS update_extension_config_timestamp
AFTER UPDATE ON extension_configs
FOR EACH ROW
BEGIN
    UPDATE extension_configs
    SET updated_at = CURRENT_TIMESTAMP
    WHERE extension_id = NEW.extension_id;
END;

-- ============================================
-- Phase 6: Usage Examples
-- ============================================

-- ===== Example 1: Insert a new extension =====
--
-- INSERT INTO extensions (
--     id, name, version, description, icon_path,
--     enabled, status, sha256, source, source_url,
--     permissions_required, capabilities, metadata
-- ) VALUES (
--     'tools.postman',
--     'Postman Toolkit',
--     '0.1.0',
--     'API testing toolkit with Postman CLI',
--     'icon.png',
--     TRUE,
--     'INSTALLED',
--     'a1b2c3d4e5f6...',
--     'url',
--     'https://example.com/postman-ext.zip',
--     json_array('network', 'exec'),
--     json_array(
--         json_object(
--             'type', 'slash_command',
--             'name', '/postman',
--             'description', 'Run Postman API tests'
--         )
--     ),
--     json_object('author', 'Example Corp', 'license', 'Apache-2.0')
-- );

-- ===== Example 2: Insert an installation record =====
--
-- INSERT INTO extension_installs (
--     install_id, extension_id, status, progress, current_step
-- ) VALUES (
--     '01GXZ9J3K4M5N6P7Q8R9S0T1U2',
--     'tools.postman',
--     'INSTALLING',
--     50,
--     'Downloading Postman CLI binary'
-- );

-- ===== Example 3: Insert extension configuration =====
--
-- INSERT INTO extension_configs (
--     extension_id, config_json, secrets_ref
-- ) VALUES (
--     'tools.postman',
--     json_object(
--         'api_endpoint', 'https://api.postman.com',
--         'default_collection', 'my-collection'
--     ),
--     'secret://postman/api_key'
-- );

-- ===== Query Pattern 1: Get all enabled extensions =====
--
-- SELECT id, name, version, capabilities
-- FROM extensions
-- WHERE enabled = TRUE AND status = 'INSTALLED'
-- ORDER BY name;

-- ===== Query Pattern 2: Get extension with capabilities =====
--
-- SELECT
--     e.id,
--     e.name,
--     e.version,
--     e.capabilities,
--     ec.config_json
-- FROM extensions e
-- LEFT JOIN extension_configs ec ON e.id = ec.extension_id
-- WHERE e.id = 'tools.postman';

-- ===== Query Pattern 3: Get installation progress =====
--
-- SELECT
--     ei.install_id,
--     ei.status,
--     ei.progress,
--     ei.current_step,
--     e.name
-- FROM extension_installs ei
-- JOIN extensions e ON ei.extension_id = e.id
-- WHERE ei.status = 'INSTALLING'
-- ORDER BY ei.started_at DESC;

-- ===== Query Pattern 4: Get extensions by capability type =====
--
-- SELECT id, name, version
-- FROM extensions
-- WHERE enabled = TRUE
--   AND status = 'INSTALLED'
--   AND json_extract(capabilities, '$[*].type') LIKE '%slash_command%'
-- ORDER BY name;

-- ============================================
-- Phase 7: Update Schema Version
-- ============================================

INSERT OR REPLACE INTO schema_version (version) VALUES ('0.33.0');

-- ============================================
-- Design Notes
-- ============================================

-- ===== Extension Lifecycle =====
--
-- 1. Installation:
--    - User uploads zip or provides URL
--    - Validator checks structure and manifest
--    - Installer extracts to ~/.agentos/extensions/<extension_id>/
--    - Registry inserts record into extensions table
--    - Status: INSTALLING -> INSTALLED (or FAILED)
--
-- 2. Activation:
--    - Extension is enabled by default after installation
--    - Can be disabled/enabled without uninstalling
--    - Only enabled extensions are loaded at runtime
--
-- 3. Configuration:
--    - Extension-specific config stored in extension_configs
--    - Secrets stored separately (referenced via secrets_ref)
--    - Config can be updated without reinstalling
--
-- 4. Uninstallation:
--    - Status changed to UNINSTALLED (soft delete)
--    - Files removed from filesystem
--    - Database records retained for audit trail
--    - Foreign keys CASCADE delete configs and install records

-- ===== Security Model =====
--
-- Extensions are sandboxed by design:
--   - No direct import of AgentOS code
--   - No arbitrary code execution
--   - Only declarative capabilities
--   - Install plan executed by Core (not by extension code)
--
-- Permission system:
--   - network: Can make HTTP requests
--   - exec: Can execute system commands
--   - filesystem.read: Can read files
--   - filesystem.write: Can write files
--
-- Permissions are declared in manifest and stored in permissions_required field.
-- Core checks permissions before executing any action.

-- ===== Capability System =====
--
-- Extensions declare capabilities in manifest.json:
--   {
--     "type": "slash_command",
--     "name": "/postman",
--     "description": "Run Postman API tests",
--     "config": { "entrypoint": "commands/postman.sh" }
--   }
--
-- Core registers capabilities from enabled extensions:
--   - Slash commands -> routed to extension command handler
--   - Tools -> exposed in tool picker
--   - Agents -> available in agent selector
--   - Workflows -> available in workflow library

-- ===== Installation Plans =====
--
-- Extensions include install/plan.yaml with declarative steps:
--   steps:
--     - action: check_dependency
--       command: node --version
--       required_version: ">=18.0.0"
--
--     - action: download_binary
--       url: https://example.com/tool.tar.gz
--       sha256: abc123...
--       target: bin/tool
--
--     - action: verify_installation
--       command: tool --version
--       expected_output: "Tool v1.0.0"
--
-- Core's Install Engine executes these steps sequentially.
-- Progress is tracked in extension_installs table.

-- ===== JSON Schema =====
--
-- capabilities field stores JSON array:
--   [
--     {
--       "type": "slash_command",
--       "name": "/postman",
--       "description": "Run Postman API tests"
--     },
--     {
--       "type": "tool",
--       "name": "postman_collection_runner",
--       "description": "Execute Postman collection"
--     }
--   ]
--
-- permissions_required field stores JSON array:
--   ["network", "exec", "filesystem.read"]
--
-- metadata field stores arbitrary JSON object:
--   {
--     "author": "Example Corp",
--     "license": "Apache-2.0",
--     "homepage": "https://example.com",
--     "tags": ["api-testing", "http"]
--   }

-- ============================================
-- Performance Considerations
-- ============================================

-- ===== Index Usage =====
--
-- idx_extensions_enabled:
--   - Query: Get all enabled extensions
--   - Covers: Runtime capability registration
--
-- idx_extensions_status:
--   - Query: Filter by installation status
--   - Covers: Admin UI, health checks
--
-- idx_extension_installs_extension_id:
--   - Query: Get install history for an extension
--   - Covers: Installation progress UI
--
-- idx_extension_installs_status:
--   - Query: Get all in-progress installations
--   - Covers: Background job monitoring
--
-- idx_extension_installs_started:
--   - Query: Get recent installations
--   - Covers: Audit log, activity feed

-- ===== Estimated Storage =====
--
-- Average extension record: ~2KB
-- Average install record: ~500 bytes
-- Average config record: ~1KB
--
-- 100 extensions: ~200KB
-- 1000 installations: ~500KB
-- Total: < 1MB (negligible)

-- ===== Concurrency =====
--
-- All writes use SQLiteWriter for serialization
-- Reads can be concurrent (SQLite read-write lock)
-- Foreign key constraints ensure referential integrity

-- ============================================
-- Completion
-- ============================================
--
-- v0.33 Migration Complete!
--
-- Changes Summary:
-- - Added extensions table (core extension registry)
-- - Added extension_installs table (installation tracking)
-- - Added extension_configs table (configuration storage)
-- - Added 5 performance indexes
-- - Added 4 validation triggers
-- - Supports capability-based plugin system
-- - Supports sandboxed installation plans
-- - Optimized for quick capability lookup
--
-- Next Steps:
-- 1. Implement ExtensionRegistry for CRUD operations
-- 2. Implement ZipInstaller for package installation
-- 3. Implement URLDownloader for remote packages
-- 4. Create API endpoints: POST /api/extensions/install, GET /api/extensions
-- 5. Build WebUI for extension management
-- 6. Implement capability routing (slash commands, tools, etc.)
--
-- Version: v0.33.0
-- Date: 2026-01-30
-- Author: Backend Agent (PR-A: Extension Infrastructure)
-- Reference: P2 Strategic Plan - Extension System
--
