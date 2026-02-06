-- Migration v0.22: Guardian Reviews
-- 添加 Guardian 验收审查记录表，用于记录治理验收事实
-- Migration from v0.21 -> v0.22

-- ============================================
-- Guardian Reviews: 验收审查记录表
-- ============================================

-- Guardian 验收审查记录
-- 记录 Guardian 对治理对象（task/decision/finding）的验收审查结果
CREATE TABLE IF NOT EXISTS guardian_reviews (
    review_id TEXT PRIMARY KEY,                      -- 唯一审查 ID
    target_type TEXT NOT NULL,                       -- 审查目标类型：task | decision | finding
    target_id TEXT NOT NULL,                         -- 审查目标 ID
    guardian_id TEXT NOT NULL,                       -- Guardian ID（agent name / human id）
    review_type TEXT NOT NULL,                       -- 审查类型：AUTO | MANUAL
    verdict TEXT NOT NULL,                           -- 验收结论：PASS | FAIL | NEEDS_REVIEW
    confidence REAL NOT NULL,                        -- 置信度（0.0-1.0）
    rule_snapshot_id TEXT,                           -- 规则快照 ID（可选，用于审计）
    evidence TEXT NOT NULL,                          -- 验收证据（JSON 格式）
    created_at TEXT NOT NULL,                        -- 创建时间（ISO8601 格式）

    -- 约束定义
    CHECK(target_type IN ('task', 'decision', 'finding')),
    CHECK(review_type IN ('AUTO', 'MANUAL')),
    CHECK(verdict IN ('PASS', 'FAIL', 'NEEDS_REVIEW')),
    CHECK(confidence >= 0.0 AND confidence <= 1.0)
);

-- ============================================
-- 索引优化（覆盖常见查询场景）
-- ============================================

-- 1. 按目标查询（最常见）：查询某个 task/decision/finding 的所有审查记录
-- 用例：GET /api/guardian/reviews?target_type=task&target_id=task_123
CREATE INDEX IF NOT EXISTS idx_guardian_reviews_target
ON guardian_reviews(target_type, target_id, created_at DESC);

-- 2. 按 Guardian 查询：查询某个 Guardian 的所有审查记录
-- 用例：GET /api/guardian/reviews?guardian_id=lead_agent
CREATE INDEX IF NOT EXISTS idx_guardian_reviews_guardian
ON guardian_reviews(guardian_id, created_at DESC);

-- 3. 按 verdict 查询：查询所有 FAIL 或 NEEDS_REVIEW 的记录（待处理）
-- 用例：GET /api/guardian/reviews?verdict=NEEDS_REVIEW
CREATE INDEX IF NOT EXISTS idx_guardian_reviews_verdict
ON guardian_reviews(verdict, created_at DESC);

-- 4. 按时间范围查询：查询某个时间段的审查记录（用于分析）
-- 用例：SELECT * FROM guardian_reviews WHERE created_at >= ? AND created_at <= ?
CREATE INDEX IF NOT EXISTS idx_guardian_reviews_created_at
ON guardian_reviews(created_at DESC);

-- 5. 复合查询：按目标类型和 verdict 查询（用于统计）
-- 用例：SELECT COUNT(*) FROM guardian_reviews WHERE target_type='task' AND verdict='PASS'
CREATE INDEX IF NOT EXISTS idx_guardian_reviews_type_verdict
ON guardian_reviews(target_type, verdict, created_at DESC);

-- 6. 规则快照关联查询：查询使用某个规则快照的所有审查记录
-- 用例：SELECT * FROM guardian_reviews WHERE rule_snapshot_id = ?
CREATE INDEX IF NOT EXISTS idx_guardian_reviews_rule_snapshot
ON guardian_reviews(rule_snapshot_id, created_at DESC)
WHERE rule_snapshot_id IS NOT NULL;

-- ============================================
-- 设计原则和契约
-- ============================================

-- Guardian Reviews 设计原则：
-- 1. Guardian = 验收事实记录器，不是流程控制器
-- 2. Review 是不可变的（immutable），一旦写入就是治理事实
-- 3. Guardian 不修改 task 状态机，只产出 review
-- 4. 支持自动验收（AUTO）和人工验收（MANUAL）
-- 5. 所有 review 必须包含完整的 evidence（可追溯）

-- Target Type 定义：
-- - task: 任务验收（如：任务执行结果验收）
-- - decision: 决策验收（如：Supervisor 决策合规性审查）
-- - finding: 发现验收（如：Lead Agent 发现的风险验收）

