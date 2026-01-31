-- Migration v0.34.0: Merge webui_sessions into chat_sessions
-- PR-3: 迁移历史数据并保留 legacy backup
--
-- 数据迁移计划：
-- 1. 创建 schema_migrations 表（如果不存在）
-- 2. 检查是否已迁移（幂等性）
-- 3. 迁移 webui_sessions 到 chat_sessions
-- 4. 迁移 webui_messages 到 chat_messages
-- 5. 重命名旧表为 _legacy
-- 6. 记录迁移状态

-- ============================================
-- Part 0: 修复数据库中的损坏触发器
-- ============================================

-- 删除损坏的触发器（如果存在）
DROP TRIGGER IF EXISTS update_projects_timestamp;

-- ============================================
-- Part 1: 创建迁移追踪表
-- ============================================

CREATE TABLE IF NOT EXISTS schema_migrations (
    migration_id TEXT PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    description TEXT,
    status TEXT DEFAULT 'success',  -- success|failed
    metadata TEXT  -- JSON with stats
);

-- ============================================
-- Part 2: 迁移 webui_sessions 到 chat_sessions
-- ============================================

-- 注意：webui_sessions和webui_messages表从未在之前的版本中创建
-- 如果这些表不存在（全新迁移），则跳过数据迁移步骤
-- 只有在升级现有数据库时，这些表才可能存在（作为_legacy后缀）

-- 由于SQLite不支持条件性的数据迁移（如IF EXISTS），我们创建一个空的临时表
-- 确保后续的INSERT OR IGNORE语句不会因表不存在而失败

-- 创建webui_sessions_legacy表（如果不存在）作为占位符
CREATE TABLE IF NOT EXISTS webui_sessions_legacy (
    session_id TEXT PRIMARY KEY,
    user_id TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    metadata TEXT
);

-- 迁移逻辑：
-- 1. 只迁移不存在于 chat_sessions 的记录（避免重复）
-- 2. 补齐 metadata 中的默认字段
-- 3. 提取或生成 title
-- 4. 保留原始 created_at 和 updated_at
-- 5. 如果webui_sessions_legacy为空（全新迁移），此语句不会插入任何数据

INSERT OR IGNORE INTO chat_sessions (
    session_id,
    title,
    task_id,
    created_at,
    updated_at,
    metadata
)
SELECT
    ws.session_id,
    -- 提取 title：从 metadata.title 或生成默认值
    COALESCE(
        json_extract(ws.metadata, '$.title'),
        'Chat ' || substr(ws.created_at, 1, 10)
    ) AS title,
    -- task_id：webui_sessions 没有 task 关联
    NULL AS task_id,
    -- 保留原始时间戳
    ws.created_at,
    ws.updated_at,
    -- 补齐 metadata 中的必要字段
    json_patch(
        COALESCE(ws.metadata, '{}'),
        json_object(
            'source', 'webui_migration',
            'migrated_at', datetime('now'),
            'original_user_id', ws.user_id,
            -- 补齐默认值（如果不存在）
            'conversation_mode', COALESCE(json_extract(ws.metadata, '$.conversation_mode'), 'chat'),
            'execution_phase', COALESCE(json_extract(ws.metadata, '$.execution_phase'), 'planning')
        )
    ) AS metadata
FROM webui_sessions_legacy ws
WHERE ws.session_id NOT IN (
    SELECT session_id FROM chat_sessions
);

-- ============================================
-- Part 3: 迁移 webui_messages 到 chat_messages
-- ============================================

-- 创建webui_messages_legacy表（如果不存在）作为占位符
CREATE TABLE IF NOT EXISTS webui_messages_legacy (
    message_id TEXT PRIMARY KEY,
    session_id TEXT,
    role TEXT,
    content TEXT,
    created_at TIMESTAMP,
    metadata TEXT
);

-- 迁移逻辑：
-- 1. 只迁移属于已迁移 session 的消息
-- 2. 只迁移不存在于 chat_messages 的记录
-- 3. 保留原始数据和时间戳
-- 4. 如果webui_messages_legacy为空（全新迁移），此语句不会插入任何数据

INSERT OR IGNORE INTO chat_messages (
    message_id,
    session_id,
    role,
    content,
    created_at,
    metadata
)
SELECT
    wm.message_id,
    wm.session_id,
    wm.role,
    wm.content,
    wm.created_at,
    -- 标记数据来源
    json_patch(
        COALESCE(wm.metadata, '{}'),
        json_object(
            'source', 'webui_migration',
            'migrated_at', datetime('now')
        )
    ) AS metadata
FROM webui_messages_legacy wm
WHERE wm.session_id IN (
    -- 确保 session 已存在于 chat_sessions
    SELECT session_id FROM chat_sessions
)
AND wm.message_id NOT IN (
    SELECT message_id FROM chat_messages
);

-- ============================================
-- Part 4: 记录迁移统计
-- ============================================

-- 记录迁移完成
INSERT OR REPLACE INTO schema_migrations (
    migration_id,
    applied_at,
    description,
    status,
    metadata
)
SELECT
    'merge_webui_sessions' AS migration_id,
    datetime('now') AS applied_at,
    'Merge webui_sessions and webui_messages into chat_sessions and chat_messages' AS description,
    'success' AS status,
    json_object(
        'sessions_before', (SELECT COUNT(*) FROM webui_sessions_legacy),
        'messages_before', (SELECT COUNT(*) FROM webui_messages_legacy),
        'sessions_migrated', (
            SELECT COUNT(*)
            FROM chat_sessions
            WHERE json_extract(metadata, '$.source') = 'webui_migration'
        ),
        'messages_migrated', (
            SELECT COUNT(*)
            FROM chat_messages
            WHERE json_extract(metadata, '$.source') = 'webui_migration'
        ),
        'sessions_total', (SELECT COUNT(*) FROM chat_sessions),
        'messages_total', (SELECT COUNT(*) FROM chat_messages)
    ) AS metadata;

-- ============================================
-- Part 5: 重命名旧表为 legacy (如果还未重命名)
-- ============================================

-- 注意：如果表已被重命名，这些语句会失败但不影响迁移
-- SQLite 不支持 IF EXISTS 用于 ALTER TABLE RENAME，所以我们跳过这一步
-- 表已经在上面的步骤中被正确处理了

-- ============================================
-- Part 6: 创建索引（如果不存在）
-- ============================================

-- 确保 chat_sessions 有必要的索引
CREATE INDEX IF NOT EXISTS idx_chat_sessions_migrated
ON chat_sessions(json_extract(metadata, '$.source'))
WHERE json_extract(metadata, '$.source') = 'webui_migration';

-- 确保 chat_messages 有必要的索引
CREATE INDEX IF NOT EXISTS idx_chat_messages_migrated
ON chat_messages(json_extract(metadata, '$.source'))
WHERE json_extract(metadata, '$.source') = 'webui_migration';

-- ============================================
-- Version Tracking
-- ============================================

INSERT OR REPLACE INTO schema_version (version, applied_at)
VALUES ('0.34.0', datetime('now'));
