# Lead Agent Contract Mapper

## 概述

Contract Mapper 模块负责在 Lead Agent 的不同数据层之间转换数据格式，确保各组件之间的数据契约匹配。

## 架构

```
┌─────────────┐
│   Storage   │  聚合数据查询层
└──────┬──────┘
       │ blocked_reasons, pause_block_churn, retry_then_fail, etc.
       ▼
┌──────────────────┐
│ StorageToMiner   │  转换器 1
│    Mapper        │
└──────┬───────────┘
       │ findings, decisions, metrics
       ▼
┌─────────────┐
│    Miner    │  规则引擎
└──────┬──────┘
       │ LeadFinding (models)
       ▼
┌──────────────────┐
│ MinerToDedupe    │  转换器 2
│    Mapper        │
└──────┬───────────┘
       │ LeadFinding (dedupe)
       ▼
┌─────────────┐
│   Dedupe    │  去重存储层
└─────────────┘
```

## 模块结构

```
agentos/core/lead/contract/
├── __init__.py         # 导出接口
├── mapper.py           # 核心转换逻辑
└── README.md           # 本文档
```

## 核心组件

### 1. StorageToMinerMapper

**职责**: 将 Storage 聚合数据转换为 Miner 期望的输入格式

**输入格式** (Storage):
```python
{
    "blocked_reasons": [
        {"code": str, "count": int, "task_ids": List[str]}
    ],
    "pause_block_churn": [
        {"task_id": str, "pause_count": int, "final_status": str}
    ],
    "retry_then_fail": [
        {"error_code": str, "count": int, "task_ids": List[str]}
    ],
    "decision_lag": {
        "p95_ms": float,
        "samples": List[float]
    },
    "redline_ratio": {
        "current_ratio": float,
        "previous_ratio": float
    },
    "high_risk_allow": [
        {
            "decision_id": str,
            "task_id": str,
            "risk_level": str,
            "findings": List[dict]
        }
    ]
}
```

**输出格式** (Miner):
```python
{
    "findings": [
        {
            "code": str,
            "kind": str,  # BLOCKED | RETRY_FAILED | REDLINE
            "severity": str,
            "decision_id": str,
            "message": str
        }
    ],
    "decisions": [
        {
            "task_id": str,
            "decision_id": str,
            "decision_type": str,  # PAUSE | BLOCK | RETRY | ALLOW
            "timestamp": str
        }
    ],
    "metrics": {
        "decision_latencies": List[float],
        "decision_lag_p95": float
    }
}
```

**使用示例**:
```python
from agentos.core.lead.contract import StorageToMinerMapper

mapper = StorageToMinerMapper()
miner_data = mapper.convert(storage_data)
```

### 2. MinerToDedupeMapper

**职责**: 将 Miner 输出的 LeadFinding 转换为 Dedupe 存储格式

**输入格式** (Miner):
```python
# models.LeadFinding
LeadFinding(
    finding_id: str,
    fingerprint: str,
    rule_code: str,
    severity: str,
    title: str,
    description: str,
    evidence: Dict[str, Any],
    window: ScanWindow,
    detected_at: str
)
```

**输出格式** (Dedupe):
```python
# dedupe.LeadFinding
LeadFinding(
    fingerprint: str,
    code: str,              # rule_code -> code
    severity: str,          # 大写标准化
    title: str,
    description: str,
    window_kind: str,       # ScanWindow.kind.value
    evidence: Dict[str, Any],
    first_seen_at: Optional[datetime],
    last_seen_at: Optional[datetime],
    count: int,
    linked_task_id: Optional[str]
)
```

**使用示例**:
```python
from agentos.core.lead.contract import MinerToDedupeMapper

mapper = MinerToDedupeMapper()
dedupe_finding = mapper.convert(miner_finding)
```

### 3. ContractMapper

**职责**: 统一的转换器入口，组合两个转换器

**使用示例**:
```python
from agentos.core.lead.contract import ContractMapper

# 初始化
mapper = ContractMapper()

# 查看版本
print(mapper.version)  # {'storage_to_miner': '1.0.0', 'miner_to_dedupe': '1.0.0'}

# Storage -> Miner
miner_data = mapper.convert_storage_to_miner(storage_data)

# Miner -> Dedupe
dedupe_finding = mapper.convert_miner_to_dedupe(miner_finding)
```

## 版本管理

每个 Mapper 都有独立的版本号（VERSION 常量），遵循语义化版本规范：

