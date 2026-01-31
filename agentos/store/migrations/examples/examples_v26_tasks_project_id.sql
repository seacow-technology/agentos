-- Schema v26 Usage Examples (NOT A MIGRATION SCRIPT)
-- Demonstrates how to use the new tasks.project_id field
--
-- ⚠️  WARNING: This file is NOT executed by the migrator
-- ⚠️  It contains example queries and INSERT statements for documentation purposes
-- ⚠️  To run these examples, execute manually in a test database

-- ============================================
-- 1. Query Tasks by Project (Direct, Fast)
-- ============================================

-- Before v26: Had to JOIN through task_repo_scope and project_repos
-- SELECT t.task_id, t.title, t.status
-- FROM tasks t
-- JOIN task_repo_scope trs ON t.task_id = trs.task_id
-- JOIN project_repos pr ON trs.repo_id = pr.repo_id
-- WHERE pr.project_id = 'my-project-id';

-- After v26: Direct query with index
SELECT task_id, title, status, created_at
FROM tasks
WHERE project_id = 'my-project-id'
ORDER BY created_at DESC;

-- ============================================
-- 2. Filter Tasks by Project and Status
-- ============================================

-- Get all active tasks for a project
SELECT task_id, title, created_at
FROM tasks
WHERE project_id = 'my-project-id'
  AND status = 'executing'
ORDER BY created_at DESC;

-- ============================================
-- 3. Count Tasks per Project
-- ============================================

-- Get task statistics grouped by project
SELECT
    project_id,
    COUNT(*) as total_tasks,
    SUM(CASE WHEN status = 'succeeded' THEN 1 ELSE 0 END) as succeeded,
    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
    SUM(CASE WHEN status IN ('created', 'planning', 'executing') THEN 1 ELSE 0 END) as active
FROM tasks
WHERE project_id IS NOT NULL
GROUP BY project_id;

-- ============================================
-- 4. Join with Projects Table
-- ============================================

-- Get tasks with project details
SELECT
    t.task_id,
    t.title,
    t.status,
    p.name as project_name,
    p.status as project_status
FROM tasks t
JOIN projects p ON t.project_id = p.id
WHERE p.status = 'active'
ORDER BY t.created_at DESC
LIMIT 50;

-- ============================================
-- 5. Create Task with project_id
-- ============================================

-- Insert a new task directly associated with a project
INSERT INTO tasks (
    task_id,
    title,
    status,
    project_id,
    created_by
) VALUES (
    '01KG46KY4ACPDJY92ZASQ377YW',
    'Implement new feature',
    'created',
    'my-project-id',
    'user@example.com'
);

-- ============================================
-- 6. Update Task's project_id
-- ============================================

-- Move a task to another project
UPDATE tasks
SET project_id = 'another-project-id'
WHERE task_id = '01KG46KY4ACPDJY92ZASQ377YW';

-- ============================================
-- 7. Find Tasks Without Projects
-- ============================================

-- Identify orphaned tasks (no project association)
SELECT task_id, title, status, created_at
FROM tasks
WHERE project_id IS NULL
ORDER BY created_at DESC;

-- ============================================
-- 8. Batch Update Tasks with project_id
-- ============================================

-- Assign project to tasks based on task_repo_scope
-- (This is what the migration does automatically)
UPDATE tasks
SET project_id = (
    SELECT DISTINCT pr.project_id
    FROM task_repo_scope trs
    JOIN project_repos pr ON trs.repo_id = pr.repo_id
    WHERE trs.task_id = tasks.task_id
    LIMIT 1
)
WHERE tasks.project_id IS NULL
  AND EXISTS (
      SELECT 1
      FROM task_repo_scope trs
      WHERE trs.task_id = tasks.task_id
  );

-- ============================================
-- 9. Performance Comparison Query Plan
-- ============================================

-- Check that the query uses the project_id index
EXPLAIN QUERY PLAN
SELECT task_id, title, status
FROM tasks
WHERE project_id = 'my-project-id'
  AND status = 'executing'
ORDER BY created_at DESC;

-- Expected: SEARCH tasks USING INDEX idx_tasks_project_status

-- ============================================
-- 10. Complex Query: Recent Tasks per Project
-- ============================================

-- Get the 5 most recent tasks for each project
WITH ranked_tasks AS (
    SELECT
        task_id,
        title,
        status,
        project_id,
        created_at,
        ROW_NUMBER() OVER (
            PARTITION BY project_id
            ORDER BY created_at DESC
        ) as rank
    FROM tasks
    WHERE project_id IS NOT NULL
)
SELECT
    rt.project_id,
    p.name as project_name,
    rt.task_id,
    rt.title,
    rt.status,
    rt.created_at
FROM ranked_tasks rt
JOIN projects p ON rt.project_id = p.id
WHERE rt.rank <= 5
ORDER BY rt.project_id, rt.rank;

-- ============================================
-- 11. Validation Query: Check Data Integrity
-- ============================================

-- Find tasks with invalid project_id (should be empty if triggers work)
SELECT task_id, title, project_id
FROM tasks
WHERE project_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM projects WHERE id = tasks.project_id
  );

-- Find tasks where task_repo_scope repos don't match project_id
SELECT
    t.task_id,
    t.title,
    t.project_id as task_project,
    pr.project_id as repo_project,
    trs.repo_id
FROM tasks t
JOIN task_repo_scope trs ON t.task_id = trs.task_id
JOIN project_repos pr ON trs.repo_id = pr.repo_id
WHERE t.project_id IS NOT NULL
  AND t.project_id != pr.project_id;

-- ============================================
-- 12. Migration Status Check
-- ============================================

-- Check migration statistics
SELECT
    'Total Tasks' as metric,
    COUNT(*) as value
FROM tasks
UNION ALL
SELECT
    'Tasks with project_id',
    COUNT(*)
FROM tasks
WHERE project_id IS NOT NULL
UNION ALL
SELECT
    'Tasks without project_id',
    COUNT(*)
FROM tasks
WHERE project_id IS NULL
UNION ALL
SELECT
    'Unique projects referenced',
    COUNT(DISTINCT project_id)
FROM tasks
WHERE project_id IS NOT NULL;
