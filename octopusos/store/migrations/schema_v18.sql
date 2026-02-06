-- Migration v0.18: Multi-Repository Project Bindings
-- Adds support for multi-repository project management and cross-repo task tracking
-- Migration from v0.17 -> v0.18

-- ============================================
-- Project Repos: 项目的仓库绑定
-- ============================================

CREATE TABLE IF NOT EXISTS project_repos (
    repo_id TEXT PRIMARY KEY,                    -- 唯一仓库 ID（ULID 或 UUID）
    project_id TEXT NOT NULL,                    -- 关联的项目 ID
    name TEXT NOT NULL,                          -- 仓库名称（用户友好的标识，如 "frontend", "backend"）
    remote_url TEXT,                             -- 远程仓库 URL（可选，用于克隆/拉取）
    default_branch TEXT DEFAULT 'main',          -- 默认分支
    workspace_relpath TEXT NOT NULL,             -- 相对于项目工作区的路径（如 ".", "services/api", "../monorepo/packages/core"）
    role TEXT NOT NULL DEFAULT 'code',           -- 仓库角色：code | docs | infra | mono-subdir
    is_writable INTEGER NOT NULL DEFAULT 1,      -- 是否可写（1=可写，0=只读）
    auth_profile TEXT,                           -- 认证配置名称（如 "github-pat", "gitlab-ssh"，关联到外部凭证管理）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT,                               -- JSON: 扩展元数据（如 submodule 配置、monorepo 根路径等）

    -- Note: projects table uses 'id' as column name, not 'project_id'
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,

    -- 约束：同一 project 内的 repo name 必须唯一
    UNIQUE(project_id, name),

    -- 约束：同一 project 内的 workspace_relpath 必须唯一（防止路径冲突）
    UNIQUE(project_id, workspace_relpath),

    -- 约束：role 必须是允许的值之一
    CHECK (role IN ('code', 'docs', 'infra', 'mono-subdir'))
);

