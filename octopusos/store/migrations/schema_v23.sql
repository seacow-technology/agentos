-- Migration v0.23: Content & Answers Management
-- Simplified schema for Content Items and Answer Packs
-- Migration from v0.22 -> v0.23

-- ============================================
-- Schema Version Table (if not exists)
-- ============================================

CREATE TABLE IF NOT EXISTS schema_version (
    version TEXT PRIMARY KEY
);

-- ============================================
-- Content Items: 内容资产单表管理
-- ============================================

CREATE TABLE IF NOT EXISTS content_items (
    id TEXT PRIMARY KEY,
    content_type TEXT NOT NULL,              -- Type: agent | workflow | skill | tool
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',    -- Status: draft | active | deprecated | frozen
    source_uri TEXT,                         -- Source URI (Git URL, file path, etc.)
    metadata_json TEXT,                      -- JSON: additional metadata
    release_notes TEXT,                      -- Release notes/changelog
    created_at TEXT NOT NULL,                -- ISO 8601 timestamp
    updated_at TEXT NOT NULL,                -- ISO 8601 timestamp

    CHECK (content_type IN ('agent', 'workflow', 'skill', 'tool')),
    CHECK (status IN ('draft', 'active', 'deprecated', 'frozen'))
);

-- Unique index: Ensure only one version per (type, name, version)
CREATE UNIQUE INDEX IF NOT EXISTS idx_content_items_type_name_version
    ON content_items(content_type, name, version);

-- Index for listing by type and name
CREATE INDEX IF NOT EXISTS idx_content_items_type_name
    ON content_items(content_type, name);

-- Index for filtering by status
CREATE INDEX IF NOT EXISTS idx_content_items_status
    ON content_items(status);

-- Composite index for type + status queries
CREATE INDEX IF NOT EXISTS idx_content_items_type_status
    ON content_items(content_type, status);


-- ============================================
-- Answer Packs: 答案包管理
-- ============================================

CREATE TABLE IF NOT EXISTS answer_packs (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,               -- Pack name (unique)
    status TEXT NOT NULL DEFAULT 'draft',    -- Status: draft | active | archived
    items_json TEXT NOT NULL,                -- JSON array: Q&A items
    metadata_json TEXT,                      -- JSON: additional metadata
    created_at TEXT NOT NULL,                -- ISO 8601 timestamp
    updated_at TEXT NOT NULL,                -- ISO 8601 timestamp

    CHECK (status IN ('draft', 'active', 'archived'))
);

-- Index for filtering by status
CREATE INDEX IF NOT EXISTS idx_answer_packs_status
    ON answer_packs(status);

-- Index for searching by name
CREATE INDEX IF NOT EXISTS idx_answer_packs_name
    ON answer_packs(name);


-- ============================================
-- Answer Pack Links: 答案包关联追踪
-- ============================================

CREATE TABLE IF NOT EXISTS answer_pack_links (
    id TEXT PRIMARY KEY,
    pack_id TEXT NOT NULL,                   -- Answer pack ID
    entity_type TEXT NOT NULL,               -- Entity type: task | intent
    entity_id TEXT NOT NULL,                 -- Task ID or Intent ID
    created_at TEXT NOT NULL,                -- ISO 8601 timestamp

    FOREIGN KEY (pack_id) REFERENCES answer_packs(id) ON DELETE CASCADE,
    CHECK (entity_type IN ('task', 'intent'))
);

-- Index for querying links by pack
CREATE INDEX IF NOT EXISTS idx_answer_pack_links_pack
    ON answer_pack_links(pack_id);

-- Index for querying links by entity
CREATE INDEX IF NOT EXISTS idx_answer_pack_links_entity
    ON answer_pack_links(entity_type, entity_id);

-- Composite index for pack + entity queries
CREATE INDEX IF NOT EXISTS idx_answer_pack_links_pack_entity
    ON answer_pack_links(pack_id, entity_type, entity_id);


-- ============================================
-- 设计原则和使用说明
-- ============================================

-- Content Items 设计原则：
-- 1. 单表设计：每个版本是独立记录（简化查询）
-- 2. 版本控制：通过 (type, name, version) 唯一约束确保版本唯一性
-- 3. 激活控制：同一 (type, name) 只能有一个 status='active' 的版本（应用层强制）
-- 4. 生命周期：draft -> active -> deprecated/frozen

-- Answer Packs 设计原则：
-- 1. items_json 格式：[{"question": "...", "answer": "..."}]
-- 2. 状态管理：draft（开发中）-> active（生产Available）-> archived（归档）
-- 3. 关联追踪：通过 answer_pack_links 表追踪哪些任务/意图使用了答案包

-- 状态转换规则：
-- Content Items:
--   draft -> active: 激活版本（同时将旧 active 版本改为 deprecated）
--   active -> deprecated: 废弃版本
--   active/deprecated -> frozen: 冻结版本（完全禁用）
--
-- Answer Packs:
--   draft -> active: 发布答案包
--   active -> archived: 归档答案包


-- ============================================
-- 使用示例
-- ============================================

-- 示例 1: 创建新 Content Item
-- INSERT INTO content_items (
--     id, content_type, name, version, status,
--     source_uri, metadata_json, release_notes,
--     created_at, updated_at
-- ) VALUES (
--     'content-001',
--     'agent',
--     'lead-scanner',
--     '1.0.0',
--     'draft',
--     'git://github.com/agentos/agents/lead-scanner',
--     '{"author": "team@agentos.dev"}',
--     'Initial version with risk mining',
--     '2026-01-29T00:00:00Z',
--     '2026-01-29T00:00:00Z'
-- );

-- 示例 2: 激活版本（事务）
-- BEGIN TRANSACTION;
-- -- 先将旧版本改为 deprecated
-- UPDATE content_items
-- SET status = 'deprecated', updated_at = '2026-01-29T01:00:00Z'
-- WHERE content_type = 'agent' AND name = 'lead-scanner' AND status = 'active';
-- -- 再激活新版本
-- UPDATE content_items
-- SET status = 'active', updated_at = '2026-01-29T01:00:00Z'
-- WHERE id = 'content-002';
-- COMMIT;

-- 示例 3: 创建 Answer Pack
-- INSERT INTO answer_packs (
--     id, name, status, items_json, metadata_json,
--     created_at, updated_at
-- ) VALUES (
--     'pack-001',
--     'python-best-practices',
--     'draft',
--     '[{"question": "How to handle errors?", "answer": "Use try-except blocks"}]',
--     '{"author": "knowledge-team@agentos.dev"}',
--     '2026-01-29T00:00:00Z',
--     '2026-01-29T00:00:00Z'
-- );

-- 示例 4: 关联 Answer Pack 到 Task
-- INSERT INTO answer_pack_links (
--     id, pack_id, entity_type, entity_id, created_at
-- ) VALUES (
--     'link-001',
--     'pack-001',
--     'task',
--     'task-123',
--     '2026-01-29T00:00:00Z'
-- );

-- Update schema version
INSERT OR REPLACE INTO schema_version (version) VALUES ('0.23.0');
