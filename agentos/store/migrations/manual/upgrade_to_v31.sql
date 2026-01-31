-- Migration: Pre-v31 fixes + v31 application
-- Purpose: Fix projects table structure, then apply full v31 migration
-- Date: 2026-01-29

PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;

-- ============================================
-- Part 1: 重建 projects 表（id → project_id）
-- ============================================

-- 1.1 检查是否需要重建（如果已经有 project_id 列，跳过）
-- SQLite 不支持条件 DDL，所以我们总是尝试重建

-- 1.2 备份现有 projects 表
DROP TABLE IF EXISTS projects_backup_v30;
ALTER TABLE projects RENAME TO projects_backup_v30;

-- 1.3 创建新的 projects 表（符合 v31 schema）
CREATE TABLE projects (
    -- 主键
    project_id TEXT PRIMARY KEY,

    -- 基本信息
    name TEXT UNIQUE NOT NULL,
    description TEXT,

    -- 元数据
    tags TEXT,
    default_repo_id TEXT,

    -- 时间戳
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    -- 扩展字段
    metadata TEXT
);

-- 1.4 迁移数据（id → project_id，保留其他字段）
INSERT INTO projects (project_id, name, description, tags, default_repo_id, created_at, updated_at, metadata)
SELECT
    id as project_id,
    name,
    description,
    tags,
    default_repo_id,
    COALESCE(created_at, CURRENT_TIMESTAMP),
    COALESCE(updated_at, CURRENT_TIMESTAMP),
    metadata
FROM projects_backup_v30;

-- 1.5 重建索引
CREATE INDEX IF NOT EXISTS idx_projects_name
ON projects(name);

CREATE INDEX IF NOT EXISTS idx_projects_created_at
ON projects(created_at DESC);

-- 1.6 如果有 project_repos 表，也需要更新外键
-- 检查是否存在 project_repos 表
CREATE TABLE IF NOT EXISTS project_repos_temp AS
SELECT * FROM project_repos WHERE 1=0;

-- 如果 project_repos 表存在且有数据，需要更新引用
-- （这个表在 v30 中可能不存在，所以要谨慎处理）

-- ============================================
-- Part 2: 应用 v31 迁移（从 schema_v31_project_aware.sql 复制）
-- ============================================

-- 阶段 2: 创建 repos 表
CREATE TABLE IF NOT EXISTS repos (
    repo_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    name TEXT NOT NULL,
    local_path TEXT NOT NULL,
    vcs_type TEXT DEFAULT 'git',
    remote_url TEXT,
    default_branch TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    metadata TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE,
    UNIQUE(project_id, name)
);

CREATE INDEX IF NOT EXISTS idx_repos_project_id
ON repos(project_id);

CREATE INDEX IF NOT EXISTS idx_repos_local_path
ON repos(local_path);

-- 阶段 3: 创建 task_specs 表
CREATE TABLE IF NOT EXISTS task_specs (
    spec_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    spec_version INTEGER NOT NULL,
    title TEXT NOT NULL,
    intent TEXT,
    constraints TEXT,
    acceptance_criteria TEXT,
    inputs TEXT,
    created_at TEXT NOT NULL,
    metadata TEXT,
    FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE,
    UNIQUE(task_id, spec_version)
);

CREATE INDEX IF NOT EXISTS idx_task_specs_task_id
ON task_specs(task_id, spec_version DESC);

