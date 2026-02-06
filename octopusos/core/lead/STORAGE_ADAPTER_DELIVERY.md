# LeadStorage Adapter - 交付文档

## 交付概述

实现了 LeadStorage 只读查询适配器，从 AgentOS 的 `task_audits` 和 `tasks` 表中提取 Supervisor 决策数据，供 Lead Agent Risk Miner 使用。所有方法均已完成单元测试，覆盖 happy path 和边界条件。

## 交付文件

### 核心代码
- `/Users/pangge/PycharmProjects/AgentOS/agentos/core/lead/adapters/__init__.py`
- `/Users/pangge/PycharmProjects/AgentOS/agentos/core/lead/adapters/storage.py`

### 测试代码
- `/Users/pangge/PycharmProjects/AgentOS/tests/unit/lead/test_storage_queries.py` (pytest 格式)
- `/Users/pangge/PycharmProjects/AgentOS/tests/unit/lead/run_storage_tests.py` (独立运行器)

## 实现的查询方法

### 1. get_blocked_reasons(window)
**规则**: blocked_reason_spike

**功能**: 返回窗口内所有 BLOCKED 任务的原因统计

**查询逻辑**:
- 从 `task_audits` 查询 `SUPERVISOR_BLOCKED` 事件
- 从 `payload.findings[].code` 提取错误代码
- 统计每个 code 的出现次数
- 限制样例 task_ids 最多 5 个

**返回格式**:
```python
[
    {
        "code": "ERROR_CODE_XYZ",
        "count": 5,
        "task_ids": ["task-1", "task-2", ...]  # 最多5个
    },
    ...
]
```

**测试覆盖**:
- ✅ 有数据时返回统计
- ✅ 空窗口返回空列表
- ✅ 样例限制为5个

---

### 2. get_pause_block_churn(window)
**规则**: pause_block_churn

**功能**: 返回窗口内 PAUSE 多次后最终 BLOCK 的任务

**查询逻辑**:
- 查询 `SUPERVISOR_PAUSED` 和 `SUPERVISOR_BLOCKED` 事件
- 按 task_id 分组，按时间排序
- 统计每个任务的 PAUSE 次数
- 检查最后一个事件是否为 BLOCK

**返回格式**:
```python
[
    {
        "task_id": "task-abc",
        "pause_count": 3,
        "final_status": "BLOCKED"
    },
    ...
]
```

**测试覆盖**:
- ✅ 检测到 PAUSE->BLOCK 模式
- ✅ 未检测到模式

---

### 3. get_retry_then_fail(window)
**规则**: retry_recommended_but_fails

**功能**: 返回窗口内建议 RETRY 但仍失败的任务

**查询逻辑**:
- 第一步：查询所有 `SUPERVISOR_RETRY_RECOMMENDED` 事件
- 第二步：对每个 RETRY 任务，查询后续是否有 `SUPERVISOR_BLOCKED` 事件
- 从 BLOCK 事件的 `payload.findings[].code` 提取失败原因
- 统计每个 error_code 的出现次数

**返回格式**:
```python
[
    {
        "error_code": "TIMEOUT",
        "count": 3,
        "task_ids": ["task-x", "task-y", ...]  # 最多5个
    },
    ...
]
```

**测试覆盖**:
- ✅ 检测到 RETRY 后失败
- ✅ RETRY 成功未触发

---

### 4. get_decision_lag(window)
**规则**: decision_lag_anomaly

**功能**: 返回窗口内决策延迟统计

**查询逻辑**:
- 查询所有 `SUPERVISOR_*` 事件（带 `source_event_ts` 和 `supervisor_processed_at`）
- 计算延迟：`lag_ms = processed_at - source_event_ts`
- 排序后计算 p95（取前5%）
- 返回 p95 值和高延迟样例（最多5个）

**返回格式**:
```python
{
    "p95_ms": 5500,
    "samples": [
        {"decision_id": "dec-1", "lag_ms": 6000},
        {"decision_id": "dec-2", "lag_ms": 5800},
        ...  # 最多5个
    ]
}
```

**测试覆盖**:
- ✅ 正确计算延迟
- ✅ 空数据返回零值

---

### 5. get_redline_ratio(window)
**规则**: redline_ratio_increase

**功能**: 返回窗口内和前一窗口的 REDLINE 占比

**查询逻辑**:
- 查询当前窗口和前一窗口的所有 `SUPERVISOR_*` 事件
- 统计 `payload.findings[]` 中 `kind="REDLINE"` 的数量
- 计算占比：`redline_count / total_count`
- 返回当前和前一窗口的对比数据

**返回格式**:
```python
{
    "current_ratio": 0.25,  # 当前窗口 25%
    "previous_ratio": 0.10,  # 前一窗口 10%
    "current_count": 25,
    "total_count": 100
}
```

**测试覆盖**:
- ✅ 正确计算占比
- ✅ 空窗口返回零值

---

### 6. get_high_risk_allow(window)
**规则**: high_risk_allow

**功能**: 返回窗口内高风险但仍被 ALLOW 的决策

**查询逻辑**:
- 查询 `SUPERVISOR_ALLOWED` 事件
- 检查 `payload.findings[]` 是否有 `severity="HIGH"` 或 `"CRITICAL"`
- 返回这些决策的详情（限制最多5个）

**返回格式**:
```python
[
    {
        "decision_id": "dec-xyz",
        "task_id": "task-123",
        "risk_level": "HIGH"
    },
    ...  # 最多5个
]
```

