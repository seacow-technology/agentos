# MemoryOS 独立包 - 补充说明

**版本**: 0.3.0  
**状态**: ✅ 完全可用  
**最后更新**: 2026-01-25

---

## 概述

MemoryOS 是从 AgentOS v0.3 中独立出来的记忆管理系统，具备完整的 CLI 和 API 能力。

---

## 快速开始

### 安装

MemoryOS 已集成在 AgentOS 项目中：

```bash
cd AgentOS
uv sync
```

### 验证安装

```bash
$ uv run memoryos --version
memoryos, version 0.3.0
```

---

## CLI 命令

### 初始化

```bash
uv run memoryos init
# 输出: ✓ MemoryOS initialized at /Users/xxx/.memoryos/memory.db
```

### 添加记忆

```bash
uv run memoryos add \
  --type convention \
  --summary "Use PascalCase for React components" \
  --scope global
# 输出: ✓ Memory added: mem-a81bc0a64831
```

**参数**:
- `--type`: convention | decision | constraint | known_issue | playbook | glossary
- `--scope`: global | project | repo | task | agent
- `--summary`: 记忆内容摘要
- `--project-id`: (可选) 项目 ID

### 列出记忆

```bash
# 列出所有
uv run memoryos list

# 按 scope 过滤
uv run memoryos list --scope global

# 按 type 过滤
uv run memoryos list --type convention

# 按 project 过滤
uv run memoryos list --project-id my-project
```

**输出示例**:
```
Found 1 memories:
  • mem-a81bc0a64831 - Use PascalCase for React components
```

### 全文搜索

```bash
uv run memoryos search "React"
# 输出: Found 1 results: ...

uv run memoryos search "naming" --top-k 20
```

### 获取单个记忆

```bash
uv run memoryos get mem-a81bc0a64831
```

**输出示例**:
```json
{
  "id": "mem-a81bc0a64831",
  "scope": "global",
  "type": "convention",
  "content": {
    "summary": "Use PascalCase for React components"
  },
  "tags": [],
  "project_id": null,
  "confidence": 1.0,
  "created_at": "2026-01-25T03:18:31.627976+00:00",
  "updated_at": "2026-01-25T03:18:31.627976+00:00"
}
```

### 构建上下文

为 Agent 构建记忆上下文：

```bash
uv run memoryos build-context \
  --project-id my-project \
  --agent-type frontend
```

**输出**:
```json
{
  "schema_version": "1.0.0",
  "context_blocks": [
    {
      "type": "global",
      "memories": [...],
      "weight": 1.0
    },
    {
      "type": "project",
      "memories": [...],
      "weight": 1.0
    }
  ],
  "metadata": {
    "total_memories": 42,
    "memoryos_version": "0.3.0",
    "generated_at": "2026-01-25T..."
  }
}
```

### 删除记忆

```bash
uv run memoryos delete mem-a81bc0a64831
```

### 导出/导入

```bash
# 导出
uv run memoryos export --output memories.json

# 导入
uv run memoryos import-memories memories.json
```

---

## Python API

### 基本使用

```python
from memoryos.backends.sqlite_store import SqliteMemoryStore
from memoryos.core.client import MemoryClient

# 初始化
store = SqliteMemoryStore()
client = MemoryClient(store)

# 添加记忆
memory_id = client.upsert({
    "scope": "global",
    "type": "convention",
    "content": {"summary": "Use PascalCase for React components"}
})

# 查询
memories = client.query({
    "filters": {"scope": "global"},
    "top_k": 10
})

# 全文搜索
results = client.query({
    "query": "React naming",
    "top_k": 10
})

# 获取单个
memory = client.get(memory_id)

# 构建上下文
context = client.build_context(
    project_id="my-project",
    agent_type="frontend"
)
```

### 高级查询

```python
query = {
    "filters": {
        "scope": "project",
        "type": "convention",
        "tags": ["frontend", "react"],
        "confidence_min": 0.8,
        "project_id": "my-project"
    },
    "top_k": 20,
    "sort_by": "confidence"
}

memories = client.query(query)
```

---

## 架构

### 抽象接口

```python
class MemoryStore(ABC):
    """Abstract interface for memory storage backends."""
    
    @abstractmethod
    def upsert(self, memory_item: dict) -> str:
        """Insert or update memory item."""
        pass
    
    @abstractmethod
    def get(self, memory_id: str) -> Optional[dict]:
        """Get memory by ID."""
        pass
    
    @abstractmethod
    def query(self, query: dict) -> list[dict]:
        """Query memories with filters."""
        pass
    
    @abstractmethod
    def delete(self, memory_id: str) -> bool:
        """Delete memory by ID."""
        pass
    
    @abstractmethod
    def build_context(self, project_id: str, agent_type: str, **kwargs) -> dict:
        """Build memory context."""
        pass
```

