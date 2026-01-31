"""Budget Configuration Demo

This script demonstrates how to use the budget configuration system.
"""

import json
from pathlib import Path
import tempfile

from agentos.config.budget_config import (
    BudgetConfig,
    BudgetAllocation,
    BudgetConfigManager,
    load_budget_config,
    save_budget_config,
)
from agentos.schemas.project import Project, ProjectSettings


def demo_basic_usage():
    """Demo 1: Basic configuration usage"""
    print("=" * 60)
    print("Demo 1: Basic Configuration Usage")
    print("=" * 60)

    # Create a budget config with default values
    config = BudgetConfig()
    print(f"Default max_tokens: {config.max_tokens}")
    print(f"Default window_tokens: {config.allocation.window_tokens}")
    print(f"Default generation_max_tokens: {config.generation_max_tokens}")

    # Create a custom config
    custom_config = BudgetConfig(
        max_tokens=16000,
        allocation=BudgetAllocation(
            window_tokens=8000,
            rag_tokens=4000,
            memory_tokens=2000,
            summary_tokens=1000,
            system_tokens=1000,
        ),
        generation_max_tokens=4000,
    )
    print(f"\nCustom max_tokens: {custom_config.max_tokens}")
    print(f"Custom window_tokens: {custom_config.allocation.window_tokens}")
    print()


def demo_auto_derive():
    """Demo 2: Auto-derive budget from model context window"""
    print("=" * 60)
    print("Demo 2: Auto-Derive Budget from Model Context Window")
    print("=" * 60)

    # Start with a base config
    base_config = BudgetConfig(
        generation_max_tokens=4000,
        safety_margin=0.2,
    )

    # Auto-derive for GPT-4 (128k context)
    gpt4_config = base_config.derive_from_model_window(128000)
    print(f"GPT-4 (128k context):")
    print(f"  Derived max_tokens: {gpt4_config.max_tokens}")
    print(f"  Auto-derived: {gpt4_config.auto_derive}")
    print(f"  Safety margin: {gpt4_config.safety_margin}")

    # Auto-derive for Claude Opus (200k context)
    claude_config = base_config.derive_from_model_window(200000)
    print(f"\nClaude Opus (200k context):")
    print(f"  Derived max_tokens: {claude_config.max_tokens}")
    print(f"  Window allocation: {claude_config.allocation.window_tokens}")
    print()


def demo_persistence():
    """Demo 3: Save and load configuration"""
    print("=" * 60)
    print("Demo 3: Configuration Persistence")
    print("=" * 60)

    # Use a temporary directory for demo
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "budget.json"
        manager = BudgetConfigManager(config_path=config_path)

        # Create and save a config
        config = BudgetConfig(
            max_tokens=32000,
            auto_derive=True,
            generation_max_tokens=8000,
        )
        manager.save(config)
        print(f"Saved config to {config_path}")

        # Load it back
        loaded = manager.load()
        print(f"Loaded max_tokens: {loaded.max_tokens}")
        print(f"Loaded auto_derive: {loaded.auto_derive}")

        # Update and save
        manager.update_max_tokens(64000)
        updated = manager.load()
        print(f"Updated max_tokens: {updated.max_tokens}")
        print()


def demo_priority_resolution():
    """Demo 4: Configuration priority resolution"""
    print("=" * 60)
    print("Demo 4: Configuration Priority Resolution")
    print("=" * 60)
    print("Priority: Session > Project > Global > Default")
    print()

    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "budget.json"
        manager = BudgetConfigManager(config_path=config_path)

        # Set global config
        global_config = BudgetConfig(max_tokens=8000)
        manager.save(global_config)
        print(f"Global config: max_tokens={global_config.max_tokens}")

        # Project overrides
        project_budget = {"max_tokens": 16000, "auto_derive": False}
        print(f"Project override: max_tokens={project_budget['max_tokens']}")

        # Session overrides
        session_budget = {"max_tokens": 32000}
        print(f"Session override: max_tokens={session_budget['max_tokens']}")

        # Resolve with all levels
        resolved = manager.resolve_config(
            session_budget=session_budget,
            project_budget=project_budget,
        )
        print(f"\nResolved config: max_tokens={resolved.max_tokens}")
        print(f"(Session took priority)")
        print()


