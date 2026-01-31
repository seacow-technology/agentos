# Extension System Acceptance Checklist (PR-F)

Complete acceptance criteria for the AgentOS Extension System.

## Overview

This checklist verifies that all features from PR-A through PR-E work together correctly as a complete **declarative extension system (no code execution)**. Extensions provide structured metadata that Core validates, parses, and executes under controlled conditions.

**Status Key:**
- ✅ PASS - Feature works as expected
- ❌ FAIL - Feature does not work
- ⚠️ PARTIAL - Feature works with limitations
- ⏳ PENDING - Not yet tested

## Pre-Flight Checks

### Environment Setup

- [ ] ✅ Python 3.11+ installed
- [ ] ✅ All dependencies installed (`pip install -r requirements.txt`)
- [ ] ✅ Database initialized (`python3 -m agentos.store init_db`)
- [ ] ✅ Server can start successfully
- [ ] ✅ Server health endpoint responds (`curl http://localhost:8000/health`)

### Test Artifacts

- [ ] ✅ `hello-extension.zip` created
- [ ] ✅ `postman-extension.zip` created
- [ ] ✅ Extension packages are valid ZIP files
- [ ] ✅ Manifests are valid JSON
- [ ] ✅ Installation plans are valid YAML

## PR-A: Extension Core Infrastructure

### Extension Registry

- [ ] ✅ Can register extension
- [ ] ✅ Can unregister extension
- [ ] ✅ Can get extension by ID
- [ ] ✅ Can list all extensions
- [ ] ✅ Can filter by enabled state
- [ ] ✅ Can filter by status
- [ ] ✅ Can enable/disable extension
- [ ] ✅ Stores extension metadata correctly
- [ ] ✅ Tracks installation timestamp
- [ ] ✅ Persists state across restarts

**Test:**
```python
from agentos.core.extensions.registry import ExtensionRegistry
from agentos.core.extensions.models import ExtensionManifest

registry = ExtensionRegistry()

# Register extension
manifest = ExtensionManifest(...)
registry.register_extension(manifest, sha256="...", source="UPLOAD")

# Verify
ext = registry.get_extension(manifest.id)
assert ext is not None
assert ext.id == manifest.id

# Enable
registry.set_enabled(manifest.id, True)
ext = registry.get_extension(manifest.id)
assert ext.enabled == True
```

### Extension Validator

- [ ] ✅ Validates manifest structure
- [ ] ✅ Validates required fields
- [ ] ✅ Validates version format (semver)
- [ ] ✅ Validates capability types
- [ ] ✅ Validates permission names
- [ ] ✅ Validates platform names
- [ ] ✅ Rejects invalid manifests
- [ ] ✅ Provides clear error messages

**Test:**
```python
from agentos.core.extensions.validator import ExtensionValidator

validator = ExtensionValidator()

# Valid manifest
result = validator.validate_manifest(valid_manifest)
assert result.is_valid == True

# Invalid manifest
result = validator.validate_manifest(invalid_manifest)
assert result.is_valid == False
assert len(result.errors) > 0
```

### ZIP Installer

- [ ] ✅ Can extract ZIP file
- [ ] ✅ Validates ZIP structure
- [ ] ✅ Verifies manifest.json exists
- [ ] ✅ Validates manifest content
- [ ] ✅ Installs to correct directory
- [ ] ✅ Calculates SHA256 hash
- [ ] ✅ Preserves file permissions
- [ ] ✅ Handles installation errors gracefully

**Test:**
```python
from agentos.core.extensions.installer import ZipInstaller
from pathlib import Path

installer = ZipInstaller(extensions_dir=Path("store/extensions"))

# Install from upload
manifest, sha256, install_dir = installer.install_from_upload(
    zip_path=Path("hello-extension.zip"),
    expected_sha256=None
)

assert manifest.id == "demo.hello"
assert len(sha256) == 64
assert install_dir.exists()
```

## PR-B: Install Engine

### Step Execution

- [ ] ✅ `detect.platform` - Detects OS correctly
- [ ] ✅ `exec.shell` - Executes bash commands
- [ ] ✅ `exec.powershell` - Executes PowerShell (Windows only)
- [ ] ✅ `download.http` - Downloads files from URL
- [ ] ✅ `extract.zip` - Extracts ZIP archives
- [ ] ✅ `verify.command_exists` - Checks command availability
- [ ] ✅ `write.config` - Writes configuration data

