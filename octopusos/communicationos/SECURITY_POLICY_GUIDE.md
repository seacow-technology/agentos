# CommunicationOS Security Policy Guide

## Overview

CommunicationOS implements comprehensive security policies and permission controls to ensure safe operation of communication channels, especially when exposed remotely. The security system follows a "secure by default" philosophy with multiple layers of defense.

## Architecture

### Security Components

1. **SecurityPolicy**: Defines what operations are allowed for a channel
2. **PolicyEnforcer**: Middleware that enforces policies on messages
3. **Command Whitelist**: Restricts which commands can be executed
4. **RemoteExposureDetector**: Detects and warns about remote exposure
5. **AdminTokenValidator**: Validates admin tokens for elevated operations

### Security Layers

```
┌─────────────────────────────────────────────┐
│         External Channel (WhatsApp)         │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│          Channel Adapter                    │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│     MessageBus Middleware Chain             │
│  1. Deduplication                           │
│  2. Rate Limiting                           │
│  3. Security Policy Enforcement ◄──────────│ Core Security Layer
│  4. Audit Logging                           │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│      Business Logic / Chat Service          │
└─────────────────────────────────────────────┘
```

## Security Modes

### CHAT_ONLY (Default, Most Secure)

**Characteristics:**
- Only chat/messaging operations allowed
- Execute operations denied by default
- Suitable for production remote deployments
- No risk of remote code execution

**Use Cases:**
- Public-facing channels (WhatsApp, Telegram)
- Multi-tenant environments
- Untrusted user access
- Compliance-sensitive deployments

**Configuration:**
```python
from agentos.communicationos import SecurityPolicy, SecurityMode

policy = SecurityPolicy(
    mode=SecurityMode.CHAT_ONLY,
    chat_only=True,
    allow_execute=False,
    allowed_commands=["/session", "/help"],
    rate_limit_per_minute=20,
    block_on_violation=True,
)
```

### CHAT_EXEC_RESTRICTED (Elevated Permissions)

**Characteristics:**
- Chat operations always allowed
- Execute operations can be enabled
- Requires command whitelisting
- Should require admin token validation
- Suitable for trusted environments only

**Use Cases:**
- Local development
- Trusted internal channels
- Admin-only channels
- Controlled remote access with VPN

**Configuration:**
```python
from agentos.communicationos import SecurityPolicy, SecurityMode, generate_admin_token

# Generate admin token
admin_token, token_hash = generate_admin_token()
print(f"Save this token securely: {admin_token}")

policy = SecurityPolicy(
    mode=SecurityMode.CHAT_EXEC_RESTRICTED,
    chat_only=False,
    allow_execute=True,
    allowed_commands=["/session", "/help", "/execute", "/run"],
    require_admin_token=True,
    admin_token_hash=token_hash,
    rate_limit_per_minute=60,
    block_on_violation=True,
)
```

## Operation Types

### CHAT (Always Allowed)
- Send and receive text messages
- Send and receive images/files
- Session management commands
- Help commands

### EXECUTE (Restricted)
- Execute system commands
- Run scripts
- Access file system
- Requires explicit permission and whitelisting

### FILE_ACCESS (Future)
- Read local files
- Write local files
- Will require explicit permission

### SYSTEM_INFO (Future)
- Query system information
- Check system status
- Will require explicit permission

### CONFIG_CHANGE (Future)
- Modify system configuration
- Change security policies
- Will require admin token

## Command Whitelisting

### Default Whitelist
```python
["/session", "/help"]
```

### Custom Whitelist
```python
policy = SecurityPolicy(
    allowed_commands=[
        "/session",      # Session management
        "/help",         # Help command
        "/status",       # Status queries
        "/info",         # Information commands
    ]
)
```

### Prefix Matching
Commands are matched by prefix, so:
- `/session` in whitelist allows `/session new`, `/session id`, etc.
- `/execute` in whitelist allows `/execute script.sh`, etc.

### Case Insensitivity
Command matching is case-insensitive:
- `/Session`, `/SESSION`, `/session` all match

## Policy Enforcement

### Enforcement Flow

1. **Message Reception**: Inbound message arrives from channel
2. **Policy Lookup**: Get security policy for channel (or use default)
3. **Command Detection**: Check if message contains a command
4. **Whitelist Check**: Verify command is whitelisted
5. **Operation Check**: Verify operation type is allowed
6. **Admin Token Validation**: If required, validate admin token
7. **Decision**: Allow (CONTINUE) or Block (REJECT)
8. **Violation Logging**: Log any security violations

### Integration with MessageBus

