-- Migration v0.31: Project-Aware Task Operating System (v0.4)
-- Description: Implements ADR-V04 Project-Aware architecture
-- Purpose: Enable multi-repo projects, task-project binding, and spec freezing
-- Migration from v0.30 -> v0.31
--
-- 背景:
--   - v0.4 引入 Project-Aware Task OS 架构
--   - 分离 Project 和 Repository 语义
--   - 强制任务绑定到项目（task.project_id 必填）
--   - 支持 spec 冻结和版本化（spec_version）
--   - 支持多仓库项目
--
-- 核心概念:
--   - Project ≠ Repository（语义分离）
--   - Task MUST bind to Project（强约束）
--   - Spec Freezing（READY 前必须冻结）
--   - Multi-Repo Support（一个 Project 多个 Repos）
--
-- 参考文档:
--   - /docs/architecture/ADR_V04_PROJECT_AWARE_TASK_OS.md
--   - /docs/V04_CONSTRAINTS_AND_GATES.md
--
-- ============================================
-- 阶段 1: 创建 projects 表
-- ============================================
--
-- projects 表: 项目根实体
-- 用途: 管理逻辑项目（可包含多个仓库）
--

CREATE TABLE IF NOT EXISTS projects (
    -- 主键
    project_id TEXT PRIMARY KEY,  -- ULID/UUID

    -- 基本信息
    name TEXT UNIQUE NOT NULL,    -- 项目名称（唯一，用户友好）
    description TEXT,             -- 项目描述

    -- 元数据
    tags TEXT,                    -- 标签 (JSON array: ["backend", "api"])
    default_repo_id TEXT,         -- 默认仓库 ID（可选）

    -- 时间戳
    created_at TEXT NOT NULL,     -- 创建时间（ISO 8601）
    updated_at TEXT NOT NULL,     -- 更新时间（ISO 8601）

    -- 扩展字段
    metadata TEXT                 -- 扩展元数据（JSON）
);

-- 索引：按名称搜索
CREATE INDEX IF NOT EXISTS idx_projects_name
ON projects(name);

-- 索引：按创建时间排序
CREATE INDEX IF NOT EXISTS idx_projects_created_at
ON projects(created_at DESC);

-- ============================================
-- 阶段 2: 创建 repos 表
-- ============================================
--
-- repos 表: 仓库管理
-- 用途: 管理项目关联的代码仓库
--

CREATE TABLE IF NOT EXISTS repos (
    -- 主键
    repo_id TEXT PRIMARY KEY,     -- ULID/UUID

    -- 关联
    project_id TEXT NOT NULL,     -- 所属项目（外键）

    -- 基本信息
    name TEXT NOT NULL,           -- 仓库名称（项目内唯一）
    local_path TEXT NOT NULL,     -- 本地路径（绝对路径，必填）

    -- VCS 配置
    vcs_type TEXT DEFAULT 'git',  -- 版本控制类型（git/none）
    remote_url TEXT,              -- 远程仓库地址（可选）
    default_branch TEXT,          -- 默认分支（可选，如 main/master）

    -- 时间戳
    created_at TEXT NOT NULL,     -- 创建时间（ISO 8601）
    updated_at TEXT NOT NULL,     -- 更新时间（ISO 8601）

    -- 扩展字段
    metadata TEXT,                -- 扩展元数据（JSON）

    -- 外键约束
    -- NOTE: projects表在v01中创建,主键列名为id,不是project_id
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,

    -- 唯一约束：项目内仓库名称唯一
    UNIQUE(project_id, name)
);

-- 索引：按项目查询仓库
CREATE INDEX IF NOT EXISTS idx_repos_project_id
ON repos(project_id);

-- 索引：按本地路径查询（用于路径冲突检测）
CREATE INDEX IF NOT EXISTS idx_repos_local_path
ON repos(local_path);

-- ============================================
-- 阶段 3: 创建 task_specs 表
-- ============================================
--
-- task_specs 表: 任务规格历史
-- 用途: 存储任务规格的版本化历史（支持 spec freezing）
--

