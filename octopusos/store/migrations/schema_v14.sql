-- Migration v0.14: Supervisor MVP
-- Adds Supervisor tables for event ingestion, deduplication, and checkpointing
-- Migration from v0.13 -> v0.14

-- ============================================
-- Supervisor Inbox: 事件去重和持久化
-- ============================================

CREATE TABLE IF NOT EXISTS supervisor_inbox (
    event_id TEXT PRIMARY KEY,               -- 全局唯一事件 ID（UUID 或 audit_id）
    task_id TEXT NOT NULL,                   -- 关联的任务 ID
    event_type TEXT NOT NULL,                -- 事件类型
    source TEXT NOT NULL,                    -- 'eventbus' 或 'polling'
    payload TEXT,                            -- JSON 事件载荷
    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- 接收时间
    processed_at TIMESTAMP,                  -- 处理完成时间（NULL = 未处理）
    status TEXT DEFAULT 'pending',           -- pending|processing|completed|failed
    error_message TEXT,                      -- 处理失败时的错误信息
    retry_count INTEGER DEFAULT 0,           -- 重试次数

    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
);

-- 索引优化
CREATE INDEX IF NOT EXISTS idx_supervisor_inbox_task ON supervisor_inbox(task_id);
CREATE INDEX IF NOT EXISTS idx_supervisor_inbox_status ON supervisor_inbox(status);
CREATE INDEX IF NOT EXISTS idx_supervisor_inbox_received ON supervisor_inbox(received_at DESC);
CREATE INDEX IF NOT EXISTS idx_supervisor_inbox_processed ON supervisor_inbox(processed_at DESC);
CREATE INDEX IF NOT EXISTS idx_supervisor_inbox_pending ON supervisor_inbox(status, received_at)
    WHERE status = 'pending';  -- 快速查询待处理事件

-- ============================================
-- Supervisor Checkpoint: Polling 游标
-- ============================================

CREATE TABLE IF NOT EXISTS supervisor_checkpoint (
    checkpoint_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_table TEXT NOT NULL,              -- 'task_audits' 或其他事件源表
    last_seen_id INTEGER NOT NULL,           -- 最后处理的 ID（用于增量扫描）
    last_seen_ts TIMESTAMP,                  -- 最后处理的时间戳（辅助字段）
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- 游标更新时间
    metadata TEXT,                           -- JSON: 额外信息（如扫描策略、统计等）

    UNIQUE(source_table)                     -- 每个源表只有一个 checkpoint
);

-- 为快速查询创建索引
CREATE INDEX IF NOT EXISTS idx_supervisor_checkpoint_table ON supervisor_checkpoint(source_table);
CREATE INDEX IF NOT EXISTS idx_supervisor_checkpoint_updated ON supervisor_checkpoint(updated_at DESC);

-- ============================================
-- 增强 task_audits 索引（优化 Supervisor 查询）
-- ============================================

-- 复合索引：event_type + created_at（用于 Polling 增量扫描）
CREATE INDEX IF NOT EXISTS idx_task_audits_event_created ON task_audits(event_type, created_at DESC);

-- 复合索引：task_id + event_type（用于查询特定任务的特定事件）
CREATE INDEX IF NOT EXISTS idx_task_audits_task_event ON task_audits(task_id, event_type);

-- ============================================
-- 初始化 Checkpoint（安全启动点）
-- ============================================

-- 为 task_audits 初始化 checkpoint（从当前最大 ID 开始）
INSERT OR IGNORE INTO supervisor_checkpoint (source_table, last_seen_id, last_seen_ts, metadata)
SELECT
    'task_audits',
    COALESCE(MAX(audit_id), 0),
    CURRENT_TIMESTAMP,
    json_object('initialized', 'v0.14', 'note', 'Start from current state, no backfill')
FROM task_audits;

-- ============================================
-- 审计事件类型常量（用于 Supervisor）
-- ============================================

-- Supervisor 专用的审计事件类型（约定）
-- SUPERVISOR_ALLOWED       - 允许继续
-- SUPERVISOR_PAUSED        - 暂停任务
-- SUPERVISOR_BLOCKED       - 阻塞任务
-- SUPERVISOR_RETRY_RECOMMENDED - 建议重试
-- SUPERVISOR_DECISION      - 一般决策记录
-- SUPERVISOR_ERROR         - Supervisor 处理错误

-- ============================================
-- 注释和元数据
-- ============================================

-- Supervisor 设计原则：
-- 1. EventBus 是快路径（实时通知），Polling 是慢路径（兜底保证）
-- 2. DB 是唯一真相源（EventBus 只做唤醒信号）
-- 3. supervisor_inbox 通过 UNIQUE(event_id) 实现去重
-- 4. Checkpoint 机制确保崩溃后可恢复、不丢事件
-- 5. 所有决策写入 task_audits，完全可审计

-- Update schema version
INSERT OR REPLACE INTO schema_version (version) VALUES ('0.14.0');
