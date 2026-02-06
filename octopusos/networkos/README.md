# NetworkOS - Tunnel Management

## What is NetworkOS?

NetworkOS is AgentOS's network control plane, managing public tunnels (Cloudflare Tunnel/ngrok/Tailscale) to make local services publicly accessible.

**Core Value:**
- No public IP needed
- No port forwarding required
- Automatic HTTPS configuration
- Health monitoring and event auditing

## Quick Start (5 minutes)

### 1. Install cloudflared

```bash
# macOS
brew install cloudflared

# Linux
wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
chmod +x cloudflared-linux-amd64
sudo mv cloudflared-linux-amd64 /usr/local/bin/cloudflared
```

### 2. Get Cloudflare Tunnel Token

1. Login to https://dash.cloudflare.com
2. Go to Zero Trust → Networks → Tunnels
3. Click "Create a Tunnel"
4. Copy the Token (format: eyJhIjoi...)

### 3. Create and Start Tunnel

```bash
# Create tunnel configuration
agentos networkos create \
  --name my-app \
  --hostname my-app.example.com \
  --target http://127.0.0.1:8000 \
  --token YOUR_CLOUDFLARE_TOKEN

# Start tunnel
agentos networkos start TUNNEL_ID

# View status
agentos networkos list
agentos networkos status TUNNEL_ID
```

### 4. Verify

Visit https://my-app.example.com - should access your local port 8000 service.

## CLI Command Reference

| Command | Description |
|---------|-------------|
| `create` | Create tunnel configuration |
| `start` | Start tunnel process |
| `stop` | Stop tunnel process |
| `list` | List all tunnels |
| `status` | View detailed tunnel status |
| `logs` | View tunnel event logs |
| `delete` | Delete tunnel configuration |

## Health Check

NetworkOS includes a comprehensive health check system to diagnose database and configuration issues.

### Run Health Check

```bash
# Via doctor command (recommended)
agentos doctor

# Output includes NetworkOS status:
# ✅ networkos - NetworkOS database healthy
# ⚠️ networkos - NetworkOS database not initialized
# ❌ networkos - NetworkOS database health check failed
```

### What is Checked

1. **DB Accessibility**: Database file exists and can be opened
2. **DB Writable**: Database accepts write operations
3. **Schema Version**: Schema is v54 or newer
4. **Required Tables**: All core tables exist (network_tunnels, network_events, network_routes, tunnel_secrets)
5. **WAL Mode**: SQLite WAL mode is enabled for better concurrency

### Via API

```bash
curl http://localhost:8000/api/health
```

Response includes NetworkOS status:
```json
{
  "components": {
    "networkos": {
      "status": "ok",
      "all_passed": true,
      "passed_count": 6,
      "failed_count": 0,
      "message": "NetworkOS health: ok"
    }
  }
}
```

### Common Issues and Fixes

**Issue**: Database not found
```
Fix: Run migration or initialize NetworkOS
$ agentos migrate
```

**Issue**: Schema version too old
```
Fix: Run migration to v54
$ agentos migrate
```

**Issue**: Missing required tables
```
Fix: Run schema migration v54 to create NetworkOS tables
$ agentos migrate
```

**Issue**: WAL mode not enabled
```
Fix: Enable WAL mode
$ sqlite3 ~/.agentos/store/networkos/db.sqlite 'PRAGMA journal_mode=WAL;'
```

**Issue**: Database is read-only
```
Fix: Check file permissions
$ chmod 644 ~/.agentos/store/networkos/db.sqlite
```

## Troubleshooting

### Q: Token error: "Invalid credentials"
**A**: Check if Token is completely copied (should be long, starting with eyJ)

### Q: cloudflared not found
**A**: Run `brew install cloudflared` or follow Linux installation steps above

### Q: Hostname not resolving
**A**: Add DNS record in Cloudflare Dashboard, pointing to the tunnel

### Q: Tunnel exits immediately after starting
**A**: Run `agentos networkos logs TUNNEL_ID` to see error details

### Q: How do I verify NetworkOS is working?
**A**: Run `agentos doctor` - the networkos check should show ✅ or ⚠️ (warning is OK if DB not yet initialized)

