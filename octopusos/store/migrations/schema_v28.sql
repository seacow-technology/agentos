-- Migration v0.28: Add exit_reason field to tasks table
-- Adds exit_reason field to track why task execution stopped
-- Migration from v0.27 -> v0.28
--
-- 目的: 明确 Runner 的终止原因，避免"假完成"
-- 背景:
--   - 当前 tasks 表没有 exit_reason 字段
--   - 任务停止原因不明确（正常完成？超限？被阻塞？）
--   - AUTONOMOUS 模式不应该因为需要批准而停止，应该标记为 blocked
-- 改进:
--   - 添加 exit_reason 字段记录终止原因
--   - 支持的原因: done, max_iterations, blocked, fatal_error, user_cancelled
--   - 区分"完成"和"被阻塞"两种状态

-- ============================================
-- 阶段 1: 添加 exit_reason 字段
-- ============================================

-- 1. 添加 exit_reason 列（允许 NULL，因为已有任务可能没有此信息）
ALTER TABLE tasks ADD COLUMN exit_reason TEXT;

-- 2. 创建索引（用于按终止原因过滤任务）
CREATE INDEX IF NOT EXISTS idx_tasks_exit_reason
ON tasks(exit_reason);

-- 3. 创建复合索引（用于状态+终止原因查询）
CREATE INDEX IF NOT EXISTS idx_tasks_status_exit_reason
ON tasks(status, exit_reason);

-- ============================================
-- 阶段 2: 添加约束验证触发器
-- ============================================

-- 触发器 1: 插入时验证 exit_reason 取值范围
CREATE TRIGGER IF NOT EXISTS check_tasks_exit_reason_insert
BEFORE INSERT ON tasks
FOR EACH ROW
WHEN NEW.exit_reason IS NOT NULL
BEGIN
    SELECT CASE
        WHEN NEW.exit_reason NOT IN ('done', 'max_iterations', 'blocked', 'fatal_error', 'user_cancelled', 'unknown')
        THEN RAISE(ABORT, 'Invalid exit_reason: must be one of (done, max_iterations, blocked, fatal_error, user_cancelled, unknown)')
    END;
END;

-- 触发器 2: 更新时验证 exit_reason 取值范围
CREATE TRIGGER IF NOT EXISTS check_tasks_exit_reason_update
BEFORE UPDATE OF exit_reason ON tasks
FOR EACH ROW
WHEN NEW.exit_reason IS NOT NULL
BEGIN
    SELECT CASE
        WHEN NEW.exit_reason NOT IN ('done', 'max_iterations', 'blocked', 'fatal_error', 'user_cancelled', 'unknown')
        THEN RAISE(ABORT, 'Invalid exit_reason: must be one of (done, max_iterations, blocked, fatal_error, user_cancelled, unknown)')
    END;
END;

-- ============================================
-- 阶段 3: 添加业务逻辑触发器
-- ============================================

-- 触发器 3: 当状态变为 blocked 时，自动记录审计日志
CREATE TRIGGER IF NOT EXISTS log_task_blocked
AFTER UPDATE OF status ON tasks
FOR EACH ROW
WHEN NEW.status = 'blocked' AND OLD.status != 'blocked'
BEGIN
    INSERT INTO task_audits (task_id, level, event_type, payload, created_at)
    VALUES (
        NEW.task_id,
        'warn',
        'TASK_BLOCKED',
        json_object(
            'from_status', OLD.status,
            'to_status', NEW.status,
            'exit_reason', NEW.exit_reason,
            'message', 'Task blocked: execution cannot continue without intervention'
        ),
        CURRENT_TIMESTAMP
    );
END;

-- ============================================
-- 设计说明
-- ============================================

-- exit_reason 取值说明:
-- - done: 任务正常完成
-- - max_iterations: 超过最大迭代次数
-- - blocked: 执行被阻塞（如 AUTONOMOUS 模式遇到需要批准的检查点）
-- - fatal_error: 致命错误导致无法继续
-- - user_cancelled: 用户主动取消
-- - unknown: 未知原因（兜底值）

-- 状态与 exit_reason 的关系:
-- - status='succeeded' → exit_reason='done'
-- - status='failed' → exit_reason='fatal_error' 或其他错误原因
-- - status='blocked' → exit_reason='blocked'
-- - status='canceled' → exit_reason='user_cancelled'
-- - status='running' → exit_reason 应为 NULL（尚未结束）

-- AUTONOMOUS 模式处理逻辑:
-- - AUTONOMOUS 模式遇到 awaiting_approval 检查点时
-- - 不应进入 awaiting_approval 状态（那是 INTERACTIVE/ASSISTED 模式的行为）
-- - 应该标记为 blocked 状态，exit_reason='blocked'
-- - 在审计日志中记录警告信息

-- Update schema version
INSERT OR REPLACE INTO schema_version (version) VALUES ('0.28.0');
