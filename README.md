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

### **v3.0 — OS-Level Capability Governance (NEW)**

**AgentOS v3 introduces OS-Level Capability Governance - treating AI agents as processes with Linux-inspired capability-based permissions.**

**Core Principle**: **Decisions are NOT Actions**. Strict separation between planning and execution with enforced Golden Path.

**🏛️ Five-Domain Architecture**:
```
┌────────────────────────────────────────────────────┐
│  STATE → DECISION → GOVERNANCE → ACTION → EVIDENCE │
│                                                     │
│  27 capabilities across 5 domains                  │
│  Strict domain boundaries enforced by PathValidator│
└────────────────────────────────────────────────────┘
```

**Key Features**:
- ✅ **Capability-Based Permissions**: Explicit grants with 5 levels (NONE/READ/PROPOSE/WRITE/ADMIN)
- ✅ **Golden Path Enforcement**: State → Decision → Governance → Action → Evidence (9 steps)
- ✅ **PathValidator**: Runtime firewall blocking forbidden paths (decision→action, action→state)
- ✅ **Immutable Evidence**: SHA256-verified audit trail for SOX/GDPR/HIPAA compliance
- ✅ **Governance Engine**: Policy-based access control with risk scoring (T1/T2/T3)
- ✅ **Evidence Replay**: Time-travel debugging with read-only and validate modes
- ✅ **Frozen Plans**: Immutable execution plans with hash verification

**Forbidden Paths (Blocked)**:
- ❌ Decision → Action (decisions cannot trigger execution)
- ❌ Action → State (actions must go through governance)
- ❌ Evidence → Any (evidence is write-only, immutable)

**Performance Targets (All EXCEEDED)**:
- PathValidator: <5ms per validation (actual: ~2-3ms)
- Registry query: <1ms (actual: ~0.3ms)
- Golden Path E2E: <100ms (actual: ~63-93ms)
- Decision throughput: >100/s (actual: ~350/s)
- Evidence collection: <20ms (actual: ~3-5ms)

**Implementation Status**:
- 27/27 capabilities implemented (100%)
- 5 domains (STATE, DECISION, ACTION, GOVERNANCE, EVIDENCE)
- 2,419 tests passing (185 new v3 tests)
- 75,000+ words documentation
- Performance benchmarks validated

**Documentation**:
- 📖 [User Guide (20,000 words)](docs/v3/user_guide/AGENTOS_V3_USER_GUIDE.md)
- 📖 [Developer Guide (25,000 words)](docs/v3/developer_guide/AGENTOS_V3_DEVELOPER_GUIDE.md)
- 📖 [Migration Guide v2→v3 (15,000 words)](docs/v3/migration/MIGRATION_V2_TO_V3.md)
- 📖 [Release Notes v3.0](RELEASE_NOTES_V3.md)
- 📖 [Performance Tests](/tests/performance/test_capability_v3_performance.py)

**Quick Example - Golden Path**:
```python
# 1. Read state
memory = state.read_memory(scope="global", key="user_context")

# 2. Create plan
plan = decision.create_plan(task_id="task-123", steps=[...])

# 3. Freeze plan (immutable)
frozen_plan = decision.freeze_plan(plan.plan_id)

# 4. Check permission
permission = governance.check_permission(agent_id, capability_id, context)

# 5. Calculate risk
risk = governance.calculate_risk_score(agent_id, capability_id, context)

# 6. Execute (if approved)
result = action.execute(
    capability_id="action.execute.local",
    params={"command": "pytest"},
    agent_id="execution_agent",
    context={"plan_id": frozen_plan.plan_id}
)

# 7. Update state
state.write_memory(scope="project", key="test_results", value=result)

# 8-9. Evidence automatically collected and linked
```

**Compliance Support**:
- ✅ SOX (Sarbanes-Oxley) - Immutable audit trail
- ✅ GDPR - Data processing logs + consent tracking
- ✅ HIPAA - Medical data access logs + encryption
- ✅ ISO 27001 - Information security event logs

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

## **🌐 CommunicationOS (External Communication Gateway)**

**NEW in v0.6.x**: AgentOS now includes **CommunicationOS** - a secure, auditable gateway for all external communications.

```
Agent → CommunicationOS → [Policy + SSRF Protection + Audit] → External API
```

