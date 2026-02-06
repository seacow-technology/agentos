-- AgentOS Store Schema v0.2
-- Extension for Control Plane features: Memory, Execution Policy, Audit Trail, Locks, Scheduler

-- ============================================
-- Memory Service Tables
-- ============================================

-- memory_items: 外置记忆存储
CREATE TABLE IF NOT EXISTS memory_items (
    id TEXT PRIMARY KEY,
    scope TEXT NOT NULL,  -- global|project|repo|task|agent
    type TEXT NOT NULL,   -- decision|convention|constraint|known_issue|playbook|glossary
    content TEXT NOT NULL,  -- JSON
    tags TEXT,  -- JSON array
    sources TEXT,  -- JSON array
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    confidence REAL DEFAULT 0.5,
    project_id TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

-- ============================================
-- Task Execution Tables
-- ============================================

-- task_runs: 任务执行记录（扩展现有 runs）
CREATE TABLE IF NOT EXISTS task_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    agent_type TEXT,
    execution_mode TEXT NOT NULL,  -- interactive|semi_auto|full_auto
    execution_policy TEXT,  -- JSON
    status TEXT NOT NULL,  -- QUEUED|RUNNING|WAITING_LOCK|SUCCEEDED|FAILED|BLOCKED
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    error TEXT,
    lease_holder TEXT,
    lease_until TIMESTAMP,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    triggered_by TEXT,  -- cron|manual|dependency
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

-- run_steps: 每个 run 的细粒度步骤
CREATE TABLE IF NOT EXISTS run_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    step_type TEXT NOT NULL,  -- plan|apply|verify|fixup|publish|rebase
    status TEXT NOT NULL,  -- PENDING|RUNNING|SUCCEEDED|FAILED
    input_summary TEXT,  -- JSON
    output_summary TEXT,  -- JSON
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    error TEXT,
    FOREIGN KEY (run_id) REFERENCES task_runs(id)
);

-- patches: 每次 apply 的变更集
CREATE TABLE IF NOT EXISTS patches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patch_id TEXT UNIQUE NOT NULL,
    run_id INTEGER NOT NULL,
    step_id INTEGER,
    intent TEXT NOT NULL,  -- 为什么改
    files TEXT NOT NULL,  -- JSON array of file paths
    diff_hash TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES task_runs(id),
    FOREIGN KEY (step_id) REFERENCES run_steps(id)
);

-- commit_links: patch 对应的 git commit
CREATE TABLE IF NOT EXISTS commit_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patch_id TEXT NOT NULL,
    commit_hash TEXT NOT NULL,
    commit_message TEXT,
    committed_at TIMESTAMP,
    repo_root TEXT,
    FOREIGN KEY (patch_id) REFERENCES patches(patch_id)
);

-- ============================================
-- Lock Management Tables
-- ============================================

-- file_locks: 文件级锁
CREATE TABLE IF NOT EXISTS file_locks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_root TEXT NOT NULL,
    file_path TEXT NOT NULL,  -- 相对路径
    locked_by_task TEXT NOT NULL,
    locked_by_run INTEGER NOT NULL,
    lease_id INTEGER,
    expires_at TIMESTAMP NOT NULL,
    metadata TEXT,  -- JSON (变更意图等)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (repo_root, file_path),
    FOREIGN KEY (locked_by_run) REFERENCES task_runs(id)
);

-- ============================================
-- Task Dependency Tables
-- ============================================

-- task_dependencies: 任务依赖图
CREATE TABLE IF NOT EXISTS task_dependencies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    depends_on_task_id TEXT NOT NULL,
    dependency_type TEXT DEFAULT 'sequential',  -- sequential|blocking
    UNIQUE (task_id, depends_on_task_id)
);

-- task_conflicts: 任务冲突关系
CREATE TABLE IF NOT EXISTS task_conflicts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    conflicts_with_task_id TEXT NOT NULL,
    UNIQUE (task_id, conflicts_with_task_id)
);

-- ============================================
-- Indexes for Performance
-- ============================================

-- Memory indexes
CREATE INDEX IF NOT EXISTS idx_memory_scope_project ON memory_items(scope, project_id);
CREATE INDEX IF NOT EXISTS idx_memory_tags ON memory_items(tags);
CREATE INDEX IF NOT EXISTS idx_memory_type ON memory_items(type);
CREATE INDEX IF NOT EXISTS idx_memory_created ON memory_items(created_at DESC);

-- Task execution indexes
CREATE INDEX IF NOT EXISTS idx_task_runs_status ON task_runs(status, lease_until);
CREATE INDEX IF NOT EXISTS idx_task_runs_task_id ON task_runs(task_id);
CREATE INDEX IF NOT EXISTS idx_task_runs_project ON task_runs(project_id);
CREATE INDEX IF NOT EXISTS idx_run_steps_run_id ON run_steps(run_id);
CREATE INDEX IF NOT EXISTS idx_patches_run_id ON patches(run_id);
CREATE INDEX IF NOT EXISTS idx_commit_links_patch ON commit_links(patch_id);

-- Lock indexes
CREATE INDEX IF NOT EXISTS idx_file_locks_path ON file_locks(repo_root, file_path);
CREATE INDEX IF NOT EXISTS idx_file_locks_expires ON file_locks(expires_at);
CREATE INDEX IF NOT EXISTS idx_file_locks_run ON file_locks(locked_by_run);

-- Dependency indexes
CREATE INDEX IF NOT EXISTS idx_task_deps_task ON task_dependencies(task_id);
CREATE INDEX IF NOT EXISTS idx_task_deps_depends ON task_dependencies(depends_on_task_id);
CREATE INDEX IF NOT EXISTS idx_task_conflicts_task ON task_conflicts(task_id);

-- ============================================
-- Full-Text Search for Memory
-- ============================================

CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
    id UNINDEXED,
    content,
    tags,
    content='memory_items',
    content_rowid='rowid'
);

-- Triggers to keep FTS in sync
CREATE TRIGGER IF NOT EXISTS memory_fts_insert AFTER INSERT ON memory_items BEGIN
    INSERT INTO memory_fts(rowid, id, content, tags)
    VALUES (new.rowid, new.id, new.content, new.tags);
END;

CREATE TRIGGER IF NOT EXISTS memory_fts_update AFTER UPDATE ON memory_items BEGIN
    UPDATE memory_fts SET content = new.content, tags = new.tags
    WHERE rowid = new.rowid;
END;

CREATE TRIGGER IF NOT EXISTS memory_fts_delete AFTER DELETE ON memory_items BEGIN
    DELETE FROM memory_fts WHERE rowid = old.rowid;
END;
