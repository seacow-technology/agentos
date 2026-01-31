# BrainOS Navigation System (P3-A)

## 概述

**第三次认知跃迁：从"看到地形"到"在地形中行动"**

BrainOS Navigation System 提供在认知地形中进行可信导航的能力。不是最短路径算法，而是"在不完整理解中的保守推进策略"。

### 核心能力

1. **Zone Detection（区域检测）**：判断当前所在认知区域
   - `CORE`：核心区 - 多源覆盖、高证据密度、低盲区
   - `EDGE`：边缘区 - 单源覆盖、中等证据密度、中等盲区
   - `NEAR_BLIND`：近盲区 - 零源或单源、低证据密度、高盲区

2. **Path Finding（路径查找）**：查找证据加权的推荐路径
   - 使用 Dijkstra 算法，边权重 = 1 / (evidence_count + 1)
   - 额外惩罚：盲区节点 +5，零覆盖节点 +10

3. **Risk Assessment（风险评估）**：评估路径风险和置信度
   - `confidence`：0-1，路径可信度
   - `risk_level`：LOW/MEDIUM/HIGH
   - `coverage_sources`：路径覆盖的来源（git/doc/code）

### 三条红线（验收 Gate）

#### 🔴 Red Line 1: 禁止认知瞬移

**禁止**：从 A 节点直接跳到一个没有证据路径的节点

**必须**：所有导航必须沿已有证据边移动

**验证**：任意推荐路径，验证每一跳都有 evidence_count >= 1 的边

#### 🔴 Red Line 2: 禁止时间抹平

**禁止**：只展示"当前最好看的那一版图"，隐藏理解退化

**必须**：明确标注理解变化（🟢 新增、🟡 弱化、🔴 消失）

**注意**：这条红线主要在 P3-B（Compare）验证，P3-A 预留数据接口

#### 🔴 Red Line 3: 禁止推荐掩盖风险

**禁止**：给用户"最短/最直接"路径，却隐藏盲区

**必须**：每一条"推荐路径"必须带：
- `confidence`：置信度（0-1）
- `risk_level`：风险级别（LOW/MEDIUM/HIGH）
- `sources`：覆盖来源（["git", "doc", "code"]）

---

## 快速开始

### 基本使用

```python
from agentos.core.brain.store import SQLiteStore
from agentos.core.brain.navigation import navigate

# 连接数据库
store = SQLiteStore("./brainos.db")
store.connect()

# 探索模式：从起点探索可达节点
result = navigate(store, seed="file:manager.py")

# 目标模式：从起点到终点的路径
result = navigate(
    store,
    seed="file:manager.py",
    goal="file:executor.py",
    max_hops=3
)

# 输出结果
print(f"Current Zone: {result.current_zone.value}")
print(f"Zone Description: {result.current_zone_description}")

for path in result.paths:
    print(f"\nPath Type: {path.path_type.value}")
    print(f"Confidence: {path.confidence:.2f}")
    print(f"Risk Level: {path.risk_level.value}")
    print(f"Recommendation: {path.recommendation_reason}")

    for node in path.nodes:
        print(f"  -> {node.entity_name} (zone: {node.zone.value})")

store.close()
```

### Zone Detection（区域检测）

```python
from agentos.core.brain.navigation import detect_zone, compute_zone_metrics

# 检测实体所在区域
zone = detect_zone(store, entity_id="entity_123")
print(f"Zone: {zone.value}")

# 获取详细指标
metrics = compute_zone_metrics(store, entity_id="entity_123")
print(f"Evidence Count: {metrics.evidence_count}")
print(f"Coverage Ratio: {metrics.coverage_ratio:.2f}")
print(f"Zone Score: {metrics.zone_score:.2f}")
```

---

## 架构设计

### 模块结构

```
navigation/
├── __init__.py           # 公共接口
├── models.py             # 数据模型
├── zone_detector.py      # 区域检测
├── path_engine.py        # 路径搜索引擎
├── risk_model.py         # 风险评估
└── navigator.py          # 主入口
```

### 数据模型

#### NavigationResult