-- Review Type 定义：
-- - AUTO: 自动验收（由 Guardian Agent 执行）
-- - MANUAL: 人工验收（由人工审查员执行）

-- Verdict 定义：
-- - PASS: 验收通过（符合治理要求）
-- - FAIL: 验收失败（不符合治理要求）
-- - NEEDS_REVIEW: 需要进一步审查（置信度不足）

-- Confidence 定义：
-- - 0.0-1.0: 验收置信度（自动验收时使用）
-- - 1.0: 人工验收固定为 1.0（最高置信度）

-- Evidence 结构：
-- JSON 格式，包含验收证据（具体结构由 Guardian 定义）
-- 示例：
-- {
--   "checks": ["test_pass", "lint_pass", "security_scan_pass"],
--   "metrics": {"coverage": 0.85, "complexity": 12},
--   "findings": ["potential_risk_1", "potential_risk_2"],
--   "reason": "All checks passed with high confidence"
-- }

-- Rule Snapshot ID 用途：
-- - 记录使用的规则版本（用于审计和回溯）
-- - 可选字段（人工审查不需要规则快照）
-- - 支持规则演化追踪（规则变更后可对比历史审查）

-- ============================================
-- 数据一致性约束
-- ============================================

-- 1. review_id 必须全局唯一（Primary Key）
-- 2. target_id 不强制外键约束（支持跨模块引用）
-- 3. evidence 必须是有效的 JSON 字符串
-- 4. created_at 使用 ISO8601 格式（如：2025-01-28T10:30:00Z）
-- 5. confidence 范围：0.0-1.0（CHECK 约束）
-- 6. 所有 ENUM 字段都有 CHECK 约束（防止脏数据）

-- ============================================
-- 与其他表的关系
-- ============================================

-- Guardian Reviews 与其他表的关系：
-- - guardian_reviews.target_id -> tasks.task_id（target_type='task'）
-- - guardian_reviews.target_id -> supervisor_decisions.decision_id（target_type='decision'）
-- - guardian_reviews.target_id -> lead_findings.finding_id（target_type='finding'）
--
-- 注意：不使用外键约束（FOREIGN KEY），因为：
-- 1. 支持跨模块引用（target 可能在不同表）
-- 2. 避免级联删除问题（guardian_reviews 是治理审计记录，不应被删除）
-- 3. 提高灵活性（支持未来扩展新的 target_type）

-- ============================================
-- 查询性能优化
-- ============================================

-- 常见查询模式及其优化策略：
--
-- 1. 查询某个任务的所有审查记录（最常见）
--    SELECT * FROM guardian_reviews
--    WHERE target_type = 'task' AND target_id = ?
--    ORDER BY created_at DESC;
--    优化：使用 idx_guardian_reviews_target 索引
--
-- 2. 查询某个 Guardian 的审查历史
--    SELECT * FROM guardian_reviews
--    WHERE guardian_id = ?
--    ORDER BY created_at DESC;
--    优化：使用 idx_guardian_reviews_guardian 索引
--
-- 3. 查询需要人工审查的记录
--    SELECT * FROM guardian_reviews
--    WHERE verdict = 'NEEDS_REVIEW'
--    ORDER BY created_at DESC;
--    优化：使用 idx_guardian_reviews_verdict 索引
--
-- 4. 统计审查通过率
--    SELECT target_type, verdict, COUNT(*) as count
--    FROM guardian_reviews
--    GROUP BY target_type, verdict;
--    优化：使用 idx_guardian_reviews_type_verdict 索引
--
-- 5. 查询某个规则的审查记录（审计场景）
--    SELECT * FROM guardian_reviews
--    WHERE rule_snapshot_id = ?
--    ORDER BY created_at DESC;
--    优化：使用 idx_guardian_reviews_rule_snapshot 条件索引

-- ============================================
-- 扩展性设计
-- ============================================

-- 未来可能的扩展方向：
-- 1. 添加 review_status 字段（PENDING | COMPLETED | EXPIRED）
-- 2. 添加 expires_at 字段（审查记录过期时间）
-- 3. 添加 metadata JSON 字段（存储额外的审查元数据）
-- 4. 添加 parent_review_id 字段（支持审查链）
-- 5. 添加 reviewer_notes TEXT 字段（审查员备注）

-- Update schema version
INSERT OR REPLACE INTO schema_version (version) VALUES ('0.22.0');

-- Migration complete
