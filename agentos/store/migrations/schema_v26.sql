-- Migration v0.26: Task Templates
-- Adds task_templates table for saving and reusing task configurations
-- Migration from v0.25 -> v0.26
--
-- 目的: 允许用户保存和重用常用任务配置
-- 功能:
--   - 创建任务模板表
--   - 支持模板标题、描述、元数据模板
--   - 使用统计和创建者追踪
--   - 从模板创建任务功能

-- ============================================
-- 创建 task_templates 表
-- ============================================

CREATE TABLE IF NOT EXISTS task_templates (
    template_id TEXT PRIMARY KEY,         -- ULID 格式的模板 ID
    name TEXT NOT NULL,                    -- 模板名称（必填，1-100 字符）
    description TEXT,                      -- 模板描述（可选）
    title_template TEXT NOT NULL,         -- 任务标题模板（支持变量）
    created_by_default TEXT,               -- 默认创建者
    metadata_template_json TEXT,           -- metadata 模板（JSON 序列化）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- 创建时间
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- 更新时间
    created_by TEXT,                       -- 模板创建者
    use_count INTEGER DEFAULT 0            -- 使用次数（统计）
);

-- ============================================
-- 创建索引
-- ============================================

-- 创建时间索引（用于按时间排序）
CREATE INDEX IF NOT EXISTS idx_task_templates_created_at
ON task_templates(created_at DESC);

-- 模板名称索引（用于名称搜索和唯一性检查）
CREATE INDEX IF NOT EXISTS idx_task_templates_name
ON task_templates(name);

-- 使用次数索引（用于查找最常用的模板）
CREATE INDEX IF NOT EXISTS idx_task_templates_use_count
ON task_templates(use_count DESC);

-- 创建者索引（用于按创建者过滤）
CREATE INDEX IF NOT EXISTS idx_task_templates_created_by
ON task_templates(created_by)
WHERE created_by IS NOT NULL;

-- ============================================
-- 添加约束（使用触发器实现）
-- ============================================

-- 触发器 1: 检查 name 长度（1-100 字符）
CREATE TRIGGER IF NOT EXISTS check_task_templates_name_length_insert
BEFORE INSERT ON task_templates
FOR EACH ROW
WHEN length(trim(NEW.name)) < 1 OR length(NEW.name) > 100
BEGIN
    SELECT RAISE(ABORT, 'Template name must be 1-100 characters');
END;

CREATE TRIGGER IF NOT EXISTS check_task_templates_name_length_update
BEFORE UPDATE ON task_templates
FOR EACH ROW
WHEN length(trim(NEW.name)) < 1 OR length(NEW.name) > 100
BEGIN
    SELECT RAISE(ABORT, 'Template name must be 1-100 characters');
END;

-- 触发器 2: 检查 title_template 不为空
CREATE TRIGGER IF NOT EXISTS check_task_templates_title_template_insert
BEFORE INSERT ON task_templates
FOR EACH ROW
WHEN length(trim(NEW.title_template)) < 1
BEGIN
    SELECT RAISE(ABORT, 'Title template cannot be empty');
END;

CREATE TRIGGER IF NOT EXISTS check_task_templates_title_template_update
BEFORE UPDATE ON task_templates
FOR EACH ROW
WHEN length(trim(NEW.title_template)) < 1
BEGIN
    SELECT RAISE(ABORT, 'Title template cannot be empty');
END;

-- 触发器 3: 验证 metadata_template_json 是有效的 JSON 对象
CREATE TRIGGER IF NOT EXISTS check_task_templates_metadata_json_insert
BEFORE INSERT ON task_templates
FOR EACH ROW
WHEN NEW.metadata_template_json IS NOT NULL
BEGIN
    SELECT CASE
        WHEN json_valid(NEW.metadata_template_json) = 0
        THEN RAISE(ABORT, 'Invalid metadata_template_json: must be valid JSON')
        WHEN json_type(NEW.metadata_template_json) != 'object'
        THEN RAISE(ABORT, 'Invalid metadata_template_json: must be JSON object')
    END;
END;

CREATE TRIGGER IF NOT EXISTS check_task_templates_metadata_json_update
BEFORE UPDATE ON task_templates
FOR EACH ROW
WHEN NEW.metadata_template_json IS NOT NULL
BEGIN
    SELECT CASE
        WHEN json_valid(NEW.metadata_template_json) = 0
        THEN RAISE(ABORT, 'Invalid metadata_template_json: must be valid JSON')
        WHEN json_type(NEW.metadata_template_json) != 'object'
        THEN RAISE(ABORT, 'Invalid metadata_template_json: must be JSON object')
    END;
END;

-- 触发器 4: 自动更新 updated_at 时间戳
CREATE TRIGGER IF NOT EXISTS update_task_templates_timestamp
AFTER UPDATE ON task_templates
FOR EACH ROW
BEGIN
    UPDATE task_templates SET updated_at = CURRENT_TIMESTAMP WHERE template_id = NEW.template_id;
END;

-- 触发器 5: 检查 use_count 不能为负数
CREATE TRIGGER IF NOT EXISTS check_task_templates_use_count_insert
BEFORE INSERT ON task_templates
FOR EACH ROW
WHEN NEW.use_count < 0
BEGIN
    SELECT RAISE(ABORT, 'use_count cannot be negative');
END;

CREATE TRIGGER IF NOT EXISTS check_task_templates_use_count_update
BEFORE UPDATE ON task_templates
FOR EACH ROW
WHEN NEW.use_count < 0
BEGIN
    SELECT RAISE(ABORT, 'use_count cannot be negative');
END;

-- ============================================
-- 设计说明
-- ============================================

-- 字段说明:
-- - template_id: ULID 格式的唯一标识符（与 task_id 格式一致）
-- - name: 模板名称（用户友好，必填，1-100 字符）
-- - description: 模板详细描述（可选）
-- - title_template: 任务标题模板（必填，支持变量占位符）
-- - created_by_default: 从此模板创建任务时的默认创建者
-- - metadata_template_json: metadata 模板（JSON 对象格式）
-- - created_at: 模板创建时间（自动设置）
-- - updated_at: 模板更新时间（自动更新）
-- - created_by: 模板创建者（用户 ID 或系统标识）
-- - use_count: 使用次数统计（每次从模板创建任务时 +1）

-- 使用场景:
-- 1. 用户创建任务时可以选择一个模板来自动填充字段
-- 2. 用户可以将当前任务配置保存为模板以便重用
-- 3. 系统可以提供内置的常用任务模板

-- 模板变量:
-- - title_template 和 metadata_template_json 支持变量占位符
-- - 例如: "Fix bug in {component}" 可以在创建任务时替换 {component}
-- - 当前版本不实现变量替换，后续可扩展

-- JSON 格式:
-- - metadata_template_json: 必须是 JSON 对象，如 {"priority": "high", "type": "bug"}
-- - 使用触发器在插入/更新时验证 JSON 格式

-- 时间戳自动管理:
-- - created_at: 插入时自动设置
-- - updated_at: 插入时自动设置，更新时自动更新

-- 使用统计:
-- - use_count: 初始值为 0，每次从模板创建任务时递增
-- - Available于显示最常用的模板

-- Update schema version
INSERT OR REPLACE INTO schema_version (version) VALUES ('0.26.0');
