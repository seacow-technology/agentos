-- ProjectKB FTS5 Trigger Hotfix (v0.10.0)
-- 修复 v0.7.0 触发器错误：不再引用不存在的列 T.path
-- 重建 FTS 表以包含 path 列（避免 join kb_sources）

-- 1. 安全删除旧 FTS 表和触发器
DROP TABLE IF EXISTS kb_chunks_fts;
DROP TRIGGER IF EXISTS kb_chunks_ai;
DROP TRIGGER IF EXISTS kb_chunks_ad;
DROP TRIGGER IF EXISTS kb_chunks_au;

-- 2. 创建新 FTS 表（contentless 模式，触发器维护内容）
-- 不使用 content='kb_chunks' 因为 kb_chunks 没有 path 列
CREATE VIRTUAL TABLE kb_chunks_fts USING fts5(
    chunk_id UNINDEXED,     -- 用于连接，不索引
    path,                   -- 文档路径（可检索）
    heading,                -- 标题（高权重）
    content                 -- 正文内容
);

-- 3. INSERT trigger: 插入 chunk 时同步到 FTS
CREATE TRIGGER kb_chunks_ai AFTER INSERT ON kb_chunks BEGIN
    INSERT INTO kb_chunks_fts(rowid, chunk_id, path, heading, content)
    SELECT 
        NEW.rowid,
        NEW.chunk_id,
        s.path,
        NEW.heading,
        NEW.content
    FROM kb_sources s
    WHERE s.source_id = NEW.source_id;
END;

-- 4. DELETE trigger: 删除 chunk 时从 FTS 移除
CREATE TRIGGER kb_chunks_ad AFTER DELETE ON kb_chunks BEGIN
    DELETE FROM kb_chunks_fts WHERE rowid = OLD.rowid;
END;

-- 5. UPDATE trigger: 更新 chunk 时删旧插新（防止幽灵命中）
CREATE TRIGGER kb_chunks_au AFTER UPDATE ON kb_chunks BEGIN
    -- 删除旧内容
    DELETE FROM kb_chunks_fts WHERE rowid = OLD.rowid;
    
    -- 插入新内容
    INSERT INTO kb_chunks_fts(rowid, chunk_id, path, heading, content)
    SELECT 
        NEW.rowid,
        NEW.chunk_id,
        s.path,
        NEW.heading,
        NEW.content
    FROM kb_sources s
    WHERE s.source_id = NEW.source_id;
END;

-- 6. 触发器验证
SELECT 
    CASE 
        WHEN COUNT(*) >= 3 THEN 'FTS5 triggers rebuilt successfully (v0.10.0)'
        ELSE 'Warning: Some triggers may not have been created'
    END as status
FROM sqlite_master 
WHERE type = 'trigger' 
  AND name LIKE 'kb_chunks_a%';

-- 更新 schema 版本（幂等操作）
INSERT OR REPLACE INTO schema_version (version, applied_at) 
VALUES ('0.10.0', datetime('now'));