-- 阶段 4: 创建 task_bindings 表
CREATE TABLE IF NOT EXISTS task_bindings (
    task_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    repo_id TEXT,
    workdir TEXT,
    created_at TEXT NOT NULL,
    metadata TEXT,
    FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE,
    FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE RESTRICT,
    FOREIGN KEY (repo_id) REFERENCES repos(repo_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_task_bindings_project_id
ON task_bindings(project_id);

CREATE INDEX IF NOT EXISTS idx_task_bindings_repo_id
ON task_bindings(repo_id)
WHERE repo_id IS NOT NULL;

-- 阶段 5: 创建 task_artifacts 表
CREATE TABLE IF NOT EXISTS task_artifacts (
    artifact_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    path TEXT NOT NULL,
    display_name TEXT,
    hash TEXT,
    size_bytes INTEGER,
    created_at TEXT NOT NULL,
    metadata TEXT,
    FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_task_artifacts_task_id
ON task_artifacts(task_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_task_artifacts_kind
ON task_artifacts(kind, created_at DESC);

-- 阶段 6: 为 tasks 表添加新字段（如果不存在）
-- 注意：SQLite 的 ALTER TABLE ADD COLUMN 如果列已存在会报错
-- 我们使用 BEGIN/END 块来捕获错误

-- 添加 project_id 列
ALTER TABLE tasks ADD COLUMN project_id TEXT;

-- 添加 repo_id 列
ALTER TABLE tasks ADD COLUMN repo_id TEXT;

-- 添加 workdir 列
ALTER TABLE tasks ADD COLUMN workdir TEXT;

-- 添加 spec_frozen 列
ALTER TABLE tasks ADD COLUMN spec_frozen INTEGER DEFAULT 0;

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_tasks_project_id
ON tasks(project_id)
WHERE project_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_tasks_spec_frozen
ON tasks(spec_frozen);

-- 阶段 7: 数据迁移（创建默认项目）
INSERT OR IGNORE INTO projects (
    project_id,
    name,
    description,
    tags,
    created_at,
    updated_at
)
VALUES (
    'proj_default',
    'Default Project',
    'Auto-created for legacy tasks migrated from v0.3',
    '["legacy", "migrated"]',
    datetime('now'),
    datetime('now')
);

-- 将所有没有 project_id 的旧任务绑定到默认项目
UPDATE tasks
SET project_id = 'proj_default'
WHERE project_id IS NULL;

-- 为旧任务创建绑定关系
INSERT OR IGNORE INTO task_bindings (task_id, project_id, created_at)
SELECT
    task_id,
    'proj_default',
    datetime('now')
FROM tasks
WHERE project_id = 'proj_default';

-- 阶段 8: 添加约束触发器
DROP TRIGGER IF EXISTS enforce_task_project_binding_insert;
CREATE TRIGGER enforce_task_project_binding_insert
BEFORE INSERT ON tasks
FOR EACH ROW
WHEN NEW.status IN ('ready', 'running', 'verifying', 'verified', 'done', 'succeeded')
    AND NEW.project_id IS NULL
BEGIN
    SELECT RAISE(ABORT, 'Tasks in READY+ states must have project_id (v0.4 constraint)');
END;

DROP TRIGGER IF EXISTS enforce_task_project_binding_update;
CREATE TRIGGER enforce_task_project_binding_update
BEFORE UPDATE OF status ON tasks
FOR EACH ROW
WHEN NEW.status IN ('ready', 'running', 'verifying', 'verified', 'done', 'succeeded')
    AND NEW.project_id IS NULL
BEGIN
    SELECT RAISE(ABORT, 'Tasks in READY+ states must have project_id (v0.4 constraint)');
END;

DROP TRIGGER IF EXISTS enforce_task_spec_frozen_insert;
CREATE TRIGGER enforce_task_spec_frozen_insert
BEFORE INSERT ON tasks
FOR EACH ROW
WHEN NEW.status IN ('ready', 'running', 'verifying', 'verified', 'done', 'succeeded')
    AND NEW.spec_frozen = 0
BEGIN
    SELECT RAISE(ABORT, 'Tasks in READY+ states must have frozen spec (spec_frozen = 1) (v0.4 constraint)');
END;

DROP TRIGGER IF EXISTS enforce_task_spec_frozen_update;
CREATE TRIGGER enforce_task_spec_frozen_update
BEFORE UPDATE OF status ON tasks
FOR EACH ROW
WHEN NEW.status IN ('ready', 'running', 'verifying', 'verified', 'done', 'succeeded')
    AND NEW.spec_frozen = 0
BEGIN
    SELECT RAISE(ABORT, 'Tasks in READY+ states must have frozen spec (spec_frozen = 1) (v0.4 constraint)');
END;

-- 阶段 9: 性能优化索引
CREATE INDEX IF NOT EXISTS idx_tasks_project_status
ON tasks(project_id, status, created_at DESC)
WHERE project_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_tasks_repo_status
ON tasks(repo_id, status, created_at DESC)
WHERE repo_id IS NOT NULL;

-- 阶段 10: 审计日志
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

-- 阶段 11: 更新 schema 版本
DELETE FROM schema_version WHERE version = '0.31.0';
INSERT INTO schema_version (version) VALUES ('0.31.0');

-- ============================================
-- Part 3: 清理备份表（可选）
-- ============================================

-- 保留备份表以防万一，生产环境可以稍后手动删除
-- DROP TABLE IF EXISTS projects_backup_v30;
-- DROP TABLE IF EXISTS project_repos_temp;

COMMIT;
PRAGMA foreign_keys=ON;

-- ============================================
-- 验证说明
-- ============================================
--
-- 执行后验证:
-- 1. SELECT version FROM schema_version; -- 应该是 0.31.0
-- 2. PRAGMA table_info(projects); -- 第一列应该是 project_id
-- 3. SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'task_%'; -- 应该包含 task_specs, task_bindings, task_artifacts
-- 4. SELECT COUNT(*) FROM tasks WHERE project_id IS NULL; -- 应该是 0
-- 5. PRAGMA foreign_key_check; -- 应该无错误
--
