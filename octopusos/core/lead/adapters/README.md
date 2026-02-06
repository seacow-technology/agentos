# Lead Agent Adapters

Lead Agent 的适配器层，负责与其他系统集成。

## 架构

```
Lead Agent Core
    ├── models.py           # 领域模型
    ├── miner.py           # 风险挖掘规则引擎
    ├── dedupe.py          # 去重存储
    ├── service.py         # 核心服务
    └── adapters/          # 适配器层
        ├── storage.py     # 只读查询适配器（访问 task_audits）
        └── task_creator.py # 任务创建适配器（创建 follow-up tasks）
```

## Task Creator Adapter

### 功能

`LeadTaskCreator` 负责将 `LeadFinding` 转换为 follow-up tasks：

1. **dry_run 支持**: 预览模式，不落库
2. **去重检查**: 检查 `finding.linked_task_id`，避免重复创建
3. **智能路由**: 根据 severity 决定任务初始状态
   - CRITICAL/HIGH → APPROVED（立即执行）
   - MEDIUM/LOW → DRAFT（需要审批）
4. **完整描述**: 任务描述包含 evidence、建议行动、fingerprint

### 使用示例

```python
from pathlib import Path
from agentos.core.lead.adapters.task_creator import LeadTaskCreator
from agentos.core.lead.dedupe import LeadFinding, LeadFindingStore

# 初始化
db_path = Path("/path/to/database.db")
task_creator = LeadTaskCreator(db_path=db_path)
finding_store = LeadFindingStore(db_path=db_path)

# 创建 finding
finding = LeadFinding(
    fingerprint="unique_fp_001",
    code="blocked_reason_spike",
    severity="HIGH",
    title="检测到大量任务因相同原因被阻塞",
    description="在过去 24 小时内，有 15 个任务因 'TIMEOUT_ERROR' 被阻塞",
    window_kind="24h",
    evidence={
        "count": 15,
        "samples": ["task-1", "task-2", "task-3"],
    }
)
finding_store.upsert_finding(finding)

# 预览模式（dry_run）
task_id = task_creator.create_follow_up_task(finding, dry_run=True)
print(f"[DRY_RUN] 将创建任务: {task_id}")

# 实际创建任务
task_id = task_creator.create_follow_up_task(finding, dry_run=False)
print(f"创建任务: {task_id}")

# 批量创建
findings = [finding1, finding2, finding3]
result = task_creator.create_batch(findings, dry_run=False)
print(f"创建: {result['created']} 个任务")
print(f"跳过: {result['skipped']} 个任务")
```

### 任务描述模板

创建的任务包含以下信息：

```markdown
## Lead Agent 风险线索

**规则代码**: blocked_reason_spike
**严重等级**: HIGH
**检测窗口**: 24h
**首次发现**: 2026-01-28T10:00:00+00:00
**最近发现**: 2026-01-28T11:00:00+00:00
**重复次数**: 3

## 问题描述
在过去 24 小时内，有 15 个任务因 'TIMEOUT_ERROR' 被阻塞

## 证据
- **发现次数**: 15
- **样例任务** (3 个):
  - `task-1`
  - `task-2`
  - `task-3`

## 建议行动
**优先处理**

1. 检查相关任务的 blocked 原因
2. 评估是否需要调整 Guardian 规则
3. 如果是系统性问题，考虑修复根因

---
*由 Lead Agent 自动生成 | fingerprint: unique_fp_001*
```

### 测试

```bash
# 运行集成测试
python3 tests/integration/lead/run_task_creator_tests.py

# 运行演示
python3 tests/integration/lead/demo_task_creator.py
```

### API

#### `create_follow_up_task(finding, dry_run=True) -> Optional[str]`

为单个 finding 创建 follow-up task。

**参数**:
- `finding`: LeadFinding 对象
- `dry_run`: True 时不落库，只返回模拟的 task_id

**返回**:
- `task_id`: 创建的任务 ID（dry_run 时返回 "DRY_RUN_xxx"）
- `None`: finding 已有 linked_task_id 时跳过

**行为**:
1. 检查 `finding.linked_task_id`，如果已有则跳过
2. 生成任务标题和描述
3. 根据 severity 决定初始状态（APPROVED/DRAFT）
4. dry_run=False 时：
   - 创建任务（通过 TaskService）
   - CRITICAL/HIGH 自动 approve
   - 更新 `finding.linked_task_id`

#### `create_batch(findings, dry_run=True) -> dict`

批量创建 follow-up tasks。

**返回**:
```python
{
    "created": int,      # 实际创建数
    "skipped": int,      # 已有 linked_task 跳过数
    "task_ids": [...]    # 创建的 task_id 列表
}
```

## Storage Adapter

### 功能

`LeadStorage` 提供只读查询接口，从 AgentOS 数据库提取数据：

- 查询 `task_audits` 表（Supervisor 决策历史）
- 支持 6 条规则的数据查询
- 所有查询都带窗口过滤（`window.start_ts`, `window.end_ts`）

### 使用示例

```python
from pathlib import Path
from agentos.core.lead.adapters.storage import LeadStorage
from agentos.core.lead.models import ScanWindow, WindowKind

# 初始化
db_path = Path("/path/to/database.db")
storage = LeadStorage(db_path=db_path)

# 创建扫描窗口
window = ScanWindow(
    kind=WindowKind.HOUR_24,
    start_ts="2026-01-27T10:00:00+00:00",
    end_ts="2026-01-28T10:00:00+00:00"
)

# 查询数据
blocked_reasons = storage.get_blocked_reasons(window)
print(f"发现 {len(blocked_reasons)} 个 blocked 原因")

pause_churn = storage.get_pause_block_churn(window)
print(f"发现 {len(pause_churn)} 个 pause/block churn")
```

### API

- `get_blocked_reasons(window)`: 规则 1 - blocked_reason_spike
- `get_pause_block_churn(window)`: 规则 2 - pause_block_churn
- `get_retry_then_fail(window)`: 规则 3 - retry_recommended_but_fails
- `get_decision_lag(window)`: 规则 4 - decision_lag_anomaly
- `get_redline_ratio(window)`: 规则 5 - redline_ratio_increase
- `get_high_risk_allow(window)`: 规则 6 - high_risk_allow

## 设计原则

### 1. 零侵入
- 不修改现有系统的表结构
- 只添加新表（`lead_findings`）
- 使用适配器模式集成

### 2. 幂等性
- 通过 `fingerprint` 实现去重
- `finding.linked_task_id` 防止重复创建
- `upsert` 操作保证原子性

### 3. 可测试性
- 所有适配器支持依赖注入（`db_path`）
- dry_run 模式支持预览
- 完整的集成测试覆盖

### 4. 性能优化
- 所有查询使用索引（`created_at`, `task_id`, `event_type`）
- 样例限制（最多 5 个）
- 批量操作支持

## 依赖

- `agentos.core.task.service`: TaskService（创建任务）
- `agentos.core.task.states`: TaskState（状态管理）
- `agentos.core.lead.dedupe`: LeadFindingStore（去重存储）
- `agentos.core.lead.models`: LeadFinding（领域模型）

## 版本

- v1.0.0: 初始版本
  - Task Creator Adapter
  - Storage Adapter
  - 完整测试覆盖
