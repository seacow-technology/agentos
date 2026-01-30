"""CLI tool for managing AgentOS extensions

Usage:
    python -m agentos.cli.extensions list
    python -m agentos.cli.extensions install <zip_path>
    python -m agentos.cli.extensions install-url <url> [--sha256 <hash>]
    python -m agentos.cli.extensions uninstall <extension_id>
    python -m agentos.cli.extensions enable <extension_id>
    python -m agentos.cli.extensions disable <extension_id>
    python -m agentos.cli.extensions show <extension_id>
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from agentos.core.extensions import (
    ExtensionRegistry,
    ZipInstaller,
    ExtensionValidator,
)
from agentos.core.extensions.exceptions import (
    ExtensionError,
    ValidationError,
    InstallationError,
)
from agentos.core.extensions.models import InstallSource

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


def cmd_list(args):
    """List installed extensions"""
    registry = ExtensionRegistry()
    extensions = registry.list_extensions()

    if not extensions:
        print("No extensions installed.")
        return

    print(f"\nInstalled Extensions ({len(extensions)}):\n")
    print(f"{'ID':<30} {'Name':<30} {'Version':<10} {'Status':<12} {'Enabled'}")
    print("-" * 95)

    for ext in extensions:
        enabled = "Yes" if ext.enabled else "No"
        print(f"{ext.id:<30} {ext.name:<30} {ext.version:<10} {ext.status.value:<12} {enabled}")


def cmd_install(args):
    """Install extension from local zip file"""
    zip_path = Path(args.zip_path).expanduser().resolve()

    if not zip_path.exists():
        print(f"Error: Zip file not found: {zip_path}")
        sys.exit(1)

    print(f"Installing extension from: {zip_path}")

    # Validate first
    validator = ExtensionValidator()
    try:
        print("Validating package...")
        root_dir, manifest, sha256 = validator.validate_extension_package(zip_path)
        print(f"  Extension ID: {manifest.id}")
        print(f"  Name: {manifest.name}")
        print(f"  Version: {manifest.version}")
        print(f"  SHA256: {sha256[:16]}...")
        print(f"  Capabilities: {len(manifest.capabilities)}")
    except ValidationError as e:
        print(f"Validation failed: {e}")
        sys.exit(1)

    # Install
    installer = ZipInstaller()
    try:
        print("\nExtracting and installing...")
        manifest, sha256, install_dir = installer.install_from_upload(zip_path)
        print(f"  Installed to: {install_dir}")
    except InstallationError as e:
        print(f"Installation failed: {e}")
        sys.exit(1)

    # Register
    registry = ExtensionRegistry()
    try:
        print("\nRegistering extension...")
        record = registry.register_extension(
            manifest=manifest,
            sha256=sha256,
            source=InstallSource.UPLOAD
        )
        print(f"  Registered: {record.id} v{record.version}")
    except ExtensionError as e:
        print(f"Registration failed: {e}")
        sys.exit(1)

    print(f"\nSuccess! Extension '{manifest.name}' installed.")


def cmd_install_url(args):
    """Install extension from URL"""
    url = args.url
    expected_sha256 = args.sha256

    print(f"Installing extension from: {url}")

    if expected_sha256:
        print(f"Expected SHA256: {expected_sha256}")

    installer = ZipInstaller()
    try:
        print("\nDownloading and installing...")
        manifest, sha256, install_dir = installer.install_from_url(
            url=url,
            expected_sha256=expected_sha256
        )
        print(f"  Extension ID: {manifest.id}")
        print(f"  Name: {manifest.name}")
        print(f"  Version: {manifest.version}")
        print(f"  SHA256: {sha256[:16]}...")
        print(f"  Installed to: {install_dir}")
    except ExtensionError as e:
        print(f"Installation failed: {e}")
        sys.exit(1)

    # Register
    registry = ExtensionRegistry()
    try:
        print("\nRegistering extension...")
        record = registry.register_extension(
            manifest=manifest,
            sha256=sha256,
            source=InstallSource.URL,
            source_url=url
        )
        print(f"  Registered: {record.id} v{record.version}")
    except ExtensionError as e:
        print(f"Registration failed: {e}")
        sys.exit(1)

    print(f"\nSuccess! Extension '{manifest.name}' installed from URL.")


def cmd_uninstall(args):
    """Uninstall an extension"""
    extension_id = args.extension_id

    registry = ExtensionRegistry()

    # Check if exists
    record = registry.get_extension(extension_id)
    if not record:
        print(f"Error: Extension not found: {extension_id}")
        sys.exit(1)

    print(f"Uninstalling extension: {record.name} ({extension_id})")

    # Remove files
    installer = ZipInstaller()
    try:
        installer.uninstall_extension(extension_id)
        print(f"  Files removed")
    except InstallationError as e:
        print(f"Warning: Failed to remove files: {e}")

    # Update registry
    try:
        registry.uninstall_extension(extension_id)
        print(f"  Registry updated")
    except ExtensionError as e:
        print(f"Error: Failed to update registry: {e}")
        sys.exit(1)

    print(f"\nSuccess! Extension '{record.name}' uninstalled.")


def cmd_enable(args):
    """Enable an extension"""
    extension_id = args.extension_id

    registry = ExtensionRegistry()
    try:
        registry.enable_extension(extension_id)
        print(f"Extension '{extension_id}' enabled.")
    except ExtensionError as e:
        print(f"Error: {e}")
        sys.exit(1)


def cmd_disable(args):
    """Disable an extension"""
    extension_id = args.extension_id

    registry = ExtensionRegistry()
    try:
        registry.disable_extension(extension_id)
        print(f"Extension '{extension_id}' disabled.")
    except ExtensionError as e:
        print(f"Error: {e}")
        sys.exit(1)


def cmd_show(args):
    """Show extension details"""
    extension_id = args.extension_id

    registry = ExtensionRegistry()
    record = registry.get_extension(extension_id)

    if not record:
        print(f"Error: Extension not found: {extension_id}")
        sys.exit(1)

    print(f"\nExtension Details:\n")
    print(f"  ID: {record.id}")
    print(f"  Name: {record.name}")
    print(f"  Version: {record.version}")
    print(f"  Status: {record.status.value}")
    print(f"  Enabled: {'Yes' if record.enabled else 'No'}")
    print(f"  Description: {record.description or 'N/A'}")
    print(f"  SHA256: {record.sha256[:32]}...")
    print(f"  Source: {record.source.value}")
    if record.source_url:
        print(f"  Source URL: {record.source_url}")
    print(f"  Installed at: {record.installed_at.strftime('%Y-%m-%d %H:%M:%S')}")

    if record.permissions_required:
        print(f"\n  Permissions Required:")
        for perm in record.permissions_required:
            print(f"    - {perm}")

    if record.capabilities:
        print(f"\n  Capabilities ({len(record.capabilities)}):")
        for cap in record.capabilities:
            print(f"    - {cap.type.value}: {cap.name}")
            print(f"      {cap.description}")

    if record.metadata:
        print(f"\n  Metadata:")
        for key, value in record.metadata.items():
            print(f"    {key}: {value}")


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Manage AgentOS extensions",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # list command
    subparsers.add_parser('list', help='List installed extensions')

    # install command
    install_parser = subparsers.add_parser('install', help='Install extension from local zip')
    install_parser.add_argument('zip_path', help='Path to extension zip file')

    # install-url command
    install_url_parser = subparsers.add_parser('install-url', help='Install extension from URL')
    install_url_parser.add_argument('url', help='URL to extension zip file')
    install_url_parser.add_argument('--sha256', help='Expected SHA256 hash (optional)')

    # uninstall command
    uninstall_parser = subparsers.add_parser('uninstall', help='Uninstall an extension')
    uninstall_parser.add_argument('extension_id', help='Extension ID to uninstall')

    # enable command
    enable_parser = subparsers.add_parser('enable', help='Enable an extension')
    enable_parser.add_argument('extension_id', help='Extension ID to enable')

    # disable command
    disable_parser = subparsers.add_parser('disable', help='Disable an extension')
    disable_parser.add_argument('extension_id', help='Extension ID to disable')

    # show command
    show_parser = subparsers.add_parser('show', help='Show extension details')
    show_parser.add_argument('extension_id', help='Extension ID to show')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Route to command handlers
    commands = {
        'list': cmd_list,
        'install': cmd_install,
        'install-url': cmd_install_url,
        'uninstall': cmd_uninstall,
        'enable': cmd_enable,
        'disable': cmd_disable,
        'show': cmd_show,
    }

    handler = commands.get(args.command)
    if handler:
        try:
            handler(args)
        except KeyboardInterrupt:
            print("\nAborted.")
            sys.exit(1)
        except Exception as e:
            logger.exception(f"Unexpected error: {e}")
            sys.exit(1)
    else:
        print(f"Unknown command: {args.command}")
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
