# Extension System Examples and Testing

This directory contains sample extensions and acceptance tests for the AgentOS Extension System.

## Overview

The Extension System provides a complete solution for extending AgentOS with custom capabilities through **declarative extensions (no code execution)**:
- **Extension Registry**: Tracks installed extensions and their state
- **Install Engine**: Executes Core-controlled installation plans with progress tracking
- **WebUI Management**: Browser-based extension management interface
- **Slash Command Router**: Routes `/command` calls to Core-executed handlers declared in extension
- **Capability Runner**: Executes capabilities based on extension declarations, with Core handling all operations

**Key Security Feature:** Extensions are pure metadata (JSON/YAML). Core validates and executes all operations. No extension code is run.

## Sample Extensions

### 1. Hello Extension (`hello-extension.zip`)

A minimal example demonstrating the basic extension structure.

**Features:**
- Simple slash command: `/hello [name]`
- Minimal installation requirements
- Platform-agnostic
- No external dependencies

**Structure:**
```
hello-extension.zip
├── manifest.json          # Extension metadata
├── icon.png               # Extension icon
├── install/
│   └── plan.yaml          # Installation steps
├── commands/
│   ├── commands.yaml      # Command definitions
│   └── hello.sh           # Command implementation
└── docs/
    └── USAGE.md           # Usage documentation
```

**Usage:**
```
/hello              # Output: "Hello, World!"
/hello AgentOS      # Output: "Hello, AgentOS!"
```

## Creating Extension Packages

Use the `create_extensions.py` script to generate extension packages:

```bash
python3 create_extensions.py
```

This will create:
- `hello-extension.zip` - Minimal example

## Running Acceptance Tests

### Prerequisites

1. **Start the AgentOS server:**
   ```bash
   cd /Users/pangge/PycharmProjects/AgentOS
   python3 -m agentos.webui.server
   ```

2. **Verify server is running:**
   ```bash
   curl http://localhost:8000/health
   ```

### Run Tests

**End-to-End Acceptance Test:**

Tests the complete extension lifecycle:
```bash
python3 e2e_acceptance_test.py --verbose
```

Options:
- `--server URL`: Specify server URL (default: `http://localhost:8000`)
- `--extension PATH`: Specify extension package (default: `hello-extension.zip`)
- `-v, --verbose`: Enable detailed output

**Install Engine Test:**

Tests the installation engine in isolation:
```bash
python3 acceptance_test.py
```

This test verifies:
- All step types execute correctly
- Conditional expressions work
- Progress tracking is accurate
- Error handling is robust
- Logging is complete

## Test Scenarios

The acceptance tests cover these scenarios:

### E2E Test Flow

1. **Server Health Check**
   - Verify server is running
   - Check API availability

2. **List Extensions (Initial)**
   - Get baseline extension count
   - Verify API response format

3. **Install Extension**
   - Upload extension ZIP
   - Get installation ID
   - Monitor progress in real-time

4. **Installation Progress**
   - Poll installation status
   - Track progress percentage
   - Verify completion

5. **Get Extension Detail**
   - Retrieve extension metadata
   - View capabilities
   - Check documentation

6. **Enable Extension**
   - Activate extension
   - Verify enabled state

7. **Disable Extension**
   - Deactivate extension
   - Verify disabled state

8. **Uninstall Extension**
   - Remove extension
   - Clean up files

9. **List Extensions (Final)**
   - Verify uninstall was successful
   - Compare to initial count

### Install Engine Test Flow

1. **All Step Types**
   - `detect.platform`
   - `exec.shell`
   - `verify.command_exists`
   - `download.http`
   - `extract.zip`
   - `write.config`

2. **Conditional Execution**
   - Platform-specific steps
   - Version checks
   - Feature detection

3. **Progress Tracking**
   - Real-time progress updates (0-100%)
   - Step completion tracking
   - Event emission

4. **Error Handling**
   - Clear error messages
   - Actionable suggestions
   - Graceful failure recovery

5. **Logging**
   - All steps logged to `system_logs`
   - Context preservation
   - Audit trail

## Expected Results

### Successful Test Run

```
============================================================
Extension System Acceptance Tests
============================================================
Server: http://localhost:8000
Extension: hello-extension.zip
============================================================

Test 1: Server health check
✓ Server is healthy

Test 2: List extensions (initial)
✓ Listed 0 extensions

Test 3: Install extension from hello-extension.zip
✓ Installation request accepted (install_id: inst_abc123)

Test 4: Monitor installation progress
✓ Installation completed (extension_id: demo.hello)

Test 5: Get extension detail
✓ Retrieved extension details for demo.hello

Test 6: Enable extension
✓ Extension demo.hello enabled

Test 7: Disable extension
✓ Extension demo.hello disabled

Test 8: Uninstall extension
✓ Extension demo.hello uninstalled

Test 9: List extensions (final verification)
✓ Extension count matches initial state (uninstall verified)

============================================================
Test Summary
============================================================
Total: 9
Passed: 9
Failed: 0
Success Rate: 100.0%
============================================================

✓ ALL TESTS PASSED!
```

## Troubleshooting

### Server Not Running

**Error:**
```
✗ Cannot connect to server
  Error: Is the server running at http://localhost:8000?
```

**Solution:**
```bash
python3 -m agentos.webui.server
```

### Extension Package Not Found

**Error:**
```
✗ Extension package not found: hello-extension.zip
```

**Solution:**
```bash
python3 create_extensions.py
```

### Installation Timeout

