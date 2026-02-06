# Ops Assistant - Governance Reference Implementation

## What is Ops Assistant?

**Ops Assistant is NOT an operations tool.**

**Ops Assistant is a demonstration of Execution Trust.**

Its value is not in its features, but in its **governance behavior**. It exists to prove that governance is real, not just documentation.

## Core Principle

> Ops Assistant must "fail gracefully and often"

When Ops Assistant is denied, it doesn't try to bypass. It explains WHY, clearly and completely.

## What Ops Assistant Can Do

### LOW Risk (Always Succeeds)
- Query system status
- View execution history
- Check risk scores
- Review trust tiers
- Read policy decisions
- Display governance health

**These operations have 100% success rate because they're read-only.**

### MEDIUM Risk (Policy Evaluated)
- Request context refresh
- Request configuration changes

**These operations may be allowed, denied, or require approval based on policy.**

### HIGH Risk (Often Denied)
- Request extension execution
- Request system modifications

**These operations are usually denied or require approval. This is correct behavior.**

## What Ops Assistant Cannot Do

- ❌ Decide execution
- ❌ Cache authorization
- ❌ Batch trigger high-risk operations
- ❌ Write security logic
- ❌ Bypass Policy Engine
- ❌ Pretend execution succeeded

**Ops Assistant is intentionally limited. This limitation is the proof point.**

## Architecture

```
┌─────────────────┐
│ Ops Assistant   │  ← Only REQUESTS
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Policy Engine   │  ← Makes DECISIONS
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Execution      │  ← Actually EXECUTES
└─────────────────┘
```

Ops Assistant never has direct access to execution. It must always go through Policy Engine.

## Usage Examples

### Example 1: LOW Risk Queries (Always Succeed)

```python
from agentos.core.appos.apps.ops_assistant import StatusQueries

queries = StatusQueries("/path/to/agentos.db")

# These will ALWAYS succeed
executions = queries.get_recent_executions(limit=10)
health = queries.get_governance_health()
decisions = queries.get_policy_decisions(limit=20)

print(f"Found {len(executions)} recent executions")
print(f"Governance health: {health['health']}")
```

### Example 2: MEDIUM Risk Request (May Be Denied)

```python
from agentos.core.appos.apps.ops_assistant import SystemActions

actions = SystemActions("/path/to/agentos.db")

result = actions.request_context_refresh("session_123")

if result['status'] == 'blocked':
    print(f"❌ DENIED: {result['reason']}")
    print(f"Context: {result['context']}")
elif result['status'] == 'pending_approval':
    print(f"⏸  PENDING: {result['reason']}")
else:
    print(f"✅ SUCCESS")
```

### Example 3: HIGH Risk Request (Usually Denied)

```python
result = actions.request_extension_execution(
    extension_id="dangerous_extension",
    action_id="dangerous_action",
    args={}
)

# Expected: DENIED or REQUIRE_APPROVAL
if result['status'] == 'denied':
    print(f"❌ DENIED: {result['reason']}")
    print("\nFull explanation:")
    print(result['explanation'])
    print(f"\nTrust Tier: {result['context']['tier']}")
    print(f"Risk Score: {result['context']['risk_score']:.1f}")
```

## Verification Tests

Three key tests prove governance works:

### Test 1: LOW Risk Always Succeeds
```python
queries = StatusQueries(db_path)
demo = queries.demonstrate_success()
assert demo['success_rate'] == "3/3 (100.0%)"
```

### Test 2: MEDIUM Risk Evaluated
```python
actions = SystemActions(db_path)
result = actions.request_context_refresh("test_session")
assert result['status'] in ['success', 'blocked', 'pending_approval']
assert 'reason' in result
```

### Test 3: HIGH Risk Often Denied
```python
demo = actions.demonstrate_denial()
# Most HIGH risk requests should be denied or require approval
assert demo['pass_rate'].endswith('100.0%)') or demo['pass_rate'].endswith('66.7%)')
```

## Design Philosophy

### Why "Fail Gracefully"?

Traditional ops tools try to succeed at all costs. Ops Assistant is different:

1. **Denials are Success**: When a dangerous operation is denied, governance worked correctly.

2. **Clear Communication**: Every denial comes with:
   - Clear reason
   - Risk context (tier, score, auth status)
   - Applied policy rules
   - Next steps for user

3. **No Bypass Paths**: Ops Assistant cannot:
   - Cache authorization tokens
   - Skip policy evaluation
   - Execute without approval
   - Hide denials from audit trail

### Why This Matters

This demonstrates that:
- Governance is not optional
- Policy Engine cannot be bypassed
- All decisions are logged
- High-risk operations are protected

**This is not a bug. This is the feature.**

## Integration with Phase D Components

Ops Assistant integrates with all Phase D components:

### D1: Sandbox Isolation
- Queries sandbox availability from context
- Respects sandbox requirements in policy

### D2: Risk Scoring
- Displays risk scores for extensions
- Policy uses risk scores in decisions

### D3: Trust Tier
- Shows trust tier assignments
- Policy enforces tier-based restrictions

### D4: Policy Engine
- All MEDIUM/HIGH operations go through Policy Engine
- Cannot bypass or cache decisions
- All denials logged to audit trail

## Success Criteria

Ops Assistant succeeds when it demonstrates:

1. ✅ LOW risk operations: 100% success rate
2. ✅ MEDIUM risk operations: Policy evaluated correctly
3. ✅ HIGH risk operations: Often denied with clear explanation
4. ✅ All denials: Logged to audit trail with context

## Anti-Patterns

What Ops Assistant should NEVER do:

```python
# ❌ BAD: Caching authorization
if self.last_auth_time > now() - 3600:
    return "cached_approval"

# ❌ BAD: Skipping policy for "safe" operations
if operation == "read_only":
    return execute_directly()

# ❌ BAD: Batch high-risk operations
for op in dangerous_ops:
    execute_without_policy(op)

# ❌ BAD: Hiding denials
if result == "DENY":
    return {"status": "success", "message": "Completed"}
```

All of these bypass governance and defeat the purpose of Ops Assistant.

## Conclusion

Ops Assistant is not about adding features. It's about **proving governance works**.

When Ops Assistant is denied access, it doesn't complain. It explains. It demonstrates that the system is working as designed.

**The value is in the failure, not the success.**
