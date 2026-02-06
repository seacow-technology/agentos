-- Migration v0.16: Lead Agent Findings Storage
-- Adds lead_findings table for Risk Miner deduplication and tracking
-- Migration from v0.15 -> v0.16

-- ============================================
-- Lead Findings: 风险发现去重和持久化
-- ============================================

CREATE TABLE IF NOT EXISTS lead_findings (
    fingerprint TEXT PRIMARY KEY,            -- 唯一指纹（用于幂等去重）
    code TEXT NOT NULL,                      -- 规则代码（如 "IDLE_TASK_3D"）
    severity TEXT NOT NULL,                  -- 严重级别：LOW | MEDIUM | HIGH | CRITICAL
    title TEXT NOT NULL,                     -- 发现标题
    description TEXT,                        -- 详细描述
    window_kind TEXT NOT NULL,               -- 扫描窗口：24h | 7d
    first_seen_at TIMESTAMP NOT NULL,        -- 首次发现时间
    last_seen_at TIMESTAMP NOT NULL,         -- 最后发现时间
    count INTEGER DEFAULT 1,                 -- 重复发现次数
    evidence_json TEXT,                      -- 证据数据（JSON 格式）
    linked_task_id TEXT,                     -- 关联的 follow-up task ID
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- 索引优化
-- ============================================

-- 按最后发现时间查询最新风险
CREATE INDEX IF NOT EXISTS idx_lead_findings_last_seen
ON lead_findings(last_seen_at DESC);

-- 按严重级别过滤
CREATE INDEX IF NOT EXISTS idx_lead_findings_severity
ON lead_findings(severity);

-- 按扫描窗口过滤
CREATE INDEX IF NOT EXISTS idx_lead_findings_window
ON lead_findings(window_kind);

-- 按规则代码查询
CREATE INDEX IF NOT EXISTS idx_lead_findings_code
ON lead_findings(code);

-- 复合索引：severity + last_seen（用于仪表盘）
CREATE INDEX IF NOT EXISTS idx_lead_findings_severity_time
ON lead_findings(severity, last_seen_at DESC);

-- ============================================
-- 设计原则
-- ============================================

-- Lead Findings 设计原则：
-- 1. fingerprint 作为主键实现幂等去重
-- 2. 使用 INSERT ... ON CONFLICT DO UPDATE 实现原子 upsert
-- 3. first_seen_at 永不更新，last_seen_at 每次更新
-- 4. count 字段累加，记录重复发现次数
-- 5. evidence_json 存储扫描时的证据快照（JSON 格式）
-- 6. linked_task_id 关联创建的 follow-up task（一旦创建不再重复）

-- Fingerprint 计算规则：
-- fingerprint = hash(code + window_kind + 关键上下文)
-- 例如：sha256(f"{code}:{window_kind}:{task_id}")
-- 保证同一问题在同一窗口内只记录一次

-- Severity 级别定义：
-- CRITICAL: 严重影响系统稳定性（如：死锁、资源耗尽）
-- HIGH: 严重影响用户体验（如：任务卡住 >3 天、频繁失败）
-- MEDIUM: 中等影响（如：性能下降、异常增多）
-- LOW: 轻微影响（如：优化建议、最佳实践）

-- Update schema version
INSERT OR REPLACE INTO schema_version (version) VALUES ('0.16.0');
