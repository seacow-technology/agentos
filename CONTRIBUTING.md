# Contributing to AgentOS

Thank you for your interest in contributing to AgentOS! We welcome contributions from the community.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [How to Contribute](#how-to-contribute)
- [Pull Request Process](#pull-request-process)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Documentation](#documentation)

## Code of Conduct

This project adheres to a code of conduct that all contributors are expected to follow:

- Be respectful and inclusive
- Focus on constructive feedback
- Assume good intentions
- Accept responsibility for your contributions

## Getting Started

### Prerequisites

- Python 3.13+
- Git
- Basic understanding of async Python and CLI tools

### Development Setup

1. **Fork and Clone**

   ```bash
   git clone https://github.com/YOUR-USERNAME/agentos.git
   cd agentos
   ```

2. **Set Up Environment**

   ```bash
   # Using uv (recommended)
   uv sync

   # Or using pip
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -e ".[dev]"
   ```

3. **Initialize Database**

   ```bash
   uv run agentos init
   ```

4. **Verify Setup**

   ```bash
   uv run agentos doctor
   uv run pytest tests/
   ```

## How to Contribute

### Types of Contributions

We welcome:

- 🐛 Bug fixes
- ✨ New features
- 📝 Documentation improvements
- 🧪 Test coverage improvements
- 🎨 UI/UX enhancements
- 🌍 Translations (i18n)

### Finding Work

- Check [Issues](https://github.com/seacow-technology/agentos/issues) labeled `good first issue`
- Look for `help wanted` labels
- Review the [roadmap](docs/ROADMAP.md) for planned features

### Before You Start

1. **Check existing issues/PRs** to avoid duplicate work
2. **Open an issue** to discuss significant changes before coding
3. **Ask questions** if anything is unclear

## Pull Request Process

### 1. Create a Feature Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/your-bug-fix
```

### 2. Make Your Changes

- Follow the [coding standards](#coding-standards)
- Add tests for new functionality
- Update documentation as needed
- Keep commits atomic and well-described

### 3. Test Your Changes

```bash
# Run all tests
uv run pytest tests/

# Run specific test
uv run pytest tests/test_your_test.py -v

# Run linting
uv run ruff check .
uv run ruff format --check .

# Run database compliance checks
python3 scripts/db_scan_check.py
python3 scripts/code_scan_no_db_literal.py
```

**Database Compliance**: Before committing, ensure your changes comply with the 5-database architecture:
- Only 5 database files are allowed (see `scripts/README_DB_SCAN.md`)
- No hardcoded database paths in code
- Use `component_db_path()` for all database access

### 4. Commit Your Changes

Follow conventional commits format:

```bash
git commit -m "feat: add new feature"
git commit -m "fix: resolve issue with task execution"
git commit -m "docs: update README quickstart"
```

Commit types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `test`: Adding or updating tests
- `refactor`: Code refactoring
- `perf`: Performance improvement
- `chore`: Maintenance tasks

### 5. Push and Create PR

```bash
git push origin feature/your-feature-name
```

Then create a Pull Request on GitHub with:

- **Clear title** describing the change
- **Description** explaining what and why
- **Related issues** (e.g., "Closes #123")
- **Testing done** (how you verified it works)
- **Screenshots** (for UI changes)

### 6. Code Review

- Address reviewer feedback promptly
- Keep discussions respectful and constructive
- Be open to suggestions and improvements

## Coding Standards

### Python Style

We follow PEP 8 with some modifications:

- **Line length**: 100 characters (not 79)
- **Imports**: Organized with `ruff` (automatic sorting)
- **Type hints**: Encouraged for public APIs
- **Docstrings**: Required for public functions/classes

### Code Quality Tools

```bash
# Auto-format code
uv run ruff format .

# Check linting
uv run ruff check .

# Auto-fix linting issues
uv run ruff check --fix .
```

### Architecture Guidelines

AgentOS has strict architectural contracts. Please read:

- [Architecture Contracts](docs/cli/CLI_ARCHITECTURE_CONTRACTS.md) - **Required reading**
- [Validation Layers](docs/architecture/VALIDATION_LAYERS.md)
- [Mode Gates](docs/architecture/MODE_GATES.md)

**Key principles:**

1. **Task-Centric**: All operations create/manage tasks (not ad-hoc execution)
2. **Interruptible**: Tasks must pause at `open_plan` for approval
3. **Auditable**: Every action must have audit trail
4. **Mode-Aware**: Respect execution mode gates
5. **Time-Aware**: Follow Time & Timestamp Contract (see below)

### Time & Timestamp Contract

AgentOS enforces strict time handling rules through CI gates:

**Rules:**

1. ❌ **NEVER** use `datetime.utcnow()` - it's deprecated in Python 3.12+
2. ❌ **NEVER** use `datetime.now()` without timezone parameter
3. ✅ **ALWAYS** use `utc_now()` from `agentos.core.time`

**Example:**

```python
# ❌ Wrong - Will fail CI
from datetime import datetime
timestamp = datetime.utcnow()
timestamp = datetime.now()

# ✅ Correct
from agentos.core.time import utc_now
timestamp = utc_now()

# Additional helpers available:
from agentos.core.time import (
    utc_now_ms,      # Get current time as epoch milliseconds
    utc_now_iso,     # Get current time as ISO 8601 string with Z
    from_epoch_ms,   # Convert epoch ms to datetime
    to_epoch_ms,     # Convert datetime to epoch ms
)
```

**CI Gate:**

The CI pipeline automatically checks for violations using `scripts/gates/gate_datetime_usage.py`. Your PR will fail if you use forbidden patterns.

**Local Testing:**

Run the check locally before pushing:

```bash
bash scripts/gates/check_datetime_usage.sh
```

**Pre-commit Hook (Optional):**

Install pre-commit hooks to catch violations early:

```bash
pip install pre-commit
pre-commit install
```

### CommunicationOS Protocol Freeze (v1)

**⚠️ IMPORTANT: Protocol Frozen as of 2026-02-01** (see [ADR-014](docs/adr/ADR-014-protocol-freeze-v1.md))

The CommunicationOS protocol is **FROZEN v1**. This includes:
- `InboundMessage` and `OutboundMessage` models
- `MessageType` enum values
- `SessionRouter` key formats
- Core routing logic

#### When Extending CommunicationOS Channels

**✅ ALLOWED (No Review Needed):**
- Add custom fields to `metadata` dictionary in messages
- Add channel-specific configuration in `ChannelManifest.metadata`
- Implement custom validation in adapter layer
- Add provider-specific API mappings

**⚠️ REQUIRES REVIEW:**
- Add new optional fields with defaults to InboundMessage/OutboundMessage
- Add new `MessageType` enum values
- Modify field validation rules

**❌ FORBIDDEN (Breaking Changes):**
- Remove or rename frozen fields
- Change frozen field types or semantics
- Modify SessionRouter key formats
- Remove MessageType enum values
- Make optional fields required

#### Extension Example

```python
# ✅ Good: Use metadata for channel-specific data
inbound_msg = InboundMessage(
    channel_id="slack_workspace_123",
    user_key="U12345",
    conversation_key="C67890",
    message_id="msg_001",
    text="Hello",
    metadata={
        "slack_thread_ts": "1234567890.123456",  # Slack-specific
        "slack_team_id": "T12345",
        "is_bot": False,
    }
)

# ❌ Bad: Don't modify frozen fields
# class InboundMessage(BaseModel):
#     channel_id: int  # <- BREAKING: Changed from str to int
```

For detailed guidelines, see:
- [ADR-014: Protocol Freeze](docs/adr/ADR-014-protocol-freeze-v1.md)
- [Channel Adapter Guide](docs/CHANNEL_ADAPTER_CONTRIBUTION_GUIDE.md) (if it exists)

#### Protocol Change Process

If you need a breaking change:
1. Open an issue with detailed rationale
2. Submit RFC (Request for Comments) to community
3. Wait for 14-day review period
4. Backward compatibility analysis required
5. If approved, requires major version bump (v2.0)

### File Organization

```
agentos/
├── cli/                  # CLI commands and interface
├── core/                 # Core orchestration logic
├── webui/                # Web UI components
├── store/                # Database and persistence
├── schemas/              # Data models and validation
├── communicationos/      # CommunicationOS (PROTOCOL FROZEN v1)
│   ├── models.py        # Frozen protocol models
│   ├── session_router.py # Frozen routing logic
│   └── channels/         # Channel adapters (extensible)
└── util/                 # Shared utilities
```

## Testing

### Test Structure

```
tests/
├── unit/         # Unit tests (fast, isolated)
├── integration/  # Integration tests (cross-component)
└── e2e/          # End-to-end tests (full workflows)
```

### Writing Tests

- Use `pytest` framework
- Follow AAA pattern (Arrange, Act, Assert)
- Mock external dependencies (LLM calls, file system when appropriate)
- Add markers for slow tests: `@pytest.mark.slow`

Example:

```python
import pytest
from agentos.core.task import TaskManager

def test_task_creation():
    # Arrange
    manager = TaskManager()

    # Act
    task = manager.create_task("Test task", mode="planning")

    # Assert
    assert task.status == "pending"
    assert task.mode == "planning"
```

### Test Coverage

- Aim for >80% coverage on new code
- Focus on critical paths and error handling
- Run coverage report:

```bash
uv run pytest --cov=agentos --cov-report=html
```

## Documentation

### Types of Documentation

1. **Code Comments**: For complex logic
2. **Docstrings**: For all public APIs
3. **README**: Keep up-to-date with changes
4. **Architecture Docs**: For design decisions
5. **User Guides**: For new features

### Docstring Format

Use Google-style docstrings:

```python
def execute_task(task_id: str, mode: str) -> TaskResult:
    """Execute a task with specified mode.

    Args:
        task_id: Unique task identifier
        mode: Execution mode (planning/implementation)

    Returns:
        TaskResult object with execution status

    Raises:
        TaskNotFoundError: If task_id is invalid
        ModeGateError: If mode transition is invalid
    """
```

### Documentation Updates

Update docs when you:

- Add a new feature (add user guide)
- Change architecture (update architecture docs)
- Modify CLI commands (update CLI reference)
- Fix a bug (add to CHANGELOG)

## Developing Channel Adapters

If you're developing a new Channel Adapter for CommunicationOS, please follow these guidelines:

### Before You Start

1. **Read the Specification** (REQUIRED)
   - 📖 [Channel Adapter Specification v1 (FROZEN)](docs/CHANNEL_ADAPTER_SPECIFICATION_V1.md)
   - This document defines the rules and patterns all adapters must follow
   - **Status: FROZEN** - Changes require RFC and community review

2. **Review Reference Implementations**
   - Slack Adapter: `agentos/communicationos/channels/slack/adapter.py` (recommended template)
   - Telegram Adapter: `agentos/communicationos/channels/telegram/adapter.py` (simple template)
   - Email Adapter: `agentos/communicationos/channels/email/adapter.py` (async template)

### Core Principles (Do NOT Violate)

1. ❌ **Adapter 不解析命令** - Adapters only pass raw text, they do not parse `/help`, `/session`, etc.
2. ❌ **Adapter 不管理 session** - Adapters only provide `user_key` + `conversation_key`, do not calculate `session_id`
3. ❌ **Adapter 不决定执行权限** - Adapters only set security defaults in manifest, do not check permissions at runtime
4. ✅ **Adapter 只做 I/O + 映射** - Adapters only handle I/O and protocol conversion, nothing more

### Required Methods

Every adapter must implement:
- `parse_event()` / `parse_update()` / `parse_message()` - Convert channel event to InboundMessage
- `send_message()` - Send OutboundMessage to channel
- `verify_signature()` / `verify_webhook()` - Verify incoming webhook signatures
- `get_channel_id()` - Return channel identifier

### Testing Requirements

- ✅ Signature verification tests (valid/invalid/missing/replay attack)
- ✅ Event parsing tests (all message types)
- ✅ Bot loop prevention tests
- ✅ Idempotency tests (duplicate events)
- ✅ Message sending tests (success/failure/retry)
- ✅ Thread isolation tests (if threads supported)
- ✅ Test coverage > 80%

### Pre-submission Checklist

Before submitting a PR for a new adapter:

```bash
# 1. Run the adapter specification linter
python scripts/lint_adapter_spec.py agentos/communicationos/channels/your_channel/adapter.py

# 2. Run code quality checks
ruff check agentos/communicationos/channels/your_channel/
ruff format agentos/communicationos/channels/your_channel/

# 3. Run tests
pytest tests/unit/communicationos/channels/your_channel/ -v

# 4. Check test coverage
pytest tests/unit/communicationos/channels/your_channel/ --cov --cov-report=term-missing
```

### Manifest Requirements

Every adapter must include a `manifest.json` with:
- Required configuration fields
- Webhook paths
- Session scope (user/conversation/user_conversation)
- Capabilities (inbound_text, outbound_text, threads, etc.)
- Security defaults (mode, allow_execute, rate_limit, etc.)
- Setup steps (wizard for users)

See examples in existing adapter directories.

### Common Mistakes to Avoid

❌ **DO NOT**:
- Parse commands in adapter (e.g., `if text.startswith('/help')`)
- Calculate session_id in adapter
- Check permissions in adapter (e.g., `if not user_has_permission()`)
- Call LLM in adapter (e.g., `openai.chat.completions.create()`)
- Access database directly in adapter
- Store conversation history in adapter
- Implement auto-reply logic in adapter

✅ **DO**:
- Only convert protocol formats (webhook → InboundMessage)
- Only verify signatures/authentication
- Only send messages (OutboundMessage → webhook)
- Handle channel-specific idempotency/retry/dedup
- Filter bot's own messages (loop prevention)
- Use `utc_now()` from `agentos.core.time` for timestamps

### Directory Structure

```
agentos/communicationos/channels/your_channel/
├── __init__.py
├── adapter.py           # Main adapter implementation
├── client.py           # Optional: API client wrapper
├── manifest.json       # Channel metadata and config
└── README.md          # Quick start guide

tests/unit/communicationos/channels/your_channel/
└── test_adapter.py    # Unit tests
```

### Questions about Adapters?

- 📖 Read the full spec: [CHANNEL_ADAPTER_SPECIFICATION_V1.md](docs/CHANNEL_ADAPTER_SPECIFICATION_V1.md)
- 💬 Ask in [Discussions](https://github.com/seacow-technology/agentos/discussions)
- 🐛 Report issues: [GitHub Issues](https://github.com/seacow-technology/agentos/issues)

---

## Questions?

- 💬 Open a [Discussion](https://github.com/seacow-technology/agentos/discussions)
- 🐛 Report bugs via [Issues](https://github.com/seacow-technology/agentos/issues)
- 📧 Email: dev@seacow.tech (replace with actual contact)

---

Thank you for contributing to AgentOS! 🚀
