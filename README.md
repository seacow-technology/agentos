# AgentOS

![Version](https://img.shields.io/badge/version-0.6.0-blue)
![Reliability](https://img.shields.io/badge/reliability-production--ready-green)
![Concurrency](https://img.shields.io/badge/concurrency-fixed-brightgreen)
![Tests](https://img.shields.io/badge/tests-2234-success)
![Docs](https://img.shields.io/badge/docs-comprehensive-blue)

> ⚠️ **Public Repository Notice**
>
> This repository is a **curated public snapshot** of AgentOS.
>
> The authoritative development source lives in a private repository.
>
> This public repo is intended for **evaluation, experimentation, and community feedback**.

---

## **AgentOS**

**可中断、可恢复、可验证、可审计的 AI 执行系统**

> A system-level, project-agnostic AI Agent orchestration platform with **interruptible, resumable, verifiable, and auditable** execution.

AgentOS is an engineering-grade execution system for AI agents, designed around:
- **可中断 (Interruptible)**: 系统崩溃 (kill -9) 不丢数据
- **可恢复 (Resumable)**: 从最后验证的检查点继续,不重跑已完成工作
- **可验证 (Verifiable)**: 每个执行步骤都有证据链 (文件哈希、命令退出码、数据库状态)
- **可审计 (Auditable)**: 所有操作可追溯,符合企业级审计要求

Unlike chat-centric tools that emphasize "full automation", AgentOS emphasizes **execution controllability** and **process traceability**. Every operation is a **first-class task** with a deterministic lifecycle and evidence-based checkpoints.

---

## **📌 Current Status**

### **v0.6.0 — Planning Safety (Latest)**

**AgentOS v0.6 introduces planning safety as a first-class concept.**
**Planning is side-effect free by convention and guarded by enforcement helpers.**
**System-level invariants and cryptographic guarantees are scheduled for v0.6.1.**

**Key Features**:
- ✅ Chat → Execution hard gate (system-level enforcement)
- ✅ Planning side-effect detection and prevention
- ✅ Frozen spec validation framework
- 🔍 Self-tested with penetration testing (48 tests)
- 🎯 Clear upgrade path to system-level enforcement (v0.6.1)

**Engineering Maturity**:
- One boundary at system-level enforcement (Chat → Execution)
- Two boundaries with convention + guard helpers (Planning, Frozen Spec)
- Honest about enforcement boundaries and limitations
- 3 critical vulnerabilities identified and documented for v0.6.1

[📖 See v0.6.0 Release Notes →](docs/releases/V0.6.0_RELEASE_NOTES.md)

---

### **v0.4.0 — Project-Aware Task Operating System**

Major architecture upgrade with multi-repository project management and strict governance.

- **Project-Aware Architecture**: Tasks must bind to projects, supports multi-repo
- **Spec Freezing**: Enforce specification stability before execution
- **Audit Trail**: Complete operation history with event logging
- **Enhanced APIs**: 16 new endpoints for projects, repos, and task specs
- **CLI v31**: 14 new commands for project and repository management
- **WebUI Wizard**: 4-step task creation flow with project binding

[📖 See v0.4 Release Notes →](docs/releases/V04_RELEASE_NOTES.md)

---

## **🚀 Autonomous Execution Engine (AEE)**

**NEW in v0.3.x**: AgentOS now includes a production-ready **Autonomous Execution Engine (AEE)** for fully autonomous task execution with built-in quality gates.

```
Chat → Task → Runner → Verify → Done
```

**Key Features**:
- ⚡ **Event-driven triggering** (<5s startup, 6-12x faster than polling)
- ✅ **Quality gates** (doctor/smoke/tests) - No false completions
- 🔄 **Automatic retry** on gate failure with failure context
- 📋 **Work items coordination** - Structured sub-task execution
- 📊 **Full auditability** - Every operation recorded with exit_reason

[📖 Learn more about AEE →](docs/architecture/AEE_OVERVIEW.md)

---

## **✨ Core Capabilities**

- 🎯 **Task-centric execution**

  Every action is a managed task — not an ephemeral chat session.

- ⏸️ **Strong interruptibility**

  Tasks pause at deterministic checkpoints (open_plan) for human review.

- 🔄 **Full resumability**

  Approved tasks resume execution with preserved context.

- 📊 **Native audit & lineage**

  Every decision, plan, and execution step is traceable.

- 🚀 **Background execution**

  CLI does not block — tasks execute asynchronously.

- 🔒 **Governance-by-design**

  Mode Gate, Pause Gate, and Execution Red Lines are enforced by the system.

- 🌐 **Cross-platform providers**

  Automatic detection and management of Ollama, LlamaCpp, LM Studio on Windows, macOS, and Linux.

- 📁 **Multi-repo project management** (NEW in v0.4)

  Organize repositories, tasks, and execution context in unified projects. Support for microservices, monorepos, and multi-repo architectures.

- 🔒 **Spec Freezing** (NEW in v0.4)

  Lock task specifications before execution to ensure stable goals and clear acceptance criteria.

- 📋 **Project Binding** (NEW in v0.4)

  All tasks must bind to projects with foreign key constraints for better organization and traceability.

- 📊 **Audit Trail** (NEW in v0.4)

  Complete operation history with event types (CREATED, SPEC_FROZEN, BOUND, READY, COMPLETED).

- ✅ **Concurrency-Safe Database**: Queue-based write serialization (SQLiteWriter)
- ✅ **Task Templates**: Reusable task configurations for faster creation
- ✅ **Batch Task Creation**: Create 1-100 tasks at once (text/CSV modes)
- ✅ **PostgreSQL Support**: Production-ready database with 2-4x performance boost
- ✅ **API Rate Limiting**: Protection against abuse (10/min, 100/hour)
- ✅ **Runtime Monitoring**: Real-time metrics for performance tracking

---

## 🎊 Recent Milestones

### v0.3.x - Concurrency & Reliability (2026-01-29) ⭐

This major milestone brings production-ready reliability and complete Task Management features:

- 🔒 **100% Solved**: SQLite "database is locked" errors completely eliminated
- 📝 **Feature Complete**: Task creation, templates, and batch operations
- 🚀 **Performance**: 2-4x faster with PostgreSQL support
- 📚 **Documentation**: 5,500+ lines of comprehensive guides
- 🧪 **Testing**: 96% coverage with 49 new tests

**Key Features**:
- SQLiteWriter queue-based architecture
- Task template system (50% faster task creation)
- Batch creation (up to 100 tasks)
- PostgreSQL production deployment
- Runtime monitoring and alerting

[📖 View Release Notes →](docs/releases/v0.3.1.md)

---

## **🔧 Environment Check & Setup**

Before using AgentOS, verify your environment is ready:

```bash
# Quick environment check (no external dependencies required)
python3 scripts/verify_doctor.py

# One-command setup (installs uv, Python 3.13, dependencies, pytest)
uv run agentos doctor --fix
```

> 💡 `agentos doctor` automatically configures your environment with zero decisions needed.

---

## **🚀 Quick Start**

### **Option 1: Using uv (Recommended)**

```bash
# Clone the repository
git clone https://github.com/seacow-technology/agentos.git
cd agentos

# 1. Verify CLI availability (auto-installs dependencies)
uv run agentos --help

# 2. Initialize local database (required on first run)
uv run agentos init

# 3. Start interactive CLI
uv run agentos
```

> If agentos is not found, always prefer: `uv run agentos`

---

### **Option 2: Using pip**

```bash
# Install in editable mode
pip install -e .

# Optional: PostgreSQL Support
pip install "agentos[postgres]"
# or
uv add --optional postgres psycopg2-binary

# Initialize database
agentos init

# Start CLI
agentos
```

---

## **🌐 WebUI (Local Control Surface)**

AgentOS includes a lightweight local WebUI for inspection and governance:

```bash
agentos --web
```

- No SaaS dependency
- No mandatory authentication
- Designed for **visibility**, not remote execution

### **AI Providers Management**

AgentOS supports automatic detection and management of local AI providers across all platforms:

- **Ollama**: Automatic detection and lifecycle management
- **LlamaCpp (llama-server)**: Multi-instance support with custom models
- **LM Studio**: Cross-platform application launcher

**Platform Support**:
- ✅ Windows 10/11
- ✅ macOS 13+
- ✅ Linux (Ubuntu 22.04+, other distributions)

**Features**:
- Automatic executable detection
- Manual path configuration with file browser
- Models directory management
- Process lifecycle control (start/stop/restart)
- Platform-specific error messages and suggestions

See [Providers Cross-Platform Setup Guide](docs/guides/providers_cross_platform_setup.md) for detailed configuration instructions.

### **Task Management**

Create and manage tasks directly through the WebUI:

1. **Via Web Interface**:
   - Navigate to Task Management page
   - Click "Create Task" button
   - Fill in task details (title, creator, metadata)
   - Task will be created with auto-generated session ID

2. **Via REST API**:
   ```bash
   curl -X POST http://localhost:8000/api/tasks \
     -H "Content-Type: application/json" \
     -d '{
       "title": "Implement feature X",
       "created_by": "user@example.com",
       "metadata": {"priority": "high"}
     }'
   ```

**Features**:
- ✅ Auto-generated session IDs (format: `auto_{task_id}_{timestamp}`)
- ✅ Rate limiting (10/min, 100/hour)
- ✅ Full validation and error handling
- ✅ Metadata support for custom fields
- ✅ Automatic audit logging

See [Task Management Guide](docs/guides/user/TASK_MANAGEMENT_GUIDE.md) for detailed usage.

---

## **🧠 Execution Model Overview**

### **Three-Layer Model**

```
1. Run Mode (human involvement)
   - interactive   : every step requires approval
   - assisted      : default, pauses at critical points
   - autonomous    : fully automated

2. Execution Mode (system phase)
   - intent → planning → implementation
   - phases cannot be skipped

3. Model Policy (compute selection)
   - declarative model assignment per phase
```

---

### **Sovereignty & Safety Guarantees**

- **Pause Gate**

  Tasks can pause *only* at open_plan checkpoints.

- **Mode Gate**

  Destructive operations are forbidden outside implementation mode.

- **Execution Red Lines**

  Certain actions are categorically disallowed by design.

- **Lineage & Audit**

  All state transitions are persisted and traceable.

---

## **🧩 Example Workflows**

### **Example 1: Code Generation with Review**

```
User intent
  ↓
System generates execution plan (open_plan)
  ↓
Human reviews plan
  ↓
Approval granted
  ↓
Task executes with full audit trail
```

---

### **Example 2: Large-Scale Refactor**

```bash
agentos
> New task: "Refactor all API error handling to unified format"

# Task pauses for approval
> Inspect task <task_id>

# Approve execution
> Resume task <task_id>

# Review execution trace
agentos task trace <task_id>
```

---

### **Example 3: Autonomous CI-style Execution**

```bash
export AGENTOS_RUN_MODE=autonomous
agentos task create "Run tests and generate report"

agentos task show <task_id>
# Status: succeeded
```

---

## **⚙️ Database Configuration**

AgentOS supports both **SQLite** (development) and **PostgreSQL** (production).

### **SQLite (Default - Auto-configured)**
Perfect for development and single-user scenarios. Zero configuration required.

```bash
# Just run AgentOS - SQLite is automatically configured
uv run agentos server
```

### **PostgreSQL (Recommended for Production)**
For multi-user production deployments with high concurrency:

```bash
# Set environment variables
export DATABASE_TYPE=postgresql
export DATABASE_HOST=localhost
export DATABASE_PORT=5432
export DATABASE_NAME=agentos
export DATABASE_USER=agentos
export DATABASE_PASSWORD=your_secure_password

# Start with Docker Compose
docker-compose up -d postgres

# Run AgentOS
uv run agentos server
```

**Performance**: PostgreSQL provides 2-4x better performance for concurrent operations.

See [Database Migration Guide](docs/deployment/DATABASE_MIGRATION.md) for details.

### **Quick Comparison**

| Feature | SQLite | PostgreSQL |
|---------|--------|------------|
| **Setup** | Zero config | Requires server |
| **Concurrency** | Limited (single writer) | Excellent (multi-user) |
| **Use Case** | Development, single user | Production, multi-user |
| **Performance** | Good for small data | Optimized for scale |

**📖 Full Documentation**: See [Database Migration Guide](docs/deployment/DATABASE_MIGRATION.md)

---

## **🛠️ Development & Testing**

### **Environment Verification**

```bash
# Verify environment without external dependencies
python3 scripts/verify_doctor.py

# Auto-configure environment (uv, Python 3.13, all dependencies)
uv run agentos doctor --fix
```

### **Run Tests**

```bash
# Quick test (recommended after environment setup)
uv run pytest -q

# Full test suite
uv run pytest tests/

# Specific test categories
uv run pytest tests/unit/           # Unit tests
uv run pytest tests/integration/    # Integration tests
```

### **Lint & Format**

```bash
uv run ruff check .
uv run ruff format .
```

---

## **📊 Project Status**

- **Version**: 0.6.0
- **Status**: 🟢 Architecture-stable with planning safety boundaries
- **License**: Apache License 2.0 (Apache-2.0)

---

## **🤝 Contributing**

Contributions are welcome.

Before submitting a PR:

1. Read the **Architecture Contracts**
2. Follow governance rules (Mode Gate, Pause Gate)
3. Add tests where applicable
4. Submit a pull request with a clear rationale

---

## **🔐 Security**

If you discover a security vulnerability, **do not open a public issue**.

Please follow the instructions in [SECURITY.md](./SECURITY.md).

---

## **📞 Community & Support**

- 🐛 Issues: GitHub Issues
- 💡 Ideas: GitHub Discussions
- 💬 Community: Discord (link in repo)
- 🧪 Feedback: Very welcome — this public snapshot exists for that purpose

---

## **🏁 Getting Started**

```bash
uv run agentos
```

---

**Built with care for control, traceability, and human-in-the-loop engineering.**
