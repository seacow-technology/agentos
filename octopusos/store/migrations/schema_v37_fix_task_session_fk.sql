-- Migration v37: Fix Task FK constraint to allow NULL session_id
-- Date: 2026-01-31
-- Purpose: Fix Task creation failure due to FK constraint on session_id
-- Issue: Task #32 - Task creation 100% fails with FK constraint error
-- Root Cause: session_id FK constraint prevents creating tasks without valid sessions
-- Solution: Make session_id FK constraint optional (allow NULL)

-- ============================================
-- Background
-- ============================================
-- Problem: tasks.session_id has FK constraint to chat_sessions(session_id)
-- This prevents creating tasks without pre-existing sessions
-- The auto-created session logic in service.py uses INSERT OR IGNORE,
-- which can fail silently, causing subsequent task insert to violate FK.

-- Solution: Recreate tasks table with optional session_id FK
-- SQLite doesn't support modifying FKs directly, so we must:
-- 1. Create new table with updated constraint
-- 2. Copy data from old table
-- 3. Drop old table
-- 4. Rename new table to original name
-- 5. Recreate indexes

-- ============================================
-- Step 0: Temporarily disable foreign key constraints
-- ============================================
PRAGMA foreign_keys = OFF;

-- ============================================
-- Step 1: Save and drop existing triggers
-- ============================================

-- Drop triggers that reference tasks table
DROP TRIGGER IF EXISTS check_task_repo_scope_project_consistency_insert;
DROP TRIGGER IF EXISTS check_task_repo_scope_project_consistency_update;
DROP TRIGGER IF EXISTS auto_set_task_project_id;

-- ============================================
-- Step 2: Create new tasks table with optional FK
-- ============================================

CREATE TABLE IF NOT EXISTS tasks_new (
    task_id TEXT PRIMARY KEY,
    session_id TEXT,  -- Now can be NULL
    title TEXT,
    status TEXT DEFAULT 'created',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT,
    metadata TEXT,
    route_plan_json TEXT DEFAULT NULL,
    requirements_json TEXT DEFAULT NULL,
    selected_instance_id TEXT DEFAULT NULL,
    router_version TEXT DEFAULT NULL,
    project_id TEXT,
    exit_reason TEXT,
    repo_id TEXT,
    workdir TEXT,
    spec_frozen INTEGER DEFAULT 0,

    -- FK constraint now allows NULL (removed NOT NULL requirement on session_id)
    -- If session_id is provided, it must reference a valid chat_sessions record
    FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id) ON DELETE SET NULL
);

-- ============================================
-- Step 3: Copy data from old table to new table
-- ============================================

INSERT INTO tasks_new (
    task_id, session_id, title, status, created_at, updated_at,
    created_by, metadata, route_plan_json, requirements_json,
    selected_instance_id, router_version, project_id, exit_reason,
    repo_id, workdir, spec_frozen
)
SELECT
    task_id, session_id, title, status, created_at, updated_at,
    created_by, metadata, route_plan_json, requirements_json,
    selected_instance_id, router_version, project_id, exit_reason,
    repo_id, workdir, spec_frozen
FROM tasks;

-- ============================================
-- Step 4: Drop old table
-- ============================================

DROP TABLE tasks;

-- ============================================
-- Step 5: Rename new table to original name
-- ============================================

ALTER TABLE tasks_new RENAME TO tasks;

-- ============================================
-- Step 6: Recreate indexes
-- ============================================

CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_session ON tasks(session_id);
CREATE INDEX IF NOT EXISTS idx_tasks_created ON tasks(created_at DESC);

-- ============================================
-- Step 7: Recreate triggers
-- ============================================

CREATE TRIGGER IF NOT EXISTS check_task_repo_scope_project_consistency_insert
BEFORE INSERT ON task_repo_scope
FOR EACH ROW
WHEN EXISTS (SELECT 1 FROM tasks WHERE task_id = NEW.task_id AND project_id IS NOT NULL)
BEGIN
    SELECT CASE
        WHEN NOT EXISTS (
            SELECT 1
            FROM tasks t
            JOIN repos r ON r.project_id = t.project_id
            WHERE t.task_id = NEW.task_id
              AND r.repo_id = NEW.repo_id
        )
        THEN RAISE(ABORT, 'Repository must belong to the task''s project')
    END;
END;

CREATE TRIGGER IF NOT EXISTS check_task_repo_scope_project_consistency_update
BEFORE UPDATE OF project_id ON tasks
FOR EACH ROW
WHEN NEW.project_id IS NOT NULL
BEGIN
    SELECT CASE
        WHEN EXISTS (
            SELECT 1
            FROM task_repo_scope trs
            LEFT JOIN repos r ON r.repo_id = trs.repo_id AND r.project_id = NEW.project_id
            WHERE trs.task_id = NEW.task_id
              AND r.repo_id IS NULL
        )
        THEN RAISE(ABORT, 'Task has repo scopes that do not belong to new project')
    END;
END;

CREATE TRIGGER IF NOT EXISTS auto_set_task_project_id
AFTER INSERT ON task_repo_scope
FOR EACH ROW
WHEN (SELECT project_id FROM tasks WHERE task_id = NEW.task_id) IS NULL
BEGIN
    UPDATE tasks
    SET project_id = (SELECT project_id FROM repos WHERE repo_id = NEW.repo_id)
    WHERE task_id = NEW.task_id;
END;

-- ============================================
-- Step 8: Re-enable foreign key constraints
-- ============================================
PRAGMA foreign_keys = ON;

-- ============================================
-- Step 9: Record migration
-- ============================================

INSERT INTO schema_migrations (migration_id, description, status, metadata)
VALUES (
    'v37_fix_task_session_fk',
    'Fix Task FK constraint to allow NULL session_id',
    'success',
    json_object(
        'migration_date', datetime('now'),
        'issue', 'Task #32 - FK constraint failure',
        'change', 'Made session_id FK optional (allow NULL)',
        'tasks_migrated', (SELECT COUNT(*) FROM tasks)
    )
);

-- ============================================
-- Version Tracking
-- ============================================

INSERT OR REPLACE INTO schema_version (version, applied_at)
VALUES ('0.37.0', datetime('now'));
