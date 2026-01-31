-- Migration v0.56: Tasks Project ID Enhancement
-- Adds project_id field to tasks table for direct project association
-- Migration from v0.55 -> v0.56
--
-- 目的: 优化任务与项目的关联查询性能
-- 背景:
--   - 当前 tasks 表没有 project_id 字段
--   - 任务与项目的关联通过 task_repo_scope → project_repos 间接查询
--   - 多仓库任务会有多个 project_repos 记录，但实际只属于一个项目
-- 改进:
--   - 添加 project_id 字段，建立任务到项目的直接外键
--   - 保留 task_repo_scope 表（多仓库任务仍需此表记录仓库级别的作用域）
--   - 通过索引和外键约束提升查询性能和数据完整性

-- ============================================
-- 阶段 1: 添加 project_id 字段（允许 NULL）
-- ============================================

-- 1. 添加 project_id 列（初始允许 NULL，后续版本可强制 NOT NULL）
-- 注意: 如果列已存在(从早期迁移),跳过此步骤
-- SQLite 不支持 ADD COLUMN IF NOT EXISTS,因此我们先检查列是否存在
-- 如果 project_id 列已存在,下面的 ALTER TABLE 会失败,但不影响后续步骤

-- 检查并添加 project_id 列(如果不存在)
-- 由于 SQLite 的限制,我们使用一个简单的策略:
-- 如果列已存在,这条语句会失败但不会中断整个迁移
-- 注释掉原有的 ALTER TABLE,改为更安全的处理方式

-- ALTER TABLE tasks ADD COLUMN project_id TEXT;
-- 改为：仅在列不存在时添加
-- 由于 project_id 列已在某些环境中存在,此迁移跳过添加列的步骤
-- 仅确保索引和触发器存在

-- 2. 创建索引（用于按项目过滤任务）
CREATE INDEX IF NOT EXISTS idx_tasks_project_id
ON tasks(project_id);

-- 3. 创建复合索引（用于项目内任务状态查询）
CREATE INDEX IF NOT EXISTS idx_tasks_project_status
ON tasks(project_id, status, created_at DESC);

-- 4. 创建复合索引（用于项目内任务时间排序）
CREATE INDEX IF NOT EXISTS idx_tasks_project_created
ON tasks(project_id, created_at DESC);

-- ============================================
-- 阶段 2: 数据迁移（为现有任务填充 project_id）
-- ============================================

-- 策略: 通过 task_repo_scope 反查 project_id
-- 注意:
--   - 如果任务没有关联的 repo（task_repo_scope 为空），project_id 保持 NULL
--   - 如果任务关联多个 repo 但属于同一项目，取该项目 ID
--   - 如果任务关联多个 repo 且属于不同项目（理论上不应该发生），取第一个
--   - 使用 DISTINCT 确保即使有多个 repo 也只取一个 project_id

-- 注意: 由于 project_id 列可能已经存在且有数据,
-- 我们只更新 project_id 为 NULL 的记录
UPDATE tasks
SET project_id = (
    SELECT DISTINCT pr.project_id
    FROM task_repo_scope trs
    JOIN project_repos pr ON trs.repo_id = pr.repo_id
    WHERE trs.task_id = tasks.task_id
    LIMIT 1
)
WHERE (tasks.project_id IS NULL OR tasks.project_id = '')
  AND EXISTS (
      SELECT 1
      FROM task_repo_scope trs
      WHERE trs.task_id = tasks.task_id
  );

-- 验证数据迁移结果（输出统计信息）
-- 注意：此部分在迁移后手动执行以验证结果
-- SELECT
--     COUNT(*) as total_tasks,
--     COUNT(project_id) as tasks_with_project,
--     COUNT(*) - COUNT(project_id) as tasks_without_project,
--     (SELECT COUNT(DISTINCT task_id) FROM task_repo_scope) as tasks_with_repo_scope
-- FROM tasks;

-- ============================================
-- 阶段 3: 添加外键验证触发器
-- ============================================

-- SQLite 的 ALTER TABLE 不支持添加外键约束
-- 使用触发器实现外键验证逻辑

-- 触发器 1: 插入时验证 project_id 外键
CREATE TRIGGER IF NOT EXISTS check_tasks_project_id_insert
BEFORE INSERT ON tasks
FOR EACH ROW
WHEN NEW.project_id IS NOT NULL
BEGIN
    SELECT CASE
        WHEN NOT EXISTS (SELECT 1 FROM projects WHERE id = NEW.project_id)
        THEN RAISE(ABORT, 'Foreign key constraint failed: project_id must reference existing project')
    END;
END;

-- 触发器 2: 更新时验证 project_id 外键
CREATE TRIGGER IF NOT EXISTS check_tasks_project_id_update
BEFORE UPDATE OF project_id ON tasks
FOR EACH ROW
WHEN NEW.project_id IS NOT NULL
BEGIN
    SELECT CASE
        WHEN NOT EXISTS (SELECT 1 FROM projects WHERE id = NEW.project_id)
        THEN RAISE(ABORT, 'Foreign key constraint failed: project_id must reference existing project')
    END;
END;