def demo_project_integration():
    """Demo 5: Integration with Project settings"""
    print("=" * 60)
    print("Demo 5: Integration with Project Settings")
    print("=" * 60)

    # Create a budget config
    budget_config = BudgetConfig(
        max_tokens=128000,
        auto_derive=True,
        allocation=BudgetAllocation(
            window_tokens=50000,
            rag_tokens=30000,
            memory_tokens=20000,
            summary_tokens=15000,
            system_tokens=5000,
        ),
        generation_max_tokens=10000,
    )

    # Create a project with budget in settings
    project = Project(
        id="proj_demo_001",
        name="Demo Project",
        description="Project with custom budget configuration",
        settings=ProjectSettings(
            default_runner="gpt-4",
            budget=budget_config.to_dict(),
        ),
    )

    print(f"Project: {project.name}")
    print(f"Project ID: {project.id}")
    print(f"Budget max_tokens: {project.settings.budget['max_tokens']}")
    print(f"Budget window_tokens: {project.settings.budget['allocation']['window_tokens']}")

    # Simulate DB roundtrip
    db_dict = project.to_db_dict()
    print(f"\nSettings in DB (JSON string): {db_dict['settings'][:100]}...")

    reconstructed = Project.from_db_row(db_dict)
    print(f"\nReconstructed project: {reconstructed.name}")
    print(f"Budget preserved: {reconstructed.settings.budget['max_tokens']}")
    print()


def demo_real_world_workflow():
    """Demo 6: Real-world workflow"""
    print("=" * 60)
    print("Demo 6: Real-World Workflow")
    print("=" * 60)
    print("Scenario: Setting up budget for a production chat session")
    print()

    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "budget.json"
        manager = BudgetConfigManager(config_path=config_path)

        # Step 1: Configure global defaults
        print("Step 1: Configure global defaults")
        global_config = BudgetConfig(
            max_tokens=8000,
            auto_derive=False,
            generation_max_tokens=2000,
        )
        manager.save(global_config)
        print(f"  Global: max_tokens={global_config.max_tokens}")

        # Step 2: Create project with higher limits
        print("\nStep 2: Create project with higher limits")
        project_budget = BudgetConfig(
            max_tokens=32000,
            allocation=BudgetAllocation(
                window_tokens=16000,
                rag_tokens=8000,
                memory_tokens=4000,
                summary_tokens=2000,
                system_tokens=2000,
            ),
            generation_max_tokens=4000,
        ).to_dict()
        print(f"  Project: max_tokens={project_budget['max_tokens']}")

        # Step 3: For a specific chat session with GPT-4, auto-derive
        print("\nStep 3: For a chat session with GPT-4, auto-derive")
        session_config = BudgetConfig(
            generation_max_tokens=8000,
            safety_margin=0.15,  # Less conservative for production
        ).derive_from_model_window(128000)

        session_budget = session_config.to_dict()
        print(f"  Session (auto-derived): max_tokens={session_budget['max_tokens']}")

        # Step 4: Resolve final configuration
        print("\nStep 4: Resolve final configuration")
        final_config = manager.resolve_config(
            session_budget=session_budget,
            project_budget=project_budget,
        )
        print(f"  Final: max_tokens={final_config.max_tokens}")
        print(f"  Auto-derived: {final_config.auto_derive}")
        print(f"  Generation max: {final_config.generation_max_tokens}")
        print(f"  Total capacity: {final_config.max_tokens + final_config.generation_max_tokens}")
        print()


def main():
    """Run all demos"""
    demos = [
        demo_basic_usage,
        demo_auto_derive,
        demo_persistence,
        demo_priority_resolution,
        demo_project_integration,
        demo_real_world_workflow,
    ]

    for demo in demos:
        try:
            demo()
        except Exception as e:
            print(f"Error in {demo.__name__}: {e}")
            import traceback
            traceback.print_exc()

    print("=" * 60)
    print("All demos completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
