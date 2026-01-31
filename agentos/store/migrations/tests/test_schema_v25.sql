-- Test Script for schema_v25: Projects Metadata Enhancement
-- This script validates all features of the migration

-- ============================================
-- Test 1: 验证表结构
-- ============================================
.print "=========================================="
.print "Test 1: Verify table structure"
.print "=========================================="
PRAGMA table_info(projects);

-- ============================================
-- Test 2: 验证索引
-- ============================================
.print ""
.print "=========================================="
.print "Test 2: Verify indexes"
.print "=========================================="
SELECT name FROM sqlite_master
WHERE type='index' AND tbl_name='projects'
ORDER BY name;

-- ============================================
-- Test 3: 验证触发器
-- ============================================
.print ""
.print "=========================================="
.print "Test 3: Verify triggers"
.print "=========================================="
SELECT name FROM sqlite_master
WHERE type='trigger' AND tbl_name='projects'
ORDER BY name;

-- ============================================
-- Test 4: 插入有效数据
-- ============================================
.print ""
.print "=========================================="
.print "Test 4: Insert valid project"
.print "=========================================="
INSERT INTO projects (id, path, name, status, tags, settings, description, created_by)
VALUES (
    'test-validation-project',
    '/tmp/validation-test',
    'Validation Test Project',
    'active',
    '["validation", "test", "python"]',
    '{"theme": "dark", "auto_save": true, "lint_on_save": false}',
    'This is a test project for validation',
    'test-user'
);

SELECT id, name, status, tags, settings, description, created_by, created_at, updated_at
FROM projects
WHERE id='test-validation-project';

-- ============================================
-- Test 5: 测试 status 约束
-- ============================================
.print ""
.print "=========================================="
.print "Test 5: Test status constraint (should fail)"
.print "=========================================="
INSERT INTO projects (id, path, name, status)
VALUES ('test-invalid-status', '/tmp/test', 'Invalid Status', 'invalid');

-- ============================================
-- Test 6: 测试 tags JSON 约束
-- ============================================
.print ""
.print "=========================================="
.print "Test 6: Test tags JSON constraint (should fail)"
.print "=========================================="
INSERT INTO projects (id, path, name, tags)
VALUES ('test-invalid-tags', '/tmp/test', 'Invalid Tags', 'not json');

-- ============================================
-- Test 7: 测试 tags 必须是数组
-- ============================================
.print ""
.print "=========================================="
.print "Test 7: Test tags must be array (should fail)"
.print "=========================================="
INSERT INTO projects (id, path, name, tags)
VALUES ('test-tags-object', '/tmp/test', 'Tags Object', '{"key": "value"}');

-- ============================================
-- Test 8: 测试 settings JSON 约束
-- ============================================
.print ""
.print "=========================================="
.print "Test 8: Test settings JSON constraint (should fail)"
.print "=========================================="
INSERT INTO projects (id, path, name, settings)
VALUES ('test-invalid-settings', '/tmp/test', 'Invalid Settings', 'not json');

-- ============================================
-- Test 9: 测试 settings 必须是对象
-- ============================================
.print ""
.print "=========================================="
.print "Test 9: Test settings must be object (should fail)"
.print "=========================================="
INSERT INTO projects (id, path, name, settings)
VALUES ('test-settings-array', '/tmp/test', 'Settings Array', '["array"]');

-- ============================================
-- Test 10: 测试 updated_at 自动更新
-- ============================================
.print ""
.print "=========================================="
.print "Test 10: Test updated_at auto-update"
.print "=========================================="
.print "Before update:"
SELECT id, name, updated_at FROM projects WHERE id='test-validation-project';

UPDATE projects SET description='Updated description' WHERE id='test-validation-project';

.print "After update (updated_at should change):"
SELECT id, name, updated_at FROM projects WHERE id='test-validation-project';

-- ============================================
-- Test 11: 测试 default_repo_id 外键约束
-- ============================================
.print ""
.print "=========================================="
.print "Test 11: Test default_repo_id foreign key"
.print "=========================================="

-- 创建测试仓库
INSERT INTO project_repos (repo_id, project_id, name, workspace_relpath, role)
VALUES ('test-repo-1', 'test-validation-project', 'main-repo', '.', 'code');

-- 设置有效的 default_repo_id（应该成功）
UPDATE projects SET default_repo_id='test-repo-1' WHERE id='test-validation-project';

.print "Valid default_repo_id set:"
SELECT id, name, default_repo_id FROM projects WHERE id='test-validation-project';

-- 尝试设置无效的 default_repo_id（应该失败）
.print ""
.print "Try to set invalid default_repo_id (should fail):"
UPDATE projects SET default_repo_id='non-existent-repo' WHERE id='test-validation-project';

-- ============================================
-- Test 12: 测试跨项目仓库引用（应该失败）
-- ============================================
.print ""
.print "=========================================="
.print "Test 12: Test cross-project repo reference (should fail)"
.print "=========================================="

-- 创建另一个项目和仓库
INSERT INTO projects (id, path, name) VALUES ('test-project-2', '/tmp/test2', 'Test Project 2');
INSERT INTO project_repos (repo_id, project_id, name, workspace_relpath, role)
VALUES ('test-repo-2', 'test-project-2', 'other-repo', '.', 'code');

-- 尝试在 test-validation-project 中引用 test-project-2 的仓库（应该失败）
UPDATE projects SET default_repo_id='test-repo-2' WHERE id='test-validation-project';

-- ============================================
-- Test 13: 验证索引性能
-- ============================================
.print ""
.print "=========================================="
.print "Test 13: Verify index usage"
.print "=========================================="
.print "Query plan for status + created_at:"
EXPLAIN QUERY PLAN SELECT * FROM projects WHERE status='active' ORDER BY created_at DESC;

.print ""
.print "Query plan for name search:"
EXPLAIN QUERY PLAN SELECT * FROM projects WHERE name='Validation Test Project';

.print ""
.print "Query plan for default_repo_id:"
EXPLAIN QUERY PLAN SELECT * FROM projects WHERE default_repo_id IS NOT NULL;

-- ============================================
-- Test 14: 测试不同状态值
-- ============================================
.print ""
.print "=========================================="
.print "Test 14: Test different status values"
.print "=========================================="

-- archived 状态
INSERT INTO projects (id, path, name, status)
VALUES ('test-archived', '/tmp/archived', 'Archived Project', 'archived');
.print "Archived project created successfully"

-- deleted 状态
INSERT INTO projects (id, path, name, status)
VALUES ('test-deleted', '/tmp/deleted', 'Deleted Project', 'deleted');
.print "Deleted project created successfully"

-- 查询不同状态的项目
.print ""
.print "Projects by status:"
SELECT id, name, status FROM projects WHERE id LIKE 'test-%' ORDER BY status, name;

-- ============================================
-- Cleanup: 清理测试数据
-- ============================================
.print ""
.print "=========================================="
.print "Cleanup: Removing test data"
.print "=========================================="
DELETE FROM projects WHERE id LIKE 'test-%';
DELETE FROM project_repos WHERE repo_id LIKE 'test-repo-%';
.print "Test data cleaned up successfully"

.print ""
.print "=========================================="
.print "All tests completed!"
.print "=========================================="
