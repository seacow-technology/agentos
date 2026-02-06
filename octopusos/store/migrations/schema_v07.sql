-- ProjectKB Migration: v0.7.0 - Project Knowledge Base Tables
--
-- 为 AgentOS 添加项目文档知识库检索能力
-- 复用现有 store/registry.sqlite 数据库

-- 1. 文档源表 - 追踪已索引的文档
CREATE TABLE IF NOT EXISTS kb_sources (
    source_id TEXT PRIMARY KEY,
    repo_id TEXT NOT NULL,              -- 项目标识 (默认使用工作区路径哈希)
    path TEXT NOT NULL,                 -- 相对于项目根的路径
    file_hash TEXT NOT NULL,            -- 文件内容 SHA256 哈希
    mtime INTEGER NOT NULL,             -- 修改时间戳 (Unix epoch)
    doc_type TEXT,                      -- 文档类型: adr/runbook/spec/guide/index
    language TEXT DEFAULT 'markdown',   -- 文档语言
    tags TEXT,                          -- JSON 数组: ["architecture", "api"]
    created_at TEXT NOT NULL,           -- 首次索引时间
    updated_at TEXT NOT NULL,           -- 最后更新时间
    UNIQUE(repo_id, path)
);

-- 2. 文档片段表 - 按 heading 切片的内容块
CREATE TABLE IF NOT EXISTS kb_chunks (
    chunk_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    heading TEXT,                       -- 所属标题 (如 "## API Design")
    start_line INTEGER NOT NULL,        -- 起始行号 (1-based)
    end_line INTEGER NOT NULL,          -- 结束行号 (inclusive)
    content TEXT NOT NULL,              -- 原始内容
    content_hash TEXT NOT NULL,         -- 片段内容哈希
    token_count INTEGER,                -- 估算 token 数
    created_at TEXT NOT NULL,
    FOREIGN KEY (source_id) REFERENCES kb_sources(source_id) ON DELETE CASCADE
);

-- 3. FTS5 全文索引 (关键词检索核心)
-- 使用 SQLite FTS5 进行 BM25 相关性评分
CREATE VIRTUAL TABLE IF NOT EXISTS kb_chunks_fts USING fts5(
    chunk_id UNINDEXED,                 -- 不索引 ID (用于连接)
    heading,                            -- 标题 (高权重)
    content,                            -- 正文内容
    path UNINDEXED,                     -- 路径 (用于过滤，不索引)
    content='kb_chunks',                -- 内容表
    content_rowid='rowid'               -- 连接列
);

-- FTS5 触发器: 自动同步 kb_chunks → kb_chunks_fts
CREATE TRIGGER IF NOT EXISTS kb_chunks_ai AFTER INSERT ON kb_chunks BEGIN
  INSERT INTO kb_chunks_fts(rowid, chunk_id, heading, content, path)
  SELECT rowid, chunk_id, heading, content, 
         (SELECT path FROM kb_sources WHERE source_id = NEW.source_id)
  FROM kb_chunks WHERE rowid = NEW.rowid;
END;

CREATE TRIGGER IF NOT EXISTS kb_chunks_ad AFTER DELETE ON kb_chunks BEGIN
  DELETE FROM kb_chunks_fts WHERE rowid = OLD.rowid;
END;

CREATE TRIGGER IF NOT EXISTS kb_chunks_au AFTER UPDATE ON kb_chunks BEGIN
  DELETE FROM kb_chunks_fts WHERE rowid = OLD.rowid;
  INSERT INTO kb_chunks_fts(rowid, chunk_id, heading, content, path)
  SELECT rowid, chunk_id, heading, content,
         (SELECT path FROM kb_sources WHERE source_id = NEW.source_id)
  FROM kb_chunks WHERE rowid = NEW.rowid;
END;

-- 4. 索引元数据表 - 存储索引版本和配置
CREATE TABLE IF NOT EXISTS kb_index_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- 初始化元数据
INSERT OR IGNORE INTO kb_index_meta (key, value, updated_at)
VALUES 
    ('kb_schema_version', '0.7.0', datetime('now')),
    ('chunking_policy', 'heading_based_300_800', datetime('now')),
    ('last_refresh', '', datetime('now'));

-- 5. [P2 可选] Embedding 表 - 向量数据
-- 用于两段式检索的 rerank 阶段
CREATE TABLE IF NOT EXISTS kb_embeddings (
    chunk_id TEXT PRIMARY KEY,
    vector BLOB NOT NULL,               -- 向量数据 (序列化为 bytes)
    model TEXT NOT NULL,                -- 模型标识 (如 "all-MiniLM-L6-v2")
    dims INTEGER NOT NULL,              -- 向量维度
    built_at TEXT NOT NULL,
    FOREIGN KEY (chunk_id) REFERENCES kb_chunks(chunk_id) ON DELETE CASCADE
);

-- 索引优化
CREATE INDEX IF NOT EXISTS idx_kb_sources_repo_path ON kb_sources(repo_id, path);
CREATE INDEX IF NOT EXISTS idx_kb_sources_mtime ON kb_sources(mtime);
CREATE INDEX IF NOT EXISTS idx_kb_sources_doc_type ON kb_sources(doc_type);
CREATE INDEX IF NOT EXISTS idx_kb_chunks_source ON kb_chunks(source_id);
CREATE INDEX IF NOT EXISTS idx_kb_chunks_hash ON kb_chunks(content_hash);

-- 验证触发器创建成功
SELECT 
    CASE 
        WHEN COUNT(*) >= 3 THEN 'ProjectKB migration v0.7.0 completed successfully'
        ELSE 'Warning: Some triggers may not have been created'
    END as status
FROM sqlite_master 
WHERE type = 'trigger' 
  AND name LIKE 'kb_chunks_a%';

-- 更新 schema 版本（幂等操作）
INSERT OR REPLACE INTO schema_version (version, applied_at) 
VALUES ('0.7.0', datetime('now'));