CREATE TABLE IF NOT EXISTS task_specs (
    -- 主键
    spec_id TEXT PRIMARY KEY,     -- ULID/UUID

    -- 关联
    task_id TEXT NOT NULL,        -- 关联任务 ID
    spec_version INTEGER NOT NULL,-- 规格版本号（从 0 开始）

    -- 规格内容
    title TEXT NOT NULL,          -- 任务标题
    intent TEXT,                  -- 任务意图（短句）
    constraints TEXT,             -- 约束条件（JSON array）
    acceptance_criteria TEXT,     -- 验收标准（JSON array）
    inputs TEXT,                  -- 输入数据（JSON）

    -- 时间戳
    created_at TEXT NOT NULL,     -- 创建时间（ISO 8601）

    -- 扩展字段
    metadata TEXT,                -- 扩展元数据（JSON）

    -- 外键约束
    FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE,

    -- 唯一约束：任务内版本号唯一
    UNIQUE(task_id, spec_version)
);

-- 索引：按任务查询规格历史
CREATE INDEX IF NOT EXISTS idx_task_specs_task_id
ON task_specs(task_id, spec_version DESC);

-- ============================================
-- 阶段 4: 创建 task_bindings 表
-- ============================================
--
-- task_bindings 表: 任务绑定关系
-- 用途: 管理任务与项目/仓库的绑定关系
--

CREATE TABLE IF NOT EXISTS task_bindings (
    -- 主键（task_id 作为主键，一个任务只有一个绑定）
    task_id TEXT PRIMARY KEY,

    -- 绑定关系
    project_id TEXT NOT NULL,     -- 绑定的项目 ID（必填）
    repo_id TEXT,                 -- 绑定的仓库 ID（可选）
    workdir TEXT,                 -- 工作目录（相对路径，相对于 repo）

    -- 时间戳
    created_at TEXT NOT NULL,     -- 绑定创建时间（ISO 8601）

    -- 扩展字段
    metadata TEXT,                -- 扩展元数据（JSON）

    -- 外键约束
    FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE,
    -- NOTE: projects表在v01中创建,主键列名为id,不是project_id
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE RESTRICT,
    FOREIGN KEY (repo_id) REFERENCES repos(repo_id) ON DELETE SET NULL
);

-- 索引：按项目查询任务
CREATE INDEX IF NOT EXISTS idx_task_bindings_project_id
ON task_bindings(project_id);

-- 索引：按仓库查询任务
CREATE INDEX IF NOT EXISTS idx_task_bindings_repo_id
ON task_bindings(repo_id)
WHERE repo_id IS NOT NULL;

-- ============================================
-- 阶段 5: 创建 task_artifacts 表
-- ============================================
--
-- task_artifacts 表: 任务产物管理
-- 用途: 记录任务生成的文件、目录、URL 等产物
--

CREATE TABLE IF NOT EXISTS task_artifacts (
    -- 主键
    artifact_id TEXT PRIMARY KEY, -- ULID/UUID

    -- 关联
    task_id TEXT NOT NULL,        -- 关联任务 ID

    -- 产物信息
    kind TEXT NOT NULL,           -- 产物类型（file/dir/url/log/report）
    path TEXT NOT NULL,           -- 产物路径（本地绝对路径 or 相对 repo 路径）
    display_name TEXT,            -- 显示名称（用户友好）

    -- 元数据
    hash TEXT,                    -- 文件哈希（可选，如 sha256:abc123）
    size_bytes INTEGER,           -- 文件大小（字节，可选）

    -- 时间戳
    created_at TEXT NOT NULL,     -- 创建时间（ISO 8601）

    -- 扩展字段
    metadata TEXT,                -- 扩展元数据（JSON）

    -- 外键约束
    FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE
);

-- 索引：按任务查询产物
CREATE INDEX IF NOT EXISTS idx_task_artifacts_task_id
ON task_artifacts(task_id, created_at DESC);

