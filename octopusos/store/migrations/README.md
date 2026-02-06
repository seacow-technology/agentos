# 数据库迁移文件

## 概述

本目录包含 AgentOS 数据库的所有 schema 迁移文件。迁移系统支持自动检测和应用，程序启动时自动执行。

## 🚀 自动迁移系统

### 特性

- ✅ **自动检测**: 程序启动时自动检测未应用的迁移
- ✅ **顺序执行**: 严格按版本号顺序执行 (v01 → v23)
- ✅ **事务保护**: 每个迁移在独立事务中执行，失败自动回滚
- ✅ **幂等性**: 所有迁移使用 `IF NOT EXISTS`，可重复执行
- ✅ **版本追踪**: schema_version 表记录所有已应用的迁移

### 使用方法

```python
# 初始化新数据库（自动应用所有迁移）
from agentos.store import init_db
db_path = init_db()

# 获取数据库连接（自动检测并应用新迁移）
from agentos.store import get_db
conn = get_db()

# 手动检查迁移状态
from agentos.store import get_migration_status
from pathlib import Path
status = get_migration_status(Path("store/registry.sqlite"))
print(f"Current: v{status['current_version']:02d}")
print(f"Pending: {status['pending_migrations']}")
```

## 📋 迁移文件清单

### 命名规范

所有迁移文件使用统一格式: `schema_vXX.sql` (XX 为两位数版本号)

### 当前版本: v23

| 版本 | 文件 | 描述 | 依赖 |
|------|------|------|------|
| v01 | schema_v01.sql | 基础 schema (projects, runs, artifacts) | 无 |
| v02 | schema_v02.sql | 项目元数据扩展 | v01 |
| v03 | schema_v03.sql | Run pipeline 状态机 | v02 |
| v04 | schema_v04.sql | 分布式调度支持 | v03 |
| v05 | schema_v05.sql | 产出物版本控制 | v04 |
| v06 | schema_v06.sql | Task-Driven Architecture | v05 |
| v07 | schema_v07.sql | 项目知识库 | v06 |
| v08 | schema_v08.sql | 聊天会话 | v07 |
| v09 | schema_v09.sql | 命令历史 | v08 |
| v10 | schema_v10.sql | FTS 触发器修复 | v09 |
| v11 | schema_v11.sql | Context Governance & chat_artifacts | v10 |
| v12 | schema_v12.sql | Task 路由 | v11 |
| v13 | schema_v13.sql | 代码片段 | v12 |
| v14 | schema_v14.sql | Supervisor 基础 | v13 |
| v15 | schema_v15.sql | Governance Replay & Decision Fields | v14 |
| v16 | schema_v16.sql | Lead Findings | v15 |
| v17 | schema_v17.sql | Guardian Workflow | v16 |
| v18 | schema_v18.sql | Multi-Repo Projects | v17 |
| v19 | schema_v19.sql | Auth Profiles | v18 |
| v20 | schema_v20.sql | Task Audits Repo | v19 |
| v21 | schema_v21.sql | Decision Fields 索引优化 | v20 |
| v22 | schema_v22.sql | Guardian Reviews | v21 |
| v23 | schema_v23.sql | Content Answers | v22 |

## 🔑 关键迁移说明

### v06: Task-Driven Architecture

引入任务驱动架构的核心表：
- `tasks`: 任务根聚合
- `task_lineage`: 任务血缘追踪
- `task_sessions`: 会话管理
- `task_agents`: Agent 调度
- `task_audits`: 审计日志

### v11: chat_artifacts 表

**重要**: 原名 `artifacts` 与 v01 冲突，已重命名为 `chat_artifacts`

```sql
CREATE TABLE IF NOT EXISTS chat_artifacts (
    artifact_id TEXT PRIMARY KEY,
    artifact_type TEXT NOT NULL,  -- summary|requirements|decision
    session_id TEXT,
    task_id TEXT,
    content TEXT NOT NULL,
    ...
);
```

### v15: Decision Fields

为 `task_audits` 添加决策相关字段：
```sql
ALTER TABLE task_audits ADD COLUMN decision_id TEXT;
ALTER TABLE task_audits ADD COLUMN source_event_ts TEXT;
ALTER TABLE task_audits ADD COLUMN supervisor_processed_at TEXT;
```

### v16: Lead Findings

Lead Agent 核心表，支持风险发现和去重：
```sql
CREATE TABLE IF NOT EXISTS lead_findings (
    fingerprint TEXT PRIMARY KEY,  -- 幂等去重键
    code TEXT NOT NULL,
    severity TEXT NOT NULL,        -- LOW|MEDIUM|HIGH|CRITICAL
    window_kind TEXT NOT NULL,     -- 24h|7d
    linked_task_id TEXT,           -- 关联的 follow-up task
    ...
);
```