```python
from agentos.communicationos import (
    MessageBus,
    SecurityPolicy,
    PolicyEnforcer,
    DedupeMiddleware,
    RateLimitMiddleware,
    AuditMiddleware,
)

# Create message bus
bus = MessageBus()

# Add middleware in order
bus.add_middleware(DedupeMiddleware(dedupe_store))
bus.add_middleware(RateLimitMiddleware(rate_limiter))

# Security enforcement (critical layer)
security_policy = SecurityPolicy.default_policy()
bus.add_middleware(PolicyEnforcer(default_policy=security_policy))

bus.add_middleware(AuditMiddleware(audit_store))

# Register channel adapters
bus.register_adapter("whatsapp_001", whatsapp_adapter)
```

### Channel-Specific Policies

```python
# Create enforcer
enforcer = PolicyEnforcer(default_policy=SecurityPolicy.default_policy())

# Set different policy for internal channel
internal_policy = SecurityPolicy(
    mode=SecurityMode.CHAT_EXEC_RESTRICTED,
    allow_execute=True,
    allowed_commands=["/session", "/help", "/execute"],
)
enforcer.set_channel_policy("internal_slack", internal_policy)

# Set different policy for public channel (more restrictive)
public_policy = SecurityPolicy(
    mode=SecurityMode.CHAT_ONLY,
    chat_only=True,
    allowed_commands=["/session", "/help"],
    rate_limit_per_minute=10,  # Lower rate limit
)
enforcer.set_channel_policy("public_telegram", public_policy)
```

## Security Violations

### Violation Types

1. **OPERATION_DENIED**: Operation not allowed by policy
2. **COMMAND_NOT_WHITELISTED**: Command not in whitelist
3. **RATE_LIMIT_EXCEEDED**: Too many requests
4. **INVALID_TOKEN**: Invalid or missing admin token
5. **REMOTE_EXPOSURE_WARNING**: Remote exposure detected

### Violation Logging

All violations are:
1. Logged to in-memory list (last 1000)
2. Logged to audit store (if available)
3. Logged to application logger (always)
4. Included in message processing context

### Querying Violations

```python
# Get all recent violations
violations = enforcer.get_violations(limit=100)

# Get violations for specific channel
channel_violations = enforcer.get_violations(
    channel_id="whatsapp_001",
    limit=50
)

# Get security statistics
stats = enforcer.get_stats()
print(f"Total violations: {stats['total_violations']}")
print(f"Blocked: {stats['blocked_count']}")
print(f"By type: {stats['by_type']}")
print(f"By channel: {stats['by_channel']}")
```

## Remote Exposure Detection

### Detection Mechanism

The system automatically detects if it's likely exposed remotely by checking:

1. **Environment Variables**:
   - `AGENTOS_REMOTE_MODE=true`
   - `RAILWAY_ENVIRONMENT`
   - `HEROKU_APP_NAME`
   - `VERCEL`
   - `AWS_EXECUTION_ENV`
   - `KUBERNETES_SERVICE_HOST`

2. **Network Configuration** (future):
   - Public IP binding
   - External webhook URLs

### Warnings

When remote exposure is detected:
1. Warning logged on system startup
2. Enhanced security checks enabled
3. Recommendations provided

### Manual Override

```python
# Explicitly enable remote warnings
enforcer = PolicyEnforcer(
    default_policy=policy,
    enable_remote_warnings=True
)

# Check if remote exposed
from agentos.communicationos.security import RemoteExposureDetector

if RemoteExposureDetector.is_remote_exposed():
    print(RemoteExposureDetector.get_exposure_warning())
```

## Admin Token Management

### Generating Tokens

```python
from agentos.communicationos.security import generate_admin_token

# Generate new token
token, token_hash = generate_admin_token()

print(f"Admin Token (save securely): {token}")
print(f"Token Hash (store in config): {token_hash}")

# Store token_hash in policy
policy = SecurityPolicy(
    require_admin_token=True,
    admin_token_hash=token_hash,
)
```

### Token Storage Best Practices

**DO:**
- Store token in password manager
- Use environment variables for token
- Rotate tokens periodically
- Store hash in configuration

**DON'T:**
- Commit tokens to git
- Share tokens in plain text
- Log tokens
- Reuse tokens across systems

### Token Validation

```python
# In message metadata
message_metadata = {
    "admin_token": "<user-provided-token>"
}

# Validation happens automatically in PolicyEnforcer
is_valid = policy.validate_admin_token(message_metadata.get("admin_token"))
```

## Manifest Integration

### Security Defaults in Manifest

```json
{
  "id": "whatsapp_twilio",
  "name": "WhatsApp (Twilio)",
  "security_defaults": {
    "mode": "chat_only",
    "allow_execute": false,
    "allowed_commands": ["/session", "/help"],
    "rate_limit_per_minute": 20,
    "retention_days": 7,
    "require_signature": true
  }
}
```

### Loading from Manifest

```python
from agentos.communicationos import SecurityPolicy

# Load from manifest
manifest = registry.get_manifest("whatsapp_twilio")
policy = SecurityPolicy.from_manifest_defaults(
    manifest.security_defaults.to_dict()
)
```

