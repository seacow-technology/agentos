-- Schema v54: NetworkOS - Tunnel and Network Management
-- AgentOS NetworkOS Component: 统一网络隧道管理
--
-- Design Philosophy:
-- - Unified tunnel management across providers (Cloudflare, ngrok, tailscale)
-- - Health monitoring and diagnostics
-- - Audit trail for all network operations
-- - Support both HTTP and TCP tunnels
--
-- Provider Support:
-- - cloudflare: Cloudflare Tunnel (primary)
-- - ngrok: ngrok tunnels (future)
-- - tailscale: Tailscale networks (future)
-- - self_hosted: Custom tunnel solutions (future)

-- ===================================================================
-- 1. Network Tunnels Table
-- ===================================================================

-- Stores tunnel configuration and runtime state
CREATE TABLE IF NOT EXISTS network_tunnels (
    tunnel_id TEXT PRIMARY KEY,                  -- Unique tunnel identifier
    provider TEXT NOT NULL,                      -- cloudflare, ngrok, tailscale, self_hosted
    name TEXT NOT NULL,                          -- Tunnel name (must be unique per provider)
    is_enabled INTEGER NOT NULL DEFAULT 0,       -- 0=disabled, 1=enabled
    public_hostname TEXT NOT NULL,               -- Public URL (e.g., myapp.trycloudflare.com)
    local_target TEXT NOT NULL,                  -- Local endpoint (e.g., localhost:8080)
    mode TEXT NOT NULL DEFAULT 'http',           -- http, https, tcp
    health_status TEXT NOT NULL DEFAULT 'unknown', -- up, down, degraded, unknown
    last_heartbeat_at INTEGER NULL,              -- Last successful health check (epoch_ms)
    last_error_code TEXT NULL,                   -- Last error code (if any)
    last_error_message TEXT NULL,                -- Last error message (if any)
    created_at INTEGER NOT NULL,                 -- Tunnel creation time (epoch_ms)
    updated_at INTEGER NOT NULL,                 -- Last update time (epoch_ms)

    CHECK (provider IN ('cloudflare', 'ngrok', 'tailscale', 'self_hosted')),
    CHECK (mode IN ('http', 'https', 'tcp')),
    CHECK (health_status IN ('up', 'down', 'degraded', 'unknown')),
    CHECK (is_enabled IN (0, 1)),
    UNIQUE(provider, name)                       -- Each provider can have unique tunnel names
);

-- Index for enabled tunnels
CREATE INDEX IF NOT EXISTS idx_network_tunnels_enabled
    ON network_tunnels(is_enabled)
    WHERE is_enabled = 1;

-- Index for health status queries
CREATE INDEX IF NOT EXISTS idx_network_tunnels_health
    ON network_tunnels(health_status);

-- Index for recent updates
CREATE INDEX IF NOT EXISTS idx_network_tunnels_updated
    ON network_tunnels(updated_at DESC);

-- Index for provider lookups
CREATE INDEX IF NOT EXISTS idx_network_tunnels_provider
    ON network_tunnels(provider, is_enabled);

-- ===================================================================
-- 2. Network Routes Table
-- ===================================================================

-- Optional: Advanced routing configuration for path-based routing
-- Allows multiple local targets behind a single tunnel
CREATE TABLE IF NOT EXISTS network_routes (
    route_id TEXT PRIMARY KEY,                   -- Unique route identifier
    tunnel_id TEXT NOT NULL,                     -- Parent tunnel ID
    path_prefix TEXT NOT NULL,                   -- Path prefix to match (e.g., /api)
    local_target TEXT NOT NULL,                  -- Local endpoint for this path
    is_enabled INTEGER NOT NULL DEFAULT 1,       -- 0=disabled, 1=enabled
    priority INTEGER NOT NULL DEFAULT 0,         -- Route priority (higher = match first)
    created_at INTEGER NOT NULL,                 -- Route creation time (epoch_ms)
    updated_at INTEGER NOT NULL,                 -- Last update time (epoch_ms)

    CHECK (is_enabled IN (0, 1)),
    FOREIGN KEY (tunnel_id) REFERENCES network_tunnels(tunnel_id) ON DELETE CASCADE,
    UNIQUE(tunnel_id, path_prefix)               -- Each path prefix is unique per tunnel
);

-- Index for tunnel route lookups
CREATE INDEX IF NOT EXISTS idx_network_routes_tunnel
    ON network_routes(tunnel_id, priority DESC);

-- Index for enabled routes
CREATE INDEX IF NOT EXISTS idx_network_routes_enabled
    ON network_routes(is_enabled)
    WHERE is_enabled = 1;

-- ===================================================================
-- 3. Network Events Table
-- ===================================================================

