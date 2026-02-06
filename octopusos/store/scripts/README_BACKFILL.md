# Backfill v21 冗余列使用指南

## 概述

`backfill_audit_decision_fields.py` 脚本用于将历史 `task_audits` 记录的 payload JSON 字段提取并填充到 v21 冗余列。

**适用场景**:
- 已执行 v21 migration
- 但历史数据的冗余列为 NULL
- 需要提升历史数据的查询性能

## 前提条件

1. ✅ 已执行 v21 migration
2. ✅ 数据库备份（建议）

## 使用方法

### 1. 预览模式（推荐首次使用）

```bash
cd agentos/store/scripts
python backfill_audit_decision_fields.py --dry-run
```

输出示例：
```
============================================================
Backfill v21 冗余列
============================================================
数据库路径:    /Users/user/.agentos/store.db
批量大小:      1,000
模式:          DRY-RUN（预览）
============================================================

需要 backfill 的记录数: 5,432

--- Batch 1 ---
[DRY-RUN] audit_id=123: 将填充 source_event_ts=2026-01-20T10:00:00, supervisor_processed_at=2026-01-20T10:00:05
...
进度: 1,000/5,432 (18.4%)
速度: 2000 行/秒
预计剩余时间: 2.2 分钟
```

### 2. 实际执行

```bash
python backfill_audit_decision_fields.py
```

### 3. 自定义参数

```bash
# 自定义批量大小（提升性能）
python backfill_audit_decision_fields.py --batch-size 5000

# 指定数据库路径
python backfill_audit_decision_fields.py --db-path /path/to/store.db
```

## 参数说明

| 参数 | 默认值 | 说明 |
|-----|--------|------|
| `--db-path` | `~/.agentos/store.db` | 数据库路径 |
| `--batch-size` | 1000 | 批量处理大小（行数） |
| `--dry-run` | False | 预览模式（不实际更新） |

## 性能建议

| 记录数 | 推荐 batch_size | 预计耗时 |
|--------|----------------|----------|
| < 1万 | 1000（默认） | < 1 分钟 |
| 1万 - 10万 | 5000 | 1-5 分钟 |
| > 10万 | 10000 | 5-30 分钟 |

## 验证结果

```sql
-- 检查填充率
SELECT
    COUNT(*) AS total_rows,
    SUM(CASE WHEN source_event_ts IS NOT NULL THEN 1 ELSE 0 END) AS filled_rows,
    ROUND(100.0 * SUM(CASE WHEN source_event_ts IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 2) AS coverage_pct
FROM task_audits
WHERE event_type LIKE '%SUPERVISOR%';

-- 期望: coverage_pct 接近 100%
```

## 常见问题

### Q1: 需要停止 Lead Agent 吗？

**A**: 不需要。Backfill 使用批量事务，不会长时间锁表。但建议在低峰期执行。

### Q2: 可以重复执行吗？

**A**: 可以。脚本是幂等的，已填充的记录会自动跳过。

### Q3: 如果中断了怎么办？

**A**: 直接重新执行，脚本会自动从未填充的记录继续。

### Q4: Backfill 失败会影响数据吗？

**A**: 不会。使用事务批量提交，每批失败会回滚该批，不影响其他批次。

## 错误排查

### 错误 1: "数据库未执行 v21 migration"

**解决**: 先执行 migration
```bash
sqlite3 ~/.agentos/store.db < agentos/store/migrations/v21_audit_decision_fields.sql
```

### 错误 2: "无法提取时间戳（payload 缺少字段）"

**原因**: 部分记录的 payload 不包含时间戳字段

**影响**: 这些记录会跳过，使用 created_at 作为 fallback

**解决**: 正常，无需处理（Lead Agent 会 fallback 到 payload）

## 监控

运行时会输出：
- 进度百分比
- 处理速度（行/秒）
- 预计剩余时间
- 失败记录数

示例：
```
进度: 3,500/5,432 (64.4%)
速度: 1800 行/秒
预计剩余时间: 1.1 分钟
```

## 字段提取逻辑

脚本会按优先级尝试从 payload JSON 提取以下字段：

### source_event_ts
尝试顺序：
1. `source_event_ts`
2. `source_ts`
3. `event_timestamp`
4. `task_created_at`
5. Fallback: 使用记录的 `created_at`

### supervisor_processed_at
尝试顺序：
1. `supervisor_processed_at`
2. `processed_at`
3. `timestamp`
4. Fallback: 使用记录的 `created_at`

## 幂等性保证

脚本只处理 `source_event_ts IS NULL OR supervisor_processed_at IS NULL` 的记录，因此：
- 已填充的记录会自动跳过
- 可以安全地重复执行
- 中断后可以从断点继续

## 事务处理

- 每个 batch 使用一个事务
- Batch 内的所有更新要么全部成功，要么全部回滚
- 不会产生部分更新的不一致状态

---

**文档版本**: 1.0.0
**最后更新**: 2026-01-28
