# Guardian Module

Guardian 是 AgentOS 的验收事实记录器（Verification / Acceptance Authority）。

## 核心原则

1. **Guardian 是只读叠加层**：不修改 Task 状态机，不引入强制卡死流程
2. **Guardian 记录验收事实**：记录 PASS/FAIL/NEEDS_REVIEW，不控制流程
3. **Guardian 是 Overlay，不是 Gate**：验收记录是辅助信息，不阻塞执行

## 架构组件

### 1. 数据模型（models.py）

#### GuardianReview
验收审查记录（不可变）

```python
from agentos.core.guardian import GuardianReview

# 创建自动验收记录
review = GuardianReview.create_auto_review(
    target_type="task",
    target_id="task_123",
    guardian_id="guardian.ruleset.v1",
    verdict="PASS",
    confidence=0.92,
    evidence={"checks": ["state_machine_ok"], "metrics": {}},
    rule_snapshot_id="ruleset:v1@sha256:abc"
)

# 创建人工验收记录
review = GuardianReview.create_manual_review(
    target_type="task",
    target_id="task_123",
    guardian_id="human.alice",
    verdict="FAIL",
    evidence={"reason": "Policy violation"}
)
```

**字段说明：**

- `review_id`: 唯一审查 ID（自动生成）
- `target_type`: 审查目标类型（task | decision | finding）
- `target_id`: 审查目标 ID
- `guardian_id`: Guardian ID（agent name / human id）
- `review_type`: 审查类型（AUTO | MANUAL）
- `verdict`: 验收结论（PASS | FAIL | NEEDS_REVIEW）
- `confidence`: 置信度（0.0-1.0）
- `rule_snapshot_id`: 规则快照 ID（可选，用于审计）
- `evidence`: 验收证据（JSON 结构）
- `created_at`: 创建时间（ISO8601）

### 2. 服务层（service.py）

#### GuardianService
提供 Guardian 验收审查记录的 CRUD 操作和统计查询。

```python
from agentos.core.guardian import GuardianService

service = GuardianService()

# 创建验收记录
review = service.create_review(
    target_type="task",
    target_id="task_123",
    guardian_id="guardian.v1",
    review_type="AUTO",
    verdict="PASS",
    confidence=0.92,
    evidence={"checks": ["all_pass"]}
)

# 查询验收记录
reviews = service.list_reviews(verdict="FAIL", limit=50)

# 获取特定目标的所有验收记录
task_reviews = service.get_reviews_by_target("task", "task_123")

# 获取统计数据
stats = service.get_statistics()
print(f"Pass rate: {stats['pass_rate']:.2%}")

# 获取目标的验收摘要
summary = service.get_verdict_summary("task", "task_123")
print(f"Latest verdict: {summary['latest_verdict']}")
```

**主要方法：**

- `create_review()`: 创建验收记录
- `get_review(review_id)`: 根据 ID 获取记录
- `list_reviews(...)`: 灵活查询（支持多维度过滤）
- `get_reviews_by_target(target_type, target_id)`: 获取目标的所有记录
- `get_statistics(...)`: 获取统计数据
- `get_verdict_summary(target_type, target_id)`: 获取验收摘要

### 3. 存储适配器（storage.py）

#### GuardianStorage
提供数据库 CRUD 操作，所有查询都经过索引优化。

```python
from agentos.core.guardian import GuardianStorage
from pathlib import Path

storage = GuardianStorage(db_path=Path("store/registry.sqlite"))

# 保存验收记录
storage.save(review)

# 根据 ID 查询
review = storage.get_by_id("review_abc123")

# 灵活查询
reviews = storage.query(
    target_type="task",
    verdict="FAIL",
    limit=100
)

# 获取目标的所有记录
reviews = storage.get_by_target("task", "task_123")

# 获取统计数据
stats = storage.get_stats(target_type="task")
```

### 4. 规则集管理（policies.py）

#### GuardianPolicy
规则集快照（不可变），用于审计追溯。

```python
from agentos.core.guardian.policies import GuardianPolicy

rules = {"check": "state_machine_valid", "threshold": 0.9}

policy = GuardianPolicy(
    policy_id="guardian.task.state_machine",
    name="Task State Machine Validator",
    version="v1.0.0",
    rules=rules,
    checksum=GuardianPolicy.compute_checksum(rules)
)

print(f"Snapshot ID: {policy.snapshot_id}")
# Output: guardian.task.state_machine:v1.0.0@sha256:abc123def456
```

#### PolicyRegistry
规则集注册表，管理所有规则快照。