-- Audit trail and diagnostics for all network operations
CREATE TABLE IF NOT EXISTS network_events (
    event_id TEXT PRIMARY KEY,                   -- Unique event identifier
    tunnel_id TEXT NULL,                         -- Related tunnel (if any)
    level TEXT NOT NULL,                         -- info, warn, error
    event_type TEXT NOT NULL,                    -- Event type (see below)
    message TEXT NOT NULL,                       -- Human-readable message
    data_json TEXT NULL,                         -- Structured event data (JSON, no secrets!)
    created_at INTEGER NOT NULL,                 -- Event timestamp (epoch_ms)

    CHECK (level IN ('info', 'warn', 'error')),
    FOREIGN KEY (tunnel_id) REFERENCES network_tunnels(tunnel_id) ON DELETE SET NULL
);

-- Event types:
-- - tunnel_start: Tunnel started successfully
-- - tunnel_stop: Tunnel stopped (graceful)
-- - tunnel_crash: Tunnel crashed unexpectedly
-- - health_up: Health check succeeded (degraded → up transition)
-- - health_down: Health check failed (up → down transition)
-- - health_degraded: Health check degraded (up → degraded transition)
-- - config_changed: Tunnel configuration updated
-- - route_added: Route added to tunnel
-- - route_removed: Route removed from tunnel
-- - cloudflared_exit: cloudflared process exited
-- - connection_error: Connection error occurred

-- Index for tunnel event history
CREATE INDEX IF NOT EXISTS idx_network_events_tunnel_time
    ON network_events(tunnel_id, created_at DESC)
    WHERE tunnel_id IS NOT NULL;

-- Index for event type queries
CREATE INDEX IF NOT EXISTS idx_network_events_type_time
    ON network_events(event_type, created_at DESC);

-- Index for error tracking
CREATE INDEX IF NOT EXISTS idx_network_events_level_time
    ON network_events(level, created_at DESC)
    WHERE level IN ('warn', 'error');

-- Index for recent events
CREATE INDEX IF NOT EXISTS idx_network_events_recent
    ON network_events(created_at DESC);

-- ===================================================================
-- 4. Views for Convenience
-- ===================================================================

-- Active tunnels with health status
CREATE VIEW IF NOT EXISTS v_active_tunnels AS
SELECT
    t.tunnel_id,
    t.provider,
    t.name,
    t.public_hostname,
    t.local_target,
    t.mode,
    t.health_status,
    t.last_heartbeat_at,
    CASE
        WHEN t.last_heartbeat_at IS NULL THEN NULL
        ELSE (strftime('%s', 'now') * 1000 - t.last_heartbeat_at) / 1000.0
    END as seconds_since_heartbeat,
    t.last_error_code,
    t.last_error_message,
    t.created_at,
    t.updated_at,
    (SELECT COUNT(*) FROM network_routes r WHERE r.tunnel_id = t.tunnel_id AND r.is_enabled = 1) as active_routes
FROM network_tunnels t
WHERE t.is_enabled = 1
ORDER BY t.updated_at DESC;

-- Tunnel health summary
CREATE VIEW IF NOT EXISTS v_tunnel_health_summary AS
SELECT
    health_status,
    COUNT(*) as tunnel_count,
    GROUP_CONCAT(tunnel_id, ', ') as tunnel_ids
FROM network_tunnels
WHERE is_enabled = 1
GROUP BY health_status
ORDER BY
    CASE health_status
        WHEN 'down' THEN 1
        WHEN 'degraded' THEN 2
        WHEN 'unknown' THEN 3
        WHEN 'up' THEN 4
    END;

-- Recent network events
CREATE VIEW IF NOT EXISTS v_recent_network_events AS
SELECT
    e.event_id,
    e.tunnel_id,
    t.name as tunnel_name,
    t.provider,
    e.level,
    e.event_type,
    e.message,
    e.created_at,
    (strftime('%s', 'now') * 1000 - e.created_at) / 1000.0 as age_seconds
FROM network_events e
LEFT JOIN network_tunnels t ON e.tunnel_id = t.tunnel_id
ORDER BY e.created_at DESC
LIMIT 100;

-- Tunnel error summary (last 24 hours)
CREATE VIEW IF NOT EXISTS v_tunnel_errors_24h AS
SELECT
    t.tunnel_id,
    t.provider,
    t.name,
    COUNT(*) as error_count,
    GROUP_CONCAT(DISTINCT e.event_type, ', ') as error_types,
    MAX(e.created_at) as last_error_at
FROM network_tunnels t
JOIN network_events e ON t.tunnel_id = e.tunnel_id
WHERE e.level IN ('warn', 'error')
  AND e.created_at > (strftime('%s', 'now') * 1000 - 86400000)  -- Last 24 hours
GROUP BY t.tunnel_id, t.provider, t.name
ORDER BY error_count DESC;

-- ===================================================================
-- 5. Tunnel Secrets Table
-- ===================================================================

