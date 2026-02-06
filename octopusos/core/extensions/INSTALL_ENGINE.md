# Extension Install Engine

The Extension Install Engine is a controlled execution engine that runs extension install/uninstall plans in a secure, observable, and reliable manner.

## Features

- **Declarative Execution**: Extensions declare steps, the engine executes them safely
- **Sandboxed Environment**: Command execution with PATH/ENV restrictions
- **Real-time Progress**: 0-100% progress tracking with step-by-step updates
- **Full Audit Trail**: All steps logged to system_logs and task_audits
- **Standardized Errors**: Clear error codes and actionable hints
- **Platform Support**: Cross-platform with conditional step execution

## Supported Step Types

### 1. `detect.platform`

Detects the operating system and architecture.

```yaml
- id: detect_platform
  type: detect.platform
```

**Variables Set:**
- `platform.os`: Operating system (linux, darwin, win32)
- `platform.arch`: Architecture (x64, arm64)

### 2. `download.http`

Downloads a file from a URL with optional SHA256 verification.

```yaml
- id: download_cli
  type: download.http
  url: https://example.com/tool.zip
  sha256: abc123...
  target: downloads/tool.zip
  timeout: 300
```

**Required Fields:**
- `url`: Download URL
- `target`: Target file path (relative to work directory)

**Optional Fields:**
- `sha256`: Expected SHA256 hash for verification
- `timeout`: Download timeout in seconds (default: 300)

### 3. `extract.zip`

Extracts a zip file to a target directory.

```yaml
- id: extract_tool
  type: extract.zip
  source: downloads/tool.zip
  target: bin/
```

**Required Fields:**
- `source`: Source zip file path
- `target`: Target extraction directory (optional, defaults to work dir)

### 4. `exec.shell`

Executes a shell command (Linux/macOS).

```yaml
- id: install_dependencies
  type: exec.shell
  command: |
    npm install -g postman-cli
    postman --version
  timeout: 600
```

**Required Fields:**
- `command`: Shell command to execute

**Optional Fields:**
- `timeout`: Execution timeout in seconds (default: 300)

**Security Restrictions:**
- Working directory: `.agentos/extensions/<extension_id>/work/`
- PATH: System paths + `~/.agentos/bin/`
- ENV: Whitelist only (HOME, USER, PATH, etc.)

### 5. `exec.powershell`

Executes a PowerShell command (Windows).

```yaml
- id: install_windows
  type: exec.powershell
  command: |
    Write-Host "Installing tool..."
    choco install postman
```

**Required Fields:**
- `command`: PowerShell command to execute

**Optional Fields:**
- `timeout`: Execution timeout in seconds (default: 300)

### 6. `verify.command_exists`

Verifies that a command is available in PATH.

```yaml
- id: verify_installation
  type: verify.command_exists
  command: postman
```

**Required Fields:**
- `command`: Command name to verify

### 7. `verify.http`

Performs an HTTP health check.

```yaml
- id: verify_service
  type: verify.http
  url: http://localhost:8080/health
  timeout: 30
```

**Required Fields:**
- `url`: URL to check

**Optional Fields:**
- `timeout`: Request timeout in seconds (default: 30)

### 8. `write.config`

Writes a configuration key-value pair to the extension's config.

```yaml
- id: save_path
  type: write.config
  config_key: installation_path
  config_value: /usr/local/bin/postman
```

**Required Fields:**
- `config_key`: Configuration key
- `config_value`: Configuration value

**Storage:** Config is saved to `.agentos/extensions/<extension_id>/work/config.json`

## Conditional Execution

Steps can be conditionally executed based on the platform:

```yaml
- id: install_linux
  type: exec.shell
  when: platform.os == "linux"
  command: apt-get install -y tool

- id: install_macos
  type: exec.shell
  when: platform.os == "darwin"
  command: brew install tool

- id: install_windows
  type: exec.powershell
  when: platform.os == "win32"
  command: choco install tool
```

**Supported Conditions:**
- `platform.os == "linux"`
- `platform.os == "darwin"`
- `platform.os == "win32"`
- `platform.arch == "x64"`
- `platform.arch == "arm64"`

## Permissions

Steps can declare required permissions:

```yaml
- id: install_tool
  type: exec.shell
  requires_permissions: ["exec", "network"]
  command: curl -O https://example.com/tool.sh && bash tool.sh
```

**Available Permissions:**
- `exec`: Execute shell commands
- `network`: Network access
- `filesystem.write`: Write to filesystem
- `filesystem.read`: Read from filesystem

## Complete Example

```yaml
id: tools.postman
steps:
  # Step 1: Detect platform
  - id: detect_platform
    type: detect.platform

  # Step 2: Install on Linux
  - id: install_postman_cli_linux
    type: exec.shell
    when: platform.os == "linux"
    requires_permissions: ["exec", "network"]
    command: |
      echo "Installing Postman CLI on Linux..."
      curl -o /tmp/postman.tar.gz \
        https://dl.pstmn.io/download/latest/linux64
      tar -xzf /tmp/postman.tar.gz -C ~/.agentos/bin/

  # Step 3: Install on macOS
  - id: install_postman_cli_macos
    type: exec.shell
    when: platform.os == "darwin"
    requires_permissions: ["exec"]
    command: |
      echo "Installing Postman CLI on macOS..."
      brew install postman

  # Step 4: Verify installation
  - id: verify
    type: verify.command_exists
    command: postman

  # Step 5: Save config
  - id: save_config
    type: write.config
    config_key: postman_path
    config_value: ~/.agentos/bin/postman

# Uninstall steps
uninstall:
  steps:
    - id: remove_postman_cli
      type: exec.shell
      command: |
        rm -rf ~/.agentos/bin/postman
        echo "Postman CLI removed"
```

## Usage

### Python API

```python
from pathlib import Path
from agentos.core.extensions import ExtensionInstallEngine, ExtensionRegistry

# Initialize engine
registry = ExtensionRegistry()
engine = ExtensionInstallEngine(registry=registry)

# Execute installation
result = engine.execute_install(
    extension_id="tools.postman",
    plan_yaml_path=Path(".agentos/extensions/tools.postman/install/plan.yaml"),
    install_id="inst_12345"
)

if result.success:
    print(f"Installation completed: {len(result.completed_steps)} steps")
else:
    print(f"Installation failed at step: {result.failed_step}")
    print(f"Error: {result.error}")
    print(f"Hint: {result.hint}")

# Check progress
progress = engine.get_install_progress("inst_12345")
print(f"Progress: {progress.progress}% ({progress.completed_steps}/{progress.total_steps})")

# Execute uninstallation
result = engine.execute_uninstall(
    extension_id="tools.postman",
    plan_yaml_path=Path(".agentos/extensions/tools.postman/install/plan.yaml"),
    install_id="uninst_67890"
)
```

## Error Codes

| Error Code | Description | Hint |
|------------|-------------|------|
| `PLATFORM_NOT_SUPPORTED` | Platform not supported by extension | Check manifest.json platforms field |
| `PERMISSION_DENIED` | Required permission not granted | Review and grant required permissions |
| `COMMAND_FAILED` | Shell command failed | Check command syntax and dependencies |
| `DOWNLOAD_FAILED` | File download failed | Check network connectivity and URL |
| `VERIFICATION_FAILED` | Verification check failed | Ensure dependencies are installed |
| `TIMEOUT` | Operation timed out | Increase timeout or optimize operation |
| `INVALID_PLAN` | Invalid plan.yaml format | Check YAML syntax and structure |
| `CONDITION_ERROR` | Condition evaluation failed | Check condition syntax |
| `UNKNOWN` | Unknown error | Check logs for details |

## Progress Tracking

Progress is calculated as:

```
progress = (completed_steps / total_steps) * 100
```

Progress updates are written to the `extension_installs` table:

```sql
SELECT install_id, extension_id, status, progress, current_step
FROM extension_installs
WHERE install_id = 'inst_12345';
```

## Audit Trail

All step executions are logged to:

### 1. System Logs

```python
{
    "level": "INFO",
    "message": "Extension step executed",
    "context": {
        "extension_id": "tools.postman",
        "install_id": "inst_12345",
        "step_id": "install_postman_cli_linux",
        "step_type": "exec.shell",
        "status": "success",
        "duration_ms": 1234
    }
}
```

