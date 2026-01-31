#!/usr/bin/env python3
"""
创建示例扩展包

生成示例扩展：
1. hello-extension.zip - 最小示例
"""
import json
import shutil
import zipfile
from pathlib import Path
from typing import Dict, Any


def create_hello_extension(output_dir: Path) -> Path:
    """创建 hello 扩展"""
    print("Creating hello extension...")

    # 创建临时目录
    temp_dir = output_dir / "temp_hello"
    temp_dir.mkdir(parents=True, exist_ok=True)

    # 1. manifest.json
    manifest = {
        "id": "demo.hello",
        "name": "Hello Extension",
        "version": "0.1.0",
        "description": "A minimal example extension that demonstrates the basic structure.",
        "author": "AgentOS Team",
        "license": "MIT",
        "icon": "icon.png",
        "capabilities": [
            {
                "type": "slash_command",
                "name": "/hello",
                "description": "Say hello and display usage information"
            }
        ],
        "permissions_required": [],
        "platforms": ["linux", "darwin", "win32"],
        "install": {
            "mode": "agentos_managed",
            "plan": "install/plan.yaml"
        },
        "docs": {
            "usage": "docs/USAGE.md"
        }
    }

    manifest_path = temp_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))

    # 2. install/plan.yaml
    install_dir = temp_dir / "install"
    install_dir.mkdir(exist_ok=True)

    plan_yaml = """steps:
  - action: detect_platform
    description: "Detect current platform"

  - action: write_config
    config_namespace: "demo.hello"
    data:
      message: "Hello from AgentOS Extension System!"
      enabled: true
    description: "Save hello configuration"

  - action: verify_command_exists
    command: "echo"
    description: "Verify echo command exists"

  - action: test_command
    command: "echo 'Hello Extension installed successfully!'"
    description: "Test extension installation"

uninstall:
  steps:
    - action: write_config
      config_namespace: "demo.hello"
      data: {}
      description: "Clean up configuration"
"""

    (install_dir / "plan.yaml").write_text(plan_yaml)

    # 3. commands/commands.yaml
    commands_dir = temp_dir / "commands"
    commands_dir.mkdir(exist_ok=True)

    commands_yaml = """commands:
  - name: /hello
    description: Say hello and display extension information
    entrypoint: commands/hello.sh
    args:
      - name: name
        description: Name to greet (optional)
        required: false
        default: "World"

    examples:
      - command: /hello
        description: Display basic greeting

      - command: /hello AgentOS
        description: Greet with a custom name
"""

    (commands_dir / "commands.yaml").write_text(commands_yaml)

    # 创建 hello.sh 脚本
    hello_sh = """#!/bin/bash
# Hello extension command handler

NAME="${1:-World}"

echo "🎉 Hello, $NAME!"
echo ""
echo "This is a minimal extension example for AgentOS."
echo "Extension ID: demo.hello"
echo "Version: 0.1.0"
echo ""
echo "To learn more, see: /extensions/demo.hello"
"""

    (commands_dir / "hello.sh").write_text(hello_sh)

    # 4. docs/USAGE.md
    docs_dir = temp_dir / "docs"
    docs_dir.mkdir(exist_ok=True)

    usage_md = """# Hello Extension

A minimal example extension for AgentOS.

## Overview

This extension demonstrates:
- Basic extension structure
- Minimal installation plan
- Slash command declaration
- Usage documentation

## Usage

Simply type `/hello` in the chat to see a greeting message.

### Examples

**Basic greeting:**
```
/hello
```
Output: "Hello, World!"

**Custom greeting:**
```
/hello AgentOS
```
Output: "Hello, AgentOS!"

## Implementation Details

### Installation

The installation plan performs these steps:
1. Detect platform (linux/darwin/win32)
2. Write configuration to store
3. Verify `echo` command exists
4. Test the installation

### Commands

The `/hello` command accepts an optional name parameter and displays:
- A greeting message
- Extension metadata
- Usage information

### Files

- `manifest.json` - Extension metadata
- `install/plan.yaml` - Installation plan
- `commands/commands.yaml` - Command definitions
- `commands/hello.sh` - Command implementation
- `docs/USAGE.md` - This documentation

## Requirements

- No external dependencies
- Works on all platforms (linux, darwin, win32)

## Configuration

This extension has no required configuration.

## Troubleshooting

If the `/hello` command doesn't work:
1. Check that the extension is installed: `/extensions list`
2. Check that the extension is enabled
3. View extension logs: `/extensions logs demo.hello`

## Support

For help, visit: https://github.com/agentos/extensions
"""

    (docs_dir / "USAGE.md").write_text(usage_md)

    # 5. icon.png (创建一个简单的占位符)
    # 这里我们创建一个空的 PNG 文件作为占位符
    # 实际使用中应该提供真实的图标
    icon_data = (
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00 \x00\x00\x00 '
        b'\x08\x06\x00\x00\x00szz\xf4\x00\x00\x00\x19tEXtSoftware\x00'
        b'Adobe ImageReadyq\xc9e<\x00\x00\x00\x0eIDATx\xdab\x00\x00\x00'
        b'\x02\x00\x01\xe2!\xbc3\x00\x00\x00\x00IEND\xaeB`\x82'
    )
    (temp_dir / "icon.png").write_bytes(icon_data)

    # 6. 打包成 zip
    zip_path = output_dir / "hello-extension.zip"
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file_path in temp_dir.rglob("*"):
            if file_path.is_file():
                arc_name = file_path.relative_to(temp_dir)
                zf.write(file_path, arc_name)

    # 清理临时目录
    shutil.rmtree(temp_dir)

    print(f"✓ Created: {zip_path}")
    return zip_path


def main():
    """主函数"""
    # 输出目录
    output_dir = Path(__file__).parent
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("Extension Package Creator")
    print("=" * 60)
    print()

    # 创建扩展
    hello_zip = create_hello_extension(output_dir)

    print()
    print("=" * 60)
    print("✓ Extension package created successfully!")
    print("=" * 60)
    print()
    print("Created package:")
    print(f"  - {hello_zip}")
    print()
    print("Next steps:")
    print("  1. Start the AgentOS server: python -m agentos.webui.server")
    print("  2. Run acceptance tests: python acceptance_test.py")
    print()


if __name__ == "__main__":
    main()
