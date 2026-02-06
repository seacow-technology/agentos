-- Migration v0.30: Recovery System - Work Items, Checkpoints, and Idempotency
-- Description: Database foundation for resumable execution (断点续跑)
-- Purpose: Enable reliable task recovery after interruption or failure
--
-- 背景:
--   - 支持任务中断后的断点续跑
--   - 提供工作项租约管理（lease management）
--   - 提供检查点证据型注册表
--   - 提供幂等性保障，减少重复执行
--
-- 核心概念:
--   - work_items: 可恢复的工作单元，支持租约和心跳
--   - checkpoints: 证据型检查点，记录执行进度
--   - idempotency_keys: 幂等性保障，防止重复执行
--
-- ============================================
-- 表 1: work_items - 工作项管理
-- ============================================
--
-- 用途: 管理可恢复的工作单元生命周期
-- 功能:
--   - 租约管理（lease_acquired_at, lease_expires_at）
--   - 心跳机制（heartbeat_at）
--   - 状态跟踪（pending, in_progress, completed, failed）
--   - 重试管理（retry_count, max_retries）
--

CREATE TABLE IF NOT EXISTS work_items (
    -- 主键和关联
    work_item_id TEXT PRIMARY KEY,  -- ULID or UUID
    task_id TEXT NOT NULL,          -- 关联任务 ID

    -- 工作项基本信息
    work_type TEXT NOT NULL,        -- 工作类型: 'tool_execution', 'llm_call', 'subtask', etc.
    status TEXT NOT NULL DEFAULT 'pending',  -- 状态: pending, in_progress, completed, failed, expired
    priority INTEGER DEFAULT 0,     -- 优先级（越大越优先）

    -- 租约管理 (Lease Management)
    lease_holder TEXT,              -- 租约持有者标识（worker_id, process_id）
    lease_acquired_at TIMESTAMP,    -- 租约获取时间
    lease_expires_at TIMESTAMP,     -- 租约过期时间
    heartbeat_at TIMESTAMP,         -- 最后心跳时间

    -- 重试管理
    retry_count INTEGER DEFAULT 0,  -- 当前重试次数
    max_retries INTEGER DEFAULT 3,  -- 最大重试次数

    -- 工作项数据
    input_data TEXT,                -- 工作项输入数据（JSON）
    output_data TEXT,               -- 工作项输出数据（JSON）
    error_message TEXT,             -- 错误信息（失败时记录）

    -- 时间戳
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,           -- 首次开始执行时间
    completed_at TIMESTAMP,         -- 完成时间
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- 外键约束
    FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE
);

-- ============================================
-- work_items 索引
-- ============================================

-- 索引 1: 按任务查询工作项
CREATE INDEX IF NOT EXISTS idx_work_items_task
ON work_items(task_id, status, created_at DESC);

-- 索引 2: 按状态查询（用于查找待处理工作项）
CREATE INDEX IF NOT EXISTS idx_work_items_status_priority
ON work_items(status, priority DESC, created_at ASC);

-- 索引 3: 租约过期查询（用于清理过期租约）
CREATE INDEX IF NOT EXISTS idx_work_items_lease_expiry
ON work_items(lease_expires_at)
WHERE lease_expires_at IS NOT NULL AND status = 'in_progress';

-- 索引 4: 租约持有者查询（用于心跳和租约续期）
CREATE INDEX IF NOT EXISTS idx_work_items_lease_holder
ON work_items(lease_holder, status)
WHERE lease_holder IS NOT NULL;

-- ============================================
-- work_items 触发器
-- ============================================

-- 触发器 1: 更新 updated_at 时间戳
CREATE TRIGGER IF NOT EXISTS update_work_items_timestamp
AFTER UPDATE ON work_items
FOR EACH ROW
BEGIN
    UPDATE work_items SET updated_at = CURRENT_TIMESTAMP
    WHERE work_item_id = NEW.work_item_id;
END;

-- 触发器 2: 验证状态转换
CREATE TRIGGER IF NOT EXISTS check_work_items_status
BEFORE UPDATE OF status ON work_items
FOR EACH ROW
BEGIN
    SELECT CASE
        -- 验证状态值合法性
        WHEN NEW.status NOT IN ('pending', 'in_progress', 'completed', 'failed', 'expired')
        THEN RAISE(ABORT, 'Invalid work_item status: must be one of (pending, in_progress, completed, failed, expired)')

        -- 不允许从终态转换
        WHEN OLD.status IN ('completed', 'failed') AND NEW.status != OLD.status
        THEN RAISE(ABORT, 'Cannot change status from terminal state')
    END;
