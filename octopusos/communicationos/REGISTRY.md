# CommunicationOS - Channel Registry and Manifest System

## Overview

The Channel Registry and Manifest system provides a declarative, manifest-driven approach to integrating external communication channels (WhatsApp, Telegram, Slack, etc.) with AgentOS. This design enables adding new channels without modifying core code, while maintaining security and privacy standards.

## Architecture

### Core Components

1. **ChannelManifest** (`manifest.py`)
   - Declarative data model describing channel capabilities and requirements
   - Includes configuration fields, security defaults, setup steps, and capabilities
   - Drives UI generation and behavior without code changes

2. **ChannelRegistry** (`registry.py`)
   - Loads and manages channel manifests
   - Provides validation and querying capabilities
   - Supports dynamic reloading for hot-updates

3. **ChannelConfigStore** (`registry.py`)
   - SQLite-based persistent storage for channel configurations
   - Manages enable/disable state, health monitoring, and audit logs
   - Thread-safe operations with WAL mode

### Design Principles

- **Manifest-Driven**: New channels are added via JSON manifests, not code changes
- **Security-First**: Chat-only by default, execution requires explicit approval
- **Privacy-Respecting**: No auto-provisioning, local storage, encrypted secrets
- **Auditable**: Complete audit trail for all configuration changes

## Data Models

### ChannelManifest

```python
ChannelManifest(
    id="whatsapp_twilio",           # Unique identifier
    name="WhatsApp (Twilio)",       # Display name
    icon="whatsapp",                # Icon identifier
    description="...",              # Short description
    provider="Twilio",              # Provider name
    required_config_fields=[...],   # Configuration fields needed
    webhook_paths=[...],            # Webhook endpoints
    session_scope=SessionScope.USER,# Session management scope
    capabilities=[...],             # Channel capabilities
    security_defaults=SecurityDefaults(...),
    setup_steps=[...],              # Setup wizard steps
)
```

### ConfigField

```python
ConfigField(
    name="api_key",
    label="API Key",
    type="password",
    required=True,
    secret=True,
    validation_regex=r"^[A-Z0-9]{32}$",
    validation_error="Invalid format",
)
```

### SecurityDefaults

```python
SecurityDefaults(
    mode=SecurityMode.CHAT_ONLY,
    allow_execute=False,
    allowed_commands=["/session", "/help"],
    rate_limit_per_minute=20,
    retention_days=7,
    require_signature=True,
)
```

## Usage

### Loading Manifests

```python
from agentos.communicationos import ChannelRegistry

# Initialize registry (auto-loads manifests from channels/)
registry = ChannelRegistry()

# List all available channels
channels = registry.list_channels()

# Get specific manifest
manifest = registry.get_manifest("whatsapp_twilio")
```

### Managing Configurations

```python
from agentos.communicationos import ChannelConfigStore

# Initialize config store
config_store = ChannelConfigStore()

# Save channel configuration
config = {
    "api_key": "sk_live_...",
    "webhook_secret": "whsec_...",
}
config_store.save_config("whatsapp_twilio", config, performed_by="admin")

# Enable channel
config_store.set_enabled("whatsapp_twilio", True, performed_by="admin")

# Check status
status = config_store.get_status("whatsapp_twilio")
```

### Validating Configurations

```python
# Validate before saving
config = {"api_key": "test"}
valid, error = registry.validate_config("whatsapp_twilio", config)
if valid:
    config_store.save_config("whatsapp_twilio", config)
else:
    print(f"Invalid config: {error}")
```

### Event Logging and Monitoring

```python
# Log channel events
config_store.log_event(
    channel_id="whatsapp_twilio",
    event_type="message_received",
    status="success",
    message_id="msg_123",
    metadata={"user": "+1234567890"}
)

# Get recent events
events = config_store.get_recent_events("whatsapp_twilio", limit=10)

# Update heartbeat
config_store.update_heartbeat("whatsapp_twilio", status="enabled")
```

## Creating a New Channel

### 1. Create Manifest File

Create `channels/my_channel_manifest.json`:

