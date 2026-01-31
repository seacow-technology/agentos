# CommunicationOS Module

CommunicationOS 是 AgentOS 的外部通信模块，提供安全、可审计的外部网络交互能力。

## 目录结构

```
agentos/core/communication/
├── __init__.py              # 模块入口，导出主要接口
├── models.py                # 数据模型定义
├── policy.py                # 安全策略引擎
├── service.py               # 主服务协调器
├── sanitizers.py            # 输入/输出净化器
├── evidence.py              # 审计证据日志
├── rate_limit.py            # 速率限制器
├── connectors/              # 连接器实现
│   ├── __init__.py
│   ├── base.py              # 连接器基类
│   ├── web_search.py        # Web 搜索连接器
│   ├── web_fetch.py         # Web 获取连接器
│   ├── rss.py               # RSS 订阅连接器
│   ├── email_smtp.py        # 邮件发送连接器
│   └── slack.py             # Slack 消息连接器
├── storage/                 # 存储后端
│   ├── __init__.py
│   └── sqlite_store.py      # SQLite 审计存储
└── tests/                   # 测试套件
    ├── __init__.py
    ├── test_policy.py           # 策略引擎测试
    ├── test_ssrf_block.py       # SSRF 防护测试
    ├── test_audit_log.py        # 审计日志测试
    └── test_injection_firewall.py  # 注入防护测试
```

## 核心组件

### 1. 数据模型 (models.py)
- `CommunicationRequest`: 通信请求模型
- `CommunicationResponse`: 通信响应模型
- `CommunicationPolicy`: 安全策略模型
- `EvidenceRecord`: 审计证据记录
- `ConnectorType`: 连接器类型枚举
- `RequestStatus`: 请求状态枚举
- `RiskLevel`: 风险级别枚举

### 2. 策略引擎 (policy.py)
- `PolicyEngine`: 安全策略评估引擎
  - 域名过滤
  - 操作验证
  - SSRF 防护
  - 风险评估
  - 参数验证

### 3. 通信服务 (service.py)
- `CommunicationService`: 主服务协调器
  - 注册和管理连接器
  - 执行通信操作
  - 强制执行安全策略
  - 速率限制
  - 审计日志

### 4. 净化器 (sanitizers.py)
- `InputSanitizer`: 输入净化器
  - SQL 注入防护
  - 命令注入防护
  - XSS 防护
  - 邮件和 URL 验证
- `OutputSanitizer`: 输出净化器
  - 敏感数据脱敏
  - 大输出截断
  - 字段过滤

### 5. 审计证据 (evidence.py)
- `EvidenceLogger`: 证据日志记录器
  - 记录所有通信操作
  - 可搜索的审计追踪
  - 统计和报告
  - 证据导出

### 6. 速率限制 (rate_limit.py)
- `RateLimiter`: 滑动窗口速率限制器
  - 按连接器类型限制
  - 全局限制
  - 使用统计

### 7. 连接器 (connectors/)
所有连接器继承自 `BaseConnector` 并实现：
- `execute()`: 执行操作
- `get_supported_operations()`: 获取支持的操作
- `validate_config()`: 验证配置

已实现的连接器：
- `WebSearchConnector`: Web 搜索
- `WebFetchConnector`: Web 内容获取
- `RSSConnector`: RSS/Atom 订阅
- `EmailSMTPConnector`: SMTP 邮件发送
- `SlackConnector`: Slack 消息和文件共享

### 8. 存储 (storage/)
- `SQLiteStore`: SQLite 审计存储
  - 证据记录持久化
  - 高效查询
  - 统计聚合

## 使用示例

```python
from agentos.core.communication import (
    CommunicationService,
    ConnectorType,
)
from agentos.core.communication.connectors import WebSearchConnector

# 初始化服务
service = CommunicationService()

# 注册连接器
web_search = WebSearchConnector()
service.register_connector(ConnectorType.WEB_SEARCH, web_search)

# 执行搜索
response = await service.execute(
    connector_type=ConnectorType.WEB_SEARCH,
    operation="search",
    params={"query": "Python programming"},
    context={"task_id": "task-123"},
)

print(f"Status: {response.status}")
print(f"Evidence ID: {response.evidence_id}")
```

## 安全特性

1. **SSRF 防护**: 阻止对内部网络的请求
2. **注入防护**: SQL、命令和脚本注入检测
3. **输入验证**: 严格的参数验证
4. **输出脱敏**: 自动脱敏敏感信息
5. **速率限制**: 防止滥用
6. **审计日志**: 完整的操作追踪
7. **策略执行**: 灵活的安全策略

## 测试

运行测试套件：

```bash
pytest agentos/core/communication/tests/
```

测试覆盖：
- 策略评估和风险评估
- SSRF 防护（包括各种绕过尝试）
- 注入防护（SQL、命令、XSS）
- 审计日志和证据追踪
- 连接器功能

## 统计

- **总文件数**: 21 个 Python 文件
- **总代码行数**: 约 3600 行
- **测试文件数**: 4 个测试套件
- **连接器数量**: 5 个连接器实现

## 下一步

这是骨架实现，需要完成以下工作：
1. 实现连接器的实际 HTTP/API 调用
2. 完善测试套件
3. 添加 REST API 端点
4. 添加 WebUI 控制面板
5. 编写 ADR 和详细文档
6. 集成测试和验收

## 许可证

参见 AgentOS 主项目许可证。
