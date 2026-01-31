# /comm search 命令使用示例

本文档展示 `/comm search` 命令的各种使用场景和输出示例。

## 前提条件

1. **Phase Gate**: 只能在 execution 阶段使用
2. **依赖**: 需要安装搜索引擎库（如 `ddgs` 或 `duckduckgo-search`）
3. **网络**: 需要网络连接

## 基本用法

### 1. 简单搜索

**命令**:
```bash
/comm search Python tutorial
```

**输出**:
```markdown
# 搜索结果：Python tutorial

找到 **10** 条结果（显示前 10 条）：

## 1. Official Python Tutorial
- **URL**: https://docs.python.org/3/tutorial/
- **摘要**: The Python Tutorial — Python 3.12.1 documentation
- **Trust Tier**: `search_result` （候选来源，需验证）

## 2. W3Schools Python Tutorial
- **URL**: https://www.w3schools.com/python/
- **摘要**: Learn Python - W3Schools
- **Trust Tier**: `search_result` （候选来源，需验证）

## 3. Real Python Tutorials
- **URL**: https://realpython.com/
- **摘要**: Python Tutorials – Real Python
- **Trust Tier**: `search_result` （候选来源，需验证）

...

---

## ⚠️ 注意

**搜索结果是候选来源，不是验证事实**

建议使用 `/comm fetch <url>` 验证内容。

---

📝 **来源归因**: CommunicationOS (search) in session abc123
🔍 **审计ID**: ev-20260130-001
🔧 **搜索引擎**: duckduckgo
⏰ **检索时间**: 2026-01-30T12:00:00Z
```

### 2. 限制结果数量

**命令**:
```bash
/comm search artificial intelligence news --max-results 5
```

**输出**:
```markdown
# 搜索结果：artificial intelligence news

找到 **5** 条结果（显示前 5 条）：

## 1. MIT Technology Review - AI
- **URL**: https://www.technologyreview.com/artificial-intelligence/
- **摘要**: The latest news and analysis on artificial intelligence
- **Trust Tier**: `search_result` （候选来源，需验证）

## 2. The Verge - AI News
- **URL**: https://www.theverge.com/ai-artificial-intelligence
- **摘要**: AI and machine learning news and analysis
- **Trust Tier**: `search_result` （候选来源，需验证）

...

---

## ⚠️ 注意

**搜索结果是候选来源，不是验证事实**

建议使用 `/comm fetch <url>` 验证内容。

---

📝 **来源归因**: CommunicationOS (search) in session abc123
🔍 **审计ID**: ev-20260130-002
```

### 3. 多词查询

**命令**:
```bash
/comm search how to install docker on ubuntu
```

查询会自动处理为 `"how to install docker on ubuntu"`

## 错误场景

### 1. Planning 阶段调用（被阻止）

**命令** (在 planning 阶段):
```bash
/comm search test query
```

**输出**:
```markdown
🚫 Command blocked: comm.* commands are forbidden in planning phase. External communication is only allowed during execution to prevent information leakage and ensure controlled access.
```

**说明**: Phase Gate 自动阻止，保护系统安全。

### 2. 无效参数

**命令**:
```bash
/comm search test --max-results abc
```

**输出**:
```markdown
Invalid --max-results value: abc
Must be a positive integer
```

### 3. 空查询

**命令**:
```bash
/comm search
```

**输出**:
```markdown
Usage: /comm search <query> [--max-results N]
Example: /comm search latest AI developments
Example: /comm search Python tutorial --max-results 5
```

### 4. 仅有标志，无查询

**命令**:
```bash
/comm search --max-results 5
```

**输出**:
```markdown
No search query provided.
Usage: /comm search <query> [--max-results N]
```

## 网络错误场景

### 1. 速率限制

**输出**:
```markdown
## ⏱️ 超过速率限制

请等待 **60 秒**后重试。
```

### 2. 网络连接失败

**输出**:
```markdown
## ❌ 搜索失败

**错误**: Network connection failed
```

### 3. 搜索引擎库未安装

**输出**:
```markdown
## ❌ 搜索失败

**错误**: DuckDuckGo search library not installed. Install it with: pip install ddgs (recommended) or pip install duckduckgo-search
```

