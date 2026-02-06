-- AgentOS Store Schema v1
-- Base schema with projects, runs, and artifacts tables
-- Migration: Initial schema

-- ============================================
-- Schema Version Tracking
-- ============================================

CREATE TABLE IF NOT EXISTS schema_version (
    version TEXT PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- Projects: 注册的项目
-- ============================================

CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    path TEXT NOT NULL,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- Runs: 每次扫描/生成的执行记录
-- ============================================

CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL,
    type TEXT NOT NULL, -- 'scan' | 'generate' | 'orchestrate'
    status TEXT NOT NULL, -- 'QUEUED' | 'RUNNING' | 'SUCCEEDED' | 'FAILED'
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    error TEXT,
    lease_until TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

-- ============================================
-- Artifacts: 产出物索引
-- ============================================

CREATE TABLE IF NOT EXISTS artifacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    type TEXT NOT NULL, -- 'factpack' | 'agent_spec' | 'agent_md'
    path TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES runs(id)
);

-- ============================================
-- Indexes
-- ============================================

CREATE INDEX IF NOT EXISTS idx_runs_project_status ON runs(project_id, status);
CREATE INDEX IF NOT EXISTS idx_runs_status_lease ON runs(status, lease_until);
CREATE INDEX IF NOT EXISTS idx_artifacts_run ON artifacts(run_id);

-- ============================================
-- Version Record
-- ============================================

INSERT OR IGNORE INTO schema_version (version) VALUES ('0.1.0');
