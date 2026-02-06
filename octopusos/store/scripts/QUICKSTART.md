# Backfill Quick Start Guide

## TL;DR

```bash
# 1. Backup database
cp ~/.agentos/store.db ~/.agentos/store.db.backup

# 2. Preview (dry-run)
python3 backfill_audit_decision_fields.py --dry-run

# 3. Execute backfill
python3 backfill_audit_decision_fields.py

# 4. Verify results
sqlite3 ~/.agentos/store.db < verify_backfill.sql
```

## What does this do?

Extracts timestamp fields from `task_audits.payload` JSON and populates redundant columns (`source_event_ts`, `supervisor_processed_at`) for faster queries.

**Before (v20)**: Query must parse JSON
```sql
SELECT payload FROM task_audits WHERE event_type='SUPERVISOR_DECISION'
-- Then extract JSON in application code
```

**After (v21)**: Direct column access
```sql
SELECT source_event_ts, supervisor_processed_at
FROM task_audits
WHERE event_type='SUPERVISOR_DECISION'
  AND source_event_ts IS NOT NULL
-- Uses index idx_task_audits_event_source_ts
```

## When to run this?

- After applying v21 migration
- When you need to query historical decision lag/latency
- When historical audit queries are slow

## How long does it take?

| Records | Time |
|---------|------|
| < 10k | < 1 min |
| 10k - 100k | 1-5 min |
| > 100k | 5-30 min |

## Command Options

```bash
# Preview mode (no changes)
python3 backfill_audit_decision_fields.py --dry-run

# Default execution (batch_size=1000)
python3 backfill_audit_decision_fields.py

# Faster for large DBs (batch_size=5000)
python3 backfill_audit_decision_fields.py --batch-size 5000

# Custom database path
python3 backfill_audit_decision_fields.py --db-path /path/to/store.db

# Show help
python3 backfill_audit_decision_fields.py --help
```

## Expected Output

```
============================================================
Backfill v21 冗余列
============================================================
数据库路径:    /Users/user/.agentos/store.db
批量大小:      1,000
模式:          实际执行
============================================================

需要 backfill 的记录数: 5,432

--- Batch 1 ---
进度: 1,000/5,432 (18.4%)
速度: 2000 行/秒
预计剩余时间: 2.2 分钟

--- Batch 2 ---
进度: 2,000/5,432 (36.8%)
速度: 1950 行/秒
预计剩余时间: 1.8 分钟

...

============================================================
Backfill 统计摘要
============================================================
总记录数:           5,432
已填充（跳过）:     0
成功填充:           5,420
解析失败:           0
缺少字段:           12
更新行数:           5,420
============================================================
最终覆盖率:         99.78%

✅ Backfill 完成！
```

## Verification

```bash
# Check coverage percentage
sqlite3 ~/.agentos/store.db "
SELECT
    COUNT(*) AS total,
    SUM(CASE WHEN source_event_ts IS NOT NULL THEN 1 ELSE 0 END) AS filled,
    ROUND(100.0 * SUM(CASE WHEN source_event_ts IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct
FROM task_audits
WHERE event_type LIKE '%SUPERVISOR%';"

# Expected: pct close to 100%
```

## Troubleshooting

### "数据库未执行 v21 migration"
```bash
sqlite3 ~/.agentos/store.db < agentos/store/migrations/v21_audit_decision_fields.sql
```

### "数据库文件不存在"
```bash
ls -l ~/.agentos/store.db
# Or use --db-path to specify location
```

### Low coverage (<95%)
- Normal for old data without timestamps in payload
- Check: `sqlite3 store.db < verify_backfill.sql`
- Fallback mechanism uses `created_at` when payload missing fields

### Script interrupted
- Just re-run - it's idempotent
- Only processes records with NULL redundant columns

## Safety Features

- **Dry-run mode**: Preview changes without executing
- **Batch transactions**: Partial failures don't corrupt data
- **Idempotent**: Safe to run multiple times
- **Non-destructive**: Only fills NULL columns, doesn't modify existing data
- **Progress tracking**: Real-time progress and ETA

## Need more help?

- Full guide: [README_BACKFILL.md](./README_BACKFILL.md)
- All scripts: [README.md](./README.md)
- Run tests: `python3 test_backfill.py`

---

**Estimated time to run**: 2-5 minutes (typical database)
**Risk level**: Low (read payload, write NULL columns)
**Required downtime**: None (concurrent access supported)
