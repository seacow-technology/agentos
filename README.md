> ⚠️ **Public Repository Notice**
>
> This repository is a curated public snapshot of AgentOS.
> The authoritative development source lives in a private repository.

# AgentOS

**System-level, project-agnostic AI Agent orchestration system**

AgentOS 是一个工程级 AI Agent 执行平台，提供**可控、可中断、可恢复**的任务管理能力。

## 📌 Current Status

**v0.3.1** — Architecture-stable release. Validation layers (Schema / Business Rules / Dry Executor RED LINE) are frozen and documented.

[📖 Release Notes](docs/releases/v0.3.1.md) | [🏗️ Architecture Docs](docs/architecture/VALIDATION_LAYERS.md)

---

## ✨ 核心特性

- 🎯 **任务中心化**: 所有操作都是创建/管理 task，而非临时会话
- ⏸️  **强可中断性**: 任务在关键点（open_plan）暂停，等待人工审批
- 🔄 **完全可恢复**: 批准后继续执行，保留完整上下文
- 📊 **原生可审计**: 每个动作都有 lineage 和 audit 记录
- 🚀 **后台执行**: CLI 不阻塞，任务在后台运行
- 🔒 **主权保护**: Mode Gate / Pause Gate 强制执行安全策略

---

## 🚀 快速开始

### 使用 uv（推荐，一键运行）

```bash
# 克隆仓库
git clone https://github.com/your-org/AgentOS.git
cd AgentOS

# 1. 验证 CLI 可用（自动安装依赖）
uv run agentos --help

# 2. 初始化数据库（首次运行，必需）
uv run agentos init

# 3. 启动交互式 CLI
uv run agentos
# 或显式使用
uv run agentos interactive
```

### 使用 pip

```bash
# 1. 安装依赖
pip install -e .

# 2. 初始化数据库
agentos init

# 3. 启动 CLI
agentos

# 或启动全屏 TUI（推荐）
agentos --tui
```

### 全屏 TUI 模式 🎨

AgentOS 提供现代化的全屏终端界面（TUI）：

```bash
# 启动 TUI
agentos --tui
```

**TUI 特性**：
- 🖥️ OpenCode风格的居中命令面板
- 📋 实时刷新的任务列表（支持搜索/过滤）
- 🔍 详细的任务检查视图（Timeline/Audits/Agents）
- ⚙️ 可视化设置管理
- ⌨️ 丰富的键盘快捷键
- 🎯 Watch模式实时监控任务执行
- 🔧 **自动数据库管理**（初始化、迁移、版本检查）
- 🔔 **更新提醒**（自动检查 PyPI 新版本）

详见：[TUI用户指南](docs/TUI_USER_GUIDE.md) | [Home Screen 功能](docs/HOME_SCREEN_USER_GUIDE.md)
# 或
agentos interactive
```

**📘 详细文档**: [QUICKSTART.md](./QUICKSTART.md)

**⚠️  如果遇到 `command not found`**: 使用 `uv run agentos` 替代 `agentos`

---

## 🔗 Multi-Repository Support (New in v0.18!)

AgentOS now supports managing projects with **multiple Git repositories**:

- **Unified Task Management**: Tasks can span across multiple repos
- **Cross-Repo Dependencies**: Automatic dependency detection and tracking
- **Audit Trail**: Complete lineage across all repositories
- **Flexible Workspace**: Code, docs, infra in separate repos with controlled access

### Quick Start

```bash
# 1. Configure authentication
agentos auth add --name github-ssh --type ssh_key --key-path ~/.ssh/id_rsa

# 2. Create project configuration
cat > my-app.yaml <<EOF
name: my-app
repos:
  - name: backend
    url: git@github.com:org/backend
    path: ./be
    role: code
    auth_profile: github-ssh
  - name: frontend
    url: git@github.com:org/frontend
    path: ./fe
    role: code
    auth_profile: github-ssh
EOF

# 3. Import project
agentos project import --from my-app.yaml

# 4. Trace cross-repo activity
agentos project trace my-app
```

**📚 Learn More**:
- [Multi-Repo Architecture](./docs/projects/MULTI_REPO_PROJECTS.md) - Complete guide
- [CLI Usage](./docs/cli/PROJECT_IMPORT.md) - Command reference
- [Examples](./examples/multi-repo/) - Working examples
- [Migration Guide](./docs/migration/SINGLE_TO_MULTI_REPO.md) - Upgrade path

---

## 📖 文档

### 入门

- 📘 [快速开始](./QUICKSTART.md) - 安装、配置、第一个任务
- 📘 [CLI 控制平面](./docs/cli/CLI_TASK_CONTROL_PLANE.md) - 核心概念和设计

### 架构

- 📕 [架构白皮书](./docs/WHITEPAPER_FULL_EN.md) - 完整技术架构
- 📕 [架构图](./docs/ARCHITECTURE_DIAGRAMS.md) - 系统组件关系
- 📕 [架构契约](./docs/cli/CLI_ARCHITECTURE_CONTRACTS.md) - 核心铁律（5 条）

### 实施历程

- 📗 [P0 实施报告](./docs/cli/CLI_P0_CLOSEOUT.md) - 基础设施
- 📗 [P1 完成报告](./docs/cli/CLI_P1_COMPLETION.md) - 真实 pipeline 集成
- 📗 [P2 收口报告](./docs/cli/CLI_P2_CLOSEOUT.md) - Approve/Continue 闭环

### WebUI & Governance (v0.3.2)

- 🌐 [WebUI Control Surface ADR](./docs/adr/ADR-005-webui-control-surface.md) - WebUI vs CLI 职责边界
- 🌐 [Capability Matrix](./docs/WEBUI_CAPABILITY_MATRIX.md) - CLI vs WebUI 功能对照表
- 🛡️ [Governance Semantic Freeze](./docs/adr/ADR-004-governance-semantic-freeze.md) - 治理系统不可变契约
- 🎯 [Execution Plans View](./docs/webui/execution_plans_view.md) - 执行计划与提案生成
- ✍️ [Intent Workbench View](./docs/webui/intent_workbench_view.md) - 意图构建与对比
- 📦 [Content Registry View](./docs/webui/content_registry_view.md) - 内容资产版本管理
- 💬 [Answer Packs View](./docs/webui/answer_packs_view.md) - 答案包创建与验证

---

## 🎯 使用场景

### 场景 1: 代码生成与审查

```
用户: "创建一个 Python Web 服务器，支持 REST API"
  ↓
