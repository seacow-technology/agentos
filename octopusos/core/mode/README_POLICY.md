# Mode Policy Configuration Guide

## 1. Overview

### What is Mode Policy System?

The Mode Policy system is a **configuration-driven permission management framework** that controls what operations each execution mode can perform in AgentOS. It separates permission logic from code, making it easy to customize, audit, and maintain operational constraints.

### Why Do We Need It?

1. **Security by Default**: Prevents accidental code modifications in non-implementation modes
2. **Separation of Concerns**: Permission rules are defined in JSON files, not hardcoded
3. **Flexibility**: Teams can customize policies for different environments (dev, staging, production)
4. **Auditability**: All permission checks are logged to run_tape for compliance tracking
5. **Runtime Overrides**: Change policies without redeploying code

### Core Advantages

- **Configuration-Driven**: Define permissions in JSON, not Python code
- **Runtime Overrides**: Switch policies dynamically via environment variables or API
- **Safe Defaults**: Unknown modes default to read-only, preventing unauthorized operations
- **Extensible**: Add custom permissions beyond commit/diff
- **Type-Safe**: Schema validation ensures policy files are well-formed

---

## 2. Policy File Format

### JSON Structure

```json
{
  "version": "1.0",
  "description": "Human-readable description of this policy",
  "modes": {
    "mode_id": {
      "allows_commit": true,
      "allows_diff": true,
      "allowed_operations": ["read", "write", "execute"],
      "risk_level": "moderate"
    }
  },
  "default_permissions": {
    "allows_commit": false,
    "allows_diff": false,
    "allowed_operations": ["read"],
    "risk_level": "safe"
  }
}
```

### Field Definitions

#### Top-Level Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `version` | string | Yes | Policy schema version (currently "1.0") |
| `description` | string | No | Human-readable policy description |
| `modes` | object | Yes | Dictionary mapping mode_id to permissions |
| `default_permissions` | object | No | Fallback permissions for unknown modes |

#### Mode Permission Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `allows_commit` | boolean | false | Can this mode perform git commits? |
| `allows_diff` | boolean | false | Can this mode generate code diffs? |
| `allowed_operations` | array | ["read"] | List of allowed operations |
| `risk_level` | string | "safe" | Risk classification: safe, moderate, high, critical |

#### Risk Levels

- **safe**: Read-only operations, no system modifications
- **moderate**: Limited writes, no version control changes
- **high**: Can modify code and files
- **critical**: Can commit changes to version control

### Complete Example

```json
{
  "version": "1.0",
  "description": "Production-ready policy with strict controls",
  "modes": {
    "implementation": {
      "allows_commit": true,
      "allows_diff": true,
      "allowed_operations": ["read", "write", "execute", "commit"],
      "risk_level": "critical"
    },
    "design": {
      "allows_commit": false,
      "allows_diff": false,
      "allowed_operations": ["read"],
      "risk_level": "safe"
    },
    "debug": {
      "allows_commit": false,
      "allows_diff": true,
      "allowed_operations": ["read", "write"],
      "risk_level": "moderate"
    }
  },
  "default_permissions": {
    "allows_commit": false,
    "allows_diff": false,
    "allowed_operations": ["read"],
    "risk_level": "safe"
  }
}
```

---

## 3. Usage

### 3.1 Using Default Policy

The default policy is automatically loaded if no custom policy is specified. It matches the original hardcoded behavior.

```python
from agentos.core.mode import get_mode

# Get a mode instance (uses global default policy)
mode = get_mode("implementation")

# Check permissions
assert mode.allows_commit() == True   # implementation allows commits
assert mode.allows_diff() == True     # implementation allows diffs

# Other modes are restricted
design_mode = get_mode("design")
assert design_mode.allows_commit() == False  # design blocks commits
assert design_mode.allows_diff() == False    # design blocks diffs
```

### 3.2 Loading Custom Policy from File

Load a policy from a JSON file and set it as the global policy.

```python
from agentos.core.mode.mode_policy import load_policy_from_file
from pathlib import Path

# Load policy from file (automatically sets as global)
policy = load_policy_from_file(
    Path("configs/mode/strict_policy.json")
)

# Now all mode.allows_commit() calls use the strict policy
from agentos.core.mode import get_mode
mode = get_mode("implementation")
print(f"Allows commit: {mode.allows_commit()}")  # Depends on strict_policy.json
```

### 3.3 Runtime Policy Override

Create a custom policy instance and set it globally at runtime.

