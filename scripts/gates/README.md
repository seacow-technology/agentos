# AgentOS Gates

Multi-layer defense system to enforce architectural contracts and prevent regressions.

## Gate Categories

1. **DB Integrity Gates** - Ensure single database instance
2. **Time & Timestamp Gate** - Enforce timezone-aware UTC timestamps
3. **Mode System Gates** - Enforce execution mode contracts
4. **Pipeline Gates** - Enforce pipeline structure and safety

## Quick Start

### Run All Gates
```bash
./scripts/gates/run_all_gates.sh
```

### Install Pre-Commit Hook
```bash
./scripts/gates/install_pre_commit_hook.sh
```

### Run Individual Gate
```bash
# DB Integrity Gates
python3 scripts/gates/gate_no_sqlite_connect_enhanced.py
python3 scripts/gates/gate_no_duplicate_tables.py
python3 scripts/gates/gate_no_sql_in_code.py
python3 scripts/gates/gate_single_db_entry.py
python3 scripts/gates/gate_no_implicit_external_io.py

# Time & Timestamp Gate
bash scripts/gates/check_datetime_usage.sh
```

## What Gets Checked

### DB Integrity Gates

#### ✅ Allowed
- Using `registry_db.get_db()` for database access
- Creating migrations in `agentos/store/migrations/`
- Using whitelisted legacy files (temporary)

#### ❌ Blocked
- Direct `sqlite3.connect()` calls
- Creating new Store classes
- SQL `CREATE TABLE` in code
- Multiple `get_db()` functions
- Duplicate database tables
- Hardcoded `.sqlite` file paths
- Implicit external I/O in Chat core (must use /comm commands)

### Time & Timestamp Gate

#### ✅ Allowed
- Using `utc_now()` from `agentos.core.time`
- Using `datetime.now(timezone.utc)` with explicit timezone
- Using `datetime.now(tz=...)` with explicit timezone parameter

#### ❌ Blocked
- `datetime.utcnow()` (deprecated in Python 3.12+)
- `datetime.now()` without timezone parameter
- Creating naive datetime objects for system timestamps

See: [Datetime Gate Documentation](README_DATETIME_GATE.md)

## Common Violations & Fixes

### Violation: Direct sqlite3.connect()
```python
# ❌ WRONG
import sqlite3
conn = sqlite3.connect("my.db")

# ✅ CORRECT
from agentos.core.db import registry_db
conn = registry_db.get_db()
```

### Violation: Creating Store Classes
```python
# ❌ WRONG
class MySessionStore:
    def __init__(self):
        self.conn = sqlite3.connect("sessions.db")

# ✅ CORRECT
from agentos.core.db import registry_db

class MySessionStore:
    def __init__(self):
        self.conn = registry_db.get_db()
```

### Violation: SQL Schema in Code
```python
# ❌ WRONG
def init():
    conn.execute("""
        CREATE TABLE IF NOT EXISTS my_table (
            id INTEGER PRIMARY KEY
        )
    """)

# ✅ CORRECT
# Create file: agentos/store/migrations/0042_add_my_table.py
def upgrade(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS my_table (
            id INTEGER PRIMARY KEY
        )
    """)
```

### Violation: Multiple get_db() Functions
```python
# ❌ WRONG
def get_db():
    return sqlite3.connect("my.db")

# ✅ CORRECT
# Delete your get_db() and use:
from agentos.core.db import registry_db
# Use registry_db.get_db() everywhere
```

### Violation: Implicit External I/O in Chat Core
```python
# ❌ WRONG - Direct call to comm_adapter in engine.py
class ChatEngine:
    def handle_message(self, query: str):
        # Implicit external I/O - FORBIDDEN!
        results = self.comm_adapter.search(query, "session1", "task1")
        return results

# ✅ CORRECT - Use /comm commands
class ChatEngine:
    def handle_message(self, query: str):
        # Prompt user to use explicit command
        return "To search the web, use: /comm search <query>"
```

## Gate Details

| Gate | Purpose | Run Time |
|------|---------|----------|
| gate_no_sqlite_connect_enhanced.py | Detect direct DB connections | ~2-3s |
| gate_no_duplicate_tables.py | Check schema for duplicates | ~0.5s |
| gate_no_sql_in_code.py | Ensure migrations for schema changes | ~2-3s |
| gate_single_db_entry.py | Verify single get_db() function | ~2-3s |
| gate_no_implicit_external_io.py | Block implicit external I/O in Chat | ~1-2s |

**Total run time**: ~8-12 seconds

## CI Integration

Gates run automatically on:
- Every push to `master`, `main`, `develop`
- Every pull request to these branches

View results: GitHub Actions → "DB Integrity Gate"

## Whitelist

Legacy files are temporarily whitelisted during migration period. See each gate script for the whitelist.

**Goal**: Reduce whitelist to <10 permanent entries

## Bypass (Emergency Only)

```bash
# Bypass pre-commit hook (NOT RECOMMENDED)
git commit --no-verify

# CI cannot be bypassed - you must fix the code
```

**After emergency bypass**:
1. Create issue documenting the bypass
2. Create task to fix violation
3. Notify team

## Troubleshooting

### Gate fails locally
1. Read the gate output (tells you exactly what's wrong)
2. Fix the violation using examples above
3. Re-run: `./scripts/gates/run_all_gates.sh`
4. Commit when green

### Gate fails in CI
1. Check CI logs for details
2. Run the same gate locally
3. Fix and push
4. Verify CI passes

### False positive
1. Verify the code is actually correct
2. Check if file should be whitelisted
3. Submit issue if gate logic is wrong

## Documentation

Full documentation: [docs/GATE_SYSTEM.md](../../docs/GATE_SYSTEM.md)

Topics covered:
- Architecture and design
- Detailed gate reference
- Whitelist management
- Best practices
- Troubleshooting guide
- Metrics and roadmap

## Support

- 📖 Full docs: `docs/GATE_SYSTEM.md`
- 🐛 Report issues: GitHub Issues with "Gate System" label
- 💬 Questions: #database or #architecture channels
- 🕒 Office hours: Thursday 2-3pm

## Architecture Principles

1. **Single DB Instance**: One `registry.sqlite`, one entry point
2. **Schema as Code**: All schema changes via migrations
3. **Unified Access**: All DB access via `registry_db.get_db()`

## Files

```
scripts/gates/
├── README.md                              # This file
├── run_all_gates.sh                       # Run all gates
├── install_pre_commit_hook.sh             # Install git hook
├── gate_no_sqlite_connect_enhanced.py     # Gate 1: Enhanced connection check
├── gate_no_duplicate_tables.py            # Gate 2: Schema duplication check
├── gate_no_sql_in_code.py                 # Gate 3: Migration enforcement
├── gate_single_db_entry.py                # Gate 4: Single entry point check
└── gate_no_implicit_external_io.py        # Gate 5: External I/O enforcement

.github/workflows/
└── gate-db-integrity.yml                  # CI workflow

docs/
└── GATE_SYSTEM.md                         # Full documentation
```