-- 索引：按产物类型查询
CREATE INDEX IF NOT EXISTS idx_task_artifacts_kind
ON task_artifacts(kind, created_at DESC);

-- ============================================
-- 阶段 6: 修改 tasks 表（添加新字段）
-- ============================================
--
-- 为 tasks 表添加 v0.4 所需的新字段
--

-- 字段 1: project_id（项目绑定，可空，迁移后不可空）
-- NOTE: project_id column已在schema_v26_tasks_project_id.sql中添加,此处跳过
-- ALTER TABLE tasks ADD COLUMN project_id TEXT;

-- 字段 2: repo_id（仓库绑定，可空）
-- NOTE: v20只向task_audits添加了repo_id,tasks表中需要在这里添加
ALTER TABLE tasks ADD COLUMN repo_id TEXT;

-- 字段 3: workdir（工作目录，可空）
-- NOTE: 该列在其他迁移中不存在,需要在这里添加
ALTER TABLE tasks ADD COLUMN workdir TEXT;

-- 字段 4: spec_frozen（规格冻结标志，默认 false）
-- NOTE: 该列在其他迁移中不存在,需要在这里添加
ALTER TABLE tasks ADD COLUMN spec_frozen INTEGER DEFAULT 0;

-- 索引：按项目查询任务
CREATE INDEX IF NOT EXISTS idx_tasks_project_id
ON tasks(project_id)
WHERE project_id IS NOT NULL;

-- 索引：按 spec_frozen 状态查询
CREATE INDEX IF NOT EXISTS idx_tasks_spec_frozen
ON tasks(spec_frozen);

-- ============================================
-- 阶段 7: 数据迁移（旧数据兼容）
-- ============================================
--
-- 为旧任务创建默认项目，确保向后兼容
--

-- 1. 创建默认项目（用于迁移旧任务）
-- NOTE: projects表在v01中创建,主键列名为id,不是project_id
INSERT OR IGNORE INTO projects (
    id,
    path,
    added_at
)
VALUES (
    'proj_default',
    '/default',
    datetime('now')
);

-- 2. 将所有旧任务绑定到默认项目
UPDATE tasks
SET project_id = 'proj_default'
WHERE project_id IS NULL;

-- 3. 为旧任务创建绑定关系
INSERT OR IGNORE INTO task_bindings (task_id, project_id, created_at)
SELECT
    task_id,
    'proj_default',
    datetime('now')
FROM tasks
WHERE project_id = 'proj_default';

-- ============================================
-- 阶段 8: 添加约束触发器
-- ============================================
--
-- 实施 v0.4 硬约束（Constraint 1: Task-Project Binding）
--

-- 触发器 1: 禁止 READY+ 状态的任务没有 project_id
CREATE TRIGGER IF NOT EXISTS enforce_task_project_binding_insert
BEFORE INSERT ON tasks
FOR EACH ROW
WHEN NEW.status IN ('ready', 'running', 'verifying', 'verified', 'done', 'succeeded')
    AND NEW.project_id IS NULL
BEGIN
    SELECT RAISE(ABORT, 'Tasks in READY+ states must have project_id (v0.4 constraint)');
END;

CREATE TRIGGER IF NOT EXISTS enforce_task_project_binding_update
BEFORE UPDATE OF status ON tasks
FOR EACH ROW
WHEN NEW.status IN ('ready', 'running', 'verifying', 'verified', 'done', 'succeeded')
    AND NEW.project_id IS NULL
BEGIN
    SELECT RAISE(ABORT, 'Tasks in READY+ states must have project_id (v0.4 constraint)');
END;

-- 触发器 2: 禁止 READY+ 状态的任务 spec_frozen = false
CREATE TRIGGER IF NOT EXISTS enforce_task_spec_frozen_insert
BEFORE INSERT ON tasks
FOR EACH ROW
WHEN NEW.status IN ('ready', 'running', 'verifying', 'verified', 'done', 'succeeded')
    AND NEW.spec_frozen = 0