**Error:**
```
✗ Installation timeout
  Error: No response after 60 seconds
```

**Possible causes:**
- Network issues (for URL downloads)
- Slow disk I/O
- Large extension package

**Solution:**
- Increase timeout in test script
- Check server logs for errors
- Verify disk space

### Permission Denied

**Error:**
```
Installation failed: Permission denied
```

**Solution:**
- Check file permissions on `store/extensions/` directory
- Run with appropriate user permissions
- Verify write access to temporary directory

## Manual Testing

You can also test extensions manually via the WebUI:

1. **Open the Extensions page:**
   ```
   http://localhost:8000/extensions
   ```

2. **Upload an extension:**
   - Click "Install Extension"
   - Select `hello-extension.zip`
   - Monitor installation progress

3. **View extension details:**
   - Click on the installed extension
   - View capabilities, documentation, and configuration

4. **Test slash commands:**
   - Go to Chat page
   - Type `/hello AgentOS`
   - Verify response

5. **Disable/Enable:**
   - Toggle extension state
   - Verify commands are (un)available

6. **Uninstall:**
   - Click "Uninstall"
   - Confirm deletion
   - Verify files are removed

## API Testing with cURL

### List Extensions

```bash
curl http://localhost:8000/api/extensions | jq
```

### Install Extension

```bash
curl -X POST http://localhost:8000/api/extensions/install \
  -F "file=@hello-extension.zip"
```

### Get Installation Progress

```bash
curl http://localhost:8000/api/extensions/install/inst_abc123 | jq
```

### Get Extension Detail

```bash
curl http://localhost:8000/api/extensions/demo.hello | jq
```

### Enable Extension

```bash
curl -X POST http://localhost:8000/api/extensions/demo.hello/enable | jq
```

### Disable Extension

```bash
curl -X POST http://localhost:8000/api/extensions/demo.hello/disable | jq
```

### Uninstall Extension

```bash
curl -X DELETE http://localhost:8000/api/extensions/demo.hello | jq
```

## Development

### Creating Your Own Extension

1. **Create directory structure:**
   ```bash
   mkdir -p my-extension/{install,commands,docs}
   ```

2. **Write manifest.json:**
   ```json
   {
     "id": "my.extension",
     "name": "My Extension",
     "version": "1.0.0",
     "description": "My custom extension",
     "capabilities": [
       {
         "type": "slash_command",
         "name": "/mycommand",
         "description": "My custom command"
       }
     ],
     "install": {
       "mode": "agentos_managed",
       "plan": "install/plan.yaml"
     }
   }
   ```

3. **Write installation plan:**
   ```yaml
   steps:
     - action: detect_platform
     - action: verify_command_exists
       command: "required-tool"
   ```

4. **Write command definitions:**
   ```yaml
   commands:
     - name: /mycommand
       description: My custom command
       entrypoint: commands/handler.sh
   ```

5. **Create handler script:**
   ```bash
   #!/bin/bash
   echo "Hello from my extension!"
   ```

6. **Package as ZIP:**
   ```bash
   cd my-extension
   zip -r ../my-extension.zip .
   ```

7. **Test:**
   ```bash
   python3 e2e_acceptance_test.py --extension my-extension.zip --verbose
   ```

## Architecture

### Component Interaction

```
┌─────────────────────────────────────────────────────────┐
│                     WebUI / API                         │
├─────────────────────────────────────────────────────────┤
│  Extensions Management                                  │
│  - Upload ZIP                                           │
│  - Monitor progress                                     │
│  - Enable/Disable                                       │
│  - View details                                         │
└─────────────────┬───────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────┐
│              Extension Registry                         │
│  - Store metadata                                       │
│  - Track state                                          │
│  - Manage lifecycle                                     │
└─────────────────┬───────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────┐
│            Install Engine                               │
│  - Parse plan YAML                                      │
│  - Execute steps                                        │
│  - Emit progress                                        │
│  - Handle errors                                        │
└─────────────────┬───────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────┐
│         Step Executors                                  │
│  - detect.platform                                      │
│  - exec.shell / exec.powershell                         │
│  - download.http                                        │
│  - extract.zip                                          │
│  - verify.command_exists                                │
│  - write.config                                         │
└─────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Installation:**
   ```
   User → Upload ZIP → ZipInstaller → Validate → Registry
                                    ↓
                              InstallEngine → Execute Steps
                                    ↓
                              Progress Events → WebSocket → UI
   ```

2. **Command Execution:**
   ```
   User → /command → SlashCommandRouter → Find Handler
                                        ↓
                                  CapabilityRunner → Execute
                                        ↓
                                    Response → User
   ```

## Related Documentation

- **PR-A**: Extension Core Infrastructure
  - `agentos/core/extensions/registry.py`
  - `agentos/core/extensions/validator.py`
  - `agentos/core/extensions/installer.py`

- **PR-B**: Install Engine
  - `agentos/core/extensions/engine.py`
  - `agentos/core/extensions/steps/`

- **PR-C**: WebUI Management
  - `agentos/webui/api/extensions.py`
  - `agentos/webui/static/js/views/ExtensionsView.js`

- **PR-D**: Slash Command Router
  - `agentos/core/extensions/router.py`

- **PR-E**: Capability Runner
  - `agentos/core/extensions/runner.py`

## Support

For issues or questions:
- Check server logs: `logs/agentos.log`
- View extension logs: API `/api/extensions/{id}/logs`
- Report bugs: GitHub Issues
- Documentation: `/docs/extensions/`

## License

MIT License - See LICENSE file for details
