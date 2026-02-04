# WebUI v1 到 v2 迁移指南

## 概述

`agentos/webui` (v1) 已于 2026-02-05 正式废弃，请尽快迁移到 `webui-v2`。

## 快速迁移

### 1. 停止使用旧的 CLI 命令

**旧方式 (已废弃)**:
```bash
agentos web --port 8080
agentos webui start
```

**新方式 (推荐)**:
```bash
cd webui-v2
npm install
npm run dev
```

### 2. 更新导入语句

如果你的代码中有引用 `agentos.webui` 的地方：

**旧代码**:
```python
from agentos.webui import something
from agentos.webui.api import some_endpoint
```

**新代码**:
webui-v2 是独立的前端应用，不再需要 Python 导入。
后端 API 已经整合到核心 AgentOS 中。

### 3. API 端点变更

大部分 API 端点保持向后兼容，但有一些改进：

| v1 路径 | v2 路径 | 状态 |
|---------|---------|------|
| `/api/chat` | `/api/chat` | ✅ 兼容 |
| `/api/sessions` | `/api/sessions` | ✅ 兼容 |
| `/api/providers` | `/api/providers` | ✅ 兼容 |
| `/api/models` | `/api/models` | ✅ 兼容 |

### 4. 配置文件更新

**旧配置** (如果存在):
```yaml
webui:
  host: 0.0.0.0
  port: 8080
```

**新配置**:
```yaml
# webui-v2 使用独立配置
# 参考 webui-v2/.env.example
```

## 主要改进

webui-v2 提供了以下改进：

### 技术栈升级
- ✅ React 18 + TypeScript
- ✅ Material-UI 3 (MUI3)
- ✅ Vite 构建工具
- ✅ react-i18next 国际化

### 用户体验
- ✅ 更快的加载速度
- ✅ 更好的响应式设计
- ✅ 完整的深色模式支持
- ✅ 多语言支持 (中文、英文)

### 开发体验
- ✅ 热模块替换 (HMR)
- ✅ TypeScript 类型安全
- ✅ 更好的代码组织
- ✅ 完整的测试覆盖

## 常见问题

### Q: 我的旧代码还能运行吗？

A: `agentos web` 命令仍然可以运行，但会显示废弃警告。建议尽快迁移。

### Q: API 是否兼容？

A: 是的，后端 API 保持向后兼容。只是前端界面升级了。

### Q: 如何访问归档的旧代码？

A: 旧代码已移至 `docs/archive/webui-legacy/`，仅供参考。

### Q: 迁移需要多长时间?

A: 如果你只是使用 WebUI 界面，迁移是即时的 - 只需使用 webui-v2。
如果你有自定义代码，可能需要 1-2 小时进行调整。

### Q: 有技术支持吗？

A: 请在主仓库提交 Issue，标记为 `migration` 标签。

## 迁移检查清单

- [ ] 停止使用 `agentos web` 命令
- [ ] 停止使用 `agentos webui` 命令
- [ ] 安装 webui-v2 依赖 (`npm install`)
- [ ] 更新文档中的引用
- [ ] 更新 CI/CD 配置
- [ ] 更新部署脚本
- [ ] 测试所有功能
- [ ] 清理旧的配置文件

## 获取帮助

- 📖 [webui-v2 文档](../webui-v2/README.md)
- 🐛 [报告问题](https://github.com/your-repo/issues)
- 💬 [讨论区](https://github.com/your-repo/discussions)

## 相关文档

- [废弃声明](./archive/WEBUI_DEPRECATION_NOTICE.md)
- [webui-v2 README](../webui-v2/README.md)
- [API 文档](./API_DOCUMENTATION.md)
