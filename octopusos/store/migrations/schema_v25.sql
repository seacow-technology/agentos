-- Migration v0.25: Projects Metadata Enhancement
-- Extends projects table with comprehensive metadata fields
-- Migration from v0.24 -> v0.25
--
-- 目的: 增强项目管理能力，添加项目元数据、配置和生命周期管理
-- 新增字段:
--   - name: 项目名称（用户友好）
--   - description: 项目描述
--   - status: 状态管理（active/archived/deleted）
--   - tags: 标签（JSON array）
--   - default_repo_id: 默认仓库 ID
--   - default_workdir: 默认工作目录
--   - settings: 项目配置（JSON blob）
--   - created_at: 创建时间
--   - updated_at: 更新时间
--   - created_by: 创建者

-- ============================================
-- 扩展 projects 表
-- ============================================

-- 1. 添加 name 字段（项目名称，必填，默认为空字符串）
ALTER TABLE projects ADD COLUMN name TEXT NOT NULL DEFAULT '';

-- 2. 添加 description 字段（项目描述，可选）
ALTER TABLE projects ADD COLUMN description TEXT;

-- 3. 添加 status 字段（项目状态，默认为 active）
ALTER TABLE projects ADD COLUMN status TEXT DEFAULT 'active';

-- 4. 添加 tags 字段（标签，JSON array 格式）
ALTER TABLE projects ADD COLUMN tags TEXT;

-- 5. 添加 default_repo_id 字段（默认仓库 ID）
ALTER TABLE projects ADD COLUMN default_repo_id TEXT;

-- 6. 添加 default_workdir 字段（默认工作目录）
ALTER TABLE projects ADD COLUMN default_workdir TEXT;

-- 7. 添加 settings 字段（项目配置，JSON blob）
ALTER TABLE projects ADD COLUMN settings TEXT;

-- 8. 添加 created_at 字段（创建时间）
-- 注意：projects 表已有 added_at 字段，created_at 将使用 added_at 的值
ALTER TABLE projects ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- 9. 添加 updated_at 字段（更新时间）
ALTER TABLE projects ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- 10. 添加 created_by 字段（创建者）
ALTER TABLE projects ADD COLUMN created_by TEXT;

-- ============================================
-- 填充现有数据的默认值
-- ============================================

-- 1. 为现有项目生成友好的名称（从 id 转换）
--    例如: 'project-a' -> 'Project A'
--          'my-app' -> 'My App'
--          'backend_service' -> 'Backend Service'
UPDATE projects
SET name = CASE
    -- 处理包含连字符的情况
    WHEN id LIKE '%-%' THEN
        -- 将连字符替换为空格，并首字母大写
        upper(substr(replace(id, '-', ' '), 1, 1)) ||
        substr(replace(id, '-', ' '), 2)
    -- 处理包含下划线的情况
    WHEN id LIKE '%_%' THEN
        upper(substr(replace(id, '_', ' '), 1, 1)) ||
        substr(replace(id, '_', ' '), 2)
    -- 默认情况：只首字母大写
    ELSE
        upper(substr(id, 1, 1)) || substr(id, 2)
END
WHERE name = '';

-- 2. 复制 added_at 到 created_at（保持时间一致性）
UPDATE projects
SET created_at = added_at
WHERE created_at = CURRENT_TIMESTAMP;

-- 3. 设置 updated_at 为当前时间
UPDATE projects
SET updated_at = CURRENT_TIMESTAMP
WHERE updated_at = CURRENT_TIMESTAMP;

-- 4. 初始化 tags 为空数组（JSON 格式）
UPDATE projects
SET tags = '[]'
WHERE tags IS NULL;

-- 5. 初始化 settings 为空对象（JSON 格式）
UPDATE projects
SET settings = '{}'
WHERE settings IS NULL;

-- ============================================
-- 创建索引
-- ============================================

-- 状态索引（用于按状态过滤项目）
CREATE INDEX IF NOT EXISTS idx_projects_status
ON projects(status);

-- 创建时间索引（用于按时间排序）
CREATE INDEX IF NOT EXISTS idx_projects_created_at
ON projects(created_at DESC);

-- 更新时间索引（用于查找最近更新的项目）
CREATE INDEX IF NOT EXISTS idx_projects_updated_at
ON projects(updated_at DESC);

-- 名称索引（用于名称搜索）
CREATE INDEX IF NOT EXISTS idx_projects_name
ON projects(name);

-- 状态和创建时间复合索引（用于状态过滤 + 时间排序）
CREATE INDEX IF NOT EXISTS idx_projects_status_created
ON projects(status, created_at DESC);

-- 默认仓库索引（用于快速查找使用特定仓库的项目）
CREATE INDEX IF NOT EXISTS idx_projects_default_repo
ON projects(default_repo_id)
WHERE default_repo_id IS NOT NULL;

-- ============================================
-- 添加约束（使用触发器实现，因为 SQLite 不支持 ALTER TABLE ADD CONSTRAINT）
-- ============================================

-- 触发器 1: 检查 status 必须是有效值
CREATE TRIGGER IF NOT EXISTS check_projects_status_insert
BEFORE INSERT ON projects
FOR EACH ROW
WHEN NEW.status NOT IN ('active', 'archived', 'deleted')
BEGIN
    SELECT RAISE(ABORT, 'Invalid status: must be active, archived, or deleted');
END;

CREATE TRIGGER IF NOT EXISTS check_projects_status_update
BEFORE UPDATE ON projects
FOR EACH ROW
WHEN NEW.status NOT IN ('active', 'archived', 'deleted')
BEGIN
    SELECT RAISE(ABORT, 'Invalid status: must be active, archived, or deleted');
