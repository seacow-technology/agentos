-- Migration v0.15: Governance Decision Replay Infrastructure
-- Adds indexes and columns for Decision Replay and Trace Assembly
-- Migration from v0.14 -> v0.15
--
-- 🔒 SEMANTIC FREEZE (F-4): Decision Audit as Single Source of Truth
-- -------------------------------------------------------------------------
-- task_audits table + DecisionSnapshot = AUTHORITATIVE source
--
-- ✅ ALLOWED:
--    - Query task_audits for governance data
--    - Derive metrics from decision snapshots
--    - Use decision_id as primary key for replay
--
-- ❌ FORBIDDEN:
--    - NO parallel audit systems (e.g., separate "shadow audit" table)
--    - NO dual-write patterns (writing same data to multiple tables)
--    - NO audit data inference (reconstructing audit from events)
--
-- GUARANTEE: task_audits is the SINGLE SOURCE OF TRUTH for all governance decisions.
-- Reference: ADR-004 Section F-4

-- ============================================
-- 1. Decision ID 冗余列
-- ============================================
-- 为 task_audits 添加 decision_id 列，用于快速查询单个决策
-- decision_id 来自 payload 中的 decision_snapshot.decision_id

ALTER TABLE task_audits ADD COLUMN decision_id TEXT;

-- ============================================
-- 2. Trace Assembly 索引
-- ============================================

-- 索引：按 task_id + created_at 查询完整 trace
-- 用途：TraceAssembler.get_decision_trace() 需要按时间顺序获取所有决策
CREATE INDEX IF NOT EXISTS idx_task_audits_task_ts
ON task_audits(task_id, created_at);

-- 唯一索引：按 decision_id 查询单个决策
-- 用途：TraceAssembler.get_decision(decision_id) 快速定位
-- 使用 WHERE 条件索引，只索引有 decision_id 的行
CREATE UNIQUE INDEX IF NOT EXISTS idx_task_audits_decision_id
ON task_audits(decision_id)
WHERE decision_id IS NOT NULL;

-- ============================================
-- 3. 事件表索引优化
-- ============================================

-- NOTE: task_events 和 supervisor_inbox 表在此版本中未定义
-- 这些索引在相应表创建后才会生效
-- 如果表不存在，索引创建会被跳过（使用 IF NOT EXISTS 保证幂等性）

-- task_events 表索引（如果表存在）
-- 用途：按 task_id + created_at 查询事件历史
-- CREATE INDEX IF NOT EXISTS idx_task_events_task_ts
-- ON task_events(task_id, created_at);

-- supervisor_inbox 表索引（如果表存在）
-- 用途：按 task_id + processed_at 查询已处理事件
-- CREATE INDEX IF NOT EXISTS idx_supervisor_inbox_task_processed
-- ON supervisor_inbox(task_id, processed_at);

-- ============================================
-- 4. Decision Lag 统计列
-- ============================================

-- source_event_ts: 源事件的时间戳（从 event.ts 提取）
-- 用途：计算 decision lag = supervisor_processed_at - source_event_ts
ALTER TABLE task_audits ADD COLUMN source_event_ts TEXT;

-- supervisor_processed_at: Supervisor 处理完成的时间戳
-- 用途：记录决策实际处理时间，用于性能分析
ALTER TABLE task_audits ADD COLUMN supervisor_processed_at TEXT;

-- 索引：按 supervisor_processed_at 查询，用于 lag 统计
CREATE INDEX IF NOT EXISTS idx_task_audits_lag
ON task_audits(supervisor_processed_at);

-- ============================================
-- 5. 统计查询优化索引
-- ============================================

-- 复合索引：按 event_type + created_at 统计决策类型分布
-- 用途：StatsCalculator.get_decision_type_stats()
CREATE INDEX IF NOT EXISTS idx_task_audits_event_created
ON task_audits(event_type, created_at DESC)
WHERE event_type LIKE 'SUPERVISOR_%';

-- 复合索引：按 task_id + event_type 查询任务的特定决策
-- 用途：get_summary() 查询最后一次 BLOCKED 决策
CREATE INDEX IF NOT EXISTS idx_task_audits_task_event_type
ON task_audits(task_id, event_type, created_at DESC);

-- ============================================
-- 6. 事件去重和幂等性索引
-- ============================================

-- supervisor_inbox 已有 event_id PRIMARY KEY，但添加复合索引优化查询
-- 用途：检查特定任务的事件是否已处理
CREATE INDEX IF NOT EXISTS idx_supervisor_inbox_task_event
ON supervisor_inbox(task_id, event_id);

-- ============================================
-- 注释和元数据
-- ============================================

-- Decision Replay 设计原则：
-- 1. 不可变性：decision_id 一旦写入就不可修改
-- 2. 完整性：捕获 event -> decision -> action 的完整链路
-- 3. 可追溯性：通过 task_id + ts 可以重建完整的决策历史
-- 4. 性能优化：通过索引支持高效的 trace 查询和统计分析

-- 索引策略：
-- - task_id + ts: 支持时间序列查询（trace assembly）
-- - decision_id: 支持单点查询（replay single decision）
-- - event_type + ts: 支持决策类型统计
-- - supervisor_processed_at: 支持 lag 分析

-- Update schema version
INSERT OR REPLACE INTO schema_version (version) VALUES ('0.15.0');