-- 索引优化
CREATE INDEX IF NOT EXISTS idx_project_repos_project
ON project_repos(project_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_project_repos_role
ON project_repos(role);

CREATE INDEX IF NOT EXISTS idx_project_repos_writable
ON project_repos(is_writable)
WHERE is_writable = 1;  -- 快速查询可写仓库

CREATE INDEX IF NOT EXISTS idx_project_repos_name
ON project_repos(project_id, name);

-- ============================================
-- Task Repo Scope: 任务涉及的仓库范围
-- ============================================

CREATE TABLE IF NOT EXISTS task_repo_scope (
    scope_id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,                       -- 关联的任务 ID
    repo_id TEXT NOT NULL,                       -- 涉及的仓库 ID
    scope TEXT NOT NULL DEFAULT 'full',          -- 作用域：full | paths | read_only
    path_filters TEXT,                           -- JSON 数组：路径过滤器（如 ["src/**", "tests/**"]）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT,                               -- JSON: 扩展元数据（如访问权限、变更统计等）

    FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE,
    FOREIGN KEY (repo_id) REFERENCES project_repos(repo_id) ON DELETE CASCADE,

    -- 约束：同一任务的同一仓库只能有一个 scope 记录
    UNIQUE(task_id, repo_id),

    -- 约束：scope 必须是允许的值之一
    CHECK (scope IN ('full', 'paths', 'read_only'))
);

-- 索引优化
CREATE INDEX IF NOT EXISTS idx_task_repo_scope_task
ON task_repo_scope(task_id);

CREATE INDEX IF NOT EXISTS idx_task_repo_scope_repo
ON task_repo_scope(repo_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_task_repo_scope_scope
ON task_repo_scope(scope);

-- 复合索引：任务+仓库联合查询
CREATE INDEX IF NOT EXISTS idx_task_repo_scope_task_repo
ON task_repo_scope(task_id, repo_id);

-- ============================================
-- Task Dependency: 任务间依赖关系
-- ============================================

CREATE TABLE IF NOT EXISTS task_dependency (
    dependency_id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,                       -- 依赖者任务 ID
    depends_on_task_id TEXT NOT NULL,            -- 被依赖任务 ID
    dependency_type TEXT NOT NULL DEFAULT 'blocks',  -- 依赖类型：blocks | requires | suggests
    reason TEXT,                                 -- 依赖原因说明
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT,                             -- 创建者（user/system/auto）
    metadata TEXT,                               -- JSON: 扩展元数据（如依赖强度、自动检测规则等）

    FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE,
    FOREIGN KEY (depends_on_task_id) REFERENCES tasks(task_id) ON DELETE CASCADE,

    -- 约束：同一对任务的同一类型依赖只能有一个记录
    UNIQUE(task_id, depends_on_task_id, dependency_type),

    -- 约束：禁止自依赖
    CHECK (task_id != depends_on_task_id),

    -- 约束：dependency_type 必须是允许的值之一
    CHECK (dependency_type IN ('blocks', 'requires', 'suggests'))
);

-- 索引优化
CREATE INDEX IF NOT EXISTS idx_task_dependency_task
ON task_dependency(task_id);

CREATE INDEX IF NOT EXISTS idx_task_dependency_depends_on
ON task_dependency(depends_on_task_id);

CREATE INDEX IF NOT EXISTS idx_task_dependency_type
ON task_dependency(dependency_type);

-- 复合索引：反向查询（谁依赖我）
CREATE INDEX IF NOT EXISTS idx_task_dependency_reverse
ON task_dependency(depends_on_task_id, task_id);

-- ============================================
-- Task Artifact Ref: 跨仓产物引用
-- ============================================

CREATE TABLE IF NOT EXISTS task_artifact_ref (
    artifact_id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,                       -- 关联的任务 ID
    repo_id TEXT NOT NULL,                       -- 产物所在的仓库 ID
    ref_type TEXT NOT NULL,                      -- 引用类型：commit | branch | pr | patch | file | tag
    ref_value TEXT NOT NULL,                     -- 引用值（commit SHA、分支名、PR号、文件路径等）
    summary TEXT,                                -- 产物摘要描述
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT,                               -- JSON: 扩展元数据（如提交信息、文件变更统计、补丁内容等）

    FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE,
    FOREIGN KEY (repo_id) REFERENCES project_repos(repo_id) ON DELETE CASCADE,

    -- 约束：同一任务的同一仓库的同一类型引用值只能有一个记录
    UNIQUE(task_id, repo_id, ref_type, ref_value),

    -- 约束：ref_type 必须是允许的值之一
    CHECK (ref_type IN ('commit', 'branch', 'pr', 'patch', 'file', 'tag'))
);

-- 索引优化
CREATE INDEX IF NOT EXISTS idx_task_artifact_ref_task
ON task_artifact_ref(task_id);

CREATE INDEX IF NOT EXISTS idx_task_artifact_ref_repo
ON task_artifact_ref(repo_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_task_artifact_ref_type
ON task_artifact_ref(ref_type);

-- 复合索引：任务+仓库联合查询
CREATE INDEX IF NOT EXISTS idx_task_artifact_ref_task_repo
ON task_artifact_ref(task_id, repo_id);

-- 复合索引：类型+引用值查询（用于反向查找哪些任务引用了某个 commit/PR）
CREATE INDEX IF NOT EXISTS idx_task_artifact_ref_type_value
ON task_artifact_ref(ref_type, ref_value);

-- ============================================
-- 数据迁移：为现有项目创建默认仓库绑定
-- ============================================

-- 为所有现有的 projects 自动创建一个默认的 repo 绑定
-- 这确保了向后兼容性：单仓项目自动转换为多仓模式（单仓库）
INSERT OR IGNORE INTO project_repos (
    repo_id,
    project_id,
    name,
    remote_url,
    default_branch,
    workspace_relpath,
    role,
    is_writable,
    auth_profile,
    created_at,
    metadata
)
SELECT
    -- 为现有项目生成确定性的 repo_id（使用 project.id + suffix）
    id || '_default_repo' AS repo_id,
    id AS project_id,
    'default' AS name,
    NULL AS remote_url,  -- 单仓模式没有 remote_url
    'main' AS default_branch,
    '.' AS workspace_relpath,  -- 工作区根目录
    'code' AS role,
    1 AS is_writable,
    NULL AS auth_profile,
    CURRENT_TIMESTAMP AS created_at,
    json_object(
        'migrated_from', 'v0.17',
        'migration_note', 'Auto-created default repo for single-repository project',
        'original_project_path', path
    ) AS metadata
FROM projects
WHERE id NOT IN (SELECT project_id FROM project_repos);

-- ============================================
-- 设计原则和约束
-- ============================================

-- Multi-Repo 设计原则：
-- 1. project_repos 表是项目-仓库绑定的唯一真相源
-- 2. workspace_relpath 支持相对路径（如 ".", "services/api", "../shared"）
-- 3. role 字段用于区分仓库用途（代码/文档/基础设施/monorepo子目录）
-- 4. is_writable 控制仓库是否可写（只读仓库用于依赖/引用）
-- 5. auth_profile 关联到外部凭证管理（如 GitHub PAT、SSH Key）
-- 6. task_repo_scope 记录任务涉及的仓库和路径范围
-- 7. task_dependency 显式记录任务间依赖（支持跨仓库任务协调）
-- 8. task_artifact_ref 记录跨仓库产物引用（commit/PR/patch/file）

-- 仓库角色 (role) 定义：
-- code: 代码仓库（默认）
-- docs: 文档仓库（只包含文档，如 GitBook、MkDocs）
-- infra: 基础设施仓库（Terraform、K8s 配置等）
-- mono-subdir: Monorepo 子目录（特殊处理）

-- 作用域 (scope) 定义：
-- full: 完整仓库访问权限
-- paths: 限定路径访问（通过 path_filters 指定）
-- read_only: 只读访问（即使仓库 is_writable=1）

-- 依赖类型 (dependency_type) 定义：
-- blocks: 阻塞依赖（必须等待依赖任务完成才能开始）
-- requires: 需要依赖（可以并行，但需要依赖任务的产物）
-- suggests: 建议依赖（弱依赖，不影响执行）

-- 引用类型 (ref_type) 定义：
-- commit: Git commit SHA（最常用，不可变引用）
-- branch: Git 分支名（可变引用）
-- pr: Pull Request 号（用于代码审查）
-- patch: 补丁文件路径或内容（用于跨仓库应用变更）
-- file: 文件路径（用于引用特定文件）
-- tag: Git tag（语义化版本引用）

-- ============================================
-- 兼容性保证
-- ============================================

-- 向后兼容性：
-- 1. 现有的 projects 表不做破坏性修改
-- 2. 所有现有 project 自动创建一个默认 repo 绑定（workspace_relpath='.'）
-- 3. 单仓模式的代码无需修改，通过默认 repo 自动适配
-- 4. 新增表使用 IF NOT EXISTS 确保幂等性
-- 5. 所有外键使用 ON DELETE CASCADE 确保数据一致性

-- 扩展性设计：
-- 1. metadata 字段（JSON）预留扩展空间
-- 2. role/scope/dependency_type/ref_type 使用 CHECK 约束，便于后续扩展
-- 3. 索引覆盖常见查询场景，支持高效跨仓库查询

-- Update schema version
INSERT OR REPLACE INTO schema_version (version) VALUES ('0.18.0');