### v21: 性能优化索引

为 v15 添加的决策字段创建索引，提升查询性能 10-100x：
```sql
CREATE INDEX IF NOT EXISTS idx_task_audits_source_event_ts
ON task_audits(source_event_ts) WHERE source_event_ts IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_task_audits_decision_lag
ON task_audits(source_event_ts, supervisor_processed_at)
WHERE source_event_ts IS NOT NULL AND supervisor_processed_at IS NOT NULL;
```

## ✏️ 添加新迁移

### 步骤

1. 创建新文件: `migrations/schema_v24.sql`

2. 文件模板:
```sql
-- Migration v24: <简短描述>
-- Migration from v23 -> v24
--
-- 详细说明:
-- - 变更内容
-- - 依赖关系
-- - 影响范围

-- ============================================
-- Schema Changes
-- ============================================

CREATE TABLE IF NOT EXISTS new_table (
    id TEXT PRIMARY KEY,
    ...
);

CREATE INDEX IF NOT EXISTS idx_new_table_field
ON new_table(field);

-- ============================================
-- Version Tracking
-- ============================================

INSERT OR IGNORE INTO schema_version (version) VALUES ('0.24.0');
```

3. 重启程序，自动应用新迁移

### 设计原则

1. **幂等性**: 使用 `IF NOT EXISTS` / `IF NOT EXISTS`
2. **事务安全**: 避免在迁移中使用 `PRAGMA`（会隐式提交事务）
3. **向后兼容**: 新增列使用 `NULL` 默认值
4. **清晰注释**: 说明变更原因和影响
5. **版本记录**: 每个迁移必须插入版本号

## 🔍 验证和调试

### 检查当前版本

```bash
sqlite3 store/registry.sqlite "SELECT version, applied_at FROM schema_version ORDER BY applied_at DESC LIMIT 5;"
```

### 检查待应用的迁移

```python
from agentos.store import get_migration_status
from pathlib import Path

status = get_migration_status(Path("store/registry.sqlite"))
print(f"Current: v{status['current_version']:02d}")
print(f"Latest: v{status['latest_version']:02d}")
print(f"Pending: {', '.join(status['pending_migrations'])}")
```

### 查看表结构

```bash
sqlite3 store/registry.sqlite ".schema table_name"
```

### 查看索引

```bash
sqlite3 store/registry.sqlite "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='table_name';"
```

## ⚠️ 注意事项

### 禁止行为

1. ❌ **不要修改已应用的迁移文件** - 会导致版本不一致
2. ❌ **不要跳过版本号** - 必须连续
3. ❌ **不要手动修改 schema_version 表** - 除非你知道自己在做什么
4. ❌ **不要在迁移中使用事务控制语句** - 迁移器会自动处理

### 最佳实践

1. ✅ **测试环境先验证** - 在测试数据库上验证迁移
2. ✅ **备份生产数据库** - 重要变更前备份
3. ✅ **小步迭代** - 一个迁移只做一件事
4. ✅ **文档齐全** - 清晰注释变更原因
5. ✅ **监控日志** - 关注迁移执行日志

## 🐛 故障排查

### 迁移失败

```python
import logging
logging.basicConfig(level=logging.DEBUG)

from agentos.store import ensure_migrations
try:
    ensure_migrations()
except Exception as e:
    print(f"Migration failed: {e}")
    # 查看详细日志
```

### 版本不一致

```bash
# 查看 schema_version 表
sqlite3 store/registry.sqlite "SELECT * FROM schema_version ORDER BY applied_at;"

# 查看实际表结构
sqlite3 store/registry.sqlite ".tables"
```

### 回滚迁移

⚠️ **警告**: 回滚可能导致数据丢失

```bash
# 1. 备份数据库
cp store/registry.sqlite store/registry.sqlite.backup

# 2. 删除版本记录
sqlite3 store/registry.sqlite "DELETE FROM schema_version WHERE version='0.24.0';"

# 3. 回滚 schema 变更（根据具体迁移内容）
sqlite3 store/registry.sqlite "DROP TABLE IF EXISTS new_table;"
```

## 📚 相关文档

- [数据库迁移系统重构文档](../../../DATABASE_MIGRATION_SYSTEM.md)
- [迁移冲突分析报告](../../../MIGRATION_CONFLICTS_ANALYSIS.md)
- Lead Agent 快速开始: `LEAD_AGENT_QUICKSTART.md`
- Supervisor 集成: `docs/governance/SUPERVISOR_V21_INTEGRATION.md`

---

**最后更新**: 2026-01-29
**当前版本**: v23
**维护者**: AgentOS Team

