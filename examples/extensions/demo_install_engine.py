#!/usr/bin/env python3
"""
Demo script for Extension Install Engine

This script demonstrates how to use the Extension Install Engine
to execute installation plans.

Usage:
    python3 demo_install_engine.py
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock

# Add AgentOS to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agentos.core.extensions.engine import ExtensionInstallEngine


def create_demo_plan(work_dir: Path) -> Path:
    """Create a demo installation plan"""
    plan_content = """id: demo.extension
version: 0.1.0

steps:
  # Step 1: Detect platform
  - id: detect_platform
    type: detect.platform

  # Step 2: Create marker file
  - id: create_marker
    type: exec.shell
    command: |
      echo "Demo installation started" > demo_marker.txt
      date >> demo_marker.txt

  # Step 3: Create directory structure
  - id: create_dirs
    type: exec.shell
    command: |
      mkdir -p data logs cache
      echo "Directories created"

  # Step 4: Write configuration
  - id: write_config
    type: write.config
    config_key: demo_mode
    config_value: "true"

  - id: write_version
    type: write.config
    config_key: version
    config_value: "0.1.0"

  # Step 5: Verify installation
  - id: verify
    type: exec.shell
    command: |
      if [ -f demo_marker.txt ]; then
        echo "✓ Installation successful"
        cat demo_marker.txt
      else
        echo "✗ Installation failed"
        exit 1
      fi

uninstall:
  steps:
    - id: cleanup
      type: exec.shell
      command: |
        rm -rf demo_marker.txt data logs cache config.json
        echo "Cleanup complete"
"""

    plan_file = work_dir / "plan.yaml"
    plan_file.write_text(plan_content)
    return plan_file


def demo_installation():
    """Demonstrate installation process"""
    print("=" * 60)
    print("Extension Install Engine Demo")
    print("=" * 60)
    print()

    # Create temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        work_dir = Path(temp_dir)
        plan_file = create_demo_plan(work_dir)

        print(f"Created demo plan at: {plan_file}")
        print()

        # Create mock registry
        mock_registry = Mock()
        mock_registry.update_install_progress = Mock()

        # Initialize engine
        engine = ExtensionInstallEngine(registry=mock_registry)

        # Execute installation
        print("Starting installation...")
        print("-" * 60)

        result = engine.execute_install(
            extension_id="demo.extension",
            plan_yaml_path=plan_file,
            install_id="demo_inst_001"
        )

        print("-" * 60)
        print()

        # Display results
        if result.success:
            print("✓ Installation completed successfully!")
            print()
            print(f"Duration: {result.duration_ms}ms")
            print(f"Completed steps ({len(result.completed_steps)}):")
            for step in result.completed_steps:
                print(f"  - {step}")

            # Show created files
            print()
            print("Created files:")
            for item in work_dir.rglob("*"):
                if item.is_file():
                    print(f"  - {item.relative_to(work_dir)}")

            # Show configuration
            config_file = work_dir / "config.json"
            if config_file.exists():
                print()
                print("Configuration:")
                import json
                with open(config_file, 'r') as f:
                    config = json.load(f)
                for key, value in config.items():
                    print(f"  {key}: {value}")

            # Test uninstallation
            print()
            print("=" * 60)
            print("Testing uninstallation...")
            print("-" * 60)

            uninstall_result = engine.execute_uninstall(
                extension_id="demo.extension",
                plan_yaml_path=plan_file,
                install_id="demo_uninst_001"
            )

            print("-" * 60)
            print()

            if uninstall_result.success:
                print("✓ Uninstallation completed successfully!")
                print()
                print(f"Duration: {uninstall_result.duration_ms}ms")
                print(f"Completed steps ({len(uninstall_result.completed_steps)}):")
                for step in uninstall_result.completed_steps:
                    print(f"  - {step}")

                # Verify cleanup
                remaining_files = list(work_dir.rglob("*"))
                if len(remaining_files) == 1 and remaining_files[0] == plan_file:
                    print()
                    print("✓ All files cleaned up")
                else:
                    print()
                    print("Remaining files:")
                    for item in remaining_files:
                        if item != plan_file:
                            print(f"  - {item.relative_to(work_dir)}")
            else:
                print("✗ Uninstallation failed!")
                print(f"Error: {uninstall_result.error}")

        else:
            print("✗ Installation failed!")
            print()
            print(f"Failed step: {result.failed_step}")
            print(f"Error code: {result.error_code}")
            print(f"Error: {result.error}")
            if result.hint:
                print(f"Hint: {result.hint}")

        # Show progress updates
        print()
        print("=" * 60)
        print(f"Progress updates: {mock_registry.update_install_progress.call_count}")
        if mock_registry.update_install_progress.call_count > 0:
            print("Progress history:")
            for i, call in enumerate(mock_registry.update_install_progress.call_args_list, 1):
                args, kwargs = call
                progress = kwargs.get('progress', 0)
                current_step = kwargs.get('current_step', 'unknown')
                print(f"  {i}. Progress: {progress}%, Step: {current_step}")

    print()
    print("=" * 60)
    print("Demo completed!")
    print("=" * 60)


if __name__ == "__main__":
    try:
        demo_installation()
    except KeyboardInterrupt:
        print("\nDemo interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
