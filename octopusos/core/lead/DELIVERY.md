# Lead Agent Miner 交付文档

## 交付概览

已完成 Lead Agent 风险规则 miner 的实现，包含6条MVP规则和完整的单元测试。

## 交付文件

### 核心实现

1. **agentos/core/lead/models.py** - 数据模型
   - `ScanWindow`: 扫描时间窗口
   - `LeadFinding`: 风险线索发现（带 fingerprint 幂等去重）
   - `WindowKind`: 窗口类型枚举

2. **agentos/core/lead/miner.py** - 风险规则引擎
   - `MinerConfig`: 可配置的规则阈值
   - `RiskMiner`: 规则引擎主类
   - 6条独立的规则方法

3. **agentos/core/lead/__init__.py** - 模块导出

### 测试文件

4. **tests/unit/lead/test_miner_rules.py** - pytest 单元测试
   - 17个测试用例（每条规则至少2个case）
   - 覆盖触发/不触发两种场景
   - Evidence 完整性验证
   - Fingerprint 幂等性验证

5. **tests/unit/lead/run_tests.py** - 独立测试运行器
   - 不依赖 pytest
   - 可直接运行验证

### 文档

6. **agentos/core/lead/README.md** - 使用文档
   - 规则说明
   - 使用示例
   - 扩展指南

7. **agentos/core/lead/DELIVERY.md** - 本文档

## 6条MVP规则

| 规则代码 | 说明 | 默认阈值 |
|---------|------|---------|
| `blocked_reason_spike` | Finding code 激增检测 | 5次 |
| `pause_block_churn` | PAUSE 后 BLOCK 模式检测 | 2次 PAUSE |
| `retry_recommended_but_fails` | RETRY 后失败检测 | - |
| `decision_lag_anomaly` | 决策延迟 p95 异常 | 5000ms |
| `redline_ratio_increase` | REDLINE 占比上升 | 10% 增幅 |
| `high_risk_allow` | 高危问题被放行 | - |

## 验收标准验证

### ✅ 1. 单元测试覆盖

每条规则都有至少2个测试用例（触发/不触发）：

```bash
$ python3 tests/unit/lead/run_tests.py

============================================================
Test Summary: 17/17 passed
============================================================
```

**测试明细**:
- Rule 1: 2个用例
- Rule 2: 3个用例
- Rule 3: 2个用例
- Rule 4: 3个用例
- Rule 5: 2个用例
- Rule 6: 4个用例
- 集成测试: 1个用例

### ✅ 2. Evidence 完整性

所有 finding 都包含完整的 evidence 数据：

```python
evidence = {
    "count": 6,                          # 数量
    "finding_code": "REDLINE_001",       # 关键维度
    "sample_decision_ids": ["dec_0", ... ]  # 样例（最多5个）
}
```

验证代码见 `test_evidence_completeness()` 测试用例。

### ✅ 3. 阈值可配置

所有规则阈值通过 `MinerConfig` 配置：

```python
config = MinerConfig(
    spike_threshold=5,
    pause_count_threshold=2,
    decision_lag_p95_ms=5000.0,
    redline_ratio_increase=0.10,
    redline_baseline_ratio=0.05
)
```

### ✅ 4. 使用 Mock 数据

测试完全使用 mock storage_data，不依赖真实 storage：

```python
storage_data = {
    "findings": [...],      # Mock findings
    "decisions": [...],     # Mock decisions
    "metrics": {...}        # Mock metrics
}
```

### ✅ 5. 规则独立实现

每条规则都是独立的方法，易于测试和扩展：

```python
def _rule_blocked_reason_spike(self, storage_data, window) -> List[LeadFinding]:
    ...

def _rule_pause_block_churn(self, storage_data, window) -> List[LeadFinding]:
    ...
```

### ✅ 6. Fingerprint 幂等性

相同风险模式在同一窗口内只产生一个 finding：

```python
fingerprint = SHA256(rule_code + window + dimensions)[:16]
```

验证代码见 `TestFingerprintIdempotency` 测试类。

## 快速验证

### 方式1: 运行测试套件

```bash
python3 tests/unit/lead/run_tests.py
```

预期输出：
```
============================================================
Running Lead Agent Miner Rules Tests
============================================================

Rule 1: blocked_reason_spike
  ✓ 触发条件满足
  ✓ 触发条件不满足

...（省略）

============================================================
Test Summary: 17/17 passed
============================================================
```

### 方式2: 交互式验证

```bash
python3 -c "
import sys
sys.path.insert(0, '.')

from agentos.core.lead.miner import RiskMiner, MinerConfig
from agentos.core.lead.models import ScanWindow, WindowKind
from datetime import datetime, timezone, timedelta

miner = RiskMiner()
now = datetime.now(timezone.utc)
window = ScanWindow(
    kind=WindowKind.HOUR_24,
    start_ts=(now - timedelta(hours=24)).isoformat(),
    end_ts=now.isoformat()
)

# 测试数据
storage_data = {
    'findings': [
        {'code': 'RL', 'kind': 'REDLINE', 'severity': 'HIGH', 'decision_id': f'd_{i}'}
        for i in range(6)
    ],
    'decisions': [],
    'metrics': {}
}

findings = miner.mine_risks(storage_data, window)
print(f'Found {len(findings)} risk findings:')
for f in findings:
    print(f'  - [{f.severity}] {f.title}')
    print(f'    Evidence: {f.evidence}')
"
```

## 接口契约

### 输入接口（冻结）

```python
storage_data: Dict[str, Any] = {
    "findings": List[Dict],      # Finding 列表
    "decisions": List[Dict],     # Decision 列表
    "metrics": Dict[str, Any]    # 性能指标
}

window: ScanWindow               # 扫描窗口
```

### 输出接口（冻结）

```python
List[LeadFinding]                # 风险发现列表

# LeadFinding 结构
{
    "finding_id": str,           # 唯一 ID
    "fingerprint": str,          # 幂等指纹
    "rule_code": str,            # 规则代码
    "severity": str,             # 严重程度
    "title": str,                # 标题
    "description": str,          # 详细描述
    "evidence": Dict[str, Any],  # 证据数据
    "window": ScanWindow,        # 扫描窗口
    "detected_at": str           # 检测时间
}
```

## 依赖关系

- **无外部依赖**: 只依赖 Python 标准库
- **类型提示**: 使用 Python 3.13+ 类型注解
- **测试独立**: 测试不依赖 pytest（提供独立运行器）

## 下一步工作

当前实现满足 L2 层（Risk Miner）的所有要求，后续可以对接：

1. **L3: Storage Adapter** - 实现从 Supervisor 审计表查询数据
2. **L4: Dedupe Store** - 实现 lead_findings 表和去重逻辑
3. **L5: Follow-up Task Creator** - 基于 findings 创建后续任务

## 质量保证

- ✅ 代码风格：遵循 PEP 8
- ✅ 类型提示：完整的类型注解
- ✅ 文档字符串：所有公开接口都有 docstring
- ✅ 测试覆盖：17个测试用例，100% 规则覆盖
- ✅ 边界测试：包含边界条件和异常情况
- ✅ Evidence 质量：所有 finding 都有完整的 evidence

## 交付确认

- [x] 6条规则全部实现
- [x] 每条规则至少2个测试用例
- [x] 所有测试通过（17/17）
- [x] Evidence 包含 count 和 samples
- [x] 阈值可配置
- [x] 使用 mock 数据测试
- [x] Fingerprint 幂等性实现
- [x] 完整的使用文档

---

**交付日期**: 2026-01-28
**版本**: v1.0.0 (MVP)