```python
@dataclass
class NavigationResult:
    seed_entity: str                    # 起点实体
    goal_entity: Optional[str]          # 终点实体（可选）
    current_zone: CognitiveZone         # 当前区域
    current_zone_description: str       # 区域描述
    paths: List[Path]                   # 推荐路径（最多 3 条）
    no_path_reason: Optional[str]       # 无路可达原因
    computed_at: str                    # 计算时间
    graph_version: str                  # 图版本
```

#### Path

```python
@dataclass
class Path:
    path_id: str                        # 路径 ID
    path_type: PathType                 # 路径类型（SAFE/INFORMATIVE/CONSERVATIVE）
    nodes: List[PathNode]               # 路径节点
    confidence: float                   # 置信度（0-1）
    risk_level: RiskLevel               # 风险等级
    total_hops: int                     # 跳数
    total_evidence: int                 # 总证据数
    coverage_sources: List[str]         # 覆盖来源
    blind_spot_count: int               # 盲区节点数
    recommendation_reason: str          # 推荐理由
```

#### PathNode

```python
@dataclass
class PathNode:
    entity_id: str                      # 实体 ID
    entity_type: str                    # 实体类型
    entity_name: str                    # 实体名称
    edge_id: Optional[str]              # 边 ID
    edge_type: Optional[str]            # 边类型
    evidence_count: int                 # 证据数
    zone: CognitiveZone                 # 所在区域
    is_blind_spot: bool                 # 是否为盲区
    coverage_sources: List[str]         # 覆盖来源
```

---

## 核心算法

### 区域判断算法

```python
def detect_zone(entity_id) -> CognitiveZone:
    metrics = compute_zone_metrics(entity_id)

    # CORE: coverage_ratio >= 0.66 AND zone_score >= 0.6 AND NOT blind_spot
    if is_core_zone(metrics):
        return CognitiveZone.CORE

    # NEAR_BLIND: coverage_ratio <= 0.33 OR blind_spot_severity >= 0.5
    elif is_near_blind_zone(metrics):
        return CognitiveZone.NEAR_BLIND

    # EDGE: 其他情况
    else:
        return CognitiveZone.EDGE
```

**Zone Score 计算公式**：

```python
zone_score = (
    0.4 * coverage_ratio +          # 覆盖来源多样性
    0.3 * evidence_density +        # 证据密度
    0.2 * (1 if not blind_spot else 0) +  # 盲区惩罚
    0.1 * centrality                # 拓扑中心性
)
```

### 路径搜索算法

使用 **Dijkstra 算法**，边权重计算：

```python
def compute_edge_weight(edge_data, target_entity_id) -> float:
    evidence_count = edge_data['evidence_count']

    # 证据越多，权重越小（越"近"）
    base_weight = 1.0 / (evidence_count + 1)

    # 检查目标节点是否为盲区
    blind_spot_penalty = 5.0 if is_blind_spot(target_entity_id) else 0.0

    return base_weight + blind_spot_penalty
```

### 路径分类算法

返回 3 种类型的路径：

1. **SAFE（最安全）**：`blind_spot_count = 0`，优先高证据
2. **INFORMATIVE（最信息增量）**：`coverage_diversity > 0.5`，探索新区域
3. **CONSERVATIVE（最保守）**：避开所有 NEAR_BLIND 区域

### 风险评估算法

**置信度计算**：

```python
confidence = evidence_weight / (evidence_weight + blind_spot_penalty + hop_penalty + 1)

# 额外惩罚
if blind_spot_count > 0:
    confidence = min(confidence, 0.7)
if total_hops > 5:
    confidence = min(confidence, 0.6)
```

**风险等级判断**：

```python
if blind_spot_count == 0 and len(coverage_sources) >= 2:
    return RiskLevel.LOW
elif blind_spot_count >= 2 or len(coverage_sources) == 0:
    return RiskLevel.HIGH
else:
    return RiskLevel.MEDIUM
```

---

## API 参考

### navigate()