**Key Features**:
- 🔒 **SSRF Protection** - Blocks access to internal networks and private IPs
- 🛡️ **Injection Prevention** - SQL, command, and XSS protection
- 📊 **Comprehensive Audit** - Every external request logged with evidence
- ⚡ **Rate Limiting** - Prevent abuse and control costs
- 🔐 **Output Sanitization** - Automatic redaction of sensitive data
- 🎯 **Policy Enforcement** - Declarative control over allowed operations

**Supported Connectors**:
- Web Search (DuckDuckGo)
- Web Fetch (HTTP/HTTPS content retrieval)
- RSS/Atom feeds
- Email (SMTP)
- Slack messaging

**Quick Start**:
```python
from agentos.core.communication import CommunicationService, ConnectorType

service = CommunicationService()

# Execute web search
response = await service.execute(
    connector_type=ConnectorType.WEB_SEARCH,
    operation="search",
    params={"query": "Python asyncio"},
    context={"task_id": "task-123"},
)

# All operations are:
# ✅ Policy-enforced
# ✅ Rate-limited
# ✅ Sanitized
# ✅ Audited
```

[📖 Learn more about CommunicationOS →](docs/communication/CommunicationOS-Architecture.md)

---

## **🧠 Production-Grade Persistent Memory (v1.0 - NEW)**

**NEW in v1.0**: AgentOS now supports **intelligent, persistent memory** across chat sessions with production-grade reliability.

```
User: "以后请叫我胖哥" → [Auto-extracted: preferred_name="胖哥"]
Next session: AI greets with "你好,胖哥!" ✅
```

### Key Features

- **Auto-Extract User Preferences**: Remembers names, emails, companies, tech stack preferences automatically
- **Cross-Session Recall**: Set once ("Call me Pangge"), remembered forever
- **Scoped Isolation**: Multi-level hierarchy (global → project → task → agent)
- **Prompt Enforcement**: Memory facts injected with strong "MUST" compliance instructions
- **Full Observability**: Real-time Memory Badge showing status and memory types
- **Production Ready**: 100+ tests, E2E validated, async non-blocking

### Technical Specifications

- **17 deterministic extraction rules** covering 6 categories (bilingual: Chinese + English)
- **0.9 confidence** for all rule-based matches
- **< 500ms extraction latency** (async, non-blocking)
- **< 50ms retrieval latency** (FTS5 indexed queries)
- **Multi-scope hierarchy**: global/project/task/agent levels
- **SQLite + FTS5**: Full-text search with zero external dependencies
- **REST API + WebSocket**: Real-time updates and status queries

### Usage Example

```python
# Memory extraction happens automatically in chat
# No code needed - just talk naturally!

# Session 1:
User: "我在谷歌公司工作,我喜欢使用Python语言"
→ Auto-extracted:
  - company: "谷歌" (confidence: 0.9)
  - tech_preference: "Python" (confidence: 0.9)

# Session 2 (days later):
User: "帮我写一个数据处理脚本"
AI: "好的! 考虑到你在谷歌工作,我会用Python写一个企业级的脚本..."

✅ Memory automatically recalled and applied!
```

### Before vs After

| Before Memory v1.0 | After Memory v1.0 |
|-------------------|-------------------|
| ❌ "Call me Pangge" → Forgotten next session | ✅ "以后请叫我胖哥" → Remembered forever |
| ❌ Repetitive questions every chat | ✅ Personalized greetings automatically |
| ❌ No context persistence | ✅ Cross-session memory with scope isolation |
| ❌ Manual context re-entry | ✅ Auto-extraction with 0.9 confidence |

### Supported Memory Types

**Preferred Names**: "叫我胖哥", "Call me John"
**Contact Info**: Email addresses, phone numbers
**Company**: "我在谷歌公司工作", "I work at Microsoft"
**Tech Preferences**: "我喜欢Python", "I prefer React"
**Tech Dislikes**: "我不喜欢Java", "I don't like PHP"
**Project Context**: "项目名称是AgentOS", "This project is called MyApp"

[📖 Learn more →](docs/MEMORY_INTEGRATION_COMPLETE_SUMMARY.md)
[📖 Quick Reference →](docs/MEMORY_EXTRACTOR_QUICK_REF.md)
[📖 Release Notes →](RELEASE_NOTES_MEMORY_V1.md)