```python
from agentos.core.guardian.policies import get_policy_registry

registry = get_policy_registry()

# 注册规则集
snapshot_id = registry.create_and_register(
    policy_id="guardian.task.state_machine",
    name="Task State Machine Validator",
    version="v1.0.0",
    rules={"check": "state_machine_valid"},
    metadata={"author": "system"}
)

# 获取规则集
policy = registry.get(snapshot_id)

# 列出所有版本
versions = registry.list_versions("guardian.task.state_machine")

# 获取最新版本
latest = registry.get_latest("guardian.task.state_machine")
```

## REST API 端点

Guardian 提供完整的 REST API（详见 `agentos/webui/api/guardian.py`）。

### 端点列表

1. **GET /api/guardian/reviews**
   - 查询验收记录列表
   - 支持过滤：target_type, target_id, guardian_id, verdict
   - 支持分页：limit 参数

2. **POST /api/guardian/reviews**
   - 创建验收记录
   - 请求体：CreateReviewRequest

3. **GET /api/guardian/reviews/{review_id}**
   - 获取单个验收记录详情

4. **GET /api/guardian/statistics**
   - 获取统计数据
   - 支持过滤：target_type, since_hours

5. **GET /api/guardian/targets/{target_type}/{target_id}/reviews**
   - 获取目标的所有验收记录

6. **GET /api/guardian/targets/{target_type}/{target_id}/verdict**
   - 获取目标的验收摘要

### API 使用示例

```bash
# 查询所有 FAIL 的记录
curl "http://localhost:8080/api/guardian/reviews?verdict=FAIL"

# 创建验收记录
curl -X POST "http://localhost:8080/api/guardian/reviews" \
  -H "Content-Type: application/json" \
  -d '{
    "target_type": "task",
    "target_id": "task_123",
    "guardian_id": "guardian.v1",
    "review_type": "AUTO",
    "verdict": "PASS",
    "confidence": 0.92,
    "evidence": {"checks": ["all_pass"]}
  }'

# 获取任务的验收摘要
curl "http://localhost:8080/api/guardian/targets/task/task_123/verdict"

# 获取统计数据
curl "http://localhost:8080/api/guardian/statistics"
```

## Task Service 集成

Guardian 与 Task Service 的集成是只读的，不影响 Task 状态机。

```python
from agentos.core.task import TaskService

service = TaskService()

# 获取任务的所有验收记录（只读叠加层）
reviews = service.get_guardian_reviews("task_123")

for review in reviews:
    print(f"{review.verdict}: {review.confidence}")
```

## 数据库 Schema

Guardian 使用 `guardian_reviews` 表存储验收记录（详见 `agentos/store/migrations/v22_guardian_reviews.sql`）。

### 表结构

```sql
CREATE TABLE guardian_reviews (
    review_id TEXT PRIMARY KEY,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    guardian_id TEXT NOT NULL,
    review_type TEXT NOT NULL,
    verdict TEXT NOT NULL,
    confidence REAL NOT NULL,
    rule_snapshot_id TEXT,
    evidence TEXT NOT NULL,
    created_at TEXT NOT NULL,
    CHECK(target_type IN ('task', 'decision', 'finding')),
    CHECK(review_type IN ('AUTO', 'MANUAL')),
    CHECK(verdict IN ('PASS', 'FAIL', 'NEEDS_REVIEW')),
    CHECK(confidence >= 0.0 AND confidence <= 1.0)
);
```

### 索引优化

为常见查询场景创建了索引：

1. `idx_guardian_reviews_target`: 按目标查询
2. `idx_guardian_reviews_guardian`: 按 Guardian 查询
3. `idx_guardian_reviews_verdict`: 按 verdict 查询
4. `idx_guardian_reviews_created_at`: 按时间查询
5. `idx_guardian_reviews_type_verdict`: 复合查询
6. `idx_guardian_reviews_rule_snapshot`: 规则快照查询

## 测试

Guardian 模块包含完整的单元测试（覆盖率 > 90%）。

### 运行测试

```bash
# 运行所有 Guardian 测试
pytest tests/unit/guardian/ -v

# 运行服务层测试
pytest tests/unit/guardian/test_service.py -v

# 运行存储层测试
pytest tests/unit/guardian/test_storage.py -v

# 运行策略管理测试
pytest tests/unit/guardian/test_policies.py -v

# 查看覆盖率
pytest tests/unit/guardian/ --cov=agentos.core.guardian --cov-report=term-missing
```

### 测试覆盖范围

- **test_service.py**: GuardianService CRUD 操作和业务逻辑
- **test_storage.py**: GuardianStorage 数据库操作
- **test_policies.py**: GuardianPolicy 和 PolicyRegistry 功能

## 设计模式

### 1. 只读叠加层（Read-only Overlay）

Guardian 不修改 Task 状态机，只记录验收事实：