```python
def navigate(
    store: SQLiteStore,
    seed: str,
    goal: Optional[str] = None,
    max_hops: int = 3,
    max_paths: int = 3
) -> NavigationResult:
    """
    主导航接口

    Args:
        store: BrainOS 数据库
        seed: 起点实体（格式: "file:xxx" or entity_id）
        goal: 终点实体（可选，None = 探索模式）
        max_hops: 最大跳数（默认 3）
        max_paths: 最多返回路径数（默认 3）

    Returns:
        NavigationResult: 导航结果
    """
```

### detect_zone()

```python
def detect_zone(
    store: SQLiteStore,
    entity_id: str
) -> CognitiveZone:
    """
    判断实体所在的认知区域

    Args:
        store: BrainOS 数据库
        entity_id: 实体 ID

    Returns:
        CognitiveZone (CORE/EDGE/NEAR_BLIND)
    """
```

### compute_zone_metrics()

```python
def compute_zone_metrics(
    store: SQLiteStore,
    entity_id: str
) -> ZoneMetrics:
    """
    计算区域指标

    Args:
        store: BrainOS 数据库
        entity_id: 实体 ID

    Returns:
        ZoneMetrics: 区域指标对象
    """
```

---

## 测试覆盖

### 单元测试（19 个）

- `test_zone_detector.py`（7 个测试）
  - ✅ infer_sources - 来源推断
  - ✅ is_core_zone - 核心区判断
  - ✅ is_near_blind_zone - 近盲区判断
  - ✅ get_zone_description - 描述生成
  - ✅ compute_zone_metrics - 指标计算
  - ✅ detect_zone - 区域检测
  - ✅ zone_metrics_to_dict - 序列化

- `test_path_engine.py`（12 个测试）
  - ✅ resolve_entity_id_by_id - ID 解析
  - ✅ resolve_entity_id_by_seed - Seed 解析
  - ✅ resolve_entity_id_not_found - 实体不存在
  - ✅ resolve_entity_id_invalid_format - 无效格式
  - ✅ build_graph - 图构建
  - ✅ compute_edge_weight - 边权重计算
  - ✅ explore_paths - 探索模式
  - ✅ dijkstra_paths - Dijkstra 算法
  - ✅ build_path_object - 路径对象构建
  - ✅ categorize_paths - 路径分类
  - ✅ find_paths_goal_mode - 目标模式
  - ✅ find_paths_explore_mode - 探索模式

### 集成测试（11 个）

- `test_navigation_e2e.py`（11 个测试）
  - ✅ scenario_1_explore_mode - 探索模式
  - ✅ scenario_2_goal_mode - 目标模式
  - ✅ scenario_3_no_path_found - 无路可达
  - ✅ red_line_1_no_cognitive_teleportation - 红线 1 验证
  - ✅ red_line_3_no_risk_hiding - 红线 3 验证
  - ✅ path_diversity - 路径多样性
  - ✅ zone_detection_accuracy - 区域检测准确性
  - ✅ serialization - 序列化
  - ✅ performance_under_500ms - 性能测试
  - ✅ red_line_1_enforcement - 红线 1 强制验证
  - ✅ red_line_3_blind_spot_risk_marking - 盲区风险标记

**测试覆盖率**：30 个测试，100% 通过率

---

## 性能指标

### 性能目标

- ✅ 导航查询 < 500ms（单次查询）
- ✅ 图构建 < 100ms（小型图 < 100 节点）
- ✅ 区域检测 < 50ms（单个实体）

### 实际性能

测试环境：MacOS, Apple Silicon, 1000+ 节点图

| 操作 | 平均耗时 | 最大耗时 |
|------|----------|----------|
| navigate (explore) | 120ms | 180ms |
| navigate (goal) | 150ms | 220ms |
| detect_zone | 15ms | 30ms |
| compute_zone_metrics | 25ms | 45ms |

---

## 使用场景

### Scenario 1: 代码导航

**需求**：从 `manager.py` 探索相关模块

```python
result = navigate(store, seed="file:manager.py", max_hops=2)

for path in result.paths:
    print(f"发现模块：{path.nodes[-1].entity_name}")
    print(f"置信度：{path.confidence:.0%}")
    print(f"风险：{path.risk_level.value}")
```

### Scenario 2: 依赖追踪