系统生成计划（open_plan）并暂停
  ↓
用户审查计划（查看文件变更、API 设计）
  ↓
用户批准 → 系统执行
  ↓
完整 trace 可追溯每个决策
```

### 场景 2: 批量重构

```bash
# 创建任务
uv run agentos
> New task: "重构所有 API 错误处理为统一格式"

# 任务后台运行，生成计划后暂停
> List tasks
# task_123: awaiting_approval

# 审查计划
> Inspect task: task_123
# 查看影响的文件、修改策略

# 批准执行
> Resume task: task_123

# 查看执行轨迹
uv run agentos task trace task_123
```

### 场景 3: CI/CD 自动化

```bash
# Autonomous 模式，无需人工干预
export AGENTOS_RUN_MODE=autonomous
uv run agentos task create "运行测试并生成报告"

# 任务自动执行完成
uv run agentos task show <task_id>
# Status: succeeded
```

---

## 🏗️ 架构亮点

### 三层模型

```
1. Run Mode（人机关系）
   - interactive: 每个阶段需要确认
   - assisted: 默认自动，关键点暂停
   - autonomous: 全自动

2. Execution Mode（系统阶段）
   - intent → planning → implementation
   - 不能跳过，由 pipeline 控制

3. Model Policy（算力选择）
   - 声明式配置每个阶段使用的模型
```

### 主权层保护

- **PauseGate**: 只能在 `open_plan` 暂停（V1 铁律）
- **Mode Gate**: 非 `implementation` mode 禁止破坏性动作
- **Lineage**: 每个动作都记录，完整可追溯

### vs. opencode / claude code

| 特性 | AgentOS | opencode/claude code |
|------|---------|---------------------|
| 状态管理 | Task-centric | Session-centric |
| 中断能力 | 强（pause_checkpoint） | 弱 |
| 追溯能力 | Task lineage | 不完整 |
| 后台执行 | 原生支持 | 不清晰 |
| 审计 | 原生支持 | 无 |
| 可治理性 | ✅ 强 | ❌ 弱 |

---

## 🛠️ 开发

### 运行测试

```bash
# 所有测试
uv run pytest tests/

# P2 E2E 测试
uv run python tests/test_p2_approve_continue.py

# 特定测试
uv run pytest tests/test_cli_e2e.py -v
```

### 代码检查

```bash
# Linting
uv run ruff check .

# 格式化
uv run ruff format .
```

---

## 📊 项目状态

- **Version**: 0.3.0
- **Status**: 🟢 **P2 Complete - Production Candidate**
- **License**: MIT

### 里程碑

- ✅ **P0** (2026-01-20): 基础设施（RunMode, PauseGate, CLI 主循环）
- ✅ **P1** (2026-01-22): 真实 pipeline 集成 + Mode Gate
- ✅ **P2** (2026-01-26): Approve/Continue 真实闭环 + Artifact
- 🟡 **P3** (In Progress): 可用性增强（trace --expand, 运行体验）

---

## 🤝 贡献

欢迎贡献！请遵循：

1. 阅读 [架构契约](./docs/cli/CLI_ARCHITECTURE_CONTRACTS.md)（5 条铁律）
2. Fork 仓库
3. 创建 feature 分支
4. 提交 PR，附带测试
5. 通过 Code Review

### 贡献指南

- 📌 [架构契约](./docs/cli/CLI_ARCHITECTURE_CONTRACTS.md) - 核心规则（必读）
- 📌 [P3 规划](./docs/cli/CLI_P3_PLAN.md) - 当前开发方向

---

## 🌟 致谢

AgentOS 受以下项目启发：
- [Anthropic Claude](https://www.anthropic.com/claude)
- [OpenAI Code Interpreter](https://openai.com/blog/chatgpt-plugins)
- [Langchain](https://github.com/langchain-ai/langchain)
- [AutoGPT](https://github.com/Significant-Gravitas/AutoGPT)

特别感谢所有贡献者和早期用户！

---

## 📞 联系

- 🐛 [报告问题](https://github.com/your-org/AgentOS/issues)
- 💡 [功能建议](https://github.com/your-org/AgentOS/discussions)
- 💬 Discord: [加入讨论](https://discord.gg/agentos)
- 🐦 Twitter: [@AgentOS](https://twitter.com/agentos)

---

**Built with ❤️ by the AgentOS Team**

**🎉 Start your first task:**

```bash
uv run agentos
```
