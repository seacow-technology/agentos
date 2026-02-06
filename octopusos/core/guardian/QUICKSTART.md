# Guardian Quick Start Guide

5 分钟快速上手 Guardian 验收系统。

## 1. 基本概念

- **Guardian = 验收事实记录器**：记录 PASS/FAIL/NEEDS_REVIEW，不控制流程
- **只读叠加层**：不修改 Task 状态机
- **不可变记录**：一旦创建就无法修改

## 2. 快速开始

### 创建验收记录

```python
from agentos.core.guardian import GuardianService

service = GuardianService()

# 自动验收（由 Guardian Agent 执行）
review = service.create_review(
    target_type="task",           # 审查目标类型：task | decision | finding
    target_id="task_123",          # 审查目标 ID
    guardian_id="guardian.v1",     # Guardian ID
    review_type="AUTO",            # 审查类型：AUTO | MANUAL
    verdict="PASS",                # 验收结论：PASS | FAIL | NEEDS_REVIEW
    confidence=0.92,               # 置信度（0.0-1.0）
    evidence={"checks": ["ok"]}    # 验收证据（JSON）
)

print(f"Review created: {review.review_id}")
```

### 查询验收记录

```python
# 查询所有 FAIL 的记录
failed_reviews = service.list_reviews(verdict="FAIL")

# 查询某个任务的所有记录
task_reviews = service.get_reviews_by_target("task", "task_123")

# 获取统计数据
stats = service.get_statistics()
print(f"Pass rate: {stats['pass_rate']:.2%}")
```

### 获取验收摘要

```python
# 快速查看某个任务的验收状态
summary = service.get_verdict_summary("task", "task_123")

print(f"Total reviews: {summary['total_reviews']}")
print(f"Latest verdict: {summary['latest_verdict']}")
print(f"Latest guardian: {summary['latest_guardian_id']}")
```

## 3. REST API 快速调用

```bash
# 查询验收记录
curl "http://localhost:8080/api/guardian/reviews?verdict=FAIL&limit=10"

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

# 获取验收摘要
curl "http://localhost:8080/api/guardian/targets/task/task_123/verdict"

# 获取统计数据
curl "http://localhost:8080/api/guardian/statistics"
```

## 4. 常用模式

### 模式 1: 任务完成后自动验收

```python
from agentos.core.task import TaskService
from agentos.core.guardian import GuardianService

task_service = TaskService()
guardian_service = GuardianService()

# 完成任务
task_service.complete_task_execution("task_123")

# Guardian 自动验收（不影响任务状态）
guardian_service.create_review(
    target_type="task",
    target_id="task_123",
    guardian_id="guardian.auto",
    review_type="AUTO",
    verdict="PASS",
    confidence=0.95,
    evidence={"checks": ["test_pass", "lint_pass"]}
)
```

### 模式 2: 人工验收

```python
# 人工审查员进行验收
guardian_service.create_review(
    target_type="task",
    target_id="task_123",
    guardian_id="human.alice",
    review_type="MANUAL",
    verdict="NEEDS_REVIEW",
    confidence=1.0,  # 人工验收固定为 1.0
    evidence={"reason": "Requires deeper investigation"}
)
```

### 模式 3: 批量查询和统计

```python
# 查询需要人工审查的记录
needs_review = service.list_reviews(verdict="NEEDS_REVIEW")

# 统计某个 Guardian 的验收情况
guardian_reviews = service.list_reviews(guardian_id="guardian.v1")
pass_count = sum(1 for r in guardian_reviews if r.verdict == "PASS")
pass_rate = pass_count / len(guardian_reviews)

print(f"Guardian v1 pass rate: {pass_rate:.2%}")
```

### 模式 4: 规则集管理

```python
from agentos.core.guardian.policies import get_policy_registry

registry = get_policy_registry()

# 注册规则集
snapshot_id = registry.create_and_register(
    policy_id="guardian.task.state_machine",
    name="Task State Machine Validator",
    version="v1.0.0",
    rules={"check_transitions": True, "allow_skip": False}
)

# 创建验收记录时关联规则快照
guardian_service.create_review(
    ...,
    rule_snapshot_id=snapshot_id
)

# 未来可以追溯使用的规则版本
policy = registry.get(snapshot_id)
print(f"Used rules: {policy.rules}")
```

## 5. 集成到现有系统

### 与 Task Service 集成（只读）

