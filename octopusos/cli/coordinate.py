"""Coordinator CLI (v0.9.2)"""

import json
import click
from pathlib import Path


@click.group()
def coordinator():
    """Coordinator CLI - Planning Engine (v0.9.2)"""
    pass


@coordinator.command()
@click.option("--intent", required=True, help="Intent ID or path to intent JSON file")
@click.option("--policy", default="semi_auto", help="Execution policy (interactive/semi_auto/full_auto)")
@click.option("--output", default="./output", help="Output directory")
@click.option("--dry-run", is_flag=True, help="Dry run mode (don't write files)")
def coordinate(intent, policy, output, dry_run):
    """
    Coordinate an ExecutionIntent into execution plan
    
    Example:
        agentos coordinate --intent intent_example_low_risk --policy semi_auto --output ./output
    """
    click.echo(f"🚀 Coordinator v0.9.2 - Planning Engine")
    click.echo(f"Intent: {intent}")
    click.echo(f"Policy: {policy}")
    click.echo(f"Output: {output}")
    
    # Load intent
    intent_data = _load_intent(intent)
    if not intent_data:
        click.echo("❌ Failed to load intent", err=True)
        return 1
    
    # Build policy
    policy_data = _build_policy(policy)
    
    # Mock factpack (would load from scanner in real implementation)
    factpack = {"project_id": "test", "evidence": []}
    
    try:
        from agentos.core.coordinator import CoordinatorEngine
        
        # Mock services (would use real services in production)
        class MockRegistry:
            def get(self, content_type, content_id):
                return {"id": content_id, "version": "1.0.0"}
        
        class MockMemoryService:
            def build_context(self, **kwargs):
                return {"memories": []}
        
        engine = CoordinatorEngine(MockRegistry(), MockMemoryService())
        
        # Run coordination
        click.echo("\n📋 Running coordination...")
        result = engine.coordinate(intent_data, policy_data, factpack)
        
        # Display result
        click.echo(f"\n✅ Coordination complete!")
        click.echo(f"   Final state: {result.final_state}")
        click.echo(f"   Intent ID: {result.intent_id}")
        click.echo(f"   Run ID: {result.run_id}")
        
        # Write outputs
        if not dry_run:
            output_dir = Path(output)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            if result.graph:
                _write_json(output_dir / "execution_graph.json", result.graph)
                click.echo(f"   📄 Wrote: execution_graph.json")
            
            if result.tape:
                _write_json(output_dir / "coordinator_run_tape.json", result.tape)
                click.echo(f"   📄 Wrote: coordinator_run_tape.json")
            
            if result.review:
                _write_json(output_dir / "review_pack.json", result.review)
                click.echo(f"   📄 Wrote: review_pack.json")
        
        return 0
        
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        return 1


@coordinator.command()
@click.option("--intent", required=True, help="Intent ID or path")
def explain(intent):
    """
    Explain mode - Generate human-readable coordination report
    
    Example:
        agentos coordinate explain --intent intent_example_low_risk
    """
    click.echo(f"📖 Coordinator Explain Mode")
    click.echo(f"Intent: {intent}")
    
    # Load intent
    intent_data = _load_intent(intent)
    if not intent_data:
        click.echo("❌ Failed to load intent", err=True)
        return 1
    
    # Display explain report
    click.echo("\n" + "=" * 70)
    click.echo("Execution Intent Analysis")
    click.echo("=" * 70)
    click.echo(f"\nIntent ID: {intent_data.get('id')}")
    click.echo(f"Title: {intent_data.get('title')}")
    click.echo(f"Risk Level: {intent_data.get('risk', {}).get('overall', 'unknown')}")
    click.echo(f"Execution Mode: {intent_data.get('interaction', {}).get('mode', 'unknown')}")
    
    click.echo(f"\nWorkflows ({len(intent_data.get('selected_workflows', []))}):")
    for wf in intent_data.get("selected_workflows", []):
        click.echo(f"  - {wf.get('workflow_id')}: {wf.get('phases')}")
    
    click.echo(f"\nAgents ({len(intent_data.get('selected_agents', []))}):")
    for agent in intent_data.get("selected_agents", []):
        click.echo(f"  - {agent.get('agent_id')} ({agent.get('role')})")
    
    click.echo(f"\nPlanned Commands ({len(intent_data.get('planned_commands', []))}):")
    for cmd in intent_data.get("planned_commands", []):
        click.echo(f"  - {cmd.get('command_id')}: {cmd.get('intent')} [{cmd.get('risk_level')}]")
    
    click.echo("\n" + "=" * 70)
    return 0


def _load_intent(intent_ref: str) -> dict:
    """Load intent from file or examples"""
    # Try as file path
    path = Path(intent_ref)
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    # Try as intent ID in examples
    examples_path = Path("examples/intents") / f"{intent_ref}.json"
    if examples_path.exists():
        with open(examples_path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    return None


def _build_policy(mode: str) -> dict:
    """Build ExecutionPolicy from mode"""
    if mode == "interactive":
        return {"mode": "interactive", "question_budget": 999, "question_policy": "all", "budgets": {"max_cost_usd": 10.0}}
    elif mode == "semi_auto":
        return {"mode": "semi_auto", "question_budget": 3, "question_policy": "blockers_only", "budgets": {"max_cost_usd": 10.0}}
    elif mode == "full_auto":
        return {"mode": "full_auto", "question_budget": 0, "question_policy": "never", "budgets": {"max_cost_usd": 10.0}}
    else:
        return {"mode": "semi_auto", "question_budget": 3, "budgets": {"max_cost_usd": 10.0}}


def _write_json(path: Path, data: dict):
    """Write JSON file"""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


if __name__ == "__main__":
    coordinator()