**测试覆盖**:
- ✅ 检测到高风险 ALLOW
- ✅ 低风险未触发
- ✅ 结果限制为5个

---

## 性能优化

### 索引利用
所有查询都使用了现有索引：
- `idx_task_audits_event` (event_type)
- `idx_task_audits_created` (created_at DESC)
- `idx_task_audits_task` (task_id)

### 窗口边界
所有查询使用 `WHERE created_at >= ? AND created_at <= ?` 确保正确过滤数据。

**测试覆盖**:
- ✅ 尊重窗口边界（验证早于窗口的事件不被包含）

---

## 边界条件处理

1. **空窗口**: 所有方法在没有数据时返回空列表或零值
2. **样例限制**: 所有返回 task_ids/samples 的方法都限制最多 5 个
3. **JSON解析失败**: 使用 try-except 捕获，记录警告日志并跳过
4. **时间戳解析失败**: 使用 try-except 捕获，记录警告日志并跳过

---

## 测试结果

### 运行方式
```bash
python3 tests/unit/lead/run_storage_tests.py
```

### 测试结果
```
============================================================
Running LeadStorage Query Tests
============================================================

Method: get_blocked_reasons
  ✓ 有数据时返回统计
  ✓ 空窗口返回空列表
  ✓ 样例限制为5个

Method: get_pause_block_churn
  ✓ 检测到 PAUSE->BLOCK 模式
  ✓ 未检测到模式

Method: get_retry_then_fail
  ✓ 检测到 RETRY 后失败
  ✓ RETRY 成功未触发

Method: get_decision_lag
  ✓ 正确计算延迟
  ✓ 空数据返回零值

Method: get_redline_ratio
  ✓ 正确计算占比
  ✓ 空窗口返回零值

Method: get_high_risk_allow
  ✓ 检测到高风险 ALLOW
  ✓ 低风险未触发
  ✓ 结果限制为5个

Boundary Conditions
  ✓ 尊重窗口边界

============================================================
Test Summary: 15/15 passed
============================================================
```

**总计**: 15/15 测试通过 ✅

---

## 设计原则

1. **只读查询**: 所有方法只读取数据，不修改任何表
2. **索引优化**: 使用 WHERE + ORDER BY 利用现有索引
3. **样例限制**: 所有返回的 task_ids/samples 最多 5 个
4. **边界条件**: 空窗口返回空列表/零值
5. **错误处理**: JSON 解析失败时记录日志并跳过

---

## 数据源映射

### task_audits 表
- **event_type**: `SUPERVISOR_ALLOWED`, `SUPERVISOR_PAUSED`, `SUPERVISOR_BLOCKED`, `SUPERVISOR_RETRY_RECOMMENDED`, `SUPERVISOR_DECISION`
- **payload**: JSON 格式，包含 `findings[]`, `decision_type`, `decision_id` 等
- **decision_id**: 决策唯一 ID（v0.15新增）
- **source_event_ts**: 源事件时间戳（v0.15新增）
- **supervisor_processed_at**: 处理完成时间（v0.15新增）

### payload 结构示例
```json
{
    "decision_id": "dec_123",
    "decision_type": "BLOCK",
    "findings": [
        {
            "code": "REDLINE_001",
            "kind": "REDLINE",
            "severity": "HIGH",
            "message": "..."
        }
    ],
    "actions": [...],
    "timestamp": "2026-01-28T10:00:00Z"
}
```

---

## 验收标准

- ✅ 查询有索引利用（使用 WHERE + ORDER BY）
- ✅ 单测：每个方法至少 1 个 happy path
- ✅ Mock 数据测试：使用 in-memory sqlite
- ✅ 边界条件：窗口为空时返回空列表/零值
- ✅ 样例限制：所有返回的 task_ids/samples 最多 5 个

---

## 后续集成

该 Storage Adapter 已可直接供 Risk Miner 使用：

```python
from agentos.core.lead.adapters import LeadStorage
from agentos.core.lead.models import ScanWindow, WindowKind
from datetime import datetime, timezone, timedelta

# 创建 Storage
storage = LeadStorage(db_path)

# 创建扫描窗口
now = datetime.now(timezone.utc)
window = ScanWindow(
    kind=WindowKind.HOUR_24,
    start_ts=(now - timedelta(hours=24)).isoformat(),
    end_ts=now.isoformat()
)

# 查询数据
blocked_reasons = storage.get_blocked_reasons(window)
pause_churn = storage.get_pause_block_churn(window)
retry_fails = storage.get_retry_then_fail(window)
lag_stats = storage.get_decision_lag(window)
redline_ratio = storage.get_redline_ratio(window)
high_risk_allows = storage.get_high_risk_allow(window)

# 传递给 Risk Miner（待 L3 完成后实现）
```

---

## 约束遵守

- ✅ 只读查询，不修改数据
- ✅ 使用 project 已有的 DB 连接方式（sqlite3）
- ✅ 参考了 supervisor/inbox.py 和 supervisor/adapters/audit_adapter.py 的查询模式
- ✅ 从 task_audits 的 payload JSON 中提取决策数据（无需 decision_snapshot 表）
- ✅ 所有查询使用索引优化

---

**交付状态**: ✅ 完成

**测试状态**: ✅ 15/15 通过

**验收标准**: ✅ 全部满足