```python
from agentos.core.mode.mode_policy import ModePolicy, set_global_policy
from pathlib import Path

# Create custom policy instance
custom_policy = ModePolicy(Path("/path/to/my_policy.json"))

# Set as global policy (affects all subsequent permission checks)
set_global_policy(custom_policy)

# Verify it's active
from agentos.core.mode.mode_policy import get_global_policy
active_policy = get_global_policy()
print(f"Policy version: {active_policy.get_policy_version()}")
```

### 3.4 Environment Variable Configuration

Set a policy file path via environment variable before starting AgentOS.

```bash
# Set policy path
export MODE_POLICY_PATH=/path/to/custom_policy.json

# Run AgentOS (will load policy at startup)
agentos run "your command"
```

**Note**: Environment variable loading must be implemented in your application startup code:

```python
import os
from pathlib import Path
from agentos.core.mode.mode_policy import load_policy_from_file

# In your startup routine
policy_path = os.getenv("MODE_POLICY_PATH")
if policy_path:
    load_policy_from_file(Path(policy_path))
```

### 3.5 Direct Permission Checks

Query the policy engine directly without going through Mode objects.

```python
from agentos.core.mode.mode_policy import check_mode_permission, get_mode_permissions

# Quick permission check
can_commit = check_mode_permission("implementation", "commit")
print(f"Implementation can commit: {can_commit}")

# Get full permission object
perms = get_mode_permissions("debug")
print(f"Debug risk level: {perms.risk_level}")
print(f"Debug operations: {perms.allowed_operations}")
```

---

## 4. Built-in Policies

AgentOS ships with three pre-configured policy files in `configs/mode/`:

### 4.1 Default Policy (`default_policy.json`)

**Purpose**: Production-ready baseline matching original hardcoded behavior

**Rules**:
- Only `implementation` mode allows commits and diffs
- All other modes are read-only or restricted
- Backwards compatible with existing code

**Use Case**: Default for most deployments

### 4.2 Strict Policy (`strict_policy.json`)

**Purpose**: High-security environments where commits are externally controlled

**Rules**:
- `implementation` can generate diffs but **cannot commit**
- All other modes are read-only
- Forces manual review before commits

**Use Case**: CI/CD pipelines, code review workflows, audited environments

### 4.3 Development Policy (`dev_policy.json`)

**Purpose**: Developer-friendly settings for local development

**Rules**:
- `implementation` can commit and diff
- `debug` mode can generate diffs (for troubleshooting)
- More permissive for development velocity

**Use Case**: Local development, debugging sessions

### Policy Comparison Table

| Mode | Default | Strict | Development |
|------|---------|--------|-------------|
| **implementation** | commit ✓ diff ✓ | commit ✗ diff ✓ | commit ✓ diff ✓ |
| **design** | commit ✗ diff ✗ | commit ✗ diff ✗ | commit ✗ diff ✗ |
| **debug** | commit ✗ diff ✗ | commit ✗ diff ✗ | commit ✗ diff ✓ |
| **chat** | commit ✗ diff ✗ | commit ✗ diff ✗ | commit ✗ diff ✗ |
| **planning** | commit ✗ diff ✗ | commit ✗ diff ✗ | commit ✗ diff ✗ |
| **ops** | commit ✗ diff ✗ | commit ✗ diff ✗ | commit ✗ diff ✗ |
| **test** | commit ✗ diff ✗ | commit ✗ diff ✗ | commit ✗ diff ✗ |
| **release** | commit ✗ diff ✗ | commit ✗ diff ✗ | commit ✗ diff ✗ |

---

## 5. Red Lines (Unbreakable Constraints)

These principles ensure system integrity and cannot be violated:

### 1. Backwards Compatibility

**Rule**: Default policy must match current hardcoded behavior

**Rationale**: Existing code depends on `implementation` mode allowing commits. Changing defaults would break deployments.

**Enforcement**:
```python
# This must always work with default policy
from agentos.core.mode import get_mode
mode = get_mode("implementation")
assert mode.allows_commit() == True  # MUST be True by default
```

### 2. Safe Default for Unknown Modes

**Rule**: Modes not defined in policy default to read-only

**Rationale**: Fail-safe design prevents privilege escalation via typos or new modes.

**Enforcement**:
```python
policy = ModePolicy()
unknown_perms = policy.get_permissions("typo_mode_xyz")
assert unknown_perms.allows_commit == False  # MUST be False
assert unknown_perms.allows_diff == False    # MUST be False
```

### 3. Audit Trail Requirement

**Rule**: All permission checks must be logged to run_tape

**Rationale**: Compliance and debugging require visibility into permission decisions.

