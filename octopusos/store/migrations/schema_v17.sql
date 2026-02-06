-- Migration v0.17: Guardian Workflow
-- Adds Guardian assignments and verdicts tables for task verification
-- Migration from v0.16 -> v0.17

-- ============================================
-- Guardian Assignments: Guardian 分配记录
-- ============================================

CREATE TABLE IF NOT EXISTS guardian_assignments (
    assignment_id TEXT PRIMARY KEY,            -- 唯一分配 ID
    task_id TEXT NOT NULL,                     -- 被验证的任务 ID
    guardian_code TEXT NOT NULL,               -- Guardian 代码（如 "smoke_test"）
    created_at TIMESTAMP NOT NULL,             -- 分配创建时间
    reason_json TEXT NOT NULL,                 -- 分配原因（JSON 格式，包含 findings）
    status TEXT NOT NULL DEFAULT 'ASSIGNED',   -- ASSIGNED | VERIFYING | COMPLETED | FAILED

    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
);

-- 索引优化
CREATE INDEX IF NOT EXISTS idx_guardian_assignments_task
ON guardian_assignments(task_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_guardian_assignments_guardian
ON guardian_assignments(guardian_code, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_guardian_assignments_status
ON guardian_assignments(status, created_at DESC);

-- ============================================
-- Guardian Verdicts: Guardian 验收结果
-- ============================================

CREATE TABLE IF NOT EXISTS guardian_verdicts (
    verdict_id TEXT PRIMARY KEY,               -- 唯一 verdict ID
    assignment_id TEXT NOT NULL,               -- 关联的 assignment ID
    task_id TEXT NOT NULL,                     -- 被验证的任务 ID
    guardian_code TEXT NOT NULL,               -- Guardian 代码
    status TEXT NOT NULL,                      -- PASS | FAIL | NEEDS_CHANGES
    created_at TIMESTAMP NOT NULL,             -- Verdict 创建时间
    verdict_json TEXT NOT NULL,                -- 完整 verdict 数据（JSON 格式）

    FOREIGN KEY (assignment_id) REFERENCES guardian_assignments(assignment_id),
    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
);

-- 索引优化
CREATE INDEX IF NOT EXISTS idx_guardian_verdicts_task
ON guardian_verdicts(task_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_guardian_verdicts_assignment
ON guardian_verdicts(assignment_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_guardian_verdicts_status
ON guardian_verdicts(status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_guardian_verdicts_guardian
ON guardian_verdicts(guardian_code, created_at DESC);

-- ============================================
-- 增强 task_audits 表：添加 verdict_id 列
-- ============================================

-- 为 task_audits 添加 verdict_id 列（用于关联 Guardian verdict）
ALTER TABLE task_audits ADD COLUMN verdict_id TEXT;

-- 为 verdict_id 创建索引（条件索引，只索引非空值）
CREATE INDEX IF NOT EXISTS idx_task_audits_verdict_id
ON task_audits(verdict_id)
WHERE verdict_id IS NOT NULL;

-- ============================================
-- 设计原则和约束
-- ============================================

-- Guardian Workflow 设计原则：
-- 1. Guardian 不直接修改状态，只产出 verdict
-- 2. Verdict 是不可变的（immutable），一旦写入就是治理事实
-- 3. Supervisor 消费 verdict 并统一落状态
-- 4. 状态流转必须经过 can_transition() 检查（在应用层实现）
-- 5. 所有 verdict 必须关联到 assignment

-- 状态机流程：
-- RUNNING -> VERIFYING (Supervisor 分配 Guardian)
--   -> GUARD_REVIEW (Guardian 开始验证)
--     -> VERIFIED (verdict = PASS)
--     -> BLOCKED (verdict = FAIL)
--     -> RUNNING (verdict = NEEDS_CHANGES)

-- Verdict Status 定义：
-- PASS: 验证通过，任务可以进入 VERIFIED 状态
-- FAIL: 验证失败，任务应该被 BLOCKED
-- NEEDS_CHANGES: 需要修改，任务返回 RUNNING 状态

-- Assignment Status 定义：
-- ASSIGNED: Guardian 已分配但尚未开始验证
-- VERIFYING: Guardian 正在执行验证
-- COMPLETED: Guardian 已完成验证（有 verdict）
-- FAILED: Guardian 执行失败（异常情况）

-- ============================================
-- 数据一致性约束
-- ============================================

-- 每个 verdict 必须有对应的 assignment
-- 每个 assignment 可以有 0 或 1 个 verdict（正常情况）
-- verdict_json 包含完整的 GuardianVerdictSnapshot 数据
-- reason_json 包含 findings 和选择 Guardian 的理由

-- Update schema version
INSERT OR REPLACE INTO schema_version (version) VALUES ('0.17.0');
