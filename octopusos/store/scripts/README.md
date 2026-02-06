# AgentOS Store Scripts

Maintenance and migration scripts for AgentOS storage layer.

## Available Scripts

### 1. backfill_audit_decision_fields.py

Backfills historical `task_audits` records by extracting JSON payload fields into v21 redundant columns (`source_event_ts`, `supervisor_processed_at`).

**Use case**: Improve query performance for historical data after v21 migration.

**Quick start**:
```bash
# Preview mode (recommended first run)
python3 backfill_audit_decision_fields.py --dry-run

# Execute backfill
python3 backfill_audit_decision_fields.py

# Custom batch size for better performance
python3 backfill_audit_decision_fields.py --batch-size 5000
```

See [README_BACKFILL.md](./README_BACKFILL.md) for detailed usage guide.

### 2. verify_backfill.sql

SQL queries to verify backfill results and check data consistency.

**Usage**:
```bash
sqlite3 ~/.agentos/store.db < verify_backfill.sql
```

**Checks**:
- Coverage percentage (% of records with filled redundant columns)
- Data consistency (payload JSON vs redundant columns)
- Event type distribution
- Index usage verification
- Timestamp range validation
- Lag calculation examples

### 3. test_backfill.py

Automated test suite for backfill script.

**Usage**:
```bash
python3 test_backfill.py
```

**Tests**:
- Timestamp extraction from various payload formats
- Fallback mechanisms
- Error handling (invalid JSON, missing fields)
- Event type filtering
- Full end-to-end backfill process

## Directory Structure

```
agentos/store/scripts/
├── __init__.py                          # Package init
├── README.md                            # This file
├── README_BACKFILL.md                   # Detailed backfill guide
├── backfill_audit_decision_fields.py    # Main backfill script
├── verify_backfill.sql                  # Verification queries
└── test_backfill.py                     # Test suite
```

## Prerequisites

### For backfill_audit_decision_fields.py

1. Python 3.8+
2. SQLite 3.35.0+ (for DROP COLUMN support)
3. v21 migration already applied
4. Database backup recommended

### For verify_backfill.sql

1. sqlite3 command-line tool
2. AgentOS database at `~/.agentos/store.db` (or custom path)

## Common Workflows

### First-time backfill

```bash
# 1. Backup database
cp ~/.agentos/store.db ~/.agentos/store.db.backup

# 2. Preview backfill (dry-run)
python3 backfill_audit_decision_fields.py --dry-run

# 3. Execute backfill
python3 backfill_audit_decision_fields.py

# 4. Verify results
sqlite3 ~/.agentos/store.db < verify_backfill.sql
```

### Incremental backfill

The script is idempotent - it only processes records where redundant columns are NULL.

```bash
# Run anytime to fill newly created records
python3 backfill_audit_decision_fields.py
```

### Performance tuning

For large databases (>100k records):

```bash
# Use larger batch size
python3 backfill_audit_decision_fields.py --batch-size 10000

# Run during low-traffic periods
# (script uses transactions but can still cause brief locks)
```

## Troubleshooting

### Error: "数据库未执行 v21 migration"

**Solution**: Apply v21 migration first
```bash
sqlite3 ~/.agentos/store.db < agentos/store/migrations/v21_audit_decision_fields.sql
```

### Error: "数据库文件不存在"

**Solution**: Check database path
```bash
# Default path
ls -l ~/.agentos/store.db

# Or specify custom path
python3 backfill_audit_decision_fields.py --db-path /path/to/store.db
```

### Low coverage percentage after backfill

**Possible causes**:
1. Payload JSON missing timestamp fields (expected for some old records)
2. Invalid JSON in payload (rare but possible)
3. Non-SUPERVISOR events (not processed by backfill)

**Check details**:
```sql
-- Find records with NULL redundant columns
SELECT audit_id, event_type, payload
FROM task_audits
WHERE (source_event_ts IS NULL OR supervisor_processed_at IS NULL)
  AND event_type LIKE '%SUPERVISOR%'
LIMIT 10;
```

### Performance issues during backfill

**Solutions**:
1. Increase batch size: `--batch-size 10000`
2. Run during low-traffic periods
3. Stop other intensive queries temporarily
4. Consider vacuuming database first: `sqlite3 store.db "VACUUM;"`

## Development

### Running tests

```bash
# Run test suite
python3 test_backfill.py

# Expected output: All tests PASSED
```

### Adding new scripts

1. Create script in `agentos/store/scripts/`
2. Make executable: `chmod +x script_name.py`
3. Add documentation to this README
4. Add tests if applicable

## Best Practices

1. **Always backup before backfill**: `cp store.db store.db.backup`
2. **Use dry-run first**: `--dry-run` flag to preview changes
3. **Monitor progress**: Script shows real-time progress and ETA
4. **Verify after backfill**: Run `verify_backfill.sql` to check results
5. **Run during low-traffic**: Minimize lock contention
6. **Check logs**: Review warnings for skipped records

## Performance Benchmarks

Based on testing:

| Records | Batch Size | Duration | Notes |
|---------|-----------|----------|-------|
| 1,000 | 1000 | ~0.5s | Default batch size |
| 10,000 | 1000 | ~5s | Standard use case |
| 10,000 | 5000 | ~3s | Optimized batch size |
| 100,000 | 10000 | ~30s | Large database |
| 1,000,000 | 10000 | ~5min | Very large database |

Note: Timings vary based on:
- Hardware (SSD vs HDD)
- Payload complexity
- Concurrent database access
- SQLite configuration

## Migration Compatibility

| Script | Schema Version | Backward Compatible | Notes |
|--------|---------------|---------------------|-------|
| backfill_audit_decision_fields.py | v0.21.0+ | Yes | Requires v21 columns |
| verify_backfill.sql | v0.21.0+ | Yes | Checks v21 columns |

## Support

For issues or questions:
1. Check [README_BACKFILL.md](./README_BACKFILL.md) for detailed guide
2. Run test suite: `python3 test_backfill.py`
3. Check verification queries: `sqlite3 store.db < verify_backfill.sql`
4. Review script help: `python3 backfill_audit_decision_fields.py --help`

---

**Last updated**: 2026-01-28
**Minimum AgentOS version**: 0.21.0