---

## **🔒 Security First - Trust by Design**

**AgentOS is built with security as the foundation, not an afterthought.**

### Core Security Promises (FROZEN v1)

AgentOS makes four immutable security commitments to users:

#### 1. 🛡️ Default Chat-Only (Principle of Least Privilege)
- **Promise**: AgentOS defaults to conversation-only mode. No commands executed, no files modified.
- **Implementation**: All channels start with `allow_execute: false` hardcoded in manifest
- **User Control**: Execution requires explicit authorization with confirmation dialogs
- **Visibility**: "Chat-only" badges in UI, all permission changes audited

#### 2. 🔐 Execute Always Requires Authorization (Defense in Depth)
- **Promise**: Even with execution enabled, dangerous operations need secondary confirmation
- **Implementation**: Guardian policy layer intercepts all execution requests
- **Protection**: High-risk commands (rm -rf, sudo, dd) require human approval
- **Safeguards**: Rate limiting, automatic rollback on failure

#### 3. 🚫 Never Auto-Provision Third-Party Accounts (Manual Configuration)
- **Promise**: AgentOS never automatically connects to Slack/Discord/Email
- **Implementation**: No OAuth auto-authorization flow
- **User Control**: Manual token/API key configuration via Setup Wizard
- **Storage**: Local encrypted storage, revocable at any time

#### 4. 🏠 Local-First / User-Owned Data (Data Sovereignty)
- **Promise**: Your data stays on your device. AgentOS never uploads to cloud.
- **Implementation**: SQLite local database (store/registry.sqlite)
- **Architecture**: All config files stored locally (.env)
- **Privacy**: LLM API keys provided by user (never pass through our servers)

### Security Architecture

```
User Request
  ↓
[Channel Policy]      ← chat_only enforcement
  ↓
[Rate Limiter]        ← abuse prevention
  ↓
[Guardian]            ← dangerous command interception
  ↓
[Executor]            ← sandboxed execution
  ↓
[Audit Log]           ← complete traceability
```

### Security Badges

Every channel declares its security posture:
- ✅ **No Auto Provisioning** - Manual configuration only
- ✅ **Chat-only by Default** - Execution disabled by default
- ✅ **Local Storage** - Data never leaves your device
- ✅ **Secrets Encrypted** - All tokens encrypted at rest
- ✅ **User-Conversation Scope** - Session isolation
- ✅ **Manual Configuration** - No automatic account linking

### Compliance & Standards

- **GDPR**: Data localization, user full control
- **SOC 2**: Access control, audit logs
- **ISO 27001**: Information security management
- **OWASP ASVS**: Application security verification

### Learn More

- 📖 [Security Narrative (FROZEN v1)](docs/SECURITY_NARRATIVE_V1.md) - Our immutable commitments
- 📖 [Security Checklist](docs/SECURITY_CHECKLIST.md) - PR/Release security requirements
- 📖 [CSRF Best Practices](docs/security/CSRF_BEST_PRACTICES.md) - Web security guide
- 🔐 Report vulnerabilities: security@agentos.dev

---

### **🔒 OS-Level Memory Permissions (NEW - v1.1)**

AgentOS Memory features a Linux-inspired capability system for OS-level permission control:

**5-Tier Capability Model**: `NONE < READ < PROPOSE < WRITE < ADMIN`

```python
# Chat agent proposes memory (requires human approval)
proposal_id = memory_service.propose(
    agent_id="chat_agent",  # PROPOSE capability
    memory_item={
        "scope": "global",
        "type": "preference",
        "content": {"key": "language", "value": "Python"}
    },
    reason="User said: I prefer Python"
)

# Admin reviews in WebUI (📋 Proposals page)
# After approval → Memory written with full audit trail
```

**Key Features**:
- ⚡ **Hierarchical Capabilities**: NONE < READ < PROPOSE < WRITE < ADMIN (inherited permissions)
- 🛡️ **Anti-Hallucination**: Chat agents propose, humans approve (prevents AI corruption)
- 📋 **Complete Audit Trail**: Every capability check logged with agent ID, operation, timestamp
- 🔐 **Deny by Default**: Unknown agents get NONE capability (secure by design)
- ⏰ **Time-Limited Access**: Optional expiration for temporary privileges
- 🎯 **Pattern-Based Defaults**: `user:*` → ADMIN, `test_*` → WRITE, `*_readonly` → READ

