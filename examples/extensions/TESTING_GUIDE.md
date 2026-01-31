# Extension System Testing Guide

Complete guide for testing the AgentOS Extension System.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Test Environments](#test-environments)
3. [Unit Tests](#unit-tests)
4. [Integration Tests](#integration-tests)
5. [End-to-End Tests](#end-to-end-tests)
6. [Manual Testing](#manual-testing)
7. [Performance Testing](#performance-testing)
8. [Security Testing](#security-testing)
9. [Troubleshooting](#troubleshooting)

## Quick Start

### 1. Create Extension Packages

```bash
cd /Users/pangge/PycharmProjects/AgentOS/examples/extensions
python3 create_extensions.py
```

Output:
```
✓ Created: hello-extension.zip
✓ Created: postman-extension.zip
```

### 2. Start Server

```bash
cd /Users/pangge/PycharmProjects/AgentOS
python3 -m agentos.webui.server
```

### 3. Run E2E Tests

```bash
cd /Users/pangge/PycharmProjects/AgentOS/examples/extensions
python3 e2e_acceptance_test.py --verbose
```

## Test Environments

### Development Environment

- **Server**: `http://localhost:8000`
- **Database**: `store/registry.sqlite` (local)
- **Extensions**: `store/extensions/` (local)
- **Logs**: `logs/agentos.log`

### Testing Environment

- **Server**: `http://localhost:8001` (separate port)
- **Database**: `test_store/registry.sqlite` (isolated)
- **Extensions**: `test_store/extensions/` (isolated)
- **Logs**: `test_logs/agentos.log`

### CI/CD Environment

- **Server**: Docker container
- **Database**: In-memory SQLite
- **Extensions**: Temporary directory
- **Logs**: stdout/stderr

## Unit Tests

### Extension Validator Tests

Test manifest validation:

```bash
cd /Users/pangge/PycharmProjects/AgentOS
python3 -m pytest tests/unit/core/extensions/test_validator.py -v
```

**Test cases:**
- Valid manifest validation
- Invalid manifest rejection
- Missing required fields
- Invalid version format
- Invalid capability types
- Platform validation

### Extension Registry Tests

Test registry operations:

```bash
python3 -m pytest tests/unit/core/extensions/test_registry.py -v
```

**Test cases:**
- Register extension
- Unregister extension
- Get extension by ID
- List extensions with filters
- Enable/disable extensions
- Configuration management

### Install Engine Tests

Test installation engine:

```bash
python3 -m pytest tests/unit/core/extensions/test_engine.py -v
```

**Test cases:**
- Execute all step types
- Conditional execution
- Progress tracking
- Error handling
- Timeout handling
- Uninstall operations

### Step Executor Tests

Test individual step executors:

```bash
python3 -m pytest tests/unit/core/extensions/steps/ -v
```

**Test cases:**
- Platform detection
- Shell command execution
- PowerShell command execution
- HTTP download
- ZIP extraction
- File verification
- Configuration writing

## Integration Tests

### Full Installation Flow

Test complete installation:

```bash
python3 acceptance_test.py
```

**Test coverage:**
- ZIP upload
- Manifest validation
- Plan execution
- Progress events
- Registry updates
- File operations

### Extension Lifecycle

Test full lifecycle:

```bash
python3 -c "
from pathlib import Path
from agentos.core.extensions.registry import ExtensionRegistry
from agentos.core.extensions.installer import ZipInstaller
from agentos.core.extensions.engine import ExtensionInstallEngine

# Initialize components
registry = ExtensionRegistry()
installer = ZipInstaller(extensions_dir=Path('store/extensions'))
engine = ExtensionInstallEngine(registry=registry)

# Install
manifest, sha256, install_dir = installer.install_from_upload(
    zip_path=Path('hello-extension.zip'),
    expected_sha256=None
)

# Execute plan
result = engine.execute_install(
    extension_id=manifest.id,
    plan_yaml_path=install_dir / manifest.install.plan,
    install_id='test_001'
)

# Register
registry.register_extension(
    manifest=manifest,
    sha256=sha256,
    source='UPLOAD',
    source_url=None,
    icon_path=manifest.icon
)

# Enable
registry.set_enabled(manifest.id, True)

# Verify
ext = registry.get_extension(manifest.id)
assert ext.enabled == True

print('✓ Lifecycle test passed')
"
```

### Cross-Platform Tests

Test on different platforms. **Cross-platform support is implemented through plan.yaml conditional steps** (e.g., `when: platform.os == "linux"`). Extensions must provide platform-specific installation steps for each supported OS.

**Linux:**
```bash
uname -s  # Linux
python3 e2e_acceptance_test.py
```

**macOS:**
```bash
uname -s  # Darwin
python3 e2e_acceptance_test.py
```

**Windows:**
```powershell
$env:OS  # Windows_NT
python e2e_acceptance_test.py
```

**Testing Platform Conditions:**
Extensions should include conditional steps in plan.yaml for each platform. Core detects platform and executes appropriate steps.

## End-to-End Tests

### Complete E2E Test

Run full acceptance test:

```bash
python3 e2e_acceptance_test.py --verbose
```

**Test flow:**
1. Server health check
2. List extensions (initial)
3. Upload extension ZIP
4. Monitor installation progress
5. Verify installation completed
6. Get extension details
7. Enable extension
8. Test slash command (manual)
9. Disable extension
10. Uninstall extension
11. Verify cleanup

### Multiple Extensions Test

Test installing multiple extensions:

```bash
# Install hello
python3 -c "
import requests
with open('hello-extension.zip', 'rb') as f:
    resp = requests.post('http://localhost:8000/api/extensions/install',
                        files={'file': f})
    print(f'Hello: {resp.json()}')
"

# Install postman
python3 -c "
import requests
with open('postman-extension.zip', 'rb') as f:
    resp = requests.post('http://localhost:8000/api/extensions/install',
                        files={'file': f})
    print(f'Postman: {resp.json()}')
"

# List all
curl http://localhost:8000/api/extensions | jq '.extensions[].id'
```

### Concurrent Installation Test

Test concurrent installs:

```bash
# Start multiple installs simultaneously
for i in {1..3}; do
  curl -X POST http://localhost:8000/api/extensions/install \
    -F "file=@hello-extension.zip" &
done
wait

# Check results
curl http://localhost:8000/api/extensions | jq
```

## Manual Testing

### WebUI Testing

1. **Open Extensions page:**
   ```
   http://localhost:8000/extensions
   ```

2. **Test installation:**
   - Click "Install Extension"
   - Select `hello-extension.zip`
   - Watch progress bar
   - Verify success message

3. **Test details view:**
   - Click on installed extension
   - Verify all fields displayed
   - Check documentation rendered
   - View capabilities list

4. **Test enable/disable:**
   - Toggle extension state
   - Verify UI updates
   - Check slash commands available

5. **Test configuration:**
   - Open configuration modal
   - Update config values
   - Save and verify

6. **Test uninstall:**
   - Click "Uninstall"
   - Confirm action
   - Verify removed from list

### Chat Testing

Test slash commands in chat:

1. **Install hello extension:**
   ```
   http://localhost:8000/extensions
   Install hello-extension.zip
   ```

2. **Open chat:**
   ```
   http://localhost:8000/chat
   ```

3. **Test commands:**
   ```
   /hello
   /hello AgentOS
   /hello "World of Extensions"
   ```

4. **Verify responses:**
   - Check output format
   - Verify extension metadata
   - Check error handling

### API Testing

Test REST API endpoints:

```bash
# Health check
curl http://localhost:8000/health

# List extensions
curl http://localhost:8000/api/extensions | jq

# Get extension detail
curl http://localhost:8000/api/extensions/demo.hello | jq

# Get icon
curl http://localhost:8000/api/extensions/demo.hello/icon -o icon.png

# Get config
curl http://localhost:8000/api/extensions/demo.hello/config | jq

# Update config
curl -X PUT http://localhost:8000/api/extensions/demo.hello/config \
  -H "Content-Type: application/json" \
  -d '{"config": {"key": "value"}}' | jq

# Enable
curl -X POST http://localhost:8000/api/extensions/demo.hello/enable | jq

# Disable
curl -X POST http://localhost:8000/api/extensions/demo.hello/disable | jq

# Uninstall
curl -X DELETE http://localhost:8000/api/extensions/demo.hello | jq
```

## Performance Testing

### Installation Speed

Measure installation time:

```bash
time python3 -c "
import requests
with open('hello-extension.zip', 'rb') as f:
    resp = requests.post('http://localhost:8000/api/extensions/install',
                        files={'file': f})
    install_id = resp.json()['install_id']

import time
while True:
    resp = requests.get(f'http://localhost:8000/api/extensions/install/{install_id}')
    status = resp.json()['status']
    if status in ('COMPLETED', 'FAILED'):
        break
    time.sleep(0.1)
"
```

Expected: < 5 seconds for hello extension

### Large Extension Test

Test with large extension:

```bash
# Create large extension (100MB)
dd if=/dev/urandom of=large_file bs=1M count=100
zip large-extension.zip large_file manifest.json

# Test upload
time curl -X POST http://localhost:8000/api/extensions/install \
  -F "file=@large-extension.zip"
```

Expected: < 30 seconds for 100MB

### Concurrent Operations

Test concurrent API calls:

```bash
# 10 concurrent list requests
ab -n 100 -c 10 http://localhost:8000/api/extensions/

# Expected: All succeed, no errors
```

## Security Testing

### Malicious ZIP Test

Test ZIP bomb protection:

```bash
# Create ZIP bomb (42.zip equivalent)
# Should be rejected by validator
```

### Path Traversal Test

Test path traversal in manifest:

```json
{
  "id": "../../../etc/passwd",
  "install": {
    "plan": "../../../etc/shadow"
  }
}
```

Expected: Validation fails with error

### Command Injection Test

Test command injection in install plan:

```yaml
steps:
  - action: exec.shell
    command: "echo hello; rm -rf /"
```

Expected: Sandboxed execution prevents damage

### Permission Validation Test

Test permission requirements:

```json
{
  "permissions_required": ["network", "filesystem.write"]
}
```

Verify:
- User is prompted for permissions
- Installation fails if denied
- Permissions are enforced at runtime

## Troubleshooting

### Test Failures

#### Server Connection Failed

**Symptom:**
```
✗ Cannot connect to server
```

**Solutions:**
1. Check server is running:
   ```bash
   ps aux | grep "agentos.webui.server"
   ```

2. Check port is available:
   ```bash
   lsof -i :8000
   ```

3. Check logs:
   ```bash
   tail -f logs/agentos.log
   ```

#### Installation Timeout

**Symptom:**
```
✗ Installation timeout
```

**Solutions:**
1. Increase timeout in test:
   ```python
   timeout=120  # 2 minutes
   ```

2. Check disk space:
   ```bash
   df -h
   ```

3. Check server load:
   ```bash
   top
   ```

#### Extension Not Found

**Symptom:**
```
✗ Extension package not found
```

**Solutions:**
1. Generate packages:
   ```bash
   python3 create_extensions.py
   ```

2. Check file exists:
   ```bash
   ls -lh *.zip
   ```

3. Use absolute path:
   ```bash
   python3 e2e_acceptance_test.py \
     --extension /full/path/to/extension.zip
   ```

### Debug Mode

Enable verbose logging:

```bash
# Server with debug logging
DEBUG=1 python3 -m agentos.webui.server

# Tests with verbose output
python3 e2e_acceptance_test.py --verbose

# Python logging
export PYTHONPATH=/Users/pangge/PycharmProjects/AgentOS
python3 -c "
import logging
logging.basicConfig(level=logging.DEBUG)
# ... run test code ...
"
```

### Database Issues

Reset database:

```bash
# Backup current database
cp store/registry.sqlite store/registry.sqlite.bak

# Reinitialize
python3 -c "
from agentos.store import init_db
init_db()
"

# Verify
sqlite3 store/registry.sqlite ".tables"
```

### Extension Cleanup

Remove all extensions:

```bash
# Via API
curl -X DELETE http://localhost:8000/api/extensions/demo.hello
curl -X DELETE http://localhost:8000/api/extensions/tools.postman

# Via filesystem
rm -rf store/extensions/*

# Via database
sqlite3 store/registry.sqlite "DELETE FROM extensions"
```

## Continuous Integration

### GitHub Actions

Example workflow:

```yaml
name: Extension System Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest requests

      - name: Initialize database
        run: |
          python3 -m agentos.store init_db

      - name: Create extensions
        run: |
          cd examples/extensions
          python3 create_extensions.py

      - name: Start server
        run: |
          python3 -m agentos.webui.server &
          sleep 5

      - name: Run E2E tests
        run: |
          cd examples/extensions
          python3 e2e_acceptance_test.py --verbose

      - name: Upload logs
        if: failure()
        uses: actions/upload-artifact@v3
        with:
          name: logs
          path: logs/
```

## Test Coverage

### Coverage Report

Generate coverage report:

```bash
# Install coverage tool
pip install coverage

# Run tests with coverage
coverage run -m pytest tests/

# Generate report
coverage report
coverage html

# View report
open htmlcov/index.html
```

Expected coverage:
- Extension Registry: > 90%
- Install Engine: > 85%
- Validators: > 95%
- API Endpoints: > 80%

### Coverage Goals

**Critical paths (must be 100%):**
- Manifest validation
- Security checks
- Permission verification
- Error handling

**Important paths (should be > 90%):**
- Installation flow
- Registry operations
- Step execution
- Progress tracking

**Nice to have (> 70%):**
- UI interactions
- Documentation
- Examples

## Reporting Issues

When reporting test failures, include:

1. **Test command:**
   ```bash
   python3 e2e_acceptance_test.py --verbose
   ```

2. **Error output:**
   ```
   ✗ Installation failed
     Error: ...
   ```

3. **Server logs:**
   ```bash
   tail -100 logs/agentos.log
   ```

4. **Environment:**
   - OS: `uname -a`
   - Python: `python3 --version`
   - Database: `sqlite3 --version`

5. **Steps to reproduce:**
   1. Start server
   2. Run test command
   3. Observe failure

## Best Practices

1. **Always test on clean database:**
   ```bash
   rm store/registry.sqlite
   python3 -m agentos.store init_db
   ```

2. **Use isolated environments:**
   ```bash
   python3 -m venv test_env
   source test_env/bin/activate
   ```

3. **Check server logs:**
   ```bash
   tail -f logs/agentos.log
   ```

4. **Verify cleanup:**
   ```bash
   ls -la store/extensions/
   ```

5. **Test edge cases:**
   - Empty extensions list
   - Duplicate installations
   - Network failures
   - Disk full scenarios

## Next Steps

After all tests pass:

1. **Review code coverage**
2. **Update documentation**
3. **Create PR with test results**
4. **Tag release version**
5. **Deploy to production**

## Support

For help with testing:
- Documentation: `/docs/extensions/`
- Issues: GitHub Issues
- Logs: `logs/agentos.log`
- Community: Discord/Slack