-- Stores tunnel authentication tokens and secret references
-- Note: v55 migration will add secret_ref support for encrypted storage
CREATE TABLE IF NOT EXISTS tunnel_secrets (
    tunnel_id TEXT PRIMARY KEY,                  -- Reference to network_tunnels
    token TEXT,                                  -- Tunnel authentication token (plaintext, deprecated in v55)
    created_at INTEGER NOT NULL,                 -- Secret creation time (epoch_ms)
    updated_at INTEGER NOT NULL,                 -- Last update time (epoch_ms)

    FOREIGN KEY (tunnel_id) REFERENCES network_tunnels(tunnel_id) ON DELETE CASCADE
);

-- Index for tunnel secret lookups
CREATE INDEX IF NOT EXISTS idx_tunnel_secrets_tunnel
    ON tunnel_secrets(tunnel_id);

-- ===================================================================
-- 6. Sample Data (for testing/development)
-- ===================================================================

-- Sample tunnel: Cloudflare Tunnel for web UI
INSERT OR IGNORE INTO network_tunnels (
    tunnel_id, provider, name, is_enabled, public_hostname,
    local_target, mode, health_status, created_at, updated_at
)
VALUES (
    'tunnel-cf-webui',
    'cloudflare',
    'agentos-webui',
    0,  -- Disabled by default
    'agentos-webui.trycloudflare.com',
    'localhost:8080',
    'http',
    'unknown',
    strftime('%s', 'now') * 1000,
    strftime('%s', 'now') * 1000
);

-- Sample tunnel: Cloudflare Tunnel for API
INSERT OR IGNORE INTO network_tunnels (
    tunnel_id, provider, name, is_enabled, public_hostname,
    local_target, mode, health_status, created_at, updated_at
)
VALUES (
    'tunnel-cf-api',
    'cloudflare',
    'agentos-api',
    0,  -- Disabled by default
    'agentos-api.trycloudflare.com',
    'localhost:8000',
    'http',
    'unknown',
    strftime('%s', 'now') * 1000,
    strftime('%s', 'now') * 1000
);

-- Sample route: API v1
INSERT OR IGNORE INTO network_routes (
    route_id, tunnel_id, path_prefix, local_target,
    is_enabled, priority, created_at, updated_at
)
VALUES (
    'route-api-v1',
    'tunnel-cf-api',
    '/api/v1',
    'localhost:8000',
    1,
    100,
    strftime('%s', 'now') * 1000,
    strftime('%s', 'now') * 1000
);

-- Sample event: Tunnel created
INSERT OR IGNORE INTO network_events (
    event_id, tunnel_id, level, event_type, message, created_at
)
VALUES (
    'event-' || hex(randomblob(8)),
    'tunnel-cf-webui',
    'info',
    'config_changed',
    'Tunnel configuration created',
    strftime('%s', 'now') * 1000
);

-- ===================================================================
-- 7. Migration Verification
-- ===================================================================

-- Verify tables exist
SELECT 'Schema v54 tables created:' as status;
SELECT name FROM sqlite_master
WHERE type='table'
AND name IN (
    'network_tunnels',
    'network_routes',
    'network_events',
    'tunnel_secrets'
)
ORDER BY name;

-- Verify views exist
SELECT 'Schema v54 views created:' as status;
SELECT name FROM sqlite_master
WHERE type='view'
AND name LIKE 'v_%tunnel%' OR name LIKE 'v_%network%'
ORDER BY name;

-- Verify indexes exist
SELECT 'Schema v54 indexes created:' as status;
SELECT name FROM sqlite_master
WHERE type='index'
AND name LIKE 'idx_network_%'
ORDER BY name;

-- Verify sample data
SELECT 'Sample tunnels loaded:' as status;
SELECT tunnel_id, provider, name, is_enabled FROM network_tunnels;

SELECT 'Sample routes loaded:' as status;
SELECT route_id, tunnel_id, path_prefix FROM network_routes;

SELECT 'Sample events loaded:' as status;
SELECT event_id, tunnel_id, event_type FROM network_events LIMIT 5;

-- Show active tunnel summary
SELECT 'Active tunnels:' as status;
SELECT * FROM v_active_tunnels;

-- Show health summary
SELECT 'Health summary:' as status;
SELECT * FROM v_tunnel_health_summary;

-- ===================================================================
-- Performance Notes:
-- - network_tunnels: Primary key on tunnel_id for O(1) lookups
-- - network_routes: Indexed by (tunnel_id, priority DESC) for fast routing
-- - network_events: Indexed by (tunnel_id, created_at DESC) for event queries
-- - Views use indexes for efficient aggregation
-- - Expected performance: Tunnel lookup < 1ms, Event query < 10ms
-- ===================================================================

-- ===================================================================
-- Design Rationale:
-- - Single component database (follows AgentOS storage pattern)
-- - All timestamps in epoch milliseconds (v44 contract)
-- - Health status tracks tunnel availability
-- - Events provide audit trail without sensitive data
-- - Routes enable advanced path-based routing (optional)
-- - Provider-agnostic design (easy to add new tunnel types)
-- - Unique constraint on (provider, name) prevents duplicates
-- ===================================================================