- **MAJOR**: 破坏性变更（不兼容的 API 修改）
- **MINOR**: 新增功能（向后兼容）
- **PATCH**: Bug 修复（向后兼容）

当前版本：
- StorageToMinerMapper: `1.0.0`
- MinerToDedupeMapper: `1.0.0`

## 测试

### 单元测试
```bash
python3 -m pytest tests/unit/lead/test_contract_mapper.py -v
```

测试覆盖：
- ✅ 空数据转换
- ✅ 各种数据类型转换（blocked_reasons, retry_then_fail, etc.）
- ✅ 窗口类型转换（24h, 7d）
- ✅ 边界情况（大量数据、空 evidence）
- ✅ 向后兼容性验证

### 集成测试
```bash
python3 tests/unit/lead/test_mapper_integration.py
```

测试覆盖：
- ✅ 真实数据形状转换
- ✅ 完整数据流模拟
- ✅ 版本追踪

## 在 lead_scan.py 中的使用

```python
class LeadScanJob:
    def __init__(self, ...):
        # 初始化 mapper
        self.mapper = ContractMapper()

    def run_scan(self, window_kind: str, dry_run: bool = True):
        # 1. 查询 Storage 数据
        storage_data = self._load_storage_data(window)

        # 2. 转换为 Miner 格式
        miner_data = self.mapper.convert_storage_to_miner(storage_data)

        # 3. 运行 Miner
        raw_findings = self.miner.mine_risks(miner_data, window)

        # 4. 转换并存储
        for miner_finding in raw_findings:
            dedupe_finding = self.mapper.convert_miner_to_dedupe(miner_finding)
            self.finding_store.upsert_finding(dedupe_finding)
```

## 设计原则

### 1. 单一职责
每个 Mapper 只负责一个方向的转换，职责清晰。

### 2. 可测试性
转换逻辑与业务逻辑解耦，可以独立测试。

### 3. 可版本化
每个 Mapper 有独立版本号，便于追踪变更历史。

### 4. 可复用性
转换逻辑独立为模块，其他组件可以复用。

### 5. 向后兼容
保持与原 lead_scan.py 实现完全一致的行为，确保平滑迁移。

## 维护指南

### 添加新的转换逻辑

1. 在 `mapper.py` 中添加新的转换方法
2. 更新对应 Mapper 的版本号（如果是破坏性变更，增加 MAJOR 版本）
3. 在 `test_contract_mapper.py` 中添加相应测试
4. 更新本 README 文档

### 修改现有转换逻辑

1. 评估是否为破坏性变更
2. 如果是破坏性变更：
   - 增加 MAJOR 版本号
   - 考虑提供迁移脚本
   - 通知所有使用方
3. 如果是非破坏性变更：
   - 增加 MINOR 或 PATCH 版本号
   - 确保现有测试仍然通过
   - 添加新测试覆盖新行为

### 检查向后兼容性

运行向后兼容性测试：
```python
# test_contract_mapper.py 中的 TestBackwardCompatibility
pytest tests/unit/lead/test_contract_mapper.py::TestBackwardCompatibility -v
```

## 故障排查

### 问题：转换后数据格式不匹配

**症状**: Miner 或 Dedupe 层抛出 KeyError 或 AttributeError

**排查步骤**:
1. 检查 Storage 返回的数据格式是否符合预期
2. 验证 Mapper 版本是否与组件版本匹配
3. 查看转换日志，确认数据经过了正确的转换路径

**解决方案**: 更新 Mapper 逻辑以匹配新的数据格式，增加版本号

### 问题：转换后数据丢失

**症状**: Storage 有数据，但 Miner 收到的数据为空

**排查步骤**:
1. 添加日志打印 storage_data 和 miner_data
2. 检查是否有过滤逻辑导致数据被过滤
3. 验证数据键名是否正确（如 `blocked_reasons` vs `blockedReasons`）

**解决方案**: 修复键名映射或过滤条件

## 未来改进

- [ ] 支持自定义转换规则注册
- [ ] 添加转换性能监控
- [ ] 提供转换失败降级策略
- [ ] 支持多版本并存（用于灰度发布）

## 相关文档

- [Lead Agent 整体架构](../README.md)
- [Storage Adapter 文档](../adapters/storage.py)
- [Risk Miner 文档](../miner.py)
- [Dedupe Store 文档](../dedupe.py)