END;

-- ============================================
-- 表 2: checkpoints - 检查点注册表
-- ============================================
--
-- 用途: 证据型检查点，记录任务执行进度
-- 特点:
--   - 只记录不修改（append-only）
--   - 支持细粒度恢复（恢复到任意检查点）
--   - 存储检查点快照数据
--

CREATE TABLE IF NOT EXISTS checkpoints (
    -- 主键和关联
    checkpoint_id TEXT PRIMARY KEY,     -- ULID or UUID
    task_id TEXT NOT NULL,              -- 关联任务 ID
    work_item_id TEXT,                  -- 关联工作项 ID（可选）

    -- 检查点基本信息
    checkpoint_type TEXT NOT NULL,      -- 类型: 'iteration_start', 'tool_executed', 'llm_response', 'approval_point', etc.
    sequence_number INTEGER NOT NULL,   -- 序号（任务内递增）

    -- 检查点数据
    snapshot_data TEXT NOT NULL,        -- 检查点快照数据（JSON）
    metadata TEXT,                      -- 元数据（JSON）

    -- 时间戳
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- 外键约束
    FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE,
    FOREIGN KEY (work_item_id) REFERENCES work_items(work_item_id) ON DELETE SET NULL
);

-- ============================================
-- checkpoints 索引
-- ============================================

-- 索引 1: 按任务查询检查点（按序号排序）
CREATE INDEX IF NOT EXISTS idx_checkpoints_task_sequence
ON checkpoints(task_id, sequence_number ASC);

-- 索引 2: 按工作项查询检查点
CREATE INDEX IF NOT EXISTS idx_checkpoints_work_item
ON checkpoints(work_item_id, sequence_number ASC)
WHERE work_item_id IS NOT NULL;

-- 索引 3: 按类型查询检查点
CREATE INDEX IF NOT EXISTS idx_checkpoints_type
ON checkpoints(checkpoint_type, created_at DESC);

-- 索引 4: 按创建时间查询（用于清理旧检查点）
CREATE INDEX IF NOT EXISTS idx_checkpoints_created_at
ON checkpoints(created_at DESC);

-- ============================================
-- checkpoints 触发器
-- ============================================

-- 触发器: 验证检查点类型
CREATE TRIGGER IF NOT EXISTS check_checkpoints_type
BEFORE INSERT ON checkpoints
FOR EACH ROW
BEGIN
    SELECT CASE
        WHEN NEW.checkpoint_type NOT IN (
            'iteration_start', 'iteration_end',
            'tool_executed', 'llm_response',
            'approval_point', 'state_transition',
            'manual_checkpoint', 'error_boundary'
        )
        THEN RAISE(ABORT, 'Invalid checkpoint_type: must be a recognized checkpoint type')
    END;
END;

-- ============================================
-- 表 3: idempotency_keys - 幂等性保障
-- ============================================
--
-- 用途: 防止重复执行
-- 功能:
--   - 记录幂等性键及其结果
--   - 支持请求去重
--   - 支持结果缓存
--

CREATE TABLE IF NOT EXISTS idempotency_keys (
    -- 主键
    idempotency_key TEXT PRIMARY KEY,  -- 幂等性键（由调用方生成）

    -- 关联信息
    task_id TEXT,                      -- 关联任务 ID（可选）
    work_item_id TEXT,                 -- 关联工作项 ID（可选）

    -- 请求和响应
    request_hash TEXT NOT NULL,        -- 请求哈希（用于验证请求一致性）
    response_data TEXT,                -- 响应数据（JSON）
    status TEXT NOT NULL DEFAULT 'pending',  -- 状态: pending, completed, failed

    -- 时间管理
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,            -- 完成时间
    expires_at TIMESTAMP,              -- 过期时间（用于清理）

    -- 外键约束（可选）
    FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE SET NULL,
    FOREIGN KEY (work_item_id) REFERENCES work_items(work_item_id) ON DELETE SET NULL
);

-- ============================================
-- idempotency_keys 索引
-- ============================================

-- 索引 1: 按任务查询幂等性键
CREATE INDEX IF NOT EXISTS idx_idempotency_keys_task
ON idempotency_keys(task_id, created_at DESC)
WHERE task_id IS NOT NULL;

-- 索引 2: 按工作项查询幂等性键
CREATE INDEX IF NOT EXISTS idx_idempotency_keys_work_item
ON idempotency_keys(work_item_id, created_at DESC)
WHERE work_item_id IS NOT NULL;