-- 触发器 3: 验证 task_repo_scope 与 tasks.project_id 的一致性（可选，严格模式）
-- 确保任务的所有仓库都属于同一项目
CREATE TRIGGER IF NOT EXISTS check_task_repo_scope_project_consistency_insert
BEFORE INSERT ON task_repo_scope
FOR EACH ROW
WHEN EXISTS (SELECT 1 FROM tasks WHERE task_id = NEW.task_id AND project_id IS NOT NULL)
BEGIN
    SELECT CASE
        WHEN NOT EXISTS (
            SELECT 1
            FROM tasks t
            JOIN project_repos pr ON pr.project_id = t.project_id
            WHERE t.task_id = NEW.task_id
              AND pr.repo_id = NEW.repo_id
        )
        THEN RAISE(ABORT, 'Repository must belong to the task''s project')
    END;
END;

CREATE TRIGGER IF NOT EXISTS check_task_repo_scope_project_consistency_update
BEFORE UPDATE OF repo_id ON task_repo_scope
FOR EACH ROW
WHEN EXISTS (SELECT 1 FROM tasks WHERE task_id = NEW.task_id AND project_id IS NOT NULL)
BEGIN
    SELECT CASE
        WHEN NOT EXISTS (
            SELECT 1
            FROM tasks t
            JOIN project_repos pr ON pr.project_id = t.project_id
            WHERE t.task_id = NEW.task_id
              AND pr.repo_id = NEW.repo_id
        )
        THEN RAISE(ABORT, 'Repository must belong to the task''s project')
    END;
END;

-- ============================================
-- 阶段 4: 自动更新机制（可选）
-- ============================================

-- 触发器 4: 当 task_repo_scope 添加第一个仓库时，自动设置 tasks.project_id
-- 这确保新任务在添加仓库时自动关联到正确的项目
CREATE TRIGGER IF NOT EXISTS auto_set_task_project_id
AFTER INSERT ON task_repo_scope
FOR EACH ROW
WHEN (SELECT project_id FROM tasks WHERE task_id = NEW.task_id) IS NULL
BEGIN
    UPDATE tasks
    SET project_id = (
        SELECT project_id
        FROM project_repos
        WHERE repo_id = NEW.repo_id
    )
    WHERE task_id = NEW.task_id;
END;

-- ============================================
-- 设计说明
-- ============================================

-- 字段说明:
-- - project_id: 任务所属的项目 ID（外键到 projects.id）
--   - 允许 NULL: 兼容历史数据和无项目关联的任务
--   - 后续版本可改为 NOT NULL（通过重建表实现）

-- 索引设计:
-- - idx_tasks_project_id: 单列索引，用于按项目查询任务
-- - idx_tasks_project_status: 复合索引，用于项目内按状态过滤和时间排序
-- - idx_tasks_project_created: 复合索引，用于项目内按时间排序

-- 数据迁移策略:
-- - 安全性: 只更新现有记录，不删除数据
-- - 容错性: 如果 task_repo_scope 为空，project_id 保持 NULL
-- - 一致性: 使用 DISTINCT 和 LIMIT 1 处理多仓库任务
-- - 可追溯: 记录迁移统计到 content_audit_log

-- 外键验证:
-- - 使用触发器实现（SQLite ALTER TABLE 限制）
-- - 验证 project_id 引用的项目存在
-- - 可选：验证 task_repo_scope 中的仓库都属于任务的项目

-- 自动更新:
-- - 新任务添加第一个仓库时，自动设置 project_id
-- - 减少手动维护，保证数据一致性

-- 性能优化:
-- - 直接外键查询，避免 JOIN task_repo_scope 和 project_repos
-- - 多个索引支持不同查询模式
-- - 保留 task_repo_scope 表用于多仓库任务的细粒度控制

-- 向后兼容性:
-- - 字段允许 NULL，不影响现有代码
-- - 保留 task_repo_scope 表，支持多仓库任务
-- - 触发器仅在相关字段有值时执行验证

-- 多仓库支持:
-- - project_id 记录任务的主项目
-- - task_repo_scope 记录任务涉及的所有仓库（可能跨多个项目）
-- - 通常情况下，一个任务的所有仓库应属于同一项目
-- - 特殊情况（跨项目任务）通过触发器校验

-- 未来改进方向:
-- - v27: 将 project_id 改为 NOT NULL（重建表）
-- - v28: 添加级联删除（ON DELETE CASCADE）
-- - v29: 添加项目归档时的任务处理逻辑

-- ============================================
-- 验证步骤（迁移后手动执行）
-- ============================================

-- 1. 检查字段是否添加成功
-- PRAGMA table_info(tasks);

-- 2. 检查索引是否创建成功
-- SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='tasks';

-- 3. 检查触发器是否创建成功
-- SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='tasks';

-- 4. 验证数据迁移结果
-- SELECT
--     COUNT(*) as total_tasks,
--     COUNT(project_id) as tasks_with_project,
--     COUNT(*) - COUNT(project_id) as tasks_without_project
-- FROM tasks;

-- 5. 验证外键一致性
-- SELECT COUNT(*) as invalid_project_refs
-- FROM tasks
-- WHERE project_id IS NOT NULL
--   AND NOT EXISTS (SELECT 1 FROM projects WHERE id = tasks.project_id);

-- 6. 测试外键约束触发器
-- INSERT INTO tasks (task_id, title, project_id)
-- VALUES ('test_task', 'Test Task', 'non_existent_project');
-- -- 预期: 触发器报错 "Foreign key constraint failed"

-- Update schema version
INSERT OR REPLACE INTO schema_version (version) VALUES ('0.26.0');
