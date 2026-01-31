# Session Core Layer Implementation

## Overview

Task #2 完成：实现了 CommunicationOS 的 Session 核心层，提供消息到会话的路由和持久化存储功能。

## 实现的组件

### 1. SessionRouter (`session_router.py`)

**职责**: 根据 channel 的 scope 配置，将 InboundMessage 路由到正确的 session。

**核心类**:

- `ResolvedContext`: 解析后的路由上下文数据模型
  - 包含 channel_id, user_key, conversation_key
  - 包含 session_scope 和 session_lookup_key
  - 包含 title_hint（消息文本的前 50 个字符）

- `SessionRouter`: 会话路由器
  - `resolve(InboundMessage) -> ResolvedContext`: 解析消息并返回路由上下文
  - `compute_lookup_key(...)`: 计算 session 查找键
  - `parse_lookup_key(...)`: 解析 lookup key 回组件

**Session Scope 支持**:

1. **USER scope**: 一个用户一个 session（跨所有对话）
   - Lookup key 格式: `{channel_id}:{user_key}`
   - 适用场景: WhatsApp, 单用户聊天场景

2. **USER_CONVERSATION scope**: 一个用户-对话对一个 session
   - Lookup key 格式: `{channel_id}:{user_key}:{conversation_key}`
   - 适用场景: Telegram groups, Slack channels

**特性**:
- 确定性路由：相同的输入总是产生相同的路由结果
- Channel-driven: 路由逻辑基于 channel manifest 配置
- 可审计：清晰的映射逻辑便于调试

### 2. SessionStore (`session_store.py`)

**职责**: 持久化存储 session 映射关系和元数据。

**数据库表**:

1. `channel_sessions`: 跟踪每个 channel/user/conversation 的活动 session
   - channel_id, user_key, conversation_key, active_session_id
   - 唯一约束: (channel_id, user_key, conversation_key)

2. `sessions`: 存储 session 元数据
   - session_id (主键)
   - channel_id, user_key, conversation_key, scope
   - title, status, message_count, metadata
   - created_at, updated_at

3. `session_history`: session 操作历史记录
   - session_id, action, details, created_at

**核心方法**:

- `create_session(...)`: 创建新 session 并设为活动
- `get_active_session(...)`: 获取活动 session
- `switch_session(...)`: 切换到不同的 session
- `list_sessions(...)`: 列出用户的所有 sessions（支持状态过滤）
- `update_session(...)`: 更新 session 元数据
- `increment_message_count(...)`: 增加消息计数
- `archive_session(...)`: 归档 session
- `get_session_history(...)`: 获取 session 历史

**特性**:
- SQLite + WAL mode: 支持并发读写
- 审计日志: 所有操作都被记录
- 上下文隔离: USER 和 USER_CONVERSATION scope 正确隔离
- 持久化: 数据跨 store 实例持久化

## 测试覆盖

### SessionRouter 测试 (`test_session_router.py`)
- ✅ 21 个测试全部通过
- 测试覆盖:
  - ResolvedContext 数据模型验证
  - USER scope 路由
  - USER_CONVERSATION scope 路由
  - Lookup key 计算和解析
  - 确定性路由验证
  - 上下文隔离验证
  - 错误处理

### SessionStore 测试 (`test_session_store.py`)
- ✅ 24 个测试全部通过
- 测试覆盖:
  - Session CRUD 操作
  - 活动 session 管理
  - Session 切换
  - 列表和过滤
  - 元数据管理
  - 消息计数
  - Session 历史
  - 上下文隔离（USER vs USER_CONVERSATION）
  - 多用户隔离
  - 数据持久化

### 全部 CommunicationOS 测试
- ✅ 185 个测试全部通过
- 无回归问题

## 集成

新组件已集成到 `agentos/communicationos/__init__.py`:

```python
from agentos.communicationos.session_router import (
    SessionRouter,
    ResolvedContext,
)

from agentos.communicationos.session_store import (
    SessionStore,
    SessionStatus,
)
```

## 使用示例

### 基本使用

```python
from agentos.communicationos import (
    ChannelRegistry,
    SessionRouter,
    SessionStore,
    InboundMessage,
)

# 1. 创建依赖
registry = ChannelRegistry()
router = SessionRouter(registry)
store = SessionStore()

# 2. 处理入站消息
message = InboundMessage(
    channel_id="whatsapp_business",
    user_key="+1234567890",
    conversation_key="+1234567890",
    message_id="msg_001",
    text="Hello, how can I help?"
)

# 3. 解析路由上下文
context = router.resolve(message)
print(f"Session lookup key: {context.session_lookup_key}")
print(f"Session scope: {context.session_scope}")

# 4. 获取或创建 session
active_session = store.get_active_session(
    channel_id=context.channel_id,
    user_key=context.user_key,
    conversation_key=context.conversation_key,
)

if not active_session:
    # 创建新 session
    session_id = store.create_session(
        channel_id=context.channel_id,
        user_key=context.user_key,
        conversation_key=context.conversation_key,
        scope=context.session_scope,
        title=context.title_hint,
    )
else:
    session_id = active_session["session_id"]
    # 增加消息计数
    store.increment_message_count(session_id)

print(f"Routing to session: {session_id}")
```

### Session 管理

```python
# 列出用户的所有 sessions
sessions = store.list_sessions(
    channel_id="whatsapp_business",
    user_key="+1234567890",
)

# 切换到不同的 session
store.switch_session(
    channel_id="whatsapp_business",
    user_key="+1234567890",
    conversation_key="+1234567890",
    new_session_id="cs_abc123",
)

# 更新 session 元数据
store.update_session(
    session_id="cs_abc123",
    title="Customer Support - John Doe",
    metadata={"priority": "high"},
)

# 归档旧 session
store.archive_session("cs_old123")

# 查看 session 历史
history = store.get_session_history("cs_abc123")
```

## 设计原则

1. **关注点分离**: SessionRouter 处理路由逻辑，SessionStore 处理持久化
2. **Channel-driven**: 路由行为由 channel manifest 的 session_scope 决定
3. **确定性**: 相同的输入总是产生相同的结果
4. **可审计**: 所有操作都有日志和历史记录
5. **线程安全**: 使用 SQLite WAL mode 支持并发访问

## 下一步

Task #2 已完成，可以继续实施：
- Task #3: 统一 CommandProcessor（已完成）
- Task #5: WhatsApp Adapter 实现
- Task #6: MessageBus 和通用中间件
- Task #10: 集成测试和验收

## 文件列表

**实现文件**:
- `/Users/pangge/PycharmProjects/AgentOS/agentos/communicationos/session_router.py` (211 行)
- `/Users/pangge/PycharmProjects/AgentOS/agentos/communicationos/session_store.py` (624 行)

**测试文件**:
- `/Users/pangge/PycharmProjects/AgentOS/tests/unit/communicationos/test_session_router.py` (431 行)
- `/Users/pangge/PycharmProjects/AgentOS/tests/unit/communicationos/test_session_store.py` (598 行)

**总计**: ~1,864 行代码和测试
