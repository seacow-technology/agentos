"""
Demonstration of Phase 2: Configuration Management Enhancement

Shows the new executable path and models directory management features.
"""

import json
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from agentos.providers.providers_config import ProvidersConfigManager
from agentos.providers import platform_utils


def print_section(title):
    """Print a formatted section header"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


def print_config(manager):
    """Pretty print the current configuration"""
    print(json.dumps(manager._config, indent=2))


def demo_migration():
    """Demonstrate automatic configuration migration"""
    print_section("1. Automatic Configuration Migration")

    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = Path(tmpdir) / "providers.json"

        # Create old-format config (without new Phase 2 fields)
        print("\n📝 Creating old-format configuration:")
        old_config = {
            "providers": {
                "ollama": {
                    "enabled": True,
                    "instances": [
                        {"id": "default", "base_url": "http://127.0.0.1:11434", "enabled": True}
                    ]
                },
                "llamacpp": {
                    "enabled": True,
                    "instances": []
                }
            }
        }
        print(json.dumps(old_config, indent=2))

        with open(config_file, "w") as f:
            json.dump(old_config, f)

        # Load with manager - triggers automatic migration
        print("\n🔄 Loading config (triggers automatic migration)...")
        manager = ProvidersConfigManager(config_file)

        print("\n✅ Migrated configuration:")
        print_config(manager)

        print("\n📊 Migration added:")
        print("  - executable_path field (set to None)")
        print("  - auto_detect field (set to True)")
        print("  - global.models_directories section")


def demo_executable_path():
    """Demonstrate executable path configuration"""
    print_section("2. Executable Path Configuration")

    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = Path(tmpdir) / "providers.json"
        manager = ProvidersConfigManager(config_file)

        # Auto-detection (default behavior)
        print("\n🔍 Auto-detection of executables:")
        print(f"  Platform: {platform_utils.get_platform()}")

        for provider_id in ["ollama", "llamacpp", "lmstudio"]:
            exe_path = manager.get_executable_path(provider_id)
            if exe_path:
                print(f"  ✅ {provider_id}: {exe_path}")
            else:
                print(f"  ❌ {provider_id}: Not found")

        # Manual configuration
        print("\n⚙️  Manual configuration:")
        print("  Setting ollama to use auto-detection (None)...")
        manager.set_executable_path("ollama", None)

        providers = manager._config["providers"]["ollama"]
        print(f"    executable_path: {providers['executable_path']}")
        print(f"    auto_detect: {providers['auto_detect']}")

        # Validation test
        print("\n🛡️  Path validation:")
        print("  Trying to set invalid path...")
        try:
            manager.set_executable_path("ollama", "/nonexistent/ollama")
            print("  ❌ Should have failed!")
        except ValueError as e:
            print(f"  ✅ Validation caught invalid path: {e}")


def demo_models_directory():
    """Demonstrate models directory configuration"""
    print_section("3. Models Directory Configuration")

    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = Path(tmpdir) / "providers.json"
        manager = ProvidersConfigManager(config_file)

        # Show default locations
        print("\n📁 Default models directories:")
        for provider_id in ["ollama", "llamacpp", "lmstudio"]:
            models_dir = platform_utils.get_models_dir(provider_id)
            print(f"  {provider_id}: {models_dir}")

        # Create test directories
        test_dirs = {
            "ollama": Path(tmpdir) / "ollama_models",
            "global": Path(tmpdir) / "shared_models",
        }
        for name, path in test_dirs.items():
            path.mkdir()

        # Set provider-specific directory
        print(f"\n⚙️  Setting provider-specific directory:")
        manager.set_models_directory("ollama", str(test_dirs["ollama"]))
        print(f"  Ollama models: {test_dirs['ollama']}")

        # Set global directory
        print(f"\n⚙️  Setting global models directory:")
        manager.set_models_directory("global", str(test_dirs["global"]))
        print(f"  Global models: {test_dirs['global']}")

        # Demonstrate priority order
        print("\n📊 Priority order demonstration:")
        print("  1. Provider-specific (ollama):")
        result = manager.get_models_directory("ollama")
        print(f"     → {result}")
        print(f"     Expected: {test_dirs['ollama']}")
        print(f"     ✅ Match: {result == test_dirs['ollama']}")

        print("  2. Global fallback (llamacpp):")
        result = manager.get_models_directory("llamacpp")
        print(f"     → {result}")
        print(f"     Expected: {test_dirs['global']}")
        print(f"     ✅ Match: {result == test_dirs['global']}")

        # Show configuration
        print("\n📝 Current models directory configuration:")
        models_config = manager._config["global"]["models_directories"]
        print(json.dumps(models_config, indent=2))


def demo_validation():
    """Demonstrate validation features"""
    print_section("4. Validation Features")

    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = Path(tmpdir) / "providers.json"
        manager = ProvidersConfigManager(config_file)

        print("\n🛡️  Executable path validation:")

        # Test 1: Non-existent file
        print("\n  Test 1: Non-existent file")
        try:
            manager.set_executable_path("ollama", "/tmp/nonexistent_file")
            print("  ❌ Should have failed!")
        except ValueError as e:
            print(f"  ✅ Caught: {str(e)[:60]}...")

        # Test 2: Non-existent directory for models
        print("\n  Test 2: Non-existent models directory")
        try:
            manager.set_models_directory("ollama", "/tmp/nonexistent_directory")
            print("  ❌ Should have failed!")
        except ValueError as e:
            print(f"  ✅ Caught: {str(e)[:60]}...")

        # Test 3: File instead of directory for models
        print("\n  Test 3: File path for models directory")
        file_path = Path(tmpdir) / "not_a_dir.txt"
        file_path.touch()
        try:
            manager.set_models_directory("ollama", str(file_path))
            print("  ❌ Should have failed!")
        except ValueError as e:
            print(f"  ✅ Caught: {str(e)[:60]}...")


def demo_platform_integration():
    """Demonstrate integration with platform_utils"""
    print_section("5. Platform Utils Integration")

    print("\n🖥️  Platform Information:")
    print(f"  Platform: {platform_utils.get_platform()}")
    print(f"  Config dir: {platform_utils.get_config_dir()}")
    print(f"  Run dir: {platform_utils.get_run_dir()}")
    print(f"  Log dir: {platform_utils.get_log_dir()}")

    print("\n🔍 Standard installation paths:")
    for provider_name in ["ollama", "llama-server", "lmstudio"]:
        paths = platform_utils.get_standard_paths(provider_name)
        print(f"\n  {provider_name}:")
        for path in paths:
            exists = "✅" if path.exists() else "❌"
            print(f"    {exists} {path}")

    print("\n🔎 Executable detection:")
    for provider_name in ["ollama", "llama-server"]:
        result = platform_utils.find_executable(provider_name)
        if result:
            print(f"  ✅ {provider_name}: {result}")
        else:
            print(f"  ❌ {provider_name}: Not found")


def demo_backward_compatibility():
    """Demonstrate backward compatibility"""
    print_section("6. Backward Compatibility")

    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = Path(tmpdir) / "providers.json"

        # Create very minimal old config
        print("\n📝 Minimal old configuration:")
        minimal_config = {
            "providers": {
                "ollama": {"enabled": True, "instances": []}
            }
        }
        print(json.dumps(minimal_config, indent=2))

        with open(config_file, "w") as f:
            json.dump(minimal_config, f)

        # Load and use
        print("\n✅ Loading old config...")
        manager = ProvidersConfigManager(config_file)

        print("✅ Using new methods with old config:")
        print(f"  - get_executable_path: {manager.get_executable_path('ollama')}")
        print(f"  - get_models_directory: {manager.get_models_directory('ollama')}")

        manager.set_executable_path("ollama", None)
        print("  - set_executable_path: OK")

        print("\n📝 Configuration after migration:")
        print_config(manager)


def demo_complete_workflow():
    """Demonstrate a complete workflow"""
    print_section("7. Complete Workflow Example")

    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = Path(tmpdir) / "providers.json"

        print("\n📝 Scenario: Setting up Ollama and LlamaCpp")

        # Step 1: Initialize
        print("\n1️⃣  Initialize configuration manager")
        manager = ProvidersConfigManager(config_file)
        print("   ✅ Initialized with default config")

        # Step 2: Configure Ollama
        print("\n2️⃣  Configure Ollama")
        print("   - Enable auto-detection")
        manager.set_executable_path("ollama", None)

        ollama_exe = manager.get_executable_path("ollama")
        if ollama_exe:
            print(f"   ✅ Found Ollama at: {ollama_exe}")
        else:
            print("   ❌ Ollama not installed")

        # Step 3: Configure models directories
        print("\n3️⃣  Configure models directories")

        # Create test directories
        global_models = Path(tmpdir) / "shared_models"
        global_models.mkdir()
        print(f"   - Created global models directory: {global_models}")

        manager.set_models_directory("global", str(global_models))
        print("   ✅ Set global models directory")

        # Step 4: Verify configuration
        print("\n4️⃣  Verify configuration")
        print("   Ollama:")
        print(f"     - Executable: {manager.get_executable_path('ollama')}")
        print(f"     - Models: {manager.get_models_directory('ollama')}")
        print("   LlamaCpp:")
        print(f"     - Executable: {manager.get_executable_path('llamacpp')}")
        print(f"     - Models: {manager.get_models_directory('llamacpp')}")

        # Step 5: Show final configuration
        print("\n5️⃣  Final configuration saved to disk:")
        print_config(manager)


def main():
    """Run all demonstrations"""
    print("="*60)
    print("  Phase 2: Configuration Management Enhancement")
    print("  Feature Demonstration")
    print("="*60)

    demo_migration()
    demo_executable_path()
    demo_models_directory()
    demo_validation()
    demo_platform_integration()
    demo_backward_compatibility()
    demo_complete_workflow()

    print("\n" + "="*60)
    print("  Demonstration Complete!")
    print("="*60)


if __name__ == "__main__":
    main()