**需求**：从 API 到数据库的完整链路

```python
result = navigate(
    store,
    seed="file:api.py",
    goal="file:database.py",
    max_hops=5
)

if result.paths:
    safest_path = result.paths[0]  # SAFE 路径
    print("完整链路：")
    for node in safest_path.nodes:
        print(f"  -> {node.entity_name} ({node.zone.value})")
```

### Scenario 3: 盲区识别

**需求**：检测导航路径中的认知盲区

```python
result = navigate(store, seed="file:core.py", goal="file:legacy.py")

for path in result.paths:
    if path.blind_spot_count > 0:
        print(f"警告：路径包含 {path.blind_spot_count} 个盲区")
        print(f"风险等级：{path.risk_level.value}")

        for node in path.nodes:
            if node.is_blind_spot:
                print(f"  盲区：{node.entity_name}")
```

---

## 限制和假设

### 当前限制

1. **最大跳数限制**：默认 max_hops=3，避免路径爆炸
2. **路径数量限制**：最多返回 3 条推荐路径（SAFE/INFORMATIVE/CONSERVATIVE）
3. **无向图假设**：边被视为无向（双向可达）
4. **证据边过滤**：零证据边自动过滤，不参与导航

### 设计假设

1. **证据必要性**：所有可信路径必须沿证据边移动
2. **盲区可知性**：系统能够识别并标记盲区
3. **静态图**：导航过程中图结构不变
4. **单源覆盖**：一个实体可能只有单一来源覆盖（如仅 git）

---

## 未来计划（P3-B 及后续）

### P3-B: Compare（对比）

- 对比不同版本的认知地形变化
- 标注理解退化（🟡）和消失（🔴）
- 历史路径追溯

### P3-C: Predict（预测）

- 预测导航路径的可信度变化
- 识别潜在的盲区扩散
- 推荐知识补充策略

### P3-D: Optimize（优化）

- 动态路径权重调整
- 多目标路径优化（最短 + 最安全）
- 并行路径搜索

---

## 常见问题

### Q1: 为什么有时找不到路径？

**A**: 可能原因：
1. 起点和终点之间没有证据边连接
2. max_hops 设置过小，无法到达
3. 中间节点全是盲区，系统过滤了高风险路径

**解决方案**：
- 增加 max_hops
- 检查图构建是否完整
- 使用探索模式查看可达节点

### Q2: SAFE 和 CONSERVATIVE 路径有什么区别？

**A**:
- **SAFE**：综合评分最高（考虑证据、覆盖、盲区）
- **CONSERVATIVE**：严格避开所有盲区，即使绕远路

### Q3: 置信度和风险等级如何对应？

**A**: 不完全对应：
- 高置信度（>0.7）通常对应 LOW/MEDIUM 风险
- 低置信度（<0.3）通常对应 HIGH 风险
- 但有例外：高证据 + 盲区 = 中等置信度 + 中等风险

### Q4: 如何判断一个实体是否在核心区？

**A**: 满足以下条件：
- coverage_ratio >= 0.66（至少 2 源）
- zone_score >= 0.6
- NOT blind_spot OR blind_spot_severity < 0.3

---

## 贡献指南

### 报告问题

请在 GitHub Issues 中提交，包含：
1. 问题描述
2. 复现步骤
3. 预期行为 vs 实际行为
4. 环境信息（Python 版本、OS）

### 提交代码

1. Fork 项目
2. 创建特性分支（`git checkout -b feature/P3-X`）
3. 编写测试（单元测试 + 集成测试）
4. 确保所有测试通过（`pytest tests/`）
5. 提交 Pull Request

### 编码规范

- 遵循 PEP 8
- 使用 type hints
- 编写 docstrings（Google 风格）
- 单元测试覆盖率 > 80%

---

## 许可证

MIT License

---

## 联系方式

- 项目主页：https://github.com/your-org/AgentOS
- 文档：https://docs.agentos.dev
- 邮件：dev@agentos.dev

---

## 致谢

感谢以下项目和论文的启发：
- Dijkstra's Algorithm
- Knowledge Graph Navigation
- Cognitive Uncertainty Quantification
