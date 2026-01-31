# Datetime Usage Gate

## Overview

The Datetime Usage Gate enforces AgentOS's Time & Timestamp Contract by preventing regression of forbidden datetime usage patterns. This gate ensures all code uses timezone-aware UTC timestamps through the centralized clock module.

## Purpose

**Problem:**
- `datetime.utcnow()` is deprecated and removed in Python 3.12+
- `datetime.now()` without timezone creates naive datetimes, leading to timezone bugs
- Inconsistent time handling across the codebase

**Solution:**
- Centralized clock module: `agentos.core.time.clock`
- CI gate that rejects code with forbidden patterns
- Clear migration path with helper functions

## Forbidden Patterns

### 1. datetime.utcnow()

```python
# ❌ FORBIDDEN
from datetime import datetime
timestamp = datetime.utcnow()
```

**Why:** Deprecated in Python 3.12+, returns naive datetime

**Fix:**
```python
# ✅ CORRECT
from agentos.core.time import utc_now
timestamp = utc_now()
```

### 2. datetime.now() without timezone

```python
# ❌ FORBIDDEN
from datetime import datetime
timestamp = datetime.now()
```

**Why:** Returns naive datetime, timezone-dependent

**Fix:**
```python
# ✅ CORRECT
from agentos.core.time import utc_now
timestamp = utc_now()
```

## Clock Module API

The `agentos.core.time.clock` module provides safe alternatives:

```python
from agentos.core.time import (
    utc_now,        # Get current UTC time (aware datetime)
    utc_now_ms,     # Get current time as epoch milliseconds (int)
    utc_now_iso,    # Get current time as ISO 8601 string with Z
    from_epoch_ms,  # Convert epoch ms to aware datetime
    to_epoch_ms,    # Convert datetime to epoch ms
    from_epoch_s,   # Convert epoch seconds to aware datetime
    to_epoch_s,     # Convert datetime to epoch seconds
)

# Examples
now = utc_now()                    # datetime(2026, 1, 31, 12, 0, 0, tzinfo=timezone.utc)
timestamp_ms = utc_now_ms()        # 1738329600000
iso_string = utc_now_iso()         # "2026-01-31T12:00:00.000000Z"
dt = from_epoch_ms(1738329600000)  # Convert back to datetime
```

## Usage

### Local Testing

Run the gate locally before committing:

```bash
# Using bash wrapper (recommended)
bash scripts/gates/check_datetime_usage.sh

# Using Python directly
python3 scripts/gates/gate_datetime_usage.py
```

### CI Integration

The gate runs automatically in CI/CD:

1. **Main CI workflow**: `.github/workflows/ci.yml` (security job)
2. **Dedicated workflow**: `.github/workflows/datetime-check.yml`

Both run on:
- Push to `master`/`main` branches
- Pull requests to `master`/`main` branches

### Pre-commit Hook

Install pre-commit hooks to catch violations before commit:

```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install

# Run manually
pre-commit run check-datetime-usage --all-files
```

Configuration: `.pre-commit-config.yaml`

## Gate Behavior

### Exit Codes

- **0**: Success - no violations found
- **1**: Failure - violations detected

### Whitelisted Files

The following files are exempt from the gate (defined in `gate_datetime_usage.py`):

- `agentos/core/time/clock.py` - Clock module implementation
- `agentos/core/time/__init__.py` - Module initialization
- `agentos/core/time/test_clock.py` - Clock module tests

### Excluded Directories

- `__pycache__/`
- `.git/`
- `.pytest_cache/`
- `node_modules/`
- `.venv/` and `venv/`

## Output Format

### Success

```
================================================================================
Time & Timestamp Contract Enforcement
================================================================================

✅ SUCCESS: No datetime usage violations found!

All code follows the Time & Timestamp Contract:
  - No datetime.utcnow() usage (deprecated)
  - No datetime.now() without timezone
  - All timestamps use agentos.core.time.clock module
```

### Violations Found