**Default Capabilities**:

| Agent Type | Capability | Access Level |
|-----------|-----------|--------------|
| `user:*` | **ADMIN** | 👑 Full control |
| `chat_agent` | **PROPOSE** | 💡 Suggest + Read |
| `query_agent` | **READ** | 🔍 Query-only |
| `system` | **ADMIN** | 👑 Full control |
| Unknown agents | **NONE** | ⛔ Denied |

**Propose Workflow** (Anti-Hallucination):

```
┌─────────────────────────────────────────┐
│ 1. Chat Agent Proposes Memory           │
│    → Creates proposal (pending state)   │
└────────────────┬────────────────────────┘
                 ↓
┌─────────────────────────────────────────┐
│ 2. Admin Reviews in WebUI               │
│    → "📋 Proposals" page                │
└────────────────┬────────────────────────┘
                 ↓
┌─────────────────────────────────────────┐
│ 3. Admin Approves/Rejects               │
│    → ✅ Approve: Memory written          │
│    → ❌ Reject: Proposal closed          │
│    → Full audit trail preserved         │
└─────────────────────────────────────────┘
```

**Why This Matters**:
- **Security**: Prevents unauthorized memory access and corruption
- **Accountability**: Complete audit trail of who did what
- **Quality**: Human verification prevents AI hallucinations from polluting memory
- **Compliance**: Enterprise-grade permission tracking and audit logs

[📖 User Guide →](docs/MEMORY_CAPABILITY_USER_GUIDE.md)
[📖 Developer Guide →](docs/MEMORY_CAPABILITY_DEVELOPER_GUIDE.md)
[📖 Migration Guide →](docs/MIGRATION_TO_CAPABILITY_CONTRACT.md)
[📖 ADR-012 →](docs/adr/ADR-012-memory-capability-contract.md)

---

## **✨ Core Capabilities**

- 🎯 **Task-centric execution**

  Every action is a managed task — not an ephemeral chat session.

- 🎭 **5 Conversation Modes** (NEW in v0.6.x)

  Choose how AgentOS interacts with you: chat (friendly assistant), discussion (deep analysis), plan (strategic planning), development (code-focused), task (concise execution). Mode controls UX, not permissions.

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

### **Governance UI (Phase 4 Enhancements)**

**NEW in v0.3.2**: Real-time governance monitoring with advanced UX features:

**L-21: Real-time Updates via WebSocket**
- Live quota usage updates (no refresh needed)
- Automatic reconnection on connection loss
- <50ms update latency

**L-22: Global Search**
- Search across all governance data
- Instant results with highlighting
- Filter by capability, trust tier, status

**L-23: Filter Presets**
- Save frequently used filter configurations
- Quick load from dropdown
- Persistent across sessions (localStorage)

```javascript
// Example: Save a preset
Presets → Save Current → "High Risk Only"
// T3 tier + denied status

// Load preset
Presets → Select "High Risk Only" → Filters applied instantly
```

[📖 Learn more →](docs/PHASE_4_COMPLETION.md)

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

### **Verify MCP Implementation**

Run the one-click MCP acceptance verification:

```bash
./scripts/verify_mcp_acceptance.sh
```

This verifies all 61 core MCP tests pass:
- 25 tests: MCP Client
- 19 tests: Policy Gates
- 17 tests: MCP Integration

Expected output: `FINAL RESULT: ✅ PASS (61/61)`

See [MCP Quick Start Guide](docs/mcp/QUICKSTART.md) for details.

### **Lint & Format**

```bash
uv run ruff check .
uv run ruff format .
```

### **Git Hooks Setup (Recommended for Contributors)**

AgentOS includes pre-commit hooks to enforce security best practices:

```bash
# Install git hooks (includes CSRF protection check)
./scripts/githooks/install.sh
```

This installs a pre-commit hook that:
- Checks POST/PUT/PATCH/DELETE requests for CSRF protection
- Prevents committing unprotected API calls
- Has 0% false positive rate (GET requests are not checked)

To run the CSRF check manually:

```bash
# Check all JavaScript files
./scripts/security/check_csrf.sh

# Run accuracy test suite
./scripts/security/test_check_csrf_accuracy.sh
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