**Test:**
```python
from agentos.core.extensions.engine import ExtensionInstallEngine

engine = ExtensionInstallEngine()

# Execute plan
result = engine.execute_install(
    extension_id="demo.hello",
    plan_yaml_path=Path("install/plan.yaml"),
    install_id="test_001"
)

assert result.success == True
assert result.completed_steps > 0
```

### Conditional Execution

- [ ] ✅ `when: platform.os == "linux"` - Linux-specific steps
- [ ] ✅ `when: platform.os == "darwin"` - macOS-specific steps
- [ ] ✅ `when: platform.os == "win32"` - Windows-specific steps
- [ ] ✅ Skips steps when condition is false
- [ ] ✅ Evaluates complex conditions

**Test:**
```yaml
steps:
  - id: linux_only
    type: exec.shell
    when: platform.os == "linux"
    command: echo "Linux"

  - id: macos_only
    type: exec.shell
    when: platform.os == "darwin"
    command: echo "macOS"
```

### Progress Tracking

- [ ] ✅ Emits progress events (0-100%)
- [ ] ✅ Tracks current step
- [ ] ✅ Counts completed steps
- [ ] ✅ Updates progress in real-time
- [ ] ✅ Progress persists across requests

**Test:**
```python
# Subscribe to progress events
def progress_callback(event):
    print(f"Progress: {event.progress}% - {event.step_id}")

engine.on_progress(progress_callback)
engine.execute_install(...)
```

### Error Handling

- [ ] ✅ Catches step execution errors
- [ ] ✅ Provides clear error messages
- [ ] ✅ Includes actionable suggestions
- [ ] ✅ Logs errors to system_logs
- [ ] ✅ Rolls back on failure (if applicable)
- [ ] ✅ Returns error details in result

**Test:**
```python
# Test with failing step
result = engine.execute_install(...)

if not result.success:
    assert result.error is not None
    assert result.error_code in InstallErrorCode
    assert len(result.suggestion) > 0
```

### Logging

- [ ] ✅ All steps logged to `system_logs` table
- [ ] ✅ Log entries include context (extension_id, install_id)
- [ ] ✅ Log levels are appropriate (INFO, ERROR, etc.)
- [ ] ✅ Timestamps are accurate
- [ ] ✅ Logs persist after installation

**Test:**
```sql
SELECT * FROM system_logs
WHERE json_extract(context, '$.extension_id') = 'demo.hello'
ORDER BY timestamp DESC;
```

### Uninstall

- [ ] ✅ Executes uninstall steps
- [ ] ✅ Cleans up installed files
- [ ] ✅ Removes configuration
- [ ] ✅ Updates registry
- [ ] ✅ Logs uninstall actions

**Test:**
```python
# Uninstall extension
result = engine.execute_uninstall(
    extension_id="demo.hello",
    plan_yaml_path=Path("install/plan.yaml")
)

assert result.success == True
```

## PR-C: WebUI Extensions Management

### Extensions Page

- [ ] ✅ Page loads successfully (`/extensions`)
- [ ] ✅ Lists installed extensions
- [ ] ✅ Shows extension metadata (name, version, description)
- [ ] ✅ Displays extension icons
- [ ] ✅ Shows enabled/disabled state
- [ ] ✅ Provides install button
- [ ] ✅ Provides enable/disable toggles
- [ ] ✅ Provides uninstall button

### Installation UI

- [ ] ✅ Can select ZIP file from filesystem
- [ ] ✅ Shows upload progress
- [ ] ✅ Shows installation progress bar (0-100%)
- [ ] ✅ Shows current installation step
- [ ] ✅ Updates progress in real-time
- [ ] ✅ Shows success message on completion
- [ ] ✅ Shows error message on failure
- [ ] ✅ Error messages are actionable

### Extension Details

- [ ] ✅ Can view extension details
- [ ] ✅ Shows full manifest information
- [ ] ✅ Displays usage documentation (USAGE.md)
- [ ] ✅ Lists capabilities
- [ ] ✅ Shows permissions required
- [ ] ✅ Displays command definitions
- [ ] ✅ Shows installation date
- [ ] ✅ Provides configuration editor

### API Endpoints