**Enforcement**: Every `check_permission()` call emits a log event:
```python
logger.info(f"Permission check: mode={mode_id}, permission={permission}, result={result}")
```

### 4. Schema Validation

**Rule**: Policy files must pass JSON schema validation

**Rationale**: Prevent runtime errors from malformed configuration.

**Enforcement**: Load fails gracefully, falls back to default:
```python
try:
    policy = ModePolicy(Path("invalid.json"))
except ValueError:
    # Falls back to safe default policy
    policy = ModePolicy()  # Uses default
```

---

## 6. Testing

### 6.1 Unit Tests

Run the comprehensive unit test suite:

```bash
# Test policy engine itself
pytest tests/unit/mode/test_mode_policy.py -v

# Expected output:
# test_default_policy_loads ✓
# test_implementation_allows_commit ✓
# test_design_blocks_commit ✓
# test_unknown_mode_safety ✓
# test_custom_policy_loading ✓
```

### 6.2 Verification Script

Run the standalone verification script:

```bash
python test_mode_policy_verification.py
```

**Output**:
```
============================================================
MODE_POLICY.PY VERIFICATION TESTS
============================================================

✓ Test 1 PASSED: Successfully imported ModePolicy and ModePermissions
✓ Test 2 PASSED: ModePolicy() instantiated successfully
✓ Test 3 PASSED: get_global_policy() returned ModePolicy
✓ Test 4 PASSED: check_permission('implementation', 'commit') = True
✓ Test 5 PASSED: check_permission('design', 'commit') = False
✓ Test 6 PASSED: check_permission('implementation', 'diff') = True
✓ Test 7 PASSED: check_permission('design', 'diff') = False
✓ Test 8 PASSED: All 7 restricted modes block commit/diff
✓ Test 9 PASSED: Unknown mode returns safe default permissions
✓ Test 10 PASSED: ModePermissions dataclass works correctly

✅ ALL 10 TESTS PASSED
```

### 6.3 Policy Enforcement Gate

Verify policy enforcement in the execution pipeline:

```bash
python scripts/gates/gm3_mode_policy_enforcement.py
```

This gate checks that:
- Mode instances delegate to ModePolicy
- Permission checks are enforced at execution boundaries
- Audit logs capture all permission decisions

---

## 7. Examples

### 7.1 Creating a Custom Policy File

**Scenario**: Create a policy where `test` mode can execute tests but not commit.

```json
{
  "version": "1.0",
  "description": "Test-execution policy",
  "modes": {
    "implementation": {
      "allows_commit": true,
      "allows_diff": true,
      "allowed_operations": ["read", "write", "execute", "commit"],
      "risk_level": "high"
    },
    "test": {
      "allows_commit": false,
      "allows_diff": false,
      "allowed_operations": ["read", "execute"],
      "risk_level": "moderate"
    }
  },
  "default_permissions": {
    "allows_commit": false,
    "allows_diff": false,
    "allowed_operations": ["read"],
    "risk_level": "safe"
  }
}
```

### 7.2 Runtime Policy Switching

**Scenario**: Switch between strict and permissive policies during execution.

```python
from pathlib import Path
from agentos.core.mode.mode_policy import load_policy_from_file, get_global_policy

# Start with strict policy
strict_policy = load_policy_from_file(Path("configs/mode/strict_policy.json"))
print(f"Current policy version: {strict_policy.get_policy_version()}")

# Do some work...
from agentos.core.mode import get_mode
mode = get_mode("implementation")
print(f"Can commit: {mode.allows_commit()}")  # False in strict mode

# Switch to dev policy for debugging
dev_policy = load_policy_from_file(Path("configs/mode/dev_policy.json"))
print(f"Can commit now: {mode.allows_commit()}")  # True in dev mode

# Verify active policy
active = get_global_policy()
assert active is dev_policy
```

### 7.3 Custom Permission Checks

**Scenario**: Add custom permission type beyond commit/diff.

```python
from agentos.core.mode.mode_policy import get_global_policy

# Check custom permission
policy = get_global_policy()
can_deploy = policy.check_permission("release", "deploy")

if can_deploy:
    print("Release mode can deploy")
else:
    print("Deployment blocked by policy")

# Check risk level
perms = policy.get_permissions("release")
if perms.risk_level == "critical":
    print("Extra review required for critical operations")
```

**Custom Policy JSON**:
```json
{
  "modes": {
    "release": {
      "allows_commit": false,
      "allows_diff": false,
      "allowed_operations": ["read", "deploy"],
      "risk_level": "critical"
    }
  }
}
```

