# Security Quick Reference

## Quick Start

### 1. Default Security (Strictest)

```python
from agentos.communicationos import SecurityPolicy, PolicyEnforcer, MessageBus

# Use default policy (chat-only)
policy = SecurityPolicy.default_policy()
enforcer = PolicyEnforcer(default_policy=policy)

bus = MessageBus()
bus.add_middleware(enforcer)
```

### 2. Enable Execute (With Caution)

```python
from agentos.communicationos import SecurityPolicy, SecurityMode, generate_admin_token

# Generate admin token
admin_token, token_hash = generate_admin_token()
print(f"Save this token: {admin_token}")

# Create permissive policy
policy = SecurityPolicy(
    mode=SecurityMode.CHAT_EXEC_RESTRICTED,
    allow_execute=True,
    allowed_commands=["/session", "/help", "/execute"],
    require_admin_token=True,
    admin_token_hash=token_hash,
)
```

### 3. Per-Channel Policies

```python
# Default: strict
default_policy = SecurityPolicy.default_policy()
enforcer = PolicyEnforcer(default_policy=default_policy)

# Internal channel: permissive
internal_policy = SecurityPolicy(
    mode=SecurityMode.CHAT_EXEC_RESTRICTED,
    allow_execute=True,
    allowed_commands=["/session", "/help", "/execute", "/status"],
)
enforcer.set_channel_policy("slack_internal", internal_policy)
```

## Security Modes

| Mode | Execute | Use Case | Risk |
|------|---------|----------|------|
| `CHAT_ONLY` | ❌ Disabled | Production, public channels | Low |
| `CHAT_EXEC_RESTRICTED` | ⚠️ Optional | Development, internal | Moderate |

## Common Commands

### Check Policy

```python
# Check if operation allowed
policy.is_operation_allowed(OperationType.EXECUTE)

# Check if command allowed
policy.is_command_allowed("/execute")

# Validate admin token
policy.validate_admin_token(user_token)
```

### Monitor Violations

```python
# Get recent violations
violations = enforcer.get_violations(limit=50)

# Get violations for specific channel
channel_violations = enforcer.get_violations(channel_id="whatsapp_001")

# Get statistics
stats = enforcer.get_stats()
print(f"Total violations: {stats['total_violations']}")
print(f"Blocked: {stats['blocked_count']}")
```

### Check Remote Exposure

```python
from agentos.communicationos.security import RemoteExposureDetector

if RemoteExposureDetector.is_remote_exposed():
    print("WARNING: Remote exposure detected!")
    print(RemoteExposureDetector.get_exposure_warning())
```

## Default Whitelisted Commands

- `/session` - Session management
- `/help` - Help information

## Operation Types

- `CHAT` - Always allowed
- `EXECUTE` - Requires explicit permission
- `FILE_ACCESS` - Future
- `SYSTEM_INFO` - Future
- `CONFIG_CHANGE` - Future

## Production Deployment Checklist

- [ ] Use `CHAT_ONLY` mode for public channels
- [ ] Set conservative rate limits (10-20 req/min)
- [ ] Enable remote exposure warnings
- [ ] Configure admin tokens if execute needed
- [ ] Monitor violation logs regularly
- [ ] Test security policies before deployment
- [ ] Document policy decisions
- [ ] Train team on security policies

## Environment Variables

Set `AGENTOS_REMOTE_MODE=true` to explicitly indicate remote deployment.

## Common Scenarios

### Public WhatsApp Bot
```python
policy = SecurityPolicy(
    mode=SecurityMode.CHAT_ONLY,
    allowed_commands=["/help", "/session"],
    rate_limit_per_minute=10,
)
```

### Internal Admin Channel
```python
admin_token, token_hash = generate_admin_token()
policy = SecurityPolicy(
    mode=SecurityMode.CHAT_EXEC_RESTRICTED,
    allow_execute=True,
    allowed_commands=["/help", "/session", "/execute", "/admin"],
    require_admin_token=True,
    admin_token_hash=token_hash,
    rate_limit_per_minute=60,
)
```

### Development Environment
```python
policy = SecurityPolicy(
    mode=SecurityMode.CHAT_EXEC_RESTRICTED,
    allow_execute=True,
    allowed_commands=["/help", "/session", "/execute", "/debug"],
    rate_limit_per_minute=100,
)
```

## Troubleshooting

### Command Blocked Unexpectedly
1. Check policy: `policy.allowed_commands`
2. Verify command prefix matches
3. Check violations: `enforcer.get_violations()`

### Admin Token Not Working
1. Verify token hash is correct
2. Check `require_admin_token=True` in policy
3. Ensure token passed in message metadata

### False Remote Exposure Warning
1. Check environment variables
2. Set `AGENTOS_REMOTE_MODE=false` if local
3. Disable warnings: `PolicyEnforcer(enable_remote_warnings=False)`

## Links

- [Complete Security Guide](./SECURITY_POLICY_GUIDE.md)
- [Security Examples](./examples_security.py)
- [Task #9 Completion Report](./TASK_9_COMPLETION_REPORT.md)