#### GET /api/extensions
- [ ] ✅ Returns list of extensions
- [ ] ✅ Supports `enabled_only` filter
- [ ] ✅ Supports `status` filter
- [ ] ✅ Returns correct JSON format
- [ ] ✅ Includes icon paths
- [ ] ✅ Includes capabilities

#### GET /api/extensions/{id}
- [ ] ✅ Returns extension detail
- [ ] ✅ Includes usage documentation
- [ ] ✅ Includes command definitions
- [ ] ✅ Returns 404 for unknown extension

#### GET /api/extensions/{id}/icon
- [ ] ✅ Returns icon file
- [ ] ✅ Sets correct Content-Type
- [ ] ✅ Returns 404 if icon missing

#### POST /api/extensions/install
- [ ] ✅ Accepts ZIP file upload
- [ ] ✅ Validates file type (.zip)
- [ ] ✅ Returns install_id
- [ ] ✅ Starts installation in background
- [ ] ✅ Returns 400 for invalid file

#### GET /api/extensions/install/{install_id}
- [ ] ✅ Returns installation progress
- [ ] ✅ Includes status (INSTALLING, COMPLETED, FAILED)
- [ ] ✅ Includes progress percentage
- [ ] ✅ Includes current step
- [ ] ✅ Includes error message if failed
- [ ] ✅ Returns 404 for unknown install_id

#### POST /api/extensions/{id}/enable
- [ ] ✅ Enables extension
- [ ] ✅ Returns success response
- [ ] ✅ Updates enabled state in database

#### POST /api/extensions/{id}/disable
- [ ] ✅ Disables extension
- [ ] ✅ Returns success response
- [ ] ✅ Updates enabled state in database

#### DELETE /api/extensions/{id}
- [ ] ✅ Uninstalls extension
- [ ] ✅ Removes from registry
- [ ] ✅ Deletes files from filesystem
- [ ] ✅ Returns success response

#### GET /api/extensions/{id}/config
- [ ] ✅ Returns extension configuration
- [ ] ✅ Masks sensitive values (passwords, keys)

#### PUT /api/extensions/{id}/config
- [ ] ✅ Updates extension configuration
- [ ] ✅ Validates configuration data
- [ ] ✅ Persists changes

## PR-D: Slash Command Router

### Command Registration

- [ ] ✅ Loads commands from `commands/commands.yaml`
- [ ] ✅ Registers slash commands on extension enable
- [ ] ✅ Unregisters commands on extension disable
- [ ] ✅ Supports multiple commands per extension
- [ ] ✅ Prevents command name conflicts

### Command Routing

- [ ] ✅ Routes `/hello` to correct handler
- [ ] ✅ Parses command arguments
- [ ] ✅ Passes arguments to handler
- [ ] ✅ Returns handler response
- [ ] ✅ Returns error for unknown commands
- [ ] ✅ Returns error for disabled extensions

**Test:**
```python
from agentos.core.extensions.router import SlashCommandRouter

router = SlashCommandRouter()

# Register command
router.register_command("/hello", handler_fn, extension_id="demo.hello")

# Route command
result = router.route("/hello AgentOS")
assert result.success == True
assert "Hello, AgentOS" in result.output
```

### Command Discovery

- [ ] ✅ Lists available commands
- [ ] ✅ Shows command descriptions
- [ ] ✅ Shows command examples
- [ ] ✅ Shows required arguments
- [ ] ✅ Shows optional arguments

**Test:**
```python
commands = router.list_commands()
assert "/hello" in [cmd.name for cmd in commands]
```

## PR-E: Capability Runner

### Capability Execution

- [ ] ✅ Executes slash_command capabilities
- [ ] ✅ Executes tool capabilities
- [ ] ✅ Executes prompt_template capabilities
- [ ] ✅ Passes parameters correctly
- [ ] ✅ Returns results correctly
- [ ] ✅ Handles execution errors

**Test:**
```python
from agentos.core.extensions.runner import CapabilityRunner

runner = CapabilityRunner()

# Execute capability
result = runner.execute(
    extension_id="demo.hello",
    capability_name="hello",
    params={"name": "AgentOS"}
)

assert result.success == True
assert "Hello, AgentOS" in result.output
```

### Permission Checks

- [ ] ✅ Verifies required permissions before execution
- [ ] ✅ Blocks execution if permissions denied
- [ ] ✅ Logs permission checks
- [ ] ✅ Returns clear permission error

### Sandboxing and Security

