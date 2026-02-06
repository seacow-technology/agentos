# Mode System - Executor 集成规范

## Mode → Executor 语义映射表 (INTEGRATOR FREEZE)

此表定义了 Executor 如何响应不同 Mode，**不可随意修改**。

| Mode ID | allows_commit() | allows_diff() | Executor 行为 | 用途 |
|---------|----------------|---------------|--------------|------|
| `implementation` | ✅ | ✅ | 允许产生 diff、应用 patch、创建 commit | 代码实施 |
| `design` | ❌ | ❌ | 拒绝所有 diff 操作，抛出 ModeViolationError | 架构设计 |
| `planning` | ❌ | ❌ | 拒绝所有 diff 操作 | 任务规划 |
| `chat` | ❌ | ❌ | 拒绝所有 diff 操作 | 对话交互 |
| `debug` | ❌ | ❌ | 拒绝所有 diff 操作 | 问题诊断 |
| `ops` | ❌ | ❌ | 拒绝所有 diff 操作 | 运维操作 |
| `test` | ❌ | ❌ | 拒绝所有 diff 操作 | 测试验证 |
| `release` | ❌ | ❌ | 拒绝所有 diff 操作 | 发布管理 |

## 关键约束（不可违反）

1. **唯一 diff Mode**: 只有 `implementation` 允许 diff
2. **闸门位置**: `apply_diff_or_raise()` 是唯一检查点
3. **拒绝行为**: 非 implementation mode 必须抛出 `ModeViolationError`
4. **默认值**: 未指定 mode 时默认 `implementation`

## 新增 Mode 检查清单

添加新 Mode 前必须回答：

- [ ] 是否需要产生代码变更？→ 如果 YES，必须重新审视架构
- [ ] 新 Mode 的 `allows_commit()` 返回值是什么？
- [ ] 是否更新了此映射表？
- [ ] 是否添加了对应的 Gate 测试？
- [ ] 是否通过了 `verify_executor_mode_integration.sh`？

## 引用此表

Executor 的行为依据此表，不是文档装饰：
- `executor_engine.py:101` - 读取 mode_id
- `executor_engine.py:575` - 检查 mode.allows_commit()
- `mode.py:38-52` - Mode 权限定义

验收命令：
```bash
grep "allows_commit" agentos/core/executor/executor_engine.py
grep "allows_commit" agentos/core/mode/mode.py
```

## Mode 系统架构

### 核心组件

1. **Mode 定义** (`mode.py`)
   - Mode 类：定义 mode 的属性和行为
   - `_BUILTIN_MODES`：内置 mode 注册表
   - `get_mode(mode_id)`：获取 mode 实例

2. **Executor 集成** (`executor_engine.py`)
   - `execute()`：唯一 mode 入口点（第 101 行）
   - `apply_diff_or_raise()`：唯一 diff 闸门（第 559 行）

3. **Gate 验证** (`scripts/gates/`)
   - GM1：非 implementation mode 拒绝 diff
   - GM2：implementation mode 必须要求 diff
   - 其他专项 mode gate（GMP1、GMD1、GCH1 等）

### Mode 权限检查流程

```
execution_request
    ↓
    └─> mode_id = request.get("mode_id", "implementation")  # 入口
        ↓
        └─> mode = get_mode(mode_id)
            ↓
            └─> self._current_mode_id = mode_id  # 保存
                ↓
                └─> apply_diff_or_raise()
                    ↓
                    └─> if not mode.allows_commit():
                        └─> raise ModeViolationError  # 闸门
```

### 审计日志记录

Mode 系统在 RunTape 中记录以下事件：

1. **mode_resolved** - Mode 解析完成
   - `mode_id`: Mode ID
   - `mode_defaulted`: 是否使用默认值
   - `allows_commit`: 是否允许 commit
   - `allows_diff`: 是否允许 diff

2. **execution_start** - 执行开始
   - `mode`: Mode ID
   - `started_at`: 开始时间

3. **mode_diff_denied** - Mode 拒绝 diff
   - `mode_id`: Mode ID
   - `operation`: 操作类型
   - `reason`: 拒绝原因

4. **diff_policy_scope** - Diff 应用时的 policy 范围
   - `mode_id`: Mode ID
   - `policy_provided`: 是否提供 policy

## INTEGRATOR 完成定义

当且仅当下面这句话成立时，Mode → Executor 集成被认为是"冻结"的：

> **Executor 不知道"设计/规划/运维"是什么，但它永远不可能在 non-implementation mode 下写出 diff；这一事实可以被 1 个脚本 + 5 个 grep 复现。**

验收脚本：`scripts/verify_executor_mode_integration.sh`

## 相关文档

- `MODE_SYSTEM_FINAL_REPORT.md` - Mode 系统终审报告
- `MODE_SYSTEM_NAILED_REPORT.md` - Mode 系统详细报告
- `scripts/verify_mode_system.sh` - Mode 系统验证脚本
