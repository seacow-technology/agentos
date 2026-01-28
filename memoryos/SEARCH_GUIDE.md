# MemoryOS 搜索使用指南

## 快速开始

### 添加记忆

```bash
# 添加全局记忆
uv run memoryos add \
  --type convention \
  --scope global \
  --summary "Use PascalCase for React components"

# 添加项目记忆
uv run memoryos add \
  --type convention \
  --scope project \
  --summary "API endpoints use RESTful naming" \
  --project-id myproject
```

### 搜索记忆

```bash
# 基本搜索（完整词匹配）
uv run memoryos search --query "PascalCase"

# 带项目过滤
uv run memoryos search --query "RESTful" --project-id myproject

# 带多重过滤
uv run memoryos search \
  --query "naming" \
  --scope project \
  --type convention \
  --project-id myproject

# 限制结果数
uv run memoryos search --query "React" --top-k 5
```

## FTS5 搜索说明

MemoryOS 使用 SQLite FTS5 进行全文搜索。

### 完整词匹配

FTS5 默认进行**完整词匹配**，不支持部分匹配：

```bash
# ✅ 可以找到 "Use PascalCase for React"
uv run memoryos search --query "PascalCase"

# ✅ 可以找到（多词匹配）
uv run memoryos search --query "PascalCase React"

# ❌ 找不到（部分词）
uv run memoryos search --query "Pascal"
```

### 前缀匹配

使用通配符 `*` 进行前缀匹配：

```bash
# ✅ 使用前缀
uv run memoryos search --query "Pascal*"

# ✅ 匹配任意开头
uv run memoryos search --query "*Case"
```

### 布尔操作符

```bash
# AND（默认）
uv run memoryos search --query "React components"

# OR
uv run memoryos search --query "React OR Vue"

# NOT
uv run memoryos search --query "React NOT class"

# 组合
uv run memoryos search --query "(React OR Vue) components"
```

### 短语搜索

使用引号进行精确短语匹配：

```bash
uv run memoryos search --query '"React components"'
```

## 过滤选项

### --scope

按作用域过滤：

```bash
uv run memoryos search --query "naming" --scope global
uv run memoryos search --query "naming" --scope project
uv run memoryos search --query "naming" --scope task
```

### --type

按类型过滤：

```bash
uv run memoryos search --query "React" --type convention
uv run memoryos search --query "React" --type decision
uv run memoryos search --query "React" --type constraint
```

### --project-id

按项目过滤：

```bash
uv run memoryos search --query "API" --project-id frontend
uv run memoryos search --query "API" --project-id backend
```

### 组合过滤

```bash
uv run memoryos search \
  --query "naming*" \
  --scope project \
  --type convention \
  --project-id myproject \
  --top-k 20
```

## 列出记忆

不使用搜索，只过滤：

```bash
# 列出所有
uv run memoryos list

# 按项目列出
uv run memoryos list --project-id myproject

# 按类型和作用域列出
uv run memoryos list --type convention --scope global
```

## 常见用例

### 1. 查找项目约定

```bash
uv run memoryos search \
  --query "convention" \
  --type convention \
  --project-id myproject
```

### 2. 查找所有 React 相关

```bash
uv run memoryos search --query "React"
```

### 3. 查找命名规范

```bash
uv run memoryos search --query "naming OR name OR Case"
```

### 4. 查找特定技术栈

```bash
# 前端
uv run memoryos search --query "(React OR Vue OR Angular) components"

# 后端
uv run memoryos search --query "(API OR REST OR GraphQL)"
```

## 故障排除

### 搜索无结果

**问题**: 搜索关键词找不到已存在的记忆

**解决**:
1. 检查是否使用完整词
   ```bash
   # 错误
   uv run memoryos search --query "Pascal"
   
   # 正确
   uv run memoryos search --query "PascalCase"
   ```

2. 使用通配符
   ```bash
   uv run memoryos search --query "Pascal*"
   ```

3. 检查过滤条件
   ```bash
   # 移除过滤重试
   uv run memoryos search --query "PascalCase"
   ```

4. 查看所有记忆确认存在
   ```bash
   uv run memoryos list
   ```

### 搜索太慢

**问题**: 搜索耗时长

**解决**: 
- 添加过滤减少范围
- 降低 `--top-k` 值
- 检查数据库大小

### FTS 索引损坏

**问题**: 搜索结果不一致

**解决**:
```bash
# 备份数据
uv run memoryos export --output backup.json

# 重新初始化
rm ~/.memoryos/memory.db
uv run memoryos init

# 恢复数据
uv run memoryos import-memories backup.json
```

## 最佳实践

### 1. 使用描述性摘要

```bash
# ❌ 太简短
uv run memoryos add --summary "PascalCase"

# ✅ 有上下文
uv run memoryos add --summary "Use PascalCase for React component names"
```

### 2. 合理使用 tags

```bash
uv run memoryos add \
  --summary "API endpoints use RESTful naming" \
  --tags "api,naming,rest,backend"
```

### 3. 指定 project-id

```bash
# 为每个项目的记忆指定 project-id
uv run memoryos add \
  --summary "..." \
  --project-id myproject \
  --scope project
```

### 4. 使用准确的 type

```bash
# convention - 编码约定
uv run memoryos add --type convention --summary "..."

# decision - 架构决策
uv run memoryos add --type decision --summary "..."

# constraint - 技术约束
uv run memoryos add --type constraint --summary "..."
```

## 性能提示

- FTS5 索引自动维护，无需手动重建
- 搜索速度: <10ms (10K 记忆)
- 使用过滤可大幅提升大数据集性能
- 定期清理过期记忆

---

**相关文档**:
- [MemoryOS README](README.md)
- [SQLite FTS5 文档](https://www.sqlite.org/fts5.html)