-- 索引 3: 按过期时间查询（用于清理过期键）
CREATE INDEX IF NOT EXISTS idx_idempotency_keys_expires_at
ON idempotency_keys(expires_at)
WHERE expires_at IS NOT NULL;

-- 索引 4: 按状态和创建时间查询
CREATE INDEX IF NOT EXISTS idx_idempotency_keys_status
ON idempotency_keys(status, created_at DESC);

-- ============================================
-- idempotency_keys 触发器
-- ============================================

-- 触发器: 验证状态值
CREATE TRIGGER IF NOT EXISTS check_idempotency_keys_status
BEFORE INSERT ON idempotency_keys
FOR EACH ROW
BEGIN
    SELECT CASE
        WHEN NEW.status NOT IN ('pending', 'completed', 'failed')
        THEN RAISE(ABORT, 'Invalid idempotency_key status: must be one of (pending, completed, failed)')
    END;
END;

-- ============================================
-- 设计说明和使用场景
-- ============================================

-- ===== work_items 表使用场景 =====
--
-- 1. 创建工作项:
--    INSERT INTO work_items (work_item_id, task_id, work_type, input_data)
--    VALUES ('work-123', 'task-456', 'tool_execution', '{"tool": "bash", "command": "ls"}');
--
-- 2. 获取待处理工作项（带租约）:
--    UPDATE work_items
--    SET status = 'in_progress',
--        lease_holder = 'worker-789',
--        lease_acquired_at = CURRENT_TIMESTAMP,
--        lease_expires_at = datetime(CURRENT_TIMESTAMP, '+5 minutes'),
--        heartbeat_at = CURRENT_TIMESTAMP
--    WHERE work_item_id = (
--        SELECT work_item_id FROM work_items
--        WHERE status = 'pending'
--        ORDER BY priority DESC, created_at ASC
--        LIMIT 1
--    );
--
-- 3. 心跳续租:
--    UPDATE work_items
--    SET heartbeat_at = CURRENT_TIMESTAMP,
--        lease_expires_at = datetime(CURRENT_TIMESTAMP, '+5 minutes')
--    WHERE work_item_id = 'work-123' AND lease_holder = 'worker-789';
--
-- 4. 完成工作项:
--    UPDATE work_items
--    SET status = 'completed',
--        output_data = '{"result": "success"}',
--        completed_at = CURRENT_TIMESTAMP,
--        lease_holder = NULL,
--        lease_expires_at = NULL
--    WHERE work_item_id = 'work-123';
--
-- 5. 清理过期租约:
--    UPDATE work_items
--    SET status = 'expired',
--        lease_holder = NULL,
--        lease_expires_at = NULL
--    WHERE status = 'in_progress'
--    AND lease_expires_at < CURRENT_TIMESTAMP;
--
-- ===== checkpoints 表使用场景 =====
--
-- 1. 创建检查点:
--    INSERT INTO checkpoints (checkpoint_id, task_id, checkpoint_type, sequence_number, snapshot_data)
--    VALUES ('ckpt-123', 'task-456', 'iteration_start', 1, '{"iteration": 1, "state": {...}}');
--
-- 2. 查询最新检查点:
--    SELECT * FROM checkpoints
--    WHERE task_id = 'task-456'
--    ORDER BY sequence_number DESC
--    LIMIT 1;
--
-- 3. 恢复到指定检查点:
--    SELECT snapshot_data FROM checkpoints
--    WHERE task_id = 'task-456' AND checkpoint_type = 'iteration_start'
--    ORDER BY sequence_number DESC
--    LIMIT 1;
--
-- ===== idempotency_keys 表使用场景 =====
--
-- 1. 检查幂等性键是否存在:
--    SELECT * FROM idempotency_keys
--    WHERE idempotency_key = 'idem-123';
--
-- 2. 创建幂等性键:
--    INSERT INTO idempotency_keys (idempotency_key, task_id, request_hash)
--    VALUES ('idem-123', 'task-456', 'sha256:abcd1234');
--
-- 3. 更新幂等性键结果:
--    UPDATE idempotency_keys
--    SET status = 'completed',
--        response_data = '{"result": "cached"}',
--        completed_at = CURRENT_TIMESTAMP
--    WHERE idempotency_key = 'idem-123';
--
-- 4. 清理过期键:
--    DELETE FROM idempotency_keys
--    WHERE expires_at < CURRENT_TIMESTAMP;

-- ============================================
-- 更新 schema 版本
-- ============================================

INSERT OR REPLACE INTO schema_version (version) VALUES ('0.30.0');
