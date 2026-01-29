# AgentOS

> ⚠️ **Public Repository Notice**
>
> This repository is a **curated public snapshot** of AgentOS.
>
> The authoritative development source lives in a private repository.
>
> This public repo is intended for **evaluation, experimentation, and community feedback**.

---

## **AgentOS**

**A system-level, project-agnostic AI Agent orchestration platform**

AgentOS is an engineering-grade execution system for AI agents, designed around **explicit tasks**, **human-in-the-loop control**, and **full auditability**.

Unlike chat-centric tools, AgentOS treats every operation as a **first-class task** with a deterministic lifecycle.

---

## **📌 Current Status**

**v0.3.x — Architecture-stable release**

Core validation layers (Schema / Governance / Execution Gates) are frozen and documented.

- Task lifecycle: **stable**
- Governance semantics: **frozen**
- CLI & WebUI control surface: **production-ready (local-first)**

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

- **Version**: 0.3.x
- **Status**: 🟢 Architecture-stable, production-candidate (local)
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
