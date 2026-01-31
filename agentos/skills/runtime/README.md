# Skills Runtime System

Runtime execution engine for AgentOS skills with phase gate and permission guards.

## Quick Start

```python
from agentos.skills.registry import SkillRegistry
from agentos.skills.runtime import SkillLoader, SkillInvoker

# 1. Initialize components
registry = SkillRegistry()  # Uses ~/.agentos/store/skill/db.sqlite
loader = SkillLoader(registry)
loader.load_enabled_skills()  # Load all enabled skills

# 2. Create invoker (default: planning phase - blocks all)
invoker = SkillInvoker(loader, execution_phase='execution')

# 3. Invoke skill
try:
    result = invoker.invoke('my.skill', 'command', {'arg': 'value'})
    print(result)
except PhaseViolationError:
    print("Cannot invoke skills during planning phase")
except SkillNotEnabledError:
    print("Skill not enabled")
except PermissionDeniedError as e:
    print(f"Permission denied: {e}")
```

## Phase Management

```python
# Start in planning phase (blocks all skills)
invoker = SkillInvoker(loader, execution_phase='planning')

# Switch to execution phase
invoker.set_phase('execution')

# Now skills can be invoked
result = invoker.invoke('skill.id', 'command', {})
```

## Permission Guards

### Network Permission
```yaml
# skill.yaml
requires:
  permissions:
    net:
      allow_domains:
        - api.github.com
        - api.example.com
```

```python
# This passes
result = invoker.invoke('skill', 'fetch', {'domain': 'api.github.com'})

# This fails with PermissionDeniedError
result = invoker.invoke('skill', 'fetch', {'domain': 'evil.com'})
```

### Filesystem Permission
```yaml
# skill.yaml
requires:
  permissions:
    fs:
      read: true
      write: false  # Write denied
```

```python
# This passes
result = invoker.invoke('skill', 'cmd', {'operation': 'read', 'path': '/tmp/file'})

# This fails with PermissionDeniedError
result = invoker.invoke('skill', 'cmd', {'operation': 'write', 'path': '/tmp/file'})
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     SkillInvoker                            │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ 1. Phase Gate                                        │   │
│  │    planning → PhaseViolationError ❌                  │   │
│  │    execution → proceed ✅                             │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ 2. Enable Check                                      │   │
│  │    not enabled → SkillNotEnabledError ❌              │   │
│  │    enabled → proceed ✅                               │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ 3. Permission Guards                                 │   │
│  │    NetGuard: Domain allowlist                        │   │
│  │    FsGuard: Read/write permissions                   │   │
│  │    violation → PermissionDeniedError ❌               │   │
│  │    OK → proceed ✅                                    │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ 4. Execution                                         │   │
│  │    Load module → Call handler → Return result        │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Exception Handling

```python
from agentos.skills.runtime import (
    PhaseViolationError,
    SkillNotEnabledError,
    PermissionDeniedError
)

try:
    result = invoker.invoke('skill', 'cmd', {})
except PhaseViolationError:
    # Planning phase attempted invocation
    pass
except SkillNotEnabledError:
    # Skill not loaded/enabled
    pass
except PermissionDeniedError as e:
    # Net or fs permission denied
    print(f"Denied: {e}")
except ValueError:
    # Command not found in manifest
    pass
except FileNotFoundError:
    # Skill module not found
    pass
```

## Security Notes

### MVP Limitations
- ⚠️ Skills run in-process (no isolation)
- ⚠️ No resource limits (CPU/memory/timeout)
- ⚠️ No path restrictions (only read/write flags)
- ⚠️ No protocol restrictions (only domains)

### Production Requirements
1. **Process isolation**: Use subprocess/container/WASM
2. **Resource limits**: Enforce CPU/memory/timeout
3. **Path restrictions**: Restrict to specific directories
4. **Protocol restrictions**: Limit to HTTP/HTTPS

### Audit Trail
All security events are logged:
```python
import logging
logging.basicConfig(level=logging.INFO)

# All security events logged with metadata
# - Phase violations
# - Enable check failures
# - Permission denials
# - Execution errors
```

## Testing

```bash
# Unit tests (14 tests)
python3 -m pytest tests/unit/skills/runtime/test_invoke.py -v

# Integration tests (5 tests)
python3 -m pytest tests/integration/skills/test_skill_execution.py -v

# All tests
python3 -m pytest tests/unit/skills/runtime/ tests/integration/skills/ -v
```

## See Also

- [Implementation Report](../../../docs/PR-0201-2026-5_IMPLEMENTATION_REPORT.md)
- [Skill Manifest Schema](../manifest.py)
- [Skill Registry](../registry.py)