```
================================================================================
Time & Timestamp Contract Enforcement
================================================================================

❌ VIOLATIONS FOUND: 5 datetime usage violations

================================================================================
Violation: datetime.utcnow()
Count: 2
================================================================================

  agentos/core/example.py:42
    timestamp = datetime.utcnow()
  agentos/webui/api/handler.py:88
    created_at = datetime.utcnow()

================================================================================
Violation: datetime.now() without timezone
Count: 3
================================================================================

  agentos/cli/main.py:105
    now = datetime.now()
  agentos/core/runner.py:234
    started_at = datetime.now()
  agentos/store/manager.py:567
    timestamp = datetime.now()

================================================================================
How to Fix
================================================================================

Replace forbidden patterns with clock module:

  Before:
    from datetime import datetime
    timestamp = datetime.utcnow()
    timestamp = datetime.now()

  After:
    from agentos.core.time import utc_now
    timestamp = utc_now()

Additional helpers:
  - utc_now_ms() -> int (epoch milliseconds)
  - utc_now_iso() -> str (ISO 8601 with Z suffix)
  - from_epoch_ms(ms) -> datetime
  - to_epoch_ms(dt) -> int

See: agentos/core/time/clock.py
```

## Testing the Gate

Run the gate test suite:

```bash
bash scripts/gates/test_datetime_gate.sh
```

This creates temporary test cases and verifies:
- ✅ Detects `datetime.utcnow()`
- ✅ Detects `datetime.now()` without timezone
- ✅ Allows `utc_now()` from clock module
- ✅ Allows `datetime.now(timezone.utc)` (when explicitly provided)
- ✅ Allows `datetime.now(tz=...)` (when explicitly provided)

## Migration Guide

### Step 1: Find violations

```bash
# Scan for datetime.utcnow()
rg "datetime\.utcnow\(\)" agentos/

# Scan for datetime.now() without timezone
rg "datetime\.now\(\)" agentos/ | grep -v timezone | grep -v tz=
```

### Step 2: Replace with clock module

```python
# Before
from datetime import datetime

def create_record():
    return {
        "created_at": datetime.utcnow(),
        "timestamp": datetime.now()
    }

# After
from agentos.core.time import utc_now

def create_record():
    return {
        "created_at": utc_now(),
        "timestamp": utc_now()
    }
```

### Step 3: Verify

```bash
# Run gate
bash scripts/gates/check_datetime_usage.sh

# Run tests
pytest tests/

# Run full CI locally (if using act)
act -j security
```

## Troubleshooting

### False Positives

If the gate incorrectly flags valid code:

1. **Ensure timezone is explicit:**
   ```python
   # Will be flagged
   timestamp = datetime.now()

   # Will NOT be flagged
   timestamp = datetime.now(timezone.utc)
   timestamp = datetime.now(tz=timezone.utc)
   ```

2. **Add file to whitelist** (if truly needed):
   Edit `WHITELIST` in `scripts/gates/gate_datetime_usage.py`

### Gate Not Running

If the gate doesn't run in CI:

1. Check workflow syntax:
   ```bash
   # Validate GitHub Actions workflow
   yamllint .github/workflows/datetime-check.yml
   ```

2. Verify script permissions:
   ```bash
   ls -l scripts/gates/check_datetime_usage.sh
   # Should show: -rwxr-xr-x
   ```

3. Check Python availability in CI:
   ```bash
   # CI uses Python 3.13 by default
   python3 --version
   ```

## Related Documentation

- [Time & Timestamp Contract](docs/adr/ADR-XXXX-time-timestamp-contract.md) (ADR)
- [Clock Module](agentos/core/time/clock.py) (Implementation)
- [Contributing Guide](CONTRIBUTING.md) (Development rules)
- [Task #11 Completion Report](scripts/verify_task11_completion.py) (Migration status)

## Maintenance

### Adding New Patterns

To detect additional forbidden patterns:

1. Edit `PATTERNS` dict in `gate_datetime_usage.py`
2. Add regex pattern
3. Update test suite in `test_datetime_gate.sh`
4. Update documentation

### Updating Whitelist

To exempt new files:

1. Edit `WHITELIST` set in `gate_datetime_usage.py`
2. Add relative path from project root
3. Document reason in comments

## Contact

For questions or issues with the datetime gate:

- Open an issue: [GitHub Issues](https://github.com/seacow-technology/agentos/issues)
- Discussion: [GitHub Discussions](https://github.com/seacow-technology/agentos/discussions)
- Email: dev@seacow.tech

---

**Version:** 1.0
**Last Updated:** 2026-01-31
**Maintainer:** AgentOS Core Team