BEGIN
    SELECT RAISE(ABORT, 'Tasks in READY+ states must have frozen spec (spec_frozen = 1) (v0.4 constraint)');
END;

CREATE TRIGGER IF NOT EXISTS enforce_task_spec_frozen_update
BEFORE UPDATE OF status ON tasks
FOR EACH ROW
WHEN NEW.status IN ('ready', 'running', 'verifying', 'verified', 'done', 'succeeded')
    AND NEW.spec_frozen = 0
BEGIN
    SELECT RAISE(ABORT, 'Tasks in READY+ states must have frozen spec (spec_frozen = 1) (v0.4 constraint)');
END;

-- ============================================
-- 阶段 9: 性能优化索引
-- ============================================
--
-- 为高频查询创建复合索引
--

-- 复合索引 1: 按项目和状态查询任务
CREATE INDEX IF NOT EXISTS idx_tasks_project_status
ON tasks(project_id, status, created_at DESC)
WHERE project_id IS NOT NULL;

-- 复合索引 2: 按仓库和状态查询任务
CREATE INDEX IF NOT EXISTS idx_tasks_repo_status
ON tasks(repo_id, status, created_at DESC)
WHERE repo_id IS NOT NULL;

-- ============================================
-- 阶段 10: 审计日志（记录迁移事件）
-- ============================================
--
-- 记录迁移到审计表（如果 task_audits 表存在）
--

INSERT OR IGNORE INTO task_audits (task_id, level, event_type, payload, created_at)
SELECT
    task_id,
    'info',
    'MIGRATION_V031',
    json_object(
        'migration', 'v0.31_project_aware',
        'action', 'bound_to_default_project',
        'project_id', 'proj_default',
        'migrated_at', datetime('now')
    ),
    CURRENT_TIMESTAMP
FROM tasks
WHERE project_id = 'proj_default';

-- ============================================
-- 阶段 11: 更新 schema 版本
-- ============================================

INSERT OR REPLACE INTO schema_version (version) VALUES ('0.31.0');

-- ============================================
-- 设计说明和使用示例
-- ============================================

