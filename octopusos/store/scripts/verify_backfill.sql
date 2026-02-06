-- v21 Backfill 验证脚本

-- 1. 检查冗余列覆盖率
SELECT
    'Coverage' AS metric,
    COUNT(*) AS total_rows,
    SUM(CASE WHEN source_event_ts IS NOT NULL THEN 1 ELSE 0 END) AS filled_rows,
    ROUND(100.0 * SUM(CASE WHEN source_event_ts IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 2) AS coverage_pct
FROM task_audits
WHERE event_type LIKE '%SUPERVISOR%';

-- 2. 检查数据一致性（payload vs 冗余列）
-- 注意: 由于 fallback 机制，部分记录可能不完全匹配
SELECT
    'Consistency Check' AS metric,
    COUNT(*) AS checked_rows,
    SUM(CASE
        WHEN json_extract(payload, '$.source_event_ts') = source_event_ts THEN 1
        WHEN json_extract(payload, '$.source_event_ts') IS NULL AND source_event_ts IS NOT NULL THEN 1
        ELSE 0
    END) AS consistent_rows
FROM task_audits
WHERE source_event_ts IS NOT NULL
  AND payload IS NOT NULL
  AND event_type LIKE '%SUPERVISOR%'
LIMIT 100;

-- 3. 统计各事件类型的覆盖率
SELECT
    event_type,
    COUNT(*) AS total,
    SUM(CASE WHEN source_event_ts IS NOT NULL THEN 1 ELSE 0 END) AS filled,
    ROUND(100.0 * SUM(CASE WHEN source_event_ts IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct
FROM task_audits
WHERE event_type LIKE '%SUPERVISOR%'
GROUP BY event_type
ORDER BY total DESC;

-- 4. 检查索引使用（性能验证）
EXPLAIN QUERY PLAN
SELECT decision_id, source_event_ts, supervisor_processed_at
FROM task_audits
WHERE source_event_ts >= datetime('now', '-1 day')
  AND source_event_ts IS NOT NULL;

-- 5. 检查时间戳范围（数据合理性）
SELECT
    'Timestamp Range Check' AS metric,
    MIN(source_event_ts) AS earliest_source_ts,
    MAX(source_event_ts) AS latest_source_ts,
    MIN(supervisor_processed_at) AS earliest_processed_at,
    MAX(supervisor_processed_at) AS latest_processed_at
FROM task_audits
WHERE source_event_ts IS NOT NULL
  AND event_type LIKE '%SUPERVISOR%';

-- 6. 检查 NULL 值分布
SELECT
    'Null Distribution' AS metric,
    SUM(CASE WHEN source_event_ts IS NULL THEN 1 ELSE 0 END) AS source_ts_null,
    SUM(CASE WHEN supervisor_processed_at IS NULL THEN 1 ELSE 0 END) AS processed_at_null,
    SUM(CASE WHEN source_event_ts IS NULL AND supervisor_processed_at IS NULL THEN 1 ELSE 0 END) AS both_null
FROM task_audits
WHERE event_type LIKE '%SUPERVISOR%';

-- 7. 抽样检查：显示前 10 条记录的数据
SELECT
    audit_id,
    event_type,
    source_event_ts,
    supervisor_processed_at,
    json_extract(payload, '$.source_event_ts') AS payload_source_ts,
    json_extract(payload, '$.supervisor_processed_at') AS payload_processed_at,
    created_at
FROM task_audits
WHERE event_type LIKE '%SUPERVISOR%'
ORDER BY created_at DESC
LIMIT 10;

-- 8. 检查决策延迟（lag）计算示例
-- 这是 Lead Agent 会使用的典型查询
SELECT
    decision_id,
    source_event_ts,
    supervisor_processed_at,
    ROUND((julianday(supervisor_processed_at) - julianday(source_event_ts)) * 86400, 2) AS lag_seconds
FROM task_audits
WHERE source_event_ts IS NOT NULL
  AND supervisor_processed_at IS NOT NULL
  AND event_type LIKE '%SUPERVISOR%'
ORDER BY lag_seconds DESC
LIMIT 10;
