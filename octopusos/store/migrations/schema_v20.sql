-- Migration v0.20: Task Audits Repository Extension
-- Extends task_audits table with repository tracking for cross-repo audit trail
-- Migration from v0.19 -> v0.20

-- ============================================
-- Extend task_audits with repo_id
-- ============================================

-- Add repo_id column to task_audits
-- This allows tracking which repository each audit event belongs to
ALTER TABLE task_audits ADD COLUMN repo_id TEXT;

-- Add foreign key constraint (SQLite doesn't support ALTER TABLE ADD CONSTRAINT)
-- This is a best practice documentation, actual constraint enforcement may vary
-- FOREIGN KEY (repo_id) REFERENCES project_repos(repo_id) ON DELETE SET NULL

-- Create index for repo-based queries
CREATE INDEX IF NOT EXISTS idx_task_audits_repo
ON task_audits(repo_id);

-- Create composite index for task+repo queries
CREATE INDEX IF NOT EXISTS idx_task_audits_task_repo
ON task_audits(task_id, repo_id);

-- Create composite index for repo+time queries (audit trail by repo)
CREATE INDEX IF NOT EXISTS idx_task_audits_repo_created
ON task_audits(repo_id, created_at DESC);

-- ============================================
-- Design Notes
-- ============================================

-- Audit Trail Design:
-- 1. Each task audit record can now be associated with a specific repository
-- 2. Enables tracking of cross-repository operations:
--    - Which files were changed in which repo
--    - Which commits were created in which repo
--    - Read/write operations per repo
-- 3. Null repo_id indicates task-level audit (not repo-specific)
-- 4. Combined with task_artifact_ref, provides complete traceability

-- Common event_type values for repo operations:
-- - repo_read: Read operation on repository files
-- - repo_write: Write operation on repository files
-- - repo_commit: Commit created in repository
-- - repo_push: Push to remote repository
-- - repo_checkout: Branch/commit checkout
-- - repo_clone: Repository cloned
-- - repo_pull: Pull from remote repository

-- Payload JSON structure examples:
-- {
--   "operation": "write",
--   "files_changed": ["src/main.py", "tests/test_main.py"],
--   "lines_added": 50,
--   "lines_deleted": 10,
--   "git_status_summary": "M  src/main.py\nA  tests/test_main.py",
--   "git_diff_summary": "src/main.py | 30 +++---\ntests/test_main.py | 20 +++++",
--   "commit_hash": "abc123...",
--   "error": null
-- }

-- Usage Patterns:
-- 1. Get all audits for a task across all repos:
--    SELECT * FROM task_audits WHERE task_id = ? ORDER BY created_at;
--
-- 2. Get all audits for a task in a specific repo:
--    SELECT * FROM task_audits WHERE task_id = ? AND repo_id = ? ORDER BY created_at;
--
-- 3. Get audit trail for a repository:
--    SELECT * FROM task_audits WHERE repo_id = ? ORDER BY created_at DESC LIMIT 100;
--
-- 4. Get all commits across repos for a task:
--    SELECT * FROM task_audits WHERE task_id = ? AND event_type = 'repo_commit'
--    ORDER BY created_at;
--
-- 5. Get task-level audits (not repo-specific):
--    SELECT * FROM task_audits WHERE task_id = ? AND repo_id IS NULL ORDER BY created_at;

-- Update schema version
INSERT OR REPLACE INTO schema_version (version) VALUES ('0.20.0');