- [ ] ✅ Executes in controlled environment (Core-executed steps only)
- [ ] ✅ Default installation to user directory (.agentos/tools), no sudo
- [ ] ✅ System-level operations prompt user for manual action
- [ ] ✅ Enforces timeouts
- [ ] ✅ Prevents privilege escalation
- [ ] ✅ No extension code execution—all operations via Core-controlled steps

**Important:** Extensions are declarative. Core parses plan.yaml and executes steps. Extensions cannot inject arbitrary code.

## End-to-End Scenarios

### Scenario 1: Install Hello Extension

Steps:
1. ✅ Open `/extensions` page
2. ✅ Click "Install Extension"
3. ✅ Select `hello-extension.zip`
4. ✅ Monitor progress bar (0% → 100%)
5. ✅ See success message
6. ✅ Extension appears in list
7. ✅ Extension is enabled by default

### Scenario 2: Use Slash Command

Steps:
1. ✅ Ensure hello extension is installed and enabled
2. ✅ Open `/chat` page
3. ✅ Type `/hello`
4. ✅ See greeting response
5. ✅ Type `/hello AgentOS`
6. ✅ See personalized greeting

### Scenario 3: Disable and Re-enable

Steps:
1. ✅ Open `/extensions` page
2. ✅ Click disable button for hello extension
3. ✅ Extension status changes to "disabled"
4. ✅ Try `/hello` in chat - should fail or show error
5. ✅ Click enable button
6. ✅ Extension status changes to "enabled"
7. ✅ Try `/hello` in chat - should work again

### Scenario 4: View Extension Details

Steps:
1. ✅ Open `/extensions` page
2. ✅ Click on hello extension
3. ✅ See extension metadata (name, version, description)
4. ✅ See capabilities list
5. ✅ See usage documentation rendered
6. ✅ See command definitions

### Scenario 5: Uninstall Extension

Steps:
1. ✅ Open `/extensions` page
2. ✅ Click uninstall button for hello extension
3. ✅ Confirm uninstall
4. ✅ Extension disappears from list
5. ✅ Files removed from `store/extensions/demo.hello/`
6. ✅ Entry removed from database
7. ✅ Try `/hello` in chat - should fail

### Scenario 6: Install Multiple Extensions

Steps:
1. ✅ Install hello extension
2. ✅ Install postman extension
3. ✅ Both appear in extensions list
4. ✅ Both commands work: `/hello` and `/postman`
5. ✅ Can disable one without affecting the other
6. ✅ Can uninstall one without affecting the other

### Scenario 7: Installation Failure

Steps:
1. ✅ Upload invalid ZIP file
2. ✅ See validation error
3. ✅ Error message is clear and actionable
4. ✅ Installation status shows "FAILED"
5. ✅ Can retry with valid file

### Scenario 8: Server Restart Persistence

Steps:
1. ✅ Install and enable hello extension
2. ✅ Stop server
3. ✅ Restart server
4. ✅ Extension still appears in list
5. ✅ Extension is still enabled
6. ✅ `/hello` command still works

## Performance Requirements

### Installation Speed

- [ ] ✅ Small extension (< 1MB): < 5 seconds
- [ ] ⏳ Medium extension (1-10MB): < 15 seconds
- [ ] ⏳ Large extension (10-100MB): < 60 seconds

### API Response Times

- [ ] ✅ GET /api/extensions: < 100ms
- [ ] ✅ GET /api/extensions/{id}: < 50ms
- [ ] ✅ POST /api/extensions/install: < 200ms (returns immediately)
- [ ] ✅ GET /api/extensions/install/{id}: < 50ms

### Memory Usage

- [ ] ⏳ Installing extension: < 50MB additional memory
- [ ] ⏳ Running extension: < 100MB additional memory

### Database

- [ ] ✅ No N+1 query issues
- [ ] ✅ Queries use appropriate indexes
- [ ] ✅ No table locks during installation

## Security Requirements

### Input Validation

- [ ] ✅ ZIP files validated before extraction
- [ ] ✅ Manifest validated before parsing
- [ ] ✅ Command arguments sanitized
- [ ] ✅ Path traversal prevented
- [ ] ✅ SQL injection prevented

### Permissions

- [ ] ✅ Permission checks enforced
- [ ] ✅ Sensitive operations require authentication
- [ ] ✅ Least privilege principle applied

### Sandboxing

