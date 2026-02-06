"""
CLI commands for Intent Evaluator (v0.9.3)
"""

import click
import json
from pathlib import Path


@click.group()
def evaluator():
    """Intent Evaluator commands (v0.9.3)"""
    pass


@evaluator.command()
@click.option("--input-set", required=True, help="Path to intent_set.json")
@click.option("--output", help="Output path for evaluation result")
def run(input_set, output):
    """Run intent evaluator on an intent set"""
    try:
        from agentos.core.evaluator import EvaluatorEngine
        
        engine = EvaluatorEngine()
        result = engine.evaluate(input_set)
        
        if output:
            output_path = Path(output)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(result.to_dict(), f, indent=2)
            click.echo(f"✅ Evaluation result saved to {output}")
        else:
            click.echo(json.dumps(result.to_dict(), indent=2))
    
    except Exception as e:
        click.echo(f"❌ Evaluation failed: {e}", err=True)
        raise click.Abort()


@evaluator.command()
@click.argument("intent_a")
@click.argument("intent_b")
def diff(intent_a, intent_b):
    """Compare two intents"""
    try:
        from agentos.core.evaluator import IntentNormalizer
        
        normalizer = IntentNormalizer()
        
        with open(intent_a, encoding="utf-8") as f:
            intent_a_data = json.load(f)
        with open(intent_b, encoding="utf-8") as f:
            intent_b_data = json.load(f)
        
        canonical_a = normalizer.normalize(intent_a_data)
        canonical_b = normalizer.normalize(intent_b_data)
        
        overlap = canonical_a.overlaps_resources(canonical_b)
        
        click.echo(f"Intent A: {canonical_a.intent_id}")
        click.echo(f"  Resources: {len(canonical_a.resources)}")
        click.echo(f"  Effects: {list(canonical_a.effects.keys())}")
        click.echo(f"  Risk: {canonical_a.risk_level}")
        click.echo(f"  Priority: {canonical_a.priority}")
        click.echo()
        click.echo(f"Intent B: {canonical_b.intent_id}")
        click.echo(f"  Resources: {len(canonical_b.resources)}")
        click.echo(f"  Effects: {list(canonical_b.effects.keys())}")
        click.echo(f"  Risk: {canonical_b.risk_level}")
        click.echo(f"  Priority: {canonical_b.priority}")
        click.echo()
        click.echo(f"Overlapping resources: {len(overlap)}")
        if overlap:
            for resource in list(overlap)[:5]:
                click.echo(f"  - {resource}")
    
    except Exception as e:
        click.echo(f"❌ Diff failed: {e}", err=True)
        raise click.Abort()


@evaluator.command()
@click.argument("result_file")
def explain(result_file):
    """Explain an evaluation result"""
    try:
        from agentos.core.evaluator import EvaluationExplainer
        
        with open(result_file, encoding="utf-8") as f:
            data = json.load(f)
        
        explainer = EvaluationExplainer()
        explanation = explainer.explain(data)
        
        click.echo(explanation)
    
    except Exception as e:
        click.echo(f"❌ Explain failed: {e}", err=True)
        raise click.Abort()


@evaluator.command()
@click.option("--strategy", required=True, type=click.Choice(["merge_union", "override_by_priority", "reject"]))
@click.option("--inputs", required=True, help="Directory with intent files")
@click.option("--output", help="Output path for merged intent")
def merge(strategy, inputs, output):
    """Plan intent merge with specific strategy"""
    try:
        from agentos.core.evaluator import IntentNormalizer, MergePlanner
        
        inputs_dir = Path(inputs)
        intent_files = list(inputs_dir.glob("intent_*.json"))
        
        if len(intent_files) < 2:
            click.echo(f"❌ Need at least 2 intent files, found {len(intent_files)}", err=True)
            raise click.Abort()
        
        intents = {}
        for intent_file in intent_files:
            with open(intent_file, encoding="utf-8") as f:
                intent_data = json.load(f)
                intent_id = intent_data.get("id", intent_file.stem)
                intents[intent_id] = intent_data
        
        normalizer = IntentNormalizer()
        canonical = normalizer.normalize_batch(intents)
        
        planner = MergePlanner()
        plan = planner.plan_merge([], canonical, hints={"strategy": strategy})
        
        click.echo(f"Merge strategy: {plan.strategy}")
        click.echo(f"Operations: {len(plan.operations)}")
        
        for op in plan.operations:
            click.echo(f"  - {op.operation} from {op.source_intent_id}")
        
        if output and plan.result_intent:
            output_path = Path(output)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(plan.result_intent, f, indent=2)
            click.echo(f"\n✅ Merged intent saved to {output}")
    
    except Exception as e:
        click.echo(f"❌ Merge failed: {e}", err=True)
        raise click.Abort()