```json
{
  "id": "my_channel",
  "name": "My Channel",
  "icon": "channel-icon",
  "description": "My custom channel",
  "version": "1.0.0",
  "provider": "Custom",
  "required_config_fields": [
    {
      "name": "api_key",
      "label": "API Key",
      "type": "password",
      "required": true,
      "secret": true
    }
  ],
  "webhook_paths": ["/api/channels/my_channel/webhook"],
  "session_scope": "user",
  "capabilities": ["inbound_text", "outbound_text"],
  "security_defaults": {
    "mode": "chat_only",
    "allow_execute": false
  }
}
```

### 2. Registry Auto-Loads

The registry automatically discovers and loads manifests from the `channels/` directory:

```python
registry = ChannelRegistry()  # Auto-loads my_channel_manifest.json
manifest = registry.get_manifest("my_channel")
```

### 3. Use in UI

The manifest drives UI generation:
- Configuration form fields are auto-generated
- Setup wizard steps are displayed
- Validation is enforced
- Privacy badges are shown

## Database Schema

### channel_configs

```sql
CREATE TABLE channel_configs (
    channel_id TEXT PRIMARY KEY,
    config_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'needs_setup',
    enabled INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    last_heartbeat_at INTEGER,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);
```

### channel_audit_log

```sql
CREATE TABLE channel_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id TEXT NOT NULL,
    action TEXT NOT NULL,
    details TEXT,
    performed_by TEXT,
    created_at INTEGER NOT NULL,
    FOREIGN KEY (channel_id) REFERENCES channel_configs(channel_id)
);
```

### channel_events

```sql
CREATE TABLE channel_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    message_id TEXT,
    status TEXT NOT NULL,
    error TEXT,
    metadata TEXT,
    created_at INTEGER NOT NULL,
    FOREIGN KEY (channel_id) REFERENCES channel_configs(channel_id)
);
```

## Enums and Types

### SessionScope
- `USER`: One session per user (channel_id + user_key)
- `USER_CONVERSATION`: One session per user-conversation pair

### ChannelCapability
- `INBOUND_TEXT`, `OUTBOUND_TEXT`: Text messaging
- `INBOUND_IMAGE`, `OUTBOUND_IMAGE`: Image attachments
- `INBOUND_AUDIO`, `OUTBOUND_AUDIO`: Audio messages
- `INBOUND_FILE`, `OUTBOUND_FILE`: File attachments
- `INTERACTIVE`: Interactive elements (buttons, menus)
- `THREADING`: Conversation threads/rooms
- `REACTIONS`: Message reactions
- `TYPING_INDICATOR`: Typing indicators

### SecurityMode
- `CHAT_ONLY`: Only allow chat operations (default, safest)
- `CHAT_EXEC_RESTRICTED`: Allow execution with admin token validation

### ChannelStatus
- `DISABLED`: Channel is disabled
- `ENABLED`: Channel is active
- `ERROR`: Channel has errors
- `NEEDS_SETUP`: Channel configuration incomplete

## Testing

Run the test suite:

```bash
python3 -m pytest tests/unit/communicationos/test_manifest.py -v
python3 -m pytest tests/unit/communicationos/test_registry.py -v
```

Test coverage includes:
- ✅ Manifest data model creation and serialization
- ✅ Config field validation (regex, required fields)
- ✅ Registry loading and querying
- ✅ Config store CRUD operations
- ✅ Enable/disable state management
- ✅ Event logging and retrieval
- ✅ Audit trail verification
- ✅ Integration tests for full lifecycle

## Security Considerations

1. **Secret Storage**: Fields marked with `secret=True` should be encrypted at rest
2. **Webhook Signature**: `require_signature=True` enforces webhook validation
3. **Rate Limiting**: Default 20 messages/minute, configurable per channel
4. **Audit Trail**: All configuration changes are logged with performer
5. **Chat-Only Default**: Execution disabled by default for all channels
6. **Privacy Badges**: Displayed to users showing security guarantees

## Example Manifest

See `/agentos/communicationos/channels/whatsapp_twilio_manifest.json` for a complete, production-ready channel manifest example.