```python
from agentos.core.task import TaskService

task_service = TaskService()

# 获取任务的所有验收记录（不影响任务状态）
reviews = task_service.get_guardian_reviews("task_123")

for review in reviews:
    print(f"{review.created_at}: {review.verdict} (confidence: {review.confidence})")
```

### 在 WebUI 中显示验收记录

```javascript
// 获取任务的验收记录
fetch('/api/guardian/targets/task/task_123/reviews')
  .then(res => res.json())
  .then(data => {
    console.log(`Total reviews: ${data.total}`);
    data.reviews.forEach(review => {
      console.log(`${review.verdict}: ${review.evidence}`);
    });
  });

// 获取验收摘要
fetch('/api/guardian/targets/task/task_123/verdict')
  .then(res => res.json())
  .then(summary => {
    console.log(`Latest verdict: ${summary.latest_verdict}`);
  });
```

## 6. 最佳实践

1. **Always provide evidence**: 所有验收记录必须包含证据
2. **Use appropriate confidence**: 置信度应反映验收可靠性
3. **Manual review for critical**: 关键决策使用人工验收
4. **Monitor statistics**: 定期检查统计数据发现异常
5. **Use rule snapshots**: 自动验收关联规则快照便于审计

## 7. 故障排查

### 问题：创建验收记录失败

```python
# 检查参数是否有效
try:
    service.create_review(...)
except ValueError as e:
    print(f"Invalid parameters: {e}")
```

常见错误：
- `target_type` 必须是 `task`, `decision`, 或 `finding`
- `verdict` 必须是 `PASS`, `FAIL`, 或 `NEEDS_REVIEW`
- `confidence` 必须在 0.0-1.0 之间
- `review_type` 必须是 `AUTO` 或 `MANUAL`

### 问题：查询结果为空

```python
# 检查是否有匹配的记录
reviews = service.list_reviews(verdict="PASS")
if not reviews:
    print("No PASS reviews found")

# 尝试不带过滤条件查询
all_reviews = service.list_reviews()
print(f"Total reviews: {len(all_reviews)}")
```

## 8. 下一步

- 阅读完整文档：`README.md`
- 查看测试示例：`tests/unit/guardian/`
- 查看 API 文档：`agentos/webui/api/guardian.py`
- 查看数据库 Schema：`agentos/store/migrations/v22_guardian_reviews.sql`

## 9. 常见问题

**Q: Guardian 会阻塞任务执行吗？**
A: 不会。Guardian 是只读叠加层，不影响 Task 状态机。

**Q: 验收记录可以修改吗？**
A: 不可以。验收记录是不可变的，确保审计完整性。

**Q: 如何删除错误的验收记录？**
A: 不支持删除。如果需要纠正，创建新的验收记录并在 evidence 中说明。

**Q: 置信度有什么用？**
A: 置信度反映自动验收的可靠性。低置信度记录可能需要人工复核。

**Q: 规则快照有什么用？**
A: 用于审计追溯，可以查看历史验收使用的是哪个版本的规则。

## 10. 示例代码

完整示例：创建任务、执行、验收

```python
from agentos.core.task import TaskService
from agentos.core.guardian import GuardianService

task_service = TaskService()
guardian_service = GuardianService()

# 1. 创建任务
task = task_service.create_draft_task(
    title="Example Task",
    created_by="system"
)

# 2. 执行任务（简化流程）
task_service.approve_task(task.task_id, actor="system")
task_service.queue_task(task.task_id)
task_service.start_task(task.task_id)
task_service.complete_task_execution(task.task_id)

# 3. Guardian 自动验收
review = guardian_service.create_review(
    target_type="task",
    target_id=task.task_id,
    guardian_id="guardian.auto",
    review_type="AUTO",
    verdict="PASS",
    confidence=0.95,
    evidence={
        "checks": ["state_transitions_valid", "no_errors"],
        "metrics": {"execution_time_ms": 1234}
    }
)

# 4. 查看验收结果
summary = guardian_service.get_verdict_summary("task", task.task_id)
print(f"Task {task.task_id} verdict: {summary['latest_verdict']}")
```

## 11. 更多资源

- [Guardian README](README.md): 完整文档
- [API Reference](../../webui/api/guardian.py): REST API 详细说明
- [Database Schema](../../store/migrations/v22_guardian_reviews.sql): 数据库结构
- [Test Examples](../../../tests/unit/guardian/): 测试示例代码

---

Happy Guardian-ing! 🛡️