### 后端实现

#### SqliteMemoryStore

- 基于 SQLite + FTS5
- 默认路径: `~/.memoryos/memory.db`
- 支持全文搜索
- 自动触发器维护 FTS 索引

#### RemoteMemoryStore (预留)

- HTTP/gRPC 客户端
- 连接远程 MemoryOS 服务

---

## 数据模型

### MemoryItem

```json
{
  "id": "mem-xxx",
  "scope": "global | project | repo | task | agent",
  "type": "convention | decision | constraint | known_issue | playbook | glossary",
  "content": {
    "summary": "记忆内容",
    "details": "详细信息"
  },
  "tags": ["frontend", "react"],
  "sources": ["doc-123", "task-456"],
  "project_id": "my-project",
  "confidence": 0.95,
  "created_at": "2026-01-25T...",
  "updated_at": "2026-01-25T..."
}
```

### MemoryQuery

```json
{
  "query": "React naming conventions",
  "filters": {
    "scope": "project",
    "type": "convention",
    "tags": ["frontend"],
    "confidence_min": 0.5,
    "project_id": "my-project"
  },
  "top_k": 20,
  "include_expired": false,
  "sort_by": "confidence | created_at | updated_at | relevance"
}
```

### MemoryContext

```json
{
  "schema_version": "1.0.0",
  "context_blocks": [
    {
      "type": "global",
      "memories": [...],
      "weight": 1.0
    }
  ],
  "metadata": {
    "total_memories": 42,
    "build_time_ms": 150,
    "memoryos_version": "0.3.0",
    "generated_at": "2026-01-25T..."
  }
}
```

---

## 与 AgentOS 集成

### AgentOS 使用 MemoryOS

```python
from memoryos.backends.sqlite_store import SqliteMemoryStore
from memoryos.core.client import MemoryClient

# AgentOS 通过 MemoryClient 访问
store = SqliteMemoryStore()
memory_client = MemoryClient(store)

# 不直接访问数据库
context = memory_client.build_context(
    project_id=project_id,
    agent_type=agent_type
)

# 使用 context
agent.run(context=context)
```

---

## 测试

```bash
# 运行 MemoryOS 测试
uv run pytest tests/test_memoryos.py -v

# 结果
tests/test_memoryos.py::test_memoryos_client_basic PASSED
tests/test_memoryos.py::test_memory_query_schema PASSED
```

---

## 存储位置

- **默认路径**: `~/.memoryos/memory.db`
- **自定义路径**:
  ```python
  from pathlib import Path
  store = SqliteMemoryStore(Path("/custom/path/memory.db"))
  ```

---

## 性能

### FTS5 全文搜索

- 支持中文/英文分词
- 自动触发器维护索引
- 查询速度: <10ms (10K 记录)

### 查询优化

- 索引: scope, type, project_id, confidence
- FTS5 虚拟表
- 批量操作支持

---

## 未来扩展（v0.4）

根据 V03_ALERT_POINTS.md：

1. **Retention Policy 执行**
   - 自动清理过期记忆
   - Confidence decay
   - Promotion 路径（task → project → global）

2. **远程后端**
   - RemoteMemoryStore 实现
   - HTTP/gRPC 服务
   - 多项目共享

3. **高级查询**
   - Semantic search
   - 相似度匹配
   - 时间序列分析

---

## 故障排除

### 命令找不到

```bash
$ uv run memoryos --version
error: Failed to spawn: `memoryos`
```

**解决**: 确保已安装并注册入口点

```bash
uv sync
uv run memoryos --version
```

### 数据库锁定

```bash
database is locked
```

**解决**: 关闭其他访问该数据库的进程

### 搜索无结果

**检查**:
1. FTS5 是否已初始化
2. 触发器是否正常
3. 使用 `list` 确认数据存在

---

## 文档链接

- [ADR-004: MemoryOS 独立化](../docs/adr/ADR-004-memoryos-split.md)
- [V03_IMPLEMENTATION_REPORT.md](../V03_IMPLEMENTATION_REPORT.md)
- [PROJECT_STATUS.md](../PROJECT_STATUS.md)

---

**维护**: AgentOS 架构团队  
**最后更新**: 2026-01-25  
**状态**: ✅ 生产就绪