END;

-- 触发器 2: 检查 default_repo_id 外键（确保引用的 repo_id 存在）
CREATE TRIGGER IF NOT EXISTS check_projects_default_repo_insert
BEFORE INSERT ON projects
FOR EACH ROW
WHEN NEW.default_repo_id IS NOT NULL
BEGIN
    SELECT CASE
        WHEN (SELECT COUNT(*) FROM project_repos WHERE repo_id = NEW.default_repo_id AND project_id = NEW.id) = 0
        THEN RAISE(ABORT, 'Invalid default_repo_id: repo must exist in project_repos for this project')
    END;
END;

CREATE TRIGGER IF NOT EXISTS check_projects_default_repo_update
BEFORE UPDATE ON projects
FOR EACH ROW
WHEN NEW.default_repo_id IS NOT NULL
BEGIN
    SELECT CASE
        WHEN (SELECT COUNT(*) FROM project_repos WHERE repo_id = NEW.default_repo_id AND project_id = NEW.id) = 0
        THEN RAISE(ABORT, 'Invalid default_repo_id: repo must exist in project_repos for this project')
    END;
END;

-- 触发器 3: 自动更新 updated_at 时间戳
CREATE TRIGGER IF NOT EXISTS update_projects_timestamp
AFTER UPDATE ON projects
FOR EACH ROW
BEGIN
    UPDATE projects SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- 触发器 4: 验证 tags 是有效的 JSON 数组
CREATE TRIGGER IF NOT EXISTS check_projects_tags_json_insert
BEFORE INSERT ON projects
FOR EACH ROW
WHEN NEW.tags IS NOT NULL
BEGIN
    SELECT CASE
        WHEN json_valid(NEW.tags) = 0
        THEN RAISE(ABORT, 'Invalid tags: must be valid JSON')
        WHEN json_type(NEW.tags) != 'array'
        THEN RAISE(ABORT, 'Invalid tags: must be JSON array')
    END;
END;

CREATE TRIGGER IF NOT EXISTS check_projects_tags_json_update
BEFORE UPDATE ON projects
FOR EACH ROW
WHEN NEW.tags IS NOT NULL
BEGIN
    SELECT CASE
        WHEN json_valid(NEW.tags) = 0
        THEN RAISE(ABORT, 'Invalid tags: must be valid JSON')
        WHEN json_type(NEW.tags) != 'array'
        THEN RAISE(ABORT, 'Invalid tags: must be JSON array')
    END;
END;

-- 触发器 5: 验证 settings 是有效的 JSON 对象
CREATE TRIGGER IF NOT EXISTS check_projects_settings_json_insert
BEFORE INSERT ON projects
FOR EACH ROW
WHEN NEW.settings IS NOT NULL
BEGIN
    SELECT CASE
        WHEN json_valid(NEW.settings) = 0
        THEN RAISE(ABORT, 'Invalid settings: must be valid JSON')
        WHEN json_type(NEW.settings) != 'object'
        THEN RAISE(ABORT, 'Invalid settings: must be JSON object')
    END;
END;

CREATE TRIGGER IF NOT EXISTS check_projects_settings_json_update
BEFORE UPDATE ON projects
FOR EACH ROW
WHEN NEW.settings IS NOT NULL
BEGIN
    SELECT CASE
        WHEN json_valid(NEW.settings) = 0
        THEN RAISE(ABORT, 'Invalid settings: must be valid JSON')
        WHEN json_type(NEW.settings) != 'object'
        THEN RAISE(ABORT, 'Invalid settings: must be JSON object')
    END;
END;

-- ============================================
-- 设计说明
-- ============================================

-- 字段说明:
-- - name: 用户友好的项目名称（必填，从 id 自动生成或用户指定）
-- - description: 项目详细描述（可选）
-- - status: 项目状态（active=活跃, archived=归档, deleted=已删除）
-- - tags: 项目标签，JSON 数组格式，如 ["python", "web", "api"]
-- - default_repo_id: 默认仓库 ID（外键到 project_repos.repo_id）
-- - default_workdir: 默认工作目录（可以是绝对路径或相对于项目根的路径）
-- - settings: 项目配置，JSON 对象，如 {"theme": "dark", "auto_save": true}
-- - created_at: 创建时间（自动设置）
-- - updated_at: 更新时间（自动更新）
-- - created_by: 创建者（用户 ID 或系统标识）

-- 状态管理:
-- - active: 活跃项目（默认状态）
-- - archived: 归档项目（不再活跃但保留数据）
-- - deleted: 已删除项目（软删除，可恢复）

-- 外键关系:
-- - default_repo_id 必须引用 project_repos 表中属于该项目的仓库
-- - 使用触发器实现外键约束（因为需要检查 project_id 匹配）

-- JSON 格式验证:
-- - tags: 必须是 JSON 数组，如 ["tag1", "tag2"]
-- - settings: 必须是 JSON 对象，如 {"key": "value"}
-- - 使用触发器在插入/更新时验证 JSON 格式

-- 时间戳自动管理:
-- - created_at: 插入时自动设置（从 added_at 复制）
-- - updated_at: 插入时自动设置，更新时自动更新

-- 向后兼容性:
-- - 所有新字段都有默认值或允许 NULL
-- - 现有数据自动填充合理的默认值
-- - 不影响现有代码的 id 和 path 字段

-- Update schema version
INSERT OR REPLACE INTO schema_version (version) VALUES ('0.25.0');