-- ===== 新表说明 =====
--
-- 1. projects: 逻辑项目管理（一个项目可包含多个仓库）
-- 2. repos: 仓库管理（代码仓库，属于项目）
-- 3. task_specs: 任务规格版本化（支持 spec freezing）
-- 4. task_bindings: 任务绑定关系（任务 ↔ 项目 ↔ 仓库）
-- 5. task_artifacts: 任务产物（文件、目录、URL 等）
--
-- ===== tasks 表新字段 =====
--
-- - project_id: 任务所属项目（v0.4 后必填）
-- - repo_id: 任务关联仓库（可选）
-- - workdir: 工作目录（可选，相对路径）
-- - spec_frozen: 规格冻结标志（0=未冻结, 1=已冻结）
--
-- ===== 使用示例 =====
--
-- 1. 创建项目和仓库:
--    INSERT INTO projects (project_id, name, description, created_at, updated_at)
--    VALUES ('proj_api', 'E-Commerce API', 'Backend API service', datetime('now'), datetime('now'));
--
--    INSERT INTO repos (repo_id, project_id, name, local_path, vcs_type, created_at, updated_at)
--    VALUES ('repo_api', 'proj_api', 'api-service', '/path/to/api', 'git', datetime('now'), datetime('now'));
--
-- 2. 创建任务并绑定:
--    INSERT INTO tasks (task_id, title, status, project_id, spec_frozen, created_at, updated_at)
--    VALUES ('task_01', 'Update API docs', 'draft', 'proj_api', 0, datetime('now'), datetime('now'));
--
--    INSERT INTO task_bindings (task_id, project_id, repo_id, created_at)
--    VALUES ('task_01', 'proj_api', 'repo_api', datetime('now'));
--
-- 3. 冻结 spec:
--    INSERT INTO task_specs (spec_id, task_id, spec_version, title, intent, created_at)
--    VALUES ('spec_01', 'task_01', 1, 'Update API docs', 'Add OpenAPI specs', datetime('now'));
--
--    UPDATE tasks SET spec_frozen = 1 WHERE task_id = 'task_01';
--
-- 4. 记录产物:
--    INSERT INTO task_artifacts (artifact_id, task_id, kind, path, display_name, created_at)
--    VALUES ('art_01', 'task_01', 'file', '/docs/openapi.yaml', 'OpenAPI Spec', datetime('now'));
--
-- ===== 约束验证 =====
--
-- 测试约束 1: 尝试将没有 project_id 的任务转为 READY（应失败）
-- UPDATE tasks SET status = 'ready' WHERE task_id = 'task_no_project';
-- 预期错误: Tasks in READY+ states must have project_id
--
-- 测试约束 2: 尝试将 spec_frozen = 0 的任务转为 READY（应失败）
-- UPDATE tasks SET status = 'ready' WHERE task_id = 'task_unfrozen';
-- 预期错误: Tasks in READY+ states must have frozen spec
--
-- ===== 迁移验证 =====
--
-- 验证所有旧任务都已绑定到默认项目:
-- SELECT COUNT(*) FROM tasks WHERE project_id IS NULL;
-- 预期结果: 0
--
-- 验证默认项目已创建:
-- SELECT * FROM projects WHERE project_id = 'proj_default';
-- 预期结果: 1 行
--
-- 验证任务绑定已创建:
-- SELECT COUNT(*) FROM task_bindings WHERE project_id = 'proj_default';
-- 预期结果: >= 已迁移任务数量
--
-- ===== 回滚步骤（如需要）=====
--
-- 警告: 回滚会删除所有 v0.4 新增的数据！
--
-- 1. 删除触发器:
-- DROP TRIGGER IF EXISTS enforce_task_project_binding_insert;
-- DROP TRIGGER IF EXISTS enforce_task_project_binding_update;
-- DROP TRIGGER IF EXISTS enforce_task_spec_frozen_insert;
-- DROP TRIGGER IF EXISTS enforce_task_spec_frozen_update;
--
-- 2. 删除索引:
-- DROP INDEX IF EXISTS idx_tasks_project_id;
-- DROP INDEX IF EXISTS idx_tasks_spec_frozen;
-- DROP INDEX IF EXISTS idx_tasks_project_status;
-- DROP INDEX IF EXISTS idx_tasks_repo_status;
--
-- 3. 删除新表:
-- DROP TABLE IF EXISTS task_artifacts;
-- DROP TABLE IF EXISTS task_bindings;
-- DROP TABLE IF EXISTS task_specs;
-- DROP TABLE IF EXISTS repos;
-- DROP TABLE IF EXISTS projects;
--
-- 4. 删除 tasks 表新列（SQLite 不支持 DROP COLUMN，需要重建表）
-- -- 注意: 此步骤复杂，建议备份后重建数据库
--
-- 5. 回滚 schema 版本:
-- DELETE FROM schema_version WHERE version = '0.31.0';
--
-- ============================================
-- 完成
-- ============================================
--
-- v0.31 迁移完成！
--
-- 变更摘要:
-- - 新增 5 个表: projects, repos, task_specs, task_bindings, task_artifacts
-- - tasks 表新增 4 个字段: project_id, repo_id, workdir, spec_frozen
-- - 新增 4 个约束触发器（强制 project binding 和 spec freezing）
-- - 新增 10+ 个性能索引
-- - 迁移所有旧任务到默认项目（proj_default）
-- - 支持多仓库项目架构
--
-- 下一步:
-- 1. 验证迁移成功（运行测试脚本）
-- 2. 更新 TaskService 使用新字段
-- 3. 更新 API 强制 project_id 必填
-- 4. 更新 WebUI 添加项目选择器
--
-- 版本: v0.31.0
-- 日期: 2026-01-29
-- 作者: AgentOS Core Team
-- 参考: ADR-V04
