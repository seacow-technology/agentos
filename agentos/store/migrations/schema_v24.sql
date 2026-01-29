-- Migration v0.24: Task Audits Foreign Key Cascade
-- Adds ON DELETE CASCADE to task_audits.task_id foreign key
-- Migration from v0.23 -> v0.24
--
-- 目的: 修复 Windows 并发环境下的外键约束冲突
-- 问题: 任务删除时,审计记录插入可能引用不存在的 task_id
-- 解决: 添加 ON DELETE CASCADE,在删除任务时自动清理相关审计记录

-- ============================================
-- 重建 task_audits 表 (SQLite 不支持 ALTER CONSTRAINT)
-- ============================================

-- 1. 备份现有数据
CREATE TABLE task_audits_backup AS SELECT * FROM task_audits;

-- 2. 删除旧表
DROP TABLE task_audits;

-- 3. 重建表结构 (添加 ON DELETE CASCADE)
CREATE TABLE task_audits (
    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    repo_id TEXT,
    level TEXT DEFAULT 'info',
    event_type TEXT NOT NULL,
    payload TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- v15 迁移添加的列 (决策追踪)
    decision_id TEXT,
    source_event_ts TEXT,
    supervisor_processed_at TEXT,

    -- v17 迁移添加的列 (Guardian 验证)
    verdict_id TEXT,

    -- 关键修改: 添加 ON DELETE CASCADE
    -- 当 task 被删除时,自动删除相关审计记录
    FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE
);

-- 4. 恢复数据 (只保留有效的 task_id)
-- 这会清理所有孤立的审计记录 (task_id 不存在的记录)
INSERT INTO task_audits
SELECT a.* FROM task_audits_backup a
WHERE EXISTS (SELECT 1 FROM tasks t WHERE t.task_id = a.task_id);

-- 5. 清理备份表
DROP TABLE task_audits_backup;

-- ============================================
-- 重建索引 (从 v06, v15, v17, v20, v21 复制)
-- ============================================

-- 基础索引 (v06)
CREATE INDEX IF NOT EXISTS idx_task_audits_task ON task_audits(task_id);
CREATE INDEX IF NOT EXISTS idx_task_audits_level ON task_audits(level);
CREATE INDEX IF NOT EXISTS idx_task_audits_event ON task_audits(event_type);
CREATE INDEX IF NOT EXISTS idx_task_audits_created ON task_audits(created_at DESC);

-- 跨仓库审计索引 (v20)
CREATE INDEX IF NOT EXISTS idx_task_audits_repo ON task_audits(repo_id);
CREATE INDEX IF NOT EXISTS idx_task_audits_task_repo ON task_audits(task_id, repo_id);
CREATE INDEX IF NOT EXISTS idx_task_audits_repo_created ON task_audits(repo_id, created_at DESC);

-- 决策追踪索引 (v15)
CREATE INDEX IF NOT EXISTS idx_task_audits_task_ts
ON task_audits(task_id, created_at);

CREATE UNIQUE INDEX IF NOT EXISTS idx_task_audits_decision_id
ON task_audits(decision_id)
WHERE decision_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_task_audits_lag
ON task_audits(supervisor_processed_at);

CREATE INDEX IF NOT EXISTS idx_task_audits_event_created
ON task_audits(event_type, created_at DESC)
WHERE event_type LIKE 'SUPERVISOR_%';

CREATE INDEX IF NOT EXISTS idx_task_audits_task_event_type
ON task_audits(task_id, event_type, created_at DESC);

-- Guardian 验证索引 (v17)
CREATE INDEX IF NOT EXISTS idx_task_audits_verdict_id
ON task_audits(verdict_id)
WHERE verdict_id IS NOT NULL;

-- 性能优化索引 (v21)
CREATE INDEX IF NOT EXISTS idx_task_audits_source_event_ts
ON task_audits(source_event_ts)
WHERE source_event_ts IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_task_audits_decision_lag
ON task_audits(source_event_ts, supervisor_processed_at)
WHERE source_event_ts IS NOT NULL AND supervisor_processed_at IS NOT NULL;

-- ============================================
-- 设计说明
-- ============================================

-- ON DELETE CASCADE 行为:
-- - 当 tasks 表中的记录被删除时,task_audits 中所有引用该 task_id 的记录会自动删除
-- - 这避免了外键约束冲突 (FOREIGN KEY constraint failed)
-- - 符合审计记录的生命周期管理原则: 任务删除 = 审计记录也应清理

-- Windows 并发优化:
-- - 与 store/__init__.py 和 session_store.py 的 PRAGMA 配置配合使用
-- - WAL 模式 + busy_timeout 提高并发写入性能
-- - CASCADE 约束消除竞态条件下的外键冲突

-- 数据完整性保证:
-- - 迁移过程会自动清理孤立数据 (WHERE EXISTS 子查询)
-- - 所有索引都重建,确保查询性能不受影响
-- - 幂等性设计: 可重复执行而不会出错

-- Update schema version
INSERT OR REPLACE INTO schema_version (version) VALUES ('0.24.0');
