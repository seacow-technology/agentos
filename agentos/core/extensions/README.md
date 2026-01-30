# AgentOS Extension System

The Extension system provides a secure, sandboxed plugin architecture for AgentOS.

## Overview

Extensions are capability packages that can be installed to extend AgentOS functionality:
- **Slash Commands**: Add custom chat commands (e.g., `/postman`, `/k6`)
- **Tools**: Add new tools for agents to use
- **Agents**: Add specialized agent types
- **Workflows**: Add pre-built workflow templates

## Core Principles

1. **No Direct System Access**: Extensions cannot directly import/patch AgentOS code
2. **Declarative Only**: Extensions declare capabilities; Core executes them
3. **Sandboxed**: No network/execution permissions by default
4. **Auditable**: All installation steps are tracked
5. **Zip-based**: Only installable via zip packages (local or URL)

## Architecture

### Components

- **`models.py`**: Pydantic data models for manifest, capabilities, etc.
- **`validator.py`**: Validates zip structure, manifest, and content
- **`downloader.py`**: Downloads extensions from URLs with SHA256 verification
- **`installer.py`**: Extracts and installs extension packages
- **`registry.py`**: Database operations for extension management
- **`exceptions.py`**: Custom exception classes

### Database Schema

The system uses three tables:

1. **`extensions`**: Core extension registry
2. **`extension_installs`**: Installation progress tracking
3. **`extension_configs`**: Extension-specific configuration

See `migrations/schema_v33_extensions.sql` for details.

## Extension Package Structure

```
extension-name/
  manifest.json              # Required: Extension metadata
  icon.png                   # Optional: Extension icon
  docs/
    USAGE.md                 # Required: Usage documentation
  install/
    plan.yaml                # Required: Installation plan
  commands/
    commands.yaml            # Required: Command definitions
```

### manifest.json

```json
{
  "id": "tools.postman",
  "name": "Postman Toolkit",
  "version": "0.1.0",
  "description": "API testing toolkit with Postman CLI",
  "author": "Example Corp",
  "license": "Apache-2.0",
  "icon": "icon.png",
  "capabilities": [
    {
      "type": "slash_command",
      "name": "/postman",
      "description": "Run Postman API tests"
    }
  ],
  "permissions_required": ["network", "exec"],
  "platforms": ["linux", "darwin", "win32"],
  "install": {
    "mode": "agentos_managed",
    "plan": "install/plan.yaml"
  },
  "docs": {
    "usage": "docs/USAGE.md"
  }
}
```

### install/plan.yaml

```yaml
steps:
  - action: check_dependency
    command: node --version
    required_version: ">=18.0.0"

  - action: download_binary
    url: https://example.com/postman-cli.tar.gz
    sha256: abc123...
    target: bin/postman

  - action: verify_installation
    command: postman --version
    expected_output: "Postman CLI v10.0.0"
```

### commands/commands.yaml

```yaml
commands:
  - name: /postman
    description: Run Postman API tests
    entrypoint: commands/postman.sh
    args:
      - name: collection
        description: Collection name
        required: true
      - name: environment
        description: Environment name
        required: false
```

## Usage

### Install from Local Zip

```python
from agentos.core.extensions import ZipInstaller, ExtensionRegistry
from agentos.core.extensions.models import InstallSource

# Validate and install
installer = ZipInstaller()
manifest, sha256, install_dir = installer.install_from_upload(
    zip_path=Path("postman-extension.zip")
)

# Register in database
registry = ExtensionRegistry()
record = registry.register_extension(
    manifest=manifest,
    sha256=sha256,
    source=InstallSource.UPLOAD
)
```

### Install from URL

```python
installer = ZipInstaller()
manifest, sha256, install_dir = installer.install_from_url(
    url="https://example.com/postman-extension.zip",
    expected_sha256="abc123..."  # Optional
)

registry = ExtensionRegistry()
record = registry.register_extension(
    manifest=manifest,
    sha256=sha256,
    source=InstallSource.URL,
    source_url="https://example.com/postman-extension.zip"
)
```

### List Extensions

```python
registry = ExtensionRegistry()
extensions = registry.list_extensions(enabled_only=True)

for ext in extensions:
    print(f"{ext.name} v{ext.version} - {ext.status.value}")
```

### Get Enabled Capabilities

```python
registry = ExtensionRegistry()
capabilities = registry.get_enabled_capabilities()

# Returns list of dicts with extension_id
for cap in capabilities:
    print(f"{cap['type']}: {cap['name']} (from {cap['extension_id']})")
```

### Enable/Disable Extensions

```python
registry = ExtensionRegistry()

# Disable
registry.disable_extension("tools.postman")

# Enable
registry.enable_extension("tools.postman")
```

### Uninstall Extension

```python
installer = ZipInstaller()
registry = ExtensionRegistry()

# Remove files
installer.uninstall_extension("tools.postman")

# Update registry
registry.uninstall_extension("tools.postman")
```

## CLI Tool

A CLI tool is provided for testing and management:

```bash
# List extensions
python -m agentos.cli.extensions list

# Install from local zip
python -m agentos.cli.extensions install /path/to/extension.zip

# Install from URL
python -m agentos.cli.extensions install-url https://example.com/ext.zip --sha256 abc123...

# Show extension details
python -m agentos.cli.extensions show tools.postman

# Enable/disable
python -m agentos.cli.extensions enable tools.postman
python -m agentos.cli.extensions disable tools.postman

# Uninstall
python -m agentos.cli.extensions uninstall tools.postman
```

## Security

### Permission System

Extensions must declare required permissions in `manifest.json`:

- `network`: Can make HTTP requests
- `exec`: Can execute system commands
- `filesystem.read`: Can read files
- `filesystem.write`: Can write files

Permissions are checked before any action is executed by Core.

### Sandboxing

- Extensions have **no direct code execution**
- All actions are declarative (install plans, commands)
- Install plans are executed by Core's controlled executor
- No access to AgentOS internals

### Validation

All packages are validated before installation:

1. **Zip Structure**: Exactly one top-level directory, required files present
2. **Size Limits**: Max 50MB package size
3. **Path Traversal**: No `..` or absolute paths allowed
4. **Manifest Schema**: Validated with Pydantic
5. **SHA256**: Optional hash verification for URL downloads

## Testing

Run unit tests:

```bash
pytest tests/unit/core/extensions/ -v
```

Test coverage:
- Models validation (8 tests)
- Validator logic (19 tests)
- Registry CRUD operations (14 tests)

Total: 41 tests, all passing

## Next Steps

This is PR-A (Core Infrastructure). Remaining PRs:

- **PR-B**: Install Engine with progress events
- **PR-C**: WebUI Extensions management page
- **PR-D**: Chat Slash Command routing
- **PR-E**: Capability Runner execution
- **PR-F**: Example extension packages

## Files

```
agentos/core/extensions/
  __init__.py           - Module exports
  models.py             - Pydantic data models (268 lines)
  exceptions.py         - Custom exceptions (27 lines)
  validator.py          - Package validator (314 lines)
  downloader.py         - URL downloader (206 lines)
  installer.py          - Zip installer (226 lines)
  registry.py           - Database registry (535 lines)
  README.md             - This file

agentos/store/migrations/
  schema_v33_extensions.sql  - Database migration (458 lines)

agentos/cli/
  extensions.py         - CLI management tool (324 lines)

tests/unit/core/extensions/
  __init__.py
  test_models.py        - Model tests (155 lines)
  test_validator.py     - Validator tests (249 lines)
  test_registry.py      - Registry tests (375 lines)
```

Total: ~2,800 lines of production code + tests