### 7.4 Programmatic Policy Creation

**Scenario**: Generate policy dynamically based on environment.

```python
import json
from pathlib import Path

def create_environment_policy(env: str) -> Path:
    """Create policy based on environment"""

    if env == "production":
        config = {
            "version": "1.0",
            "description": f"Auto-generated {env} policy",
            "modes": {
                "implementation": {
                    "allows_commit": False,  # No direct commits in prod
                    "allows_diff": True,
                    "allowed_operations": ["read"],
                    "risk_level": "high"
                }
            }
        }
    else:  # dev/staging
        config = {
            "version": "1.0",
            "description": f"Auto-generated {env} policy",
            "modes": {
                "implementation": {
                    "allows_commit": True,
                    "allows_diff": True,
                    "allowed_operations": ["read", "write", "execute"],
                    "risk_level": "moderate"
                }
            }
        }

    # Write to file
    policy_path = Path(f"/tmp/{env}_policy.json")
    with open(policy_path, 'w') as f:
        json.dump(config, f, indent=2)

    return policy_path

# Usage
import os
env = os.getenv("DEPLOYMENT_ENV", "development")
policy_path = create_environment_policy(env)

from agentos.core.mode.mode_policy import load_policy_from_file
load_policy_from_file(policy_path)
```

---

## 8. Troubleshooting

### Problem: Policy File Not Loading

**Symptoms**: Default policy is used even after specifying custom file

**Diagnosis**:
```python
import logging
logging.basicConfig(level=logging.DEBUG)

from agentos.core.mode.mode_policy import load_policy_from_file
from pathlib import Path

policy = load_policy_from_file(Path("my_policy.json"))
# Check logs for "Policy loaded from..." or "Falling back to default"
```

**Solutions**:
1. Verify file path is absolute: `Path("my_policy.json").resolve()`
2. Check file permissions: `ls -l my_policy.json`
3. Validate JSON syntax: `python -m json.tool my_policy.json`
4. Check schema: `version` and `modes` fields are required

---

### Problem: Permissions Not Applied

**Symptoms**: `mode.allows_commit()` returns unexpected value

**Diagnosis**:
```python
from agentos.core.mode.mode_policy import get_global_policy

policy = get_global_policy()
print(f"Policy version: {policy.get_policy_version()}")
print(f"All modes: {policy.get_all_modes()}")

perms = policy.get_permissions("implementation")
print(f"Implementation perms: {perms}")
```

**Solutions**:
1. Verify global policy is set: `get_global_policy()` should not be default
2. Check mode_id spelling: Must match exactly (case-sensitive)
3. Reload policy: `set_global_policy(new_policy)` before checking
4. Clear cached Mode instances: Create new `get_mode(mode_id)` call

---

### Problem: Invalid Policy File

**Symptoms**: Error message "Policy must contain 'version' field"

**Diagnosis**:
```python
import json

with open("my_policy.json") as f:
    data = json.load(f)
    print("Top-level keys:", data.keys())
    print("Version:", data.get("version"))
    print("Modes:", data.get("modes", {}).keys())
```

**Solutions**:
1. Add required `version` field:
   ```json
   {"version": "1.0", "modes": {...}}
   ```
2. Add required `modes` object:
   ```json
   {"version": "1.0", "modes": {"implementation": {...}}}
   ```
3. Use schema validator (future):
   ```bash
   jsonschema -i my_policy.json agentos/core/mode/mode_policy.schema.json
   ```

---

### Problem: Permission Denied Despite Policy

**Symptoms**: Operation blocked even though policy allows it

**Diagnosis**:
```python
from agentos.core.mode import get_mode

mode = get_mode("implementation")
print(f"Mode allows commit: {mode.allows_commit()}")
print(f"Mode allows diff: {mode.allows_diff()}")

# Check execution boundary
from agentos.core.mode.mode_policy import get_mode_permissions
perms = get_mode_permissions("implementation")
print(f"Direct policy check: {perms.allows_commit}")
```

**Solutions**:
1. Check other gate conditions (not just policy)
2. Verify mode_id is passed correctly to executor
3. Check for overriding environment restrictions
4. Review execution logs for permission denial location

---

### Problem: Policy Changes Not Taking Effect

**Symptoms**: Edited policy file but behavior unchanged

**Solutions**:
1. **Restart the application**: Policy is loaded at startup
2. **Reload policy dynamically**:
   ```python
   from agentos.core.mode.mode_policy import load_policy_from_file
   load_policy_from_file(Path("configs/mode/my_policy.json"))
   ```
