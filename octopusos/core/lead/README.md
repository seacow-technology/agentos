# Lead Agent - 风险线索挖掘系统

## 概述

Lead Agent 是一个自动化的风险检测和线索挖掘系统，通过分析 Supervisor 决策历史，识别系统性风险、异常模式和潜在问题。

## 文件结构

```
agentos/core/lead/
├── __init__.py          # 模块导出
├── models.py            # 数据模型（LeadFinding, ScanWindow 等）
├── miner.py             # 风险规则引擎（RiskMiner）
└── README.md            # 本文档

tests/unit/lead/
├── __init__.py
├── test_miner_rules.py  # pytest 单元测试（需要 pytest）
└── run_tests.py         # 独立测试运行器（不需要 pytest）
```

## MVP 规则（6条）

### 1. blocked_reason_spike
**检测**: 24h 内某 finding.code 激增（count > threshold）

**触发条件**:
- 某个 finding.code 出现次数超过配置的阈值（默认5次）

**Evidence**:
- `count`: 出现次数
- `finding_code`: 激增的 finding code
- `sample_decision_ids`: 样例决策 ID（最多5个）

### 2. pause_block_churn
**检测**: 同一任务多次 PAUSE 后最终 BLOCK

**触发条件**:
- 任务被 PAUSE 次数 >= 阈值（默认2次）
- 最终决策为 BLOCK

**Evidence**:
- `task_id`: 任务 ID
- `pause_count`: PAUSE 次数
- `final_decision`: 最终决策类型
- `sample_decision_ids`: 样例决策 ID

### 3. retry_recommended_but_fails
**检测**: RETRY 建议后仍然失败

**触发条件**:
- 决策类型为 RETRY
- 同一任务后续出现 BLOCK 决策

**Evidence**:
- `task_id`: 任务 ID
- `retry_decision_id`: RETRY 决策 ID
- `failed_decision_id`: 失败决策 ID
- `failed_decision_type`: 失败决策类型

### 4. decision_lag_anomaly
**检测**: 决策延迟 p95 超过阈值

**触发条件**:
- 决策延迟 p95 > 配置的阈值（默认5000ms）

**Evidence**:
- `p95_latency_ms`: P95 延迟（毫秒）
- `sample_count`: 样本数量
- `threshold_ms`: 配置的阈值

### 5. redline_ratio_increase
**检测**: REDLINE 类型 finding 占比显著上升

**触发条件**:
- REDLINE 占比 - 基准占比 > 增幅阈值（默认10%）

**Evidence**:
- `redline_count`: REDLINE 类型数量
- `total_count`: 总 finding 数量
- `redline_ratio`: REDLINE 占比
- `baseline_ratio`: 基准占比
- `increase`: 增幅

### 6. high_risk_allow
**检测**: HIGH/CRITICAL 严重度问题仍被 ALLOW

**触发条件**:
- 决策类型为 ALLOW
- 决策包含 HIGH 或 CRITICAL 严重度的 findings

**Evidence**:
- `count`: 违规决策数量
- `sample_decision_ids`: 样例决策 ID（最多5个）

## 使用示例

### 基本用法

```python
from agentos.core.lead import RiskMiner, MinerConfig, ScanWindow, WindowKind
from datetime import datetime, timezone, timedelta

# 创建配置（可选，使用默认值）
config = MinerConfig(
    spike_threshold=5,
    pause_count_threshold=2,
    decision_lag_p95_ms=5000.0,
    redline_ratio_increase=0.10,
    redline_baseline_ratio=0.05
)

# 创建 miner
miner = RiskMiner(config)

# 定义扫描窗口
now = datetime.now(timezone.utc)
window = ScanWindow(
    kind=WindowKind.HOUR_24,
    start_ts=(now - timedelta(hours=24)).isoformat(),
    end_ts=now.isoformat()
)

# 准备 storage_data（从 LeadStorage 获取）
storage_data = {
    "findings": [
        {
            "code": "REDLINE_001",
            "kind": "REDLINE",
            "severity": "HIGH",
            "decision_id": "dec_123"
        },
        # ...更多 findings
    ],
    "decisions": [
        {
            "decision_id": "dec_123",
            "task_id": "task_456",
            "decision_type": "BLOCK",
            "timestamp": "2026-01-28T10:00:00Z"
        },
        # ...更多 decisions
    ],
    "metrics": {
        "decision_latencies": [1000.0, 2000.0, 3000.0]
    }
}

# 执行风险挖掘
findings = miner.mine_risks(storage_data, window)

# 处理结果
for finding in findings:
    print(f"[{finding.severity}] {finding.title}")
    print(f"  Rule: {finding.rule_code}")
    print(f"  Evidence: {finding.evidence}")
    print(f"  Fingerprint: {finding.fingerprint}")
```

### 配置阈值

```python
# 自定义配置
config = MinerConfig(
    spike_threshold=10,              # 激增阈值提高到10
    pause_count_threshold=3,         # PAUSE 次数阈值提高到3
    decision_lag_p95_ms=3000.0,      # 延迟阈值降低到3000ms
    redline_ratio_increase=0.05,     # 占比增幅阈值降低到5%
    redline_baseline_ratio=0.10      # 基准占比提高到10%
)

miner = RiskMiner(config)
```

## 幂等性保证

每个 `LeadFinding` 都包含一个 `fingerprint` 字段，通过以下方式计算：

```
fingerprint = SHA256(rule_code + window + 关键维度)[:16]
```

相同的风险模式在同一窗口内只会产生一个 finding，避免重复告警。

## 测试

### 使用 pytest（需要安装 pytest）

```bash
pytest tests/unit/lead/test_miner_rules.py -v
```

### 使用独立测试运行器（不需要 pytest）

```bash
python3 tests/unit/lead/run_tests.py
```

测试覆盖：
- 每条规则至少2个测试用例（触发/不触发）
- Evidence 完整性验证
- Fingerprint 幂等性验证
- 多规则集成测试

## 约束和设计原则

1. **接口冻结**: 使用 `storage_data` 字典作为输入，返回 `List[LeadFinding]`
2. **幂等性**: 通过 fingerprint 实现，避免重复告警
3. **可配置**: 所有阈值通过 `MinerConfig` 配置
4. **独立性**: 每条规则独立实现，易于测试和扩展
5. **Evidence 完整**: 所有 finding 必须包含 count 和 samples
6. **样例限制**: sample_decision_ids 最多5个

## 扩展

如需添加新规则：

1. 在 `MinerConfig` 中添加配置项
2. 在 `RiskMiner` 中实现 `_rule_xxx()` 方法
3. 在 `mine_risks()` 中调用新规则
4. 在测试文件中添加至少2个测试用例

示例：

```python
def _rule_new_pattern(
    self,
    storage_data: Dict[str, Any],
    window: ScanWindow
) -> List[LeadFinding]:
    """新规则：检测某种模式"""
    # 实现逻辑
    pass
```
