"""
Dry Executor CLI Commands

Provides CLI interface for dry execution planning.
"""

import json
import sys
from pathlib import Path

import click

from agentos.core.executor_dry import run_dry_execution
from agentos.core.executor_dry.utils import compute_checksum, enforce_red_lines
from agentos.core.verify.schema_validator_service import SchemaValidatorService


@click.group(name="dry-run")
def dry_run_group():
    """Dry executor: generate execution plans without running anything."""
    pass


@dry_run_group.command(name="plan")
@click.option("--intent", required=True, type=click.Path(exists=True), 
              help="Path to ExecutionIntent JSON file")
@click.option("--coordinator", type=click.Path(exists=True), 
              help="Optional path to coordinator outputs JSON")
@click.option("--out", required=True, type=click.Path(), 
              help="Output directory for dry execution result")
@click.option("--db", type=click.Path(), 
              help="Optional database path for registry queries (for isolation testing)")
def plan_cmd(intent: str, coordinator: str, out: str, db: str):
    """
    Generate a dry execution plan from an intent.
    
    Reads ExecutionIntent (v0.9.1) and produces DryExecutionResult (v0.10)
    without performing any actual execution.
    """
    click.echo("=" * 70)
    click.echo("Dry Executor: Generating Execution Plan")
    click.echo("=" * 70)
    
    # Load intent
    click.echo(f"\n📖 Loading intent from: {intent}")
    try:
        with open(intent, "r", encoding="utf-8") as f:
            intent_data = json.load(f)
    except Exception as e:
        click.echo(f"❌ Error loading intent: {e}", err=True)
        sys.exit(1)
    
    # Load optional coordinator outputs
    coordinator_data = None
    if coordinator:
        click.echo(f"📖 Loading coordinator outputs from: {coordinator}")
        try:
            with open(coordinator, "r", encoding="utf-8") as f:
                coordinator_data = json.load(f)
        except Exception as e:
            click.echo(f"❌ Error loading coordinator outputs: {e}", err=True)
            sys.exit(1)
    
    # Run dry execution
    click.echo(f"\n🔧 Running dry execution...")
    try:
        result = run_dry_execution(intent_data, coordinator_data)
    except Exception as e:
        click.echo(f"❌ Error during dry execution: {e}", err=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Create output directory
    out_path = Path(out)
    out_path.mkdir(parents=True, exist_ok=True)
    
    # Write result
    result_file = out_path / f"{result['result_id']}.json"
    click.echo(f"\n💾 Writing result to: {result_file}")
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    
    # Print summary
    click.echo("\n" + "=" * 70)
    click.echo("✅ Dry Execution Complete")
    click.echo("=" * 70)
    click.echo(f"Result ID: {result['result_id']}")
    click.echo(f"Graph Nodes: {len(result['graph']['nodes'])}")
    click.echo(f"Files Planned: {len(result['patch_plan']['files'])}")
    click.echo(f"Commits Planned: {len(result['commit_plan']['commits'])}")
    click.echo(f"Dominant Risk: {result['review_pack_stub']['risk_summary']['dominant_risk']}")
    click.echo(f"Required Reviews: {', '.join(result['review_pack_stub']['requires_review'])}")
    
    # Check for warnings
    warnings = result['metadata'].get('warnings', [])
    if warnings:
        click.echo(f"\n⚠️  Warnings: {len(warnings)}")
        for warning in warnings:
            click.echo(f"  - {warning}")
    
    click.echo(f"\n📁 Output: {result_file}")


@dry_run_group.command(name="explain")
@click.option("--result", required=True, type=click.Path(exists=True), 
              help="Path to DryExecutionResult JSON file")
@click.option("--format", type=click.Choice(["text", "json"]), default="text",
              help="Output format (text or json)")
def explain_cmd(result: str, format: str):
    """
    Explain a dry execution result in human-readable format.
    
    Used for Gate F snapshot testing - output must be stable.
    """
    # Load result
    try:
        with open(result, "r", encoding="utf-8") as f:
            result_data = json.load(f)
    except Exception as e:
        click.echo(f"❌ Error loading result: {e}", err=True)
        sys.exit(1)
    
    if format == "json":
        # JSON format (for snapshot)
        explanation = _generate_explanation_json(result_data)
        click.echo(json.dumps(explanation, indent=2, sort_keys=True))
    else:
        # Text format (human-readable)
        explanation = _generate_explanation_text(result_data)
        click.echo(explanation)


@dry_run_group.command(name="validate")
@click.option("--file", "file_path", required=True, type=click.Path(exists=True), 
              help="Path to DryExecutionResult JSON file to validate")
def validate_cmd(file_path: str):
    """
    Validate a dry execution result.
    
    Checks:
    - Schema compliance
    - Checksum validity
    - Red line enforcement (DE1-DE6)
    """
    click.echo("=" * 70)
    click.echo("Dry Executor: Validating Result")
    click.echo("=" * 70)
    
    # Load result
    click.echo(f"\n📖 Loading result from: {file_path}")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            result_data = json.load(f)
    except Exception as e:
        click.echo(f"❌ Error loading result: {e}", err=True)
        sys.exit(1)
    
    all_valid = True
    
    # Validate schema
    click.echo("\n🔍 Validating against schema...")
    try:
        validator = SchemaValidatorService()
        schema_path = Path("executor/dry_execution_result.schema.json")

        is_valid, errors = validator.validate_by_path(result_data, schema_path)

        if is_valid:
            click.echo("  ✅ Schema validation passed")
        else:
            click.echo("  ❌ Schema validation failed:")
            for error in errors:
                click.echo(f"    - {error}")
            all_valid = False
    except Exception as e:
        click.echo(f"  ❌ Schema validation error: {e}")
        all_valid = False
    
    # Validate checksum
    click.echo("\n🔍 Validating checksum...")
    try:
        stored_checksum = result_data.get("checksum")
        computed_checksum = compute_checksum(result_data)
        
        if stored_checksum == computed_checksum:
            click.echo("  ✅ Checksum valid")
        else:
            click.echo("  ❌ Checksum mismatch:")
            click.echo(f"    Stored:   {stored_checksum}")
            click.echo(f"    Computed: {computed_checksum}")
            all_valid = False
    except Exception as e:
        click.echo(f"  ❌ Checksum validation error: {e}")
        all_valid = False
    
    # Validate red lines
    click.echo("\n🔍 Validating red lines (DE1-DE6)...")
    try:
        violations = enforce_red_lines(result_data)
        
        if not violations:
            click.echo("  ✅ All red lines enforced")
        else:
            click.echo("  ❌ Red line violations:")
            for violation in violations:
                click.echo(f"    - {violation}")
            all_valid = False
    except Exception as e:
        click.echo(f"  ❌ Red line validation error: {e}")
        all_valid = False
    
    # Summary
    click.echo("\n" + "=" * 70)
    if all_valid:
        click.echo("✅ Validation PASSED")
        click.echo("=" * 70)
        sys.exit(0)
    else:
        click.echo("❌ Validation FAILED")
        click.echo("=" * 70)
        sys.exit(1)


def _generate_explanation_text(result_data: dict) -> str:
    """Generate human-readable text explanation."""
    lines = []
    lines.append("=" * 70)
    lines.append("DRY EXECUTION RESULT EXPLANATION")
    lines.append("=" * 70)
    
    # Basic info
    lines.append(f"\nResult ID: {result_data['result_id']}")
    lines.append(f"Schema Version: {result_data['schema_version']}")
    lines.append(f"Created: {result_data['created_at']}")
    
    # Intent reference
    intent_ref = result_data['intent_ref']
    lines.append(f"\nSource Intent: {intent_ref['intent_id']}")
    lines.append(f"Intent Checksum: {intent_ref['checksum'][:16]}...")
    
    # Graph summary
    graph = result_data['graph']
    lines.append(f"\n--- Execution Graph ---")
    lines.append(f"Nodes: {len(graph['nodes'])}")
    lines.append(f"Edges: {len(graph['edges'])}")
    lines.append(f"Swimlanes: {len(graph['swimlanes'])}")
    
    # Patch plan summary
    patch_plan = result_data['patch_plan']
    lines.append(f"\n--- Patch Plan ---")
    lines.append(f"Files: {len(patch_plan['files'])}")
    for file_entry in patch_plan['files'][:5]:  # Show first 5
        lines.append(f"  - {file_entry['action']}: {file_entry['path']} (risk: {file_entry['risk']})")
    if len(patch_plan['files']) > 5:
        lines.append(f"  ... and {len(patch_plan['files']) - 5} more")
    
    # Commit plan summary
    commit_plan = result_data['commit_plan']
    lines.append(f"\n--- Commit Plan ---")
    lines.append(f"Commits: {len(commit_plan['commits'])}")
    for commit in commit_plan['commits'][:3]:  # Show first 3
        lines.append(f"  - {commit['commit_id']}: {commit['title']}")
        lines.append(f"    Files: {len(commit['files'])}, Risk: {commit['risk']}")
    if len(commit_plan['commits']) > 3:
        lines.append(f"  ... and {len(commit_plan['commits']) - 3} more")
    
    # Review summary
    review = result_data['review_pack_stub']
    lines.append(f"\n--- Review Requirements ---")
    lines.append(f"Dominant Risk: {review['risk_summary']['dominant_risk']}")
    lines.append(f"Required Reviews: {', '.join(review['requires_review'])}")
    lines.append(f"Estimated Review Time: {review['estimated_review_time']}")
    
    lines.append("\n" + "=" * 70)
    
    return "\n".join(lines)


def _generate_explanation_json(result_data: dict) -> dict:
    """Generate JSON explanation (for snapshot)."""
    return {
        "result_id": result_data["result_id"],
        "schema_version": result_data["schema_version"],
        "intent_id": result_data["intent_ref"]["intent_id"],
        "summary": {
            "graph_nodes": len(result_data["graph"]["nodes"]),
            "graph_edges": len(result_data["graph"]["edges"]),
            "files_planned": len(result_data["patch_plan"]["files"]),
            "commits_planned": len(result_data["commit_plan"]["commits"]),
            "dominant_risk": result_data["review_pack_stub"]["risk_summary"]["dominant_risk"],
            "required_reviews": result_data["review_pack_stub"]["requires_review"],
            "estimated_review_time": result_data["review_pack_stub"]["estimated_review_time"]
        },
        "constraints_enforced": result_data["metadata"]["constraints_enforced"],
        "checksum": result_data["checksum"][:16] + "..."
    }