```python
# Task 状态机（独立运行）
task_service.start_task("task_123")
task_service.complete_task_execution("task_123")

# Guardian 验收（叠加层，不影响状态）
guardian_service.create_review(
    target_type="task",
    target_id="task_123",
    verdict="PASS",
    ...
)
```

### 2. 不可变记录（Immutable Records）

验收记录一旦创建就无法修改，确保审计完整性：

- 只提供 `create_review()` 和查询方法
- 不提供 `update_review()` 或 `delete_review()`
- 所有验收记录永久保存

### 3. 证据驱动（Evidence-based）

所有验收记录必须包含完整的证据：

```python
evidence = {
    "checks": ["state_machine_ok", "dependencies_resolved"],
    "metrics": {"coverage": 0.85, "complexity": 12},
    "findings": ["potential_risk_1"],
    "reason": "All checks passed with high confidence"
}
```

### 4. 规则版本追踪（Rule Versioning）

使用规则快照确保可审计性：

```python
# 注册规则集
snapshot_id = registry.create_and_register(
    policy_id="guardian.task.state_machine",
    version="v1.0.0",
    rules={...}
)

# 创建验收记录时关联规则快照
review = service.create_review(
    ...,
    rule_snapshot_id=snapshot_id
)

# 未来可以追溯：使用的是哪个版本的规则
policy = registry.get(review.rule_snapshot_id)
```

## 使用场景

### 1. 任务验收

```python
# 任务完成后，Guardian 进行验收
task_service.complete_task_execution("task_123")

# Guardian 自动验收
guardian_service.create_review(
    target_type="task",
    target_id="task_123",
    guardian_id="guardian.task.auto",
    review_type="AUTO",
    verdict="PASS",
    confidence=0.95,
    evidence={"checks": ["test_pass", "lint_pass"]}
)
```

### 2. 决策验收

```python
# Supervisor 做出决策后，Guardian 验收决策合规性
guardian_service.create_review(
    target_type="decision",
    target_id="decision_456",
    guardian_id="guardian.compliance",
    review_type="AUTO",
    verdict="FAIL",
    confidence=0.88,
    evidence={"findings": ["policy_violation"]}
)
```

### 3. 发现验收

```python
# Lead Agent 发现风险后，Guardian 验收风险等级
guardian_service.create_review(
    target_type="finding",
    target_id="finding_789",
    guardian_id="human.reviewer",
    review_type="MANUAL",
    verdict="NEEDS_REVIEW",
    confidence=1.0,
    evidence={"reason": "Requires human judgment"}
)
```

## 扩展性

Guardian 设计为可扩展：

1. **新的 target_type**：支持扩展到新的治理对象（如：deployment, release）
2. **新的 Guardian**：支持注册新的 Guardian Agent 或人工审查员
3. **新的规则集**：支持动态注册和版本管理
4. **新的统计指标**：支持添加新的聚合统计

## 性能优化

1. **索引优化**：所有常见查询都有对应索引
2. **分页查询**：支持 limit 参数，避免大量数据返回
3. **按需查询**：支持灵活过滤，只返回需要的数据
4. **缓存友好**：规则注册表使用内存缓存

## 最佳实践

1. **always provide evidence**: 所有验收记录必须包含完整的证据
2. **use rule snapshots**: 自动验收应关联规则快照（便于审计）
3. **set appropriate confidence**: 置信度应反映验收的可靠性
4. **manual review for critical**: 关键决策应使用人工验收
5. **monitor statistics**: 定期检查统计数据，发现异常模式

## 故障排查

### 问题：验收记录创建失败

**解决方案：**
1. 检查 target_type 是否有效（task | decision | finding）
2. 检查 verdict 是否有效（PASS | FAIL | NEEDS_REVIEW）
3. 检查 confidence 是否在 0.0-1.0 范围内
4. 检查数据库连接是否正常

### 问题：查询性能慢

**解决方案：**
1. 使用 limit 参数限制返回数量
2. 使用索引优化的字段过滤（target_type, target_id, guardian_id, verdict）
3. 检查数据库索引是否正常创建

### 问题：规则快照校验失败

**解决方案：**
1. 确保 checksum 使用 `GuardianPolicy.compute_checksum(rules)` 计算
2. 不要手动修改 rules 内容
3. 使用 `PolicyRegistry.create_and_register()` 自动计算校验和

## 贡献指南

如需扩展 Guardian 功能，请遵循以下原则：

1. **保持只读叠加层**：不修改 Task 状态机
2. **保持不可变性**：验收记录不可修改
3. **保持证据驱动**：所有验收必须有证据
4. **保持可审计性**：支持规则版本追踪
5. **添加测试**：确保测试覆盖率 > 90%

## 许可证

MIT License

## 联系方式

如有问题或建议，请联系 AgentOS 团队。