## Best Practices

### For Production Deployments

1. **Always use CHAT_ONLY mode** for public-facing channels
2. **Enable remote exposure warnings**
3. **Set conservative rate limits** (10-20 req/min)
4. **Monitor violation logs** regularly
5. **Use webhook signature validation**
6. **Deploy behind VPN or IP whitelist** if possible
7. **Rotate admin tokens** quarterly

### For Development

1. **Use CHAT_EXEC_RESTRICTED** with caution
2. **Test security policies** before deployment
3. **Document policy decisions**
4. **Review audit logs** after testing
5. **Never commit admin tokens**

### For Internal Channels

1. **Assess trust level** of users
2. **Use admin tokens** for elevated operations
3. **Set appropriate rate limits**
4. **Monitor for abuse**
5. **Regular security reviews**

## Examples

### Example 1: Public WhatsApp Bot (Strictest)

```python
from agentos.communicationos import (
    MessageBus,
    SecurityPolicy,
    PolicyEnforcer,
    SecurityMode,
)

# Create strictest policy
policy = SecurityPolicy(
    mode=SecurityMode.CHAT_ONLY,
    chat_only=True,
    allow_execute=False,
    allowed_commands=["/help", "/session"],
    rate_limit_per_minute=10,
    block_on_violation=True,
)

# Setup message bus with security
bus = MessageBus()
enforcer = PolicyEnforcer(default_policy=policy, enable_remote_warnings=True)
bus.add_middleware(enforcer)

# Register adapter
bus.register_adapter("whatsapp_public", whatsapp_adapter)
```

### Example 2: Internal Slack Bot (Moderate)

```python
from agentos.communicationos import (
    SecurityPolicy,
    PolicyEnforcer,
    SecurityMode,
    generate_admin_token,
)

# Generate admin token
admin_token, token_hash = generate_admin_token()

# Moderate policy
policy = SecurityPolicy(
    mode=SecurityMode.CHAT_EXEC_RESTRICTED,
    chat_only=False,
    allow_execute=True,
    allowed_commands=["/help", "/session", "/status", "/execute"],
    require_admin_token=True,
    admin_token_hash=token_hash,
    rate_limit_per_minute=30,
    block_on_violation=True,
)

enforcer = PolicyEnforcer(default_policy=policy)
```

### Example 3: Multi-Channel with Different Policies

```python
# Default policy (strictest)
default_policy = SecurityPolicy.default_policy()
enforcer = PolicyEnforcer(default_policy=default_policy)

# Public channels use default
bus.register_adapter("whatsapp_public", whatsapp_adapter)
bus.register_adapter("telegram_public", telegram_adapter)

# Internal channel gets elevated policy
internal_policy = SecurityPolicy(
    mode=SecurityMode.CHAT_EXEC_RESTRICTED,
    allow_execute=True,
    allowed_commands=["/help", "/session", "/execute", "/status"],
    rate_limit_per_minute=60,
)
enforcer.set_channel_policy("slack_internal", internal_policy)
bus.register_adapter("slack_internal", slack_adapter)

# Add enforcer to bus
bus.add_middleware(enforcer)
```

## Troubleshooting

### Command Blocked Unexpectedly

**Problem**: Legitimate command is being blocked

**Solution**:
1. Check current policy: `policy.to_dict()`
2. Verify command is in whitelist: `policy.allowed_commands`
3. Check violation logs: `enforcer.get_violations()`
4. Add command to whitelist if appropriate

### Remote Exposure Warning

**Problem**: Getting remote exposure warning in local environment

**Solution**:
1. Check environment variables
2. Set `AGENTOS_REMOTE_MODE=false` if running locally
3. Disable warnings if false positive: `enable_remote_warnings=False`

### Admin Token Not Working

**Problem**: Admin token validation failing

**Solution**:
1. Verify token hash is correct
2. Check token is passed in message metadata
3. Ensure `require_admin_token=True` in policy
4. Generate new token if lost

## Security Checklist

Before deploying to production:

- [ ] Security mode set to `CHAT_ONLY` for public channels
- [ ] Command whitelist reviewed and minimized
- [ ] Rate limits configured appropriately
- [ ] Admin tokens generated and stored securely
- [ ] Remote exposure detection enabled
- [ ] Violation monitoring configured
- [ ] Audit logging enabled
- [ ] Webhook signature validation enabled
- [ ] Documentation reviewed and team trained
- [ ] Security policy tested thoroughly

## Further Reading

- [CommunicationOS Architecture](./README.md)
- [Manifest System Guide](./MANIFEST_GUIDE.md)
- [Audit and Compliance](./AUDIT_GUIDE.md)
- [Rate Limiting Guide](./RATE_LIMIT_GUIDE.md)