3. **Check file modification time**:
   ```bash
   stat configs/mode/my_policy.json
   ```
4. **Force policy reload**:
   ```python
   from agentos.core.mode.mode_policy import ModePolicy, set_global_policy
   policy = ModePolicy(Path("configs/mode/my_policy.json"))
   set_global_policy(policy)
   ```

---

## Appendix A: Schema Reference

### JSON Schema Definition

See `agentos/core/mode/mode_policy.schema.json` for the formal JSON Schema definition.

### Quick Schema Rules

1. **version** (string, required): Must be "1.0"
2. **description** (string, optional): Human-readable text
3. **modes** (object, required): Key = mode_id, Value = permissions object
4. **default_permissions** (object, optional): Fallback for unknown modes

**Permissions Object**:
- `allows_commit` (boolean, default=false)
- `allows_diff` (boolean, default=false)
- `allowed_operations` (array of strings, default=["read"])
- `risk_level` (string, default="safe", enum: safe|moderate|high|critical)

---

## Appendix B: Migration Guide

### From Hardcoded Permissions to Policy-Based

**Before** (hardcoded in mode.py):
```python
def allows_commit(self) -> bool:
    return self.mode_id == "implementation"
```

**After** (policy-driven):
```python
def allows_commit(self) -> bool:
    policy = get_global_policy()
    return policy.check_permission(self.mode_id, "commit")
```

**Migration Steps**:
1. Keep default policy identical to hardcoded behavior
2. Test with default policy (no changes expected)
3. Create custom policy files for specific use cases
4. Load custom policies via environment variable
5. Monitor logs for permission checks
6. Gradually customize policies per environment

---

## Appendix C: Best Practices

### 1. Version Control Your Policies

Store policy files in git alongside code:
```
configs/
  mode/
    production_policy.json
    staging_policy.json
    development_policy.json
```

### 2. Use Descriptive Policy Names

Include environment/purpose in filename:
- ✓ `production_strict_policy.json`
- ✗ `policy1.json`

### 3. Document Custom Policies

Add detailed `description` fields:
```json
{
  "version": "1.0",
  "description": "Production policy for regulated environment. No commits allowed in automated runs. All diffs require manual review. Updated: 2024-01-15",
  "modes": {...}
}
```

### 4. Test Policy Changes

Always test policy files before deploying:
```bash
# Unit test
pytest tests/unit/mode/test_mode_policy.py

# Integration test
python test_mode_policy_verification.py

# Gate verification
python scripts/gates/gm3_mode_policy_enforcement.py
```

### 5. Use Environment-Specific Policies

Set policy via environment variable in deployment:
```yaml
# docker-compose.yml
environment:
  MODE_POLICY_PATH: /app/configs/mode/production_policy.json
```

### 6. Monitor Permission Denials

Track denied operations in production logs:
```python
from agentos.core.mode import get_mode
import logging

logger = logging.getLogger(__name__)

mode = get_mode("design")
if not mode.allows_commit():
    logger.warning(
        f"Commit blocked by policy in mode={mode.mode_id}",
        extra={"mode": mode.mode_id, "operation": "commit"}
    )
```

---

## Quick Reference Card

```python
# Load policy from file
from agentos.core.mode.mode_policy import load_policy_from_file
from pathlib import Path
load_policy_from_file(Path("configs/mode/strict_policy.json"))

# Check permissions via Mode
from agentos.core.mode import get_mode
mode = get_mode("implementation")
mode.allows_commit()  # True/False
mode.allows_diff()    # True/False

# Check permissions directly
from agentos.core.mode.mode_policy import check_mode_permission
check_mode_permission("debug", "commit")  # True/False

# Get full permissions
from agentos.core.mode.mode_policy import get_mode_permissions
perms = get_mode_permissions("ops")
perms.risk_level         # "safe" | "moderate" | "high" | "critical"
perms.allowed_operations # Set of operation strings

# Get active policy
from agentos.core.mode.mode_policy import get_global_policy
policy = get_global_policy()
policy.get_policy_version()  # "1.0"
policy.get_all_modes()       # Set of mode_ids
```

---

## Support

For questions or issues:
1. Check logs: `tail -f logs/agentos.log | grep "Policy"`
2. Run verification: `python test_mode_policy_verification.py`
3. Review code: `agentos/core/mode/mode_policy.py`
4. File issue: Include policy file and error logs

---

**Version**: 1.0
**Last Updated**: 2024-01-30
**Maintainer**: AgentOS Core Team