## Security Recommendations

- ✅ Store tokens in encrypted storage (don't commit to Git)
- ✅ Only expose necessary ports/paths
- ✅ Regularly check `agentos networkos list` to confirm running status
- ✅ Use `agentos doctor` to verify health

## Advanced Features

- Path routing: Multiple paths per tunnel
- Health monitoring: Automatic tunnel status detection
- Event auditing: Complete log tracking

---

## Developer Documentation

### Architecture

#### Components

```
networkos/
├── __init__.py          # Package exports
├── store.py             # Data persistence layer (SQLite)
└── README.md           # This file
```

#### Database Schema (v54)

NetworkOS uses three main tables in the AgentOS database:

1. **network_tunnels**: Tunnel configuration and runtime state
2. **network_routes**: Optional path-based routing rules
3. **network_events**: Audit trail and diagnostic events

Schema migration: `agentos/store/migrations/schema_v54_networkos.sql`

### Programmatic Usage

#### Basic Usage

```python
from agentos.networkos import NetworkOSStore, Tunnel
from agentos.core.time import utc_now_ms

# Initialize store
store = NetworkOSStore()

# Create tunnel
now = utc_now_ms()
tunnel = Tunnel(
    tunnel_id="tunnel-cf-1",
    provider="cloudflare",
    name="my-app",
    is_enabled=True,
    public_hostname="my-app.trycloudflare.com",
    local_target="localhost:8080",
    mode="http",
    health_status="unknown",
    last_heartbeat_at=None,
    last_error_code=None,
    last_error_message=None,
    created_at=now,
    updated_at=now
)
store.create_tunnel(tunnel)

# Update health status
store.update_health(
    tunnel_id="tunnel-cf-1",
    health_status="up",
    error_code=None,
    error_message=None
)

# List all tunnels
tunnels = store.list_tunnels(enabled_only=True)
for tunnel in tunnels:
    print(f"{tunnel.name}: {tunnel.health_status}")

# Enable/disable tunnel
store.set_enabled("tunnel-cf-1", False)

# Log events
event = {
    'event_id': "event-123",
    'tunnel_id': "tunnel-cf-1",
    'level': "info",
    'event_type': "tunnel_start",
    'message': "Tunnel started successfully",
    'data_json': None,
    'created_at': utc_now_ms()
}
store.append_event(event)

# Get recent events
events = store.get_recent_events("tunnel-cf-1", limit=50)
```

#### Tunnel Configuration

```python
# Tunnel modes
mode = "http"   # HTTP tunnel (default)
mode = "https"  # HTTPS tunnel
mode = "tcp"    # TCP tunnel

# Health status
health_status = "unknown"   # Not yet checked
health_status = "up"        # Tunnel is operational
health_status = "down"      # Tunnel is down
health_status = "degraded"  # Tunnel has issues
```

#### Secret Management

```python
# Save tunnel token
store.save_token("tunnel-cf-1", "cloudflare-token-abc123")

# Retrieve token
token = store.get_token("tunnel-cf-1")
```

## Database Schema Details

### network_tunnels

| Column | Type | Description |
|--------|------|-------------|
| tunnel_id | TEXT PK | Unique tunnel identifier |
| provider | TEXT | Provider name (cloudflare, ngrok, etc.) |
| name | TEXT | Tunnel name (unique per provider) |
| is_enabled | INTEGER | 0=disabled, 1=enabled |
| public_hostname | TEXT | Public URL |
| local_target | TEXT | Local endpoint (e.g., localhost:8080) |
| mode | TEXT | http, https, or tcp |
| health_status | TEXT | up, down, degraded, or unknown |
| last_heartbeat_at | INTEGER | Last health check timestamp (epoch_ms) |
| last_error_code | TEXT | Last error code |
| last_error_message | TEXT | Last error message |
| created_at | INTEGER | Creation timestamp (epoch_ms) |
| updated_at | INTEGER | Last update timestamp (epoch_ms) |

**Constraints:**
- `UNIQUE(provider, name)`: Each provider can have unique tunnel names
- `CHECK` constraints on provider, mode, health_status, is_enabled

### network_routes (Optional)

| Column | Type | Description |
|--------|------|-------------|
| route_id | TEXT PK | Unique route identifier |
| tunnel_id | TEXT FK | Parent tunnel ID |
| path_prefix | TEXT | Path prefix to match (e.g., /api) |
| local_target | TEXT | Local endpoint for this path |
| is_enabled | INTEGER | 0=disabled, 1=enabled |
| priority | INTEGER | Route priority (higher = match first) |
| created_at | INTEGER | Creation timestamp (epoch_ms) |
| updated_at | INTEGER | Last update timestamp (epoch_ms) |

**Constraints:**
- `FOREIGN KEY (tunnel_id)` with CASCADE DELETE
- `UNIQUE(tunnel_id, path_prefix)`

### network_events

| Column | Type | Description |
|--------|------|-------------|
| event_id | TEXT PK | Unique event identifier |
| tunnel_id | TEXT FK | Related tunnel (nullable) |
| level | TEXT | info, warn, or error |
| event_type | TEXT | Event type identifier |
| message | TEXT | Human-readable message |
| data_json | TEXT | Structured event data (JSON) |
| created_at | INTEGER | Event timestamp (epoch_ms) |

**Event Types:**
- `tunnel_start`: Tunnel started successfully
- `tunnel_stop`: Tunnel stopped gracefully
- `tunnel_crash`: Tunnel crashed unexpectedly
- `health_up`: Health transitioned to up
- `health_down`: Health transitioned to down
- `health_degraded`: Health transitioned to degraded
- `config_changed`: Configuration updated
- `route_added`: Route added
- `route_removed`: Route removed
- `cloudflared_exit`: cloudflared process exited
- `connection_error`: Connection error occurred

## Time Contract

NetworkOS follows the AgentOS Time & Timestamp Contract (ADR-011):

- All timestamps are stored as **epoch milliseconds** (13-digit integers)
- Uses `agentos.core.time.utc_now_ms()` for timestamp generation
- No timezone-aware datetimes in database (UTC epoch_ms only)
- Frontend/API converts epoch_ms to ISO 8601 with 'Z' suffix

## Integration with AgentOS

### Storage Path

NetworkOS uses the component-based storage pattern:

```python
from agentos.core.storage.paths import ensure_db_exists

db_path = ensure_db_exists("networkos")
# Result: ~/.agentos/store/networkos/db.sqlite
```

### Migration System

The schema is automatically applied via the migration system:

```bash
# Check migration status
python -c "from agentos.store.migrator import get_migration_status; \
           from agentos.core.storage.paths import component_db_path; \
           print(get_migration_status(component_db_path('agentos')))"
```

## Testing

Run tests with pytest:

```bash
# Run all NetworkOS tests
pytest tests/unit/networkos/ -v

# Run specific test class
pytest tests/unit/networkos/test_store.py::TestNetworkOSStore -v

# Run with coverage
pytest tests/unit/networkos/ --cov=agentos.networkos --cov-report=term-missing
```

## Future Enhancements

1. **Additional Providers**:
   - ngrok integration
   - Tailscale network management
   - Self-hosted tunnel support

2. **Advanced Features**:
   - Automatic failover between tunnels
   - Load balancing across multiple tunnels
   - Traffic metrics and analytics
   - Tunnel performance monitoring

3. **Security**:
   - Encrypted token storage
   - Token rotation
   - Access control lists

4. **UI Integration**:
   - WebUI dashboard for tunnel management
   - Real-time health monitoring
   - Event log viewer

## Contributing

When contributing to NetworkOS:

1. Follow the AgentOS Time Contract (epoch_ms for all timestamps)
2. Add tests for new functionality
3. Update migration schema if changing database structure
4. Document new event types in this README
5. Follow the existing code style and patterns

## References

- Migration: `agentos/store/migrations/schema_v54_networkos.sql`
- Time Contract: `docs/adr/ADR-011-time-timestamp-contract.md`
- Storage Pattern: `agentos/core/storage/paths.py`
- Tests: `tests/unit/networkos/test_store.py`