## 典型工作流

### 场景: 研究 Python 最佳实践

```bash
# 1. 搜索相关内容
/comm search Python best practices 2024 --max-results 5

# 输出: 5 条搜索结果

# 2. 选择一个可靠的 URL 进行验证
/comm fetch https://docs.python-guide.org/writing/style/

# 输出: 完整的页面内容，包含 Trust Tier 和引用信息

# 3. 基于验证的内容做决策
# 现在可以安全地使用这些信息，因为已经过 SSRF 防护和内容清洗
```

## Trust Tier 说明

### search_result

- **含义**: 搜索结果是**候选来源**，未经验证
- **风险**: 可能包含过时、错误或误导性信息
- **建议**: 使用 `/comm fetch <url>` 进一步验证

### 升级路径

```
search_result (候选)
    ↓ /comm fetch
external_source (验证)
    ↓ 管理员审核
trusted_source (可信)
```

## 审计追踪

每次搜索都会生成完整的审计记录：

```json
{
  "audit_type": "comm_command",
  "command": "search",
  "args": ["Python", "tutorial", "--max-results", "5"],
  "session_id": "abc123",
  "task_id": "task-001",
  "timestamp": "2026-01-30T12:00:00Z",
  "result": "success",
  "evidence_id": "ev-20260130-001"
}
```

## 性能说明

### 缓存

- CommunicationService 提供 15 分钟自清理缓存
- 重复查询可以快速返回

### 超时

- 默认搜索超时: 30 秒
- 可通过 CommunicationService 配置调整

### 并发

- 支持多个会话并发搜索
- 受 Rate Limiter 约束（防止滥用）

## 与其他命令集成

### /comm fetch

```bash
# 搜索 -> 获取详细内容
/comm search React hooks tutorial
# 从结果中选择 URL
/comm fetch https://react.dev/reference/react/hooks
```

### /comm brief (未来)

```bash
# 搜索 -> 生成综合报告
/comm brief AI developments --today
# 内部会调用 search，然后 fetch，最后聚合
```

## 最佳实践

### 1. 精确查询

❌ **不好**: `/comm search ai`
✅ **好**: `/comm search artificial intelligence applications 2024`

### 2. 合理限制结果

- 探索性搜索: `--max-results 10`（默认）
- 快速查找: `--max-results 3`
- 深入研究: `--max-results 20`

### 3. 验证关键信息

对于重要决策，务必：
1. 使用 `/comm search` 找到候选来源
2. 使用 `/comm fetch` 验证完整内容
3. 检查 Trust Tier 和 Attribution
4. 对比多个来源

### 4. 注意 Phase Gate

只在 execution 阶段使用 `/comm` 命令，planning 阶段专注于规划。

## 故障排除

### 问题: "Command blocked"

**原因**: 在 planning 阶段调用
**解决**: 等待进入 execution 阶段

### 问题: "Rate limited"

**原因**: 短时间内发送过多请求
**解决**: 等待指定时间后重试

### 问题: "搜索引擎库未安装"

**原因**: 缺少依赖库
**解决**:
```bash
pip install ddgs
# 或
pip install duckduckgo-search
```

### 问题: 结果为空

**原因**: 查询过于具体或搜索引擎无结果
**解决**:
- 简化查询
- 使用更通用的关键词
- 检查拼写

## 安全提示

### ⚠️ 重要

1. **不要信任未验证的搜索结果**: 始终检查 Trust Tier
2. **不要基于搜索结果执行危险操作**: 先用 `/comm fetch` 验证
3. **不要忽略 SSRF 警告**: 这是为了保护系统安全
4. **保存审计ID**: 方便后续追溯和问题排查

## 相关命令

- `/comm fetch <url>` - 验证和获取 URL 内容
- `/comm brief <topic>` - 生成综合主题报告（开发中）

## 技术支持

如有问题，请查看：
- 审计日志: 包含完整的请求和响应信息
- 证据追踪: 通过 `audit_id` 查询详细记录
- 错误消息: 提供清晰的故障原因和解决建议
