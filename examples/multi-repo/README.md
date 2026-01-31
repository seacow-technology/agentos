# Multi-Repository Examples

**Hands-on examples for AgentOS multi-repository projects**

This directory contains practical examples demonstrating multi-repo project patterns.

---

## Available Examples

### 01. Minimal Example

**Path**: `01_minimal/`

**What it demonstrates**:
- Simplest possible multi-repo project
- Two local repositories
- Basic import and verification

**Run it**:
```bash
cd 01_minimal
bash demo.sh
```

**Learn**: Project basics, import workflow

---

### 02. Frontend + Backend Example

**Path**: `02_frontend_backend/`

**What it demonstrates**:
- Realistic full-stack app (React + Python)
- Cross-repo task execution
- Dependency tracking
- Artifact references

**Run it**:
```bash
cd 02_frontend_backend
bash demo.sh
```

**Learn**: Cross-repo dependencies, artifact management

---

### 03. Monorepo Example

**Path**: `03_monorepo/`

**What it demonstrates**:
- Monorepo with subdirectories
- Path-scoped operations
- Isolated package changes
- Shared dependencies

**Run it**:
```bash
cd 03_monorepo
bash demo.sh
```

**Learn**: Monorepo patterns, path filters

---

## Prerequisites

All examples require:

- AgentOS installed (`pip install -e .`)
- Git installed
- Basic CLI knowledge

Some examples may require:

- GitHub account (for remote repos)
- SSH keys configured
- Auth profiles created

---

## Example Structure

Each example contains:

```
example/
  ├── README.md       # Example-specific documentation
  ├── project.yaml    # Project configuration
  ├── demo.sh         # One-click demo script
  └── cleanup.sh      # Cleanup script (if applicable)
```

---

## Running Examples

### Quick Run

```bash
# Run specific example
cd 01_minimal
bash demo.sh
```

### Manual Exploration

```bash
# Navigate to example
cd 01_minimal

# Review configuration
cat project.yaml

# Import manually
agentos project import --from project.yaml

# Explore commands
agentos project repos list minimal-demo
agentos project validate minimal-demo
agentos project trace minimal-demo
```

---

## Learning Path

**Recommended order**:

1. **01_minimal** - Learn project import basics
2. **02_frontend_backend** - Understand cross-repo workflows
3. **03_monorepo** - Master advanced patterns

---

## Troubleshooting

### Demo script fails

**Common causes**:
- AgentOS not installed: `pip install -e .`
- Git not available: `which git`
- Permission issues: `chmod +x demo.sh`

**Solution**: Check prerequisites and error messages

### "Command not found: agentos"

**Solution**:
```bash
# Use uv run
uv run agentos project import --from project.yaml

# Or activate venv
source .venv/bin/activate
```

### Import fails

**Solution**: Review troubleshooting guide:
- [Multi-Repo Troubleshooting](../../docs/troubleshooting/MULTI_REPO.md)

---

## Creating Your Own Example

Use the minimal example as a template:

```bash
# Copy minimal example
cp -r 01_minimal my-custom-example

# Edit configuration
cd my-custom-example
vi project.yaml

# Update demo script
vi demo.sh

# Test
bash demo.sh
```

---

## Resources

- [Multi-Repo Architecture](../../docs/projects/MULTI_REPO_PROJECTS.md)
- [CLI Usage Guide](../../docs/cli/PROJECT_IMPORT.md)
- [Migration Guide](../../docs/migration/SINGLE_TO_MULTI_REPO.md)
- [Troubleshooting](../../docs/troubleshooting/MULTI_REPO.md)

---

**Contributions Welcome!**

Have a useful multi-repo pattern? Submit a PR with a new example!

- 🐛 [Report Issues](https://github.com/your-org/AgentOS/issues)
- 💡 [Suggest Examples](https://github.com/your-org/AgentOS/discussions)