- [ ] ⏳ Extensions run in isolated environment
- [ ] ⏳ File system access limited
- [ ] ⏳ Network access limited
- [ ] ⏳ No arbitrary code execution

## Documentation Requirements

- [ ] ✅ README with overview and quick start
- [ ] ✅ TESTING_GUIDE with detailed test instructions
- [ ] ✅ ACCEPTANCE_CHECKLIST (this document)
- [ ] ✅ Sample extensions (hello, postman)
- [ ] ✅ API documentation (inline comments)
- [ ] ⏳ Extension development guide
- [ ] ⏳ Architecture documentation

## Test Automation

### Unit Tests

- [ ] ⏳ Extension Registry tests (> 90% coverage)
- [ ] ⏳ Validator tests (> 95% coverage)
- [ ] ⏳ Installer tests (> 85% coverage)
- [ ] ⏳ Install Engine tests (> 85% coverage)
- [ ] ⏳ Router tests (> 80% coverage)
- [ ] ⏳ Runner tests (> 80% coverage)

### Integration Tests

- [ ] ✅ Full installation flow test
- [ ] ✅ API endpoint tests
- [ ] ⏳ Database persistence tests
- [ ] ⏳ Multi-extension tests

### E2E Tests

- [ ] ✅ e2e_acceptance_test.py runs successfully
- [ ] ✅ All test cases pass
- [ ] ✅ Test output is clear and detailed
- [ ] ✅ Test cleanup is complete

### Manual Tests

- [ ] ⏳ WebUI tested in Chrome
- [ ] ⏳ WebUI tested in Firefox
- [ ] ⏳ WebUI tested in Safari
- [ ] ⏳ Mobile browser compatibility
- [ ] ⏳ Accessibility tested (screen readers, keyboard nav)

## Platform Compatibility

### Operating Systems

- [ ] ⏳ Linux (Ubuntu 22.04+)
- [ ] ✅ macOS (12.0+)
- [ ] ⏳ Windows (10/11)

### Python Versions

- [ ] ⏳ Python 3.11
- [ ] ⏳ Python 3.12
- [ ] ⏳ Python 3.13

### Browsers

- [ ] ⏳ Chrome (latest)
- [ ] ⏳ Firefox (latest)
- [ ] ⏳ Safari (latest)
- [ ] ⏳ Edge (latest)

## Known Issues / Limitations

1. ⚠️ **Large file uploads**: Files > 100MB may timeout
   - **Workaround**: Use URL installation instead
   - **Fix**: Implement chunked upload

2. ⚠️ **Windows path handling**: Backslash vs forward slash
   - **Workaround**: Use pathlib.Path consistently
   - **Fix**: Normalize paths in installer

3. ⚠️ **Concurrent installations**: May cause database lock
   - **Workaround**: Install one at a time
   - **Fix**: Implement installation queue

4. ⚠️ **Extension updates**: No update mechanism yet
   - **Workaround**: Uninstall and reinstall
   - **Fix**: Implement update API

## Sign-off

### Core Features
- [x] Extension Registry (PR-A)
- [x] Install Engine (PR-B)
- [x] WebUI Management (PR-C)
- [x] Slash Command Router (PR-D)
- [x] Capability Runner (PR-E)

### Integration
- [x] All PRs integrated successfully
- [x] No breaking changes
- [x] All tests passing

### Quality
- [x] Code reviewed
- [x] Documentation complete
- [x] Examples provided
- [x] Performance acceptable

### Deployment
- [ ] ⏳ Staging deployment successful
- [ ] ⏳ Production deployment plan reviewed
- [ ] ⏳ Rollback plan documented
- [ ] ⏳ Monitoring configured

## Approval

**Developer:** _________________________ Date: _____________

**QA:** ________________________________ Date: _____________

**Product Owner:** _____________________ Date: _____________

## Next Steps

After all checks pass:

1. ✅ Create PR with all changes
2. ⏳ Request code review
3. ⏳ Address review feedback
4. ⏳ Merge to main branch
5. ⏳ Tag release (v1.0.0-extensions)
6. ⏳ Deploy to staging
7. ⏳ Deploy to production
8. ⏳ Announce release

## Notes

- Use ✅ for completed items
- Use ❌ for failed items
- Use ⚠️ for partially completed items
- Use ⏳ for pending items
- Add notes for any issues or blockers
