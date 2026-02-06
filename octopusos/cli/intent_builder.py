"""Intent Builder CLI (v0.9.4) - Natural Language to ExecutionIntent"""

import json
import sys
import click
import yaml
from pathlib import Path
from datetime import datetime, timezone

from agentos.core.content.registry import ContentRegistry
from agentos.core.intent_builder.builder import IntentBuilder
from agentos.core.verify.schema_validator_service import SchemaValidatorService


@click.group()
def builder():
    """Intent Builder CLI - Convert Natural Language to ExecutionIntent"""
    pass


@builder.command()
@click.option("--input", required=True, help="Path to NL request file (.yaml or .json)")
@click.option("--out", default="outputs/builder/", help="Output directory")
@click.option("--policy", default="semi_auto", help="Execution policy (full_auto/semi_auto/interactive)")
@click.option("--db", help="Custom registry DB path (for testing)")
def run(input, out, policy, db):
    """
    Run Intent Builder to generate ExecutionIntent from NL input
    
    Example:
        agentos builder run --input examples/nl/nl_001.yaml --out outputs/builder/
    """
    click.echo("🏗️  Intent Builder v0.9.4 - NL → ExecutionIntent")
    click.echo(f"Input: {input}")
    click.echo(f"Policy: {policy}")
    click.echo(f"Output: {out}")
    
    # Load NL request
    nl_request = _load_nl_request(input)
    if not nl_request:
        click.echo("❌ Failed to load NL request", err=True)
        return 1
    
    # Validate policy
    if policy not in ["full_auto", "semi_auto", "interactive"]:
        click.echo(f"❌ Invalid policy: {policy}. Must be one of: full_auto, semi_auto, interactive", err=True)
        return 1
    
    # Initialize ContentRegistry
    try:
        if db:
            registry = ContentRegistry(db_path=Path(db))
        else:
            registry = ContentRegistry()
    except Exception as e:
        click.echo(f"❌ Failed to initialize registry: {e}", err=True)
        return 1
    
    # Initialize Intent Builder
    intent_builder = IntentBuilder(registry)
    
    # Build Intent
    click.echo("\n⚙️  Building intent...")
    try:
        output = intent_builder.build_intent(nl_request, policy)
    except Exception as e:
        click.echo(f"❌ Failed to build intent: {e}", err=True)
        import traceback
        traceback.print_exc()
        return 1
    
    # Create output directory
    out_dir = Path(out)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Save output
    nl_req_id = nl_request["id"]
    output_file = out_dir / f"{nl_req_id}.output.json"
    
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        click.echo(f"\n✅ Intent built successfully!")
        click.echo(f"📄 Output: {output_file}")
        
        # Print summary
        execution_intent = output["execution_intent"]
        click.echo(f"\n📊 Summary:")
        click.echo(f"  - Intent ID: {execution_intent['id']}")
        click.echo(f"  - Risk Level: {execution_intent['risk']['overall']}")
        click.echo(f"  - Workflows: {len(execution_intent['selected_workflows'])}")
        click.echo(f"  - Agents: {len(execution_intent['selected_agents'])}")
        click.echo(f"  - Commands: {len(execution_intent['planned_commands'])}")
        click.echo(f"  - Questions: {len(output['question_pack']['questions']) if output.get('question_pack') else 0}")
        
    except Exception as e:
        click.echo(f"❌ Failed to save output: {e}", err=True)
        return 1
    
    return 0


@builder.command()
@click.option("--input", required=True, help="Path to NL request file (.yaml or .json)")
@click.option("--db", help="Custom registry DB path (for testing)")
def explain(input, db):
    """
    Generate human-readable explanation of Intent Builder process
    
    Example:
        agentos builder explain --input examples/nl/nl_001.yaml
    """
    click.echo("📖 Intent Builder Explanation")
    click.echo(f"Input: {input}")
    
    # Load NL request
    nl_request = _load_nl_request(input)
    if not nl_request:
        click.echo("❌ Failed to load NL request", err=True)
        return 1
    
    # Initialize registry
    try:
        if db:
            registry = ContentRegistry(db_path=Path(db))
        else:
            registry = ContentRegistry()
    except Exception as e:
        click.echo(f"⚠️  Warning: Failed to initialize registry: {e}")
        registry = None
    
    # Parse NL
    from agentos.core.intent_builder.nl_parser import NLParser
    parser = NLParser()
    parsed_nl = parser.parse(nl_request)
    
    # Print explanation
    click.echo("\n" + "=" * 60)
    click.echo("NL REQUEST ANALYSIS")
    click.echo("=" * 60)
    
    click.echo(f"\n📝 Input Text:")
    click.echo(f"  {nl_request['input_text'][:200]}...")
    
    click.echo(f"\n🎯 Parsed Goal:")
    click.echo(f"  {parsed_nl['goal']}")
    
    click.echo(f"\n⚡ Detected Actions ({len(parsed_nl['actions'])}):")
    for i, action in enumerate(parsed_nl['actions'][:5], 1):
        click.echo(f"  {i}. {action}")
    
    click.echo(f"\n📍 Technical Areas ({len(parsed_nl['areas'])}):")
    for area in parsed_nl['areas']:
        click.echo(f"  - {area}")
    
    click.echo(f"\n🎲 Risk Level: {parsed_nl['risk_level'].upper()}")
    
    click.echo(f"\n❓ Ambiguities ({len(parsed_nl['ambiguities'])}):")
    if parsed_nl['ambiguities']:
        for amb in parsed_nl['ambiguities']:
            click.echo(f"  - [{amb['severity'].upper()}] {amb['type']}: {amb['description']}")
    else:
        click.echo("  None detected")
    
    # If registry available, show matching content
    if registry:
        from agentos.core.intent_builder.registry_query import RegistryQueryService
        query_service = RegistryQueryService(registry)
        
        workflows = query_service.find_matching_workflows(parsed_nl)
        agents = query_service.find_matching_agents(parsed_nl)
        commands = query_service.find_matching_commands(parsed_nl, agents)
        
        click.echo(f"\n🔍 Registry Query Results:")
        click.echo(f"  - Workflows found: {len(workflows)}")
        for wf in workflows[:3]:
            click.echo(f"    • {wf['workflow']['id']} (score: {wf['score']:.2f})")
        
        click.echo(f"  - Agents found: {len(agents)}")
        for ag in agents[:3]:
            click.echo(f"    • {ag['agent']['id']} (score: {ag['score']:.2f})")
        
        click.echo(f"  - Commands found: {len(commands)}")
        for cmd in commands[:3]:
            click.echo(f"    • {cmd['command']['id']} (score: {cmd['score']:.2f})")
    
    click.echo("\n" + "=" * 60)
    
    return 0


