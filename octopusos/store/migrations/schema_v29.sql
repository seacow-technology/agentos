-- Migration v0.29: Project Snapshots
-- Description: Support project snapshot export and history tracking
-- Purpose: Enable auditable project delivery and configuration freeze
--
-- 背景:
--   - 支持"冻结 spec / 可审计交付"场景
--   - 导出完整项目配置和元数据
--   - 预留 import/diff 扩展点
--
-- 功能:
--   - 存储项目快照数据 (JSON格式)
--   - 支持快照历史查询
--   - 提供未来导入/对比能力基础
--
-- ============================================
-- 阶段 1: 创建 project_snapshots 表
-- ============================================

CREATE TABLE IF NOT EXISTS project_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    data TEXT NOT NULL,  -- JSON 格式的快照数据 (ProjectSnapshot schema)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Foreign key constraint (with CASCADE delete)
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

-- ============================================
-- 阶段 2: 创建索引
-- ============================================

-- 索引 1: 按项目查询快照列表（降序时间）
CREATE INDEX IF NOT EXISTS idx_project_snapshots_project
ON project_snapshots(project_id, created_at DESC);

-- 索引 2: 按创建时间查询（用于清理旧快照）
CREATE INDEX IF NOT EXISTS idx_project_snapshots_created_at
ON project_snapshots(created_at DESC);

-- ============================================
-- 设计说明
-- ============================================

-- Snapshot 数据格式 (JSON):
-- {
--   "snapshot_version": "1.0",
--   "snapshot_id": "snap-<project_id>-<timestamp>",
--   "timestamp": "2025-01-29T10:30:00Z",
--   "project": {...},  // 完整 Project 数据
--   "repos": [...],    // Repository 引用
--   "tasks_summary": {...},  // Task 统计
--   "settings_hash": "sha256:...",
--   "metadata": {...}  // 扩展字段
-- }

-- 快照用途:
-- 1. 项目配置导出/备份
-- 2. 审计交付物
-- 3. 快照对比 (future)
-- 4. 配置还原 (future)

-- 清理策略 (未来可实现):
-- - 保留最近 N 个快照
-- - 删除超过 X 天的旧快照
-- - 手动标记保护的快照不删除

-- 扩展点 (预留):
-- 1. import_snapshot(snapshot_data) -> new_project_id
-- 2. snapshot_diff(snap_a, snap_b) -> diff_object
-- 3. restore_snapshot(project_id, snapshot_id) -> success

-- Update schema version
INSERT OR REPLACE INTO schema_version (version) VALUES ('0.29.0');
