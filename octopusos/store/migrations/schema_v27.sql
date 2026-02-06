-- Migration v0.27: Add metadata column to projects table
-- Adds generic metadata JSON field to projects
-- Migration from v0.26 -> v0.27
--
-- 目的: 添加通用的 metadata 字段用于存储项目额外信息
-- 功能:
--   - 添加 metadata 列（JSON 格式）
--   - 初始化现有数据为空对象
--   - 添加 JSON 格式验证触发器

-- ============================================
-- 添加 metadata 字段
-- ============================================

-- 添加 metadata 字段（JSON blob，存储额外的项目元数据）
ALTER TABLE projects ADD COLUMN metadata TEXT;

-- ============================================
-- 填充现有数据的默认值
-- ============================================

-- 初始化 metadata 为空对象（JSON 格式）
UPDATE projects
SET metadata = '{}'
WHERE metadata IS NULL;

-- ============================================
-- 添加约束（使用触发器实现）
-- ============================================

-- 触发器 1: 验证 metadata 是有效的 JSON 对象
CREATE TRIGGER IF NOT EXISTS check_projects_metadata_json_insert
BEFORE INSERT ON projects
FOR EACH ROW
WHEN NEW.metadata IS NOT NULL
BEGIN
    SELECT CASE
        WHEN json_valid(NEW.metadata) = 0
        THEN RAISE(ABORT, 'Invalid metadata: must be valid JSON')
        WHEN json_type(NEW.metadata) != 'object'
        THEN RAISE(ABORT, 'Invalid metadata: must be JSON object')
    END;
END;

CREATE TRIGGER IF NOT EXISTS check_projects_metadata_json_update
BEFORE UPDATE ON projects
FOR EACH ROW
WHEN NEW.metadata IS NOT NULL
BEGIN
    SELECT CASE
        WHEN json_valid(NEW.metadata) = 0
        THEN RAISE(ABORT, 'Invalid metadata: must be valid JSON')
        WHEN json_type(NEW.metadata) != 'object'
        THEN RAISE(ABORT, 'Invalid metadata: must be JSON object')
    END;
END;

-- ============================================
-- 设计说明
-- ============================================

-- 字段说明:
-- - metadata: 通用元数据字段，JSON 对象格式
--   可以存储任意额外信息，如 {"owner": "team-a", "priority": "high"}

-- JSON 格式验证:
-- - metadata 必须是 JSON 对象，如 {"key": "value"}
-- - 使用触发器在插入/更新时验证 JSON 格式
-- - 空值允许，但如果提供必须是有效的 JSON 对象

-- 与 settings 的区别:
-- - settings: 项目配置（影响项目行为）
-- - metadata: 项目元数据（描述性信息）

-- Update schema version
INSERT OR REPLACE INTO schema_version (version) VALUES ('0.27.0');