### 2. Task Audits

```sql
SELECT event_type, payload, created_at
FROM task_audits
WHERE json_extract(payload, '$.extension_id') = 'tools.postman'
ORDER BY created_at DESC;
```

## Security

### Sandboxed Execution

Commands are executed in a controlled environment with:

- **Restricted PATH**: Only system paths + `~/.agentos/bin/`
- **Restricted ENV**: Whitelist-only environment variables
- **Working Directory**: Scoped to `.agentos/extensions/<extension_id>/work/`
- **Timeout Enforcement**: Prevents runaway processes
- **No Privilege Escalation**: sudo/su disabled by default

### File Access

Extensions can only:
- Read/write files in their work directory
- Execute commands from system PATH
- Download files to their work directory

They CANNOT:
- Access other extensions' directories
- Modify AgentOS core files
- Access user's home directory directly

## Best Practices

1. **Always detect platform first**: Use `detect.platform` as the first step
2. **Use conditional steps**: Write platform-specific installation steps
3. **Verify installations**: Use `verify.command_exists` or `verify.http` after installation
4. **Set reasonable timeouts**: Adjust timeouts based on expected operation duration
5. **Provide clear error messages**: Use descriptive step IDs and commands
6. **Test on all platforms**: Test install/uninstall on Linux, macOS, and Windows
7. **Clean up on uninstall**: Remove all files and configurations in uninstall steps
8. **Use SHA256 verification**: Always verify downloaded files with SHA256 hashes
9. **Log important operations**: Use `write.config` to save important paths/settings
10. **Handle failures gracefully**: Ensure failed installations leave no partial state

## Troubleshooting

### Installation Hangs

**Symptom**: Installation progress stuck at a specific step

**Solution**: Check timeout settings and increase if needed:

```yaml
- id: slow_operation
  type: exec.shell
  command: long-running-command
  timeout: 1800  # 30 minutes
```

### Command Not Found

**Symptom**: `verify.command_exists` fails

**Solution**: Ensure command is in PATH or add to `~/.agentos/bin/`:

```yaml
- id: add_to_path
  type: exec.shell
  command: |
    ln -s /opt/tool/bin/tool ~/.agentos/bin/tool
```

### Permission Denied

**Symptom**: Commands fail with permission errors

**Solution**: Check if step declares required permissions:

```yaml
- id: install_tool
  type: exec.shell
  requires_permissions: ["exec", "network", "filesystem.write"]
  command: install-command
```

### SHA256 Mismatch

**Symptom**: Download fails with SHA256 verification error

**Solution**: Verify the correct SHA256 hash:

```bash
sha256sum downloaded_file.zip
```

Update the plan.yaml with the correct hash.

## Integration with Registry

The install engine integrates with the Extension Registry:

```python
# In registry.py
from agentos.core.extensions.engine import ExtensionInstallEngine

class ExtensionRegistry:
    def install_extension(self, manifest, sha256, install_dir):
        # 1. Create install record
        install_id = f"inst_{uuid.uuid4().hex[:12]}"
        self.create_install_record(install_id, manifest.id)

        # 2. Execute install plan
        engine = ExtensionInstallEngine(registry=self)
        plan_path = install_dir / "install" / "plan.yaml"

        result = engine.execute_install(
            extension_id=manifest.id,
            plan_yaml_path=plan_path,
            install_id=install_id
        )

        # 3. Update extension status
        if result.success:
            self.update_extension_status(manifest.id, ExtensionStatus.INSTALLED)
            self.complete_install(install_id, InstallStatus.COMPLETED)
        else:
            self.update_extension_status(manifest.id, ExtensionStatus.FAILED)
            self.complete_install(install_id, InstallStatus.FAILED, result.error)

        return result
```

## Future Enhancements

- [ ] Step dependencies (require/depends_on)
- [ ] Rollback support (automatic cleanup on failure)
- [ ] Retry logic for transient failures
- [ ] Parallel step execution
- [ ] Custom step types via plugins
- [ ] Interactive prompts (for user input)
- [ ] Progress callbacks (for real-time UI updates)
- [ ] Docker container execution
- [ ] Network isolation options
- [ ] Resource limits (CPU, memory, disk)