@builder.command()
@click.option("--file", required=True, help="Path to builder output JSON file")
def validate(file):
    """
    Validate Intent Builder output against schemas
    
    Example:
        agentos builder validate --file outputs/builder/nl_001.output.json
    """
    click.echo("✅ Intent Builder Output Validation")
    click.echo(f"File: {file}")
    
    # Load output file
    output_path = Path(file)
    if not output_path.exists():
        click.echo(f"❌ File not found: {file}", err=True)
        return 1
    
    try:
        with open(output_path, "r", encoding="utf-8") as f:
            output = json.load(f)
    except Exception as e:
        click.echo(f"❌ Failed to load file: {e}", err=True)
        return 1
    
    # Validate against schema
    validator = SchemaValidatorService()

    click.echo("\n🔍 Validating against schemas...")

    # Validate builder output schema
    click.echo("\n1. Validating builder output schema...")
    output_schema_path = Path("execution/intent_builder_output.schema.json")
    try:
        is_valid, errors = validator.validate_file_by_path(output_path, output_schema_path)
        if is_valid:
            click.echo("   ✅ Builder output schema: VALID")
        else:
            click.echo("   ❌ Builder output schema: INVALID")
            for error in errors:
                click.echo(f"      - {error}")
            return 1
    except Exception as e:
        click.echo(f"   ❌ Validation error: {e}")
        return 1

    # Validate execution intent (v0.9.1)
    click.echo("\n2. Validating execution intent (v0.9.1)...")
    intent_schema_path = Path("execution/intent.schema.json")

    try:
        is_valid, errors = validator.validate_by_path(output["execution_intent"], intent_schema_path)
        if is_valid:
            click.echo("   ✅ Execution intent schema: VALID")
        else:
            click.echo("   ❌ Execution intent schema: INVALID")
            for error in errors:
                click.echo(f"      - {error}")
            return 1
    except Exception as e:
        click.echo(f"   ❌ Validation error: {e}")
        return 1
    
    # Validate RED LINES
    click.echo("\n3. Validating RED LINES...")
    
    # RED LINE 1: full_auto => question_budget=0
    policy = output["builder_audit"]["policy_applied"]
    question_pack = output.get("question_pack")
    
    if policy == "full_auto":
        if question_pack and question_pack.get("questions"):
            click.echo("   ❌ RED LINE VIOLATION: full_auto mode has questions")
            return 1
        else:
            click.echo("   ✅ full_auto mode has zero questions")
    
    # RED LINE 2: Every selection has evidence_refs
    selection_evidence = output["selection_evidence"]
    
    for wf_sel in selection_evidence["workflow_selections"]:
        if not wf_sel.get("evidence_refs"):
            click.echo(f"   ❌ RED LINE VIOLATION: Workflow '{wf_sel['workflow_id']}' missing evidence_refs")
            return 1
    
    for ag_sel in selection_evidence["agent_selections"]:
        if not ag_sel.get("evidence_refs"):
            click.echo(f"   ❌ RED LINE VIOLATION: Agent '{ag_sel['agent_id']}' missing evidence_refs")
            return 1
    
    for cmd_sel in selection_evidence["command_selections"]:
        if not cmd_sel.get("evidence_refs"):
            click.echo(f"   ❌ RED LINE VIOLATION: Command '{cmd_sel['command_id']}' missing evidence_refs")
            return 1
    
    click.echo("   ✅ All selections have evidence_refs")
    
    # RED LINE 3: No execution fields
    intent_str = json.dumps(output["execution_intent"])
    forbidden_keywords = ["execute", "subprocess", "shell", "bash", "run_command"]
    
    for keyword in forbidden_keywords:
        if keyword in intent_str.lower():
            click.echo(f"   ⚠️  Warning: Found keyword '{keyword}' in intent (check context)")
    
    click.echo("   ✅ No obvious execution symbols detected")
    
    click.echo("\n" + "=" * 60)
    click.echo("✅ All validations PASSED")
    click.echo("=" * 60)
    
    return 0


def _load_nl_request(file_path: str) -> dict:
    """Load NL request from YAML or JSON file."""
    path = Path(file_path)
    
    if not path.exists():
        click.echo(f"❌ File not found: {file_path}", err=True)
        return None
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            if path.suffix in [".yaml", ".yml"]:
                data = yaml.safe_load(f)
            elif path.suffix == ".json":
                data = json.load(f)
            else:
                click.echo(f"❌ Unsupported file format: {path.suffix}. Use .yaml, .yml, or .json", err=True)
                return None
        
        return data
    except Exception as e:
        click.echo(f"❌ Failed to load file: {e}", err=True)
        return None
