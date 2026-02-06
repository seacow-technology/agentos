"""CLI commands for AnswerPack management."""

import json
import click
from pathlib import Path
from datetime import datetime, timezone
from rich.console import Console
from rich.table import Table

from agentos.core.time import utc_now_iso
from agentos.core.answers import (
    AnswerStore,
    AnswerValidator,
    validate_answer_pack,
    apply_answer_pack
)

console = Console()


@click.group(name="answers")
def answers_group():
    """Manage AnswerPacks for resolving BLOCKED pipelines."""
    pass


@answers_group.command(name="create")
@click.option("--from", "question_pack_path", required=True, type=click.Path(exists=True),
              help="Path to question_pack.json file")
@click.option("--out", "output_path", required=True, type=click.Path(),
              help="Output path for answer_pack.json")
@click.option("--llm/--no-llm", default=False,
              help="Use LLM to generate answer suggestions")
@click.option("--llm-provider", type=click.Choice(["openai", "anthropic"]), default="openai",
              help="LLM provider for suggestions")
@click.option("--interactive/--no-interactive", default=True,
              help="Interactive mode (prompt for answers)")
def create_cmd(
    question_pack_path: str,
    output_path: str,
    llm: bool,
    llm_provider: str,
    interactive: bool
):
    """Create an AnswerPack from a QuestionPack."""
    try:
        # Load question pack
        with open(question_pack_path, "r", encoding="utf-8") as f:
            question_pack = json.load(f)

        console.print(f"[cyan]Loaded QuestionPack: {question_pack.get('pack_id')}[/cyan]")
        console.print(f"Questions: {len(question_pack.get('questions', []))}\n")

        # Generate LLM suggestions if requested
        llm_suggestions = None
        if llm and interactive:
            console.print(f"[yellow]Generating LLM suggestions using {llm_provider}...[/yellow]")
            try:
                from agentos.core.answers.llm_suggester import suggest_all_answers
                
                llm_suggestions, errors = suggest_all_answers(
                    question_pack=question_pack,
                    provider=llm_provider,
                    fallback_provider="anthropic" if llm_provider == "openai" else "openai"
                )
                
                if errors:
                    console.print("[yellow]Some suggestions failed:[/yellow]")
                    for error in errors:
                        console.print(f"  - {error}")
                
                console.print(f"[green]✓ Generated suggestions for {len(llm_suggestions)} questions[/green]\n")
            except Exception as e:
                console.print(f"[yellow]Warning: LLM suggestions failed: {e}[/yellow]")
                console.print("[yellow]Continuing without suggestions...[/yellow]\n")
                llm_suggestions = None

        # Initialize answer pack
        store = AnswerStore()
        answer_pack_id = store.generate_pack_id(question_pack.get("pack_id"))

        answers = []

        if interactive:
            # Interactive mode: prompt for each question
            for i, question in enumerate(question_pack.get("questions", []), 1):
                console.print(f"\n[bold]Question {i}/{len(question_pack.get('questions'))}[/bold]")
                console.print(f"ID: {question.get('question_id')}")
                console.print(f"Type: {question.get('type')} (Blocking: {question.get('blocking_level')})")
                console.print(f"\n{question.get('question_text')}\n")
                console.print(f"[dim]Context: {question.get('context')}[/dim]\n")

                # Show suggested answers if available
                suggested = question.get("suggested_answers", [])
                if suggested:
                    console.print("[cyan]Suggested answers:[/cyan]")
                    for j, sugg in enumerate(suggested, 1):
                        console.print(f"  {j}. {sugg.get('answer_text')}")
                        console.print(f"     [dim]{sugg.get('rationale')}[/dim]")
                    console.print()

                answer_text = click.prompt("Your answer", type=str)
                evidence_refs = click.prompt(
                    "Evidence references (comma-separated)",
                    type=str,
                    default="user_input"
                ).split(",")
                evidence_refs = [ref.strip() for ref in evidence_refs if ref.strip()]

                answers.append({
                    "question_id": question.get("question_id"),
                    "answer_type": "text",
                    "answer_text": answer_text,
                    "evidence_refs": evidence_refs if evidence_refs else ["user_input"],
                    "provided_at": utc_now_iso(),
                    "provided_by": "human",
                    "rationale": f"Provided by user interactively"
                })
        else:
            # Non-interactive: create stub with fallback answers
            console.print("[yellow]Non-interactive mode: creating stub AnswerPack[/yellow]")
            for question in question_pack.get("questions", []):
                answers.append({
                    "question_id": question.get("question_id"),
                    "answer_type": "fallback",
                    "answer_text": question.get("default_strategy", "Proceed with default"),
                    "evidence_refs": ["fallback_strategy"],
                    "provided_at": utc_now_iso(),
                    "provided_by": "fallback"
                })

        # Build answer pack
        answer_pack = {
            "answer_pack_id": answer_pack_id,
            "schema_version": "0.11.0",
            "question_pack_id": question_pack.get("pack_id"),
            "intent_id": question_pack.get("intent_id"),
            "answers": answers,
            "provided_at": utc_now_iso(),
            "completeness": {
                "total_questions": len(question_pack.get("questions", [])),
                "answered": len(answers),
                "unanswered_question_ids": [],
                "fallback_used": not interactive
            },
            "lineage": {
                "nl_request_id": question_pack.get("intent_id", "unknown"),
                "pipeline_run_id": str(Path(question_pack_path).parent.parent),
                "created_by": "agentos-cli",
                "created_at": utc_now_iso()
            }
        }

        # Compute checksum
        answer_pack["checksum"] = store.compute_checksum(answer_pack)

        # Validate before saving
        console.print("\n[cyan]Validating AnswerPack...[/cyan]")
        valid, errors = validate_answer_pack(answer_pack, question_pack)
        if not valid:
            console.print("[red]Validation failed:[/red]")
            for error in errors:
                console.print(f"  - {error}")
            raise click.Abort()

        # Save
        output_file = store.save(answer_pack, Path(output_path))
        console.print(f"\n[green]✓ AnswerPack created: {output_file}[/green]")
        console.print(f"  ID: {answer_pack_id}")
        console.print(f"  Answers: {len(answers)}")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.Abort()


@answers_group.command(name="validate")
@click.option("--file", "answer_pack_path", required=True, type=click.Path(exists=True),
              help="Path to answer_pack.json file")
@click.option("--question-pack", "question_pack_path", type=click.Path(exists=True),
              help="Optional: path to question_pack.json for full validation")
def validate_cmd(answer_pack_path: str, question_pack_path: str = None):
    """Validate an AnswerPack against schemas and red lines."""
    try:
        # Load answer pack
        with open(answer_pack_path, "r", encoding="utf-8") as f:
            answer_pack = json.load(f)

        # Load question pack if provided
        question_pack = None
        if question_pack_path:
            with open(question_pack_path, "r", encoding="utf-8") as f:
                question_pack = json.load(f)

        console.print(f"[cyan]Validating AnswerPack: {answer_pack.get('answer_pack_id')}[/cyan]\n")

        # Validate
        valid, errors = validate_answer_pack(answer_pack, question_pack)

        if valid:
            console.print("[green]✓ AnswerPack is valid[/green]")
            console.print(f"  Answers: {len(answer_pack.get('answers', []))}")
            console.print(f"  Question Pack: {answer_pack.get('question_pack_id')}")
            console.print(f"  Checksum: {answer_pack.get('checksum')[:16]}...")
        else:
            console.print("[red]✗ Validation failed:[/red]\n")
            for error in errors:
                console.print(f"  - {error}")
            raise click.Abort()

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.Abort()


@answers_group.command(name="apply")
@click.option("--intent", "intent_path", required=True, type=click.Path(exists=True),
              help="Path to intent.json file")
@click.option("--answers", "answer_pack_path", required=True, type=click.Path(exists=True),
              help="Path to answer_pack.json file")
@click.option("--out", "output_path", required=True, type=click.Path(),
              help="Output path for enriched intent")
def apply_cmd(intent_path: str, answer_pack_path: str, output_path: str):
    """Apply AnswerPack to an Intent (for testing)."""
    try:
        # Load intent
        with open(intent_path, "r", encoding="utf-8") as f:
            intent = json.load(f)

        # Load answer pack
        with open(answer_pack_path, "r", encoding="utf-8") as f:
            answer_pack = json.load(f)

        # Load question pack (from same directory as intent)
        intent_dir = Path(intent_path).parent
        question_pack_path = intent_dir / "question_pack.json"
        
        if not question_pack_path.exists():
            console.print("[red]Error: question_pack.json not found in intent directory[/red]")
            raise click.Abort()

        with open(question_pack_path, "r", encoding="utf-8") as f:
            question_pack = json.load(f)

        console.print("[cyan]Applying AnswerPack to Intent...[/cyan]\n")

        # Apply
        from agentos.core.answers import AnswerApplier
        applier = AnswerApplier()
        enriched_intent = applier.apply_to_intent(intent, answer_pack, question_pack)

        # Save
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(enriched_intent, f, indent=2, ensure_ascii=False)

        console.print(f"[green]✓ Enriched intent saved: {output_file}[/green]")
        console.print(f"  Answers applied: {len(answer_pack.get('answers', []))}")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.Abort()


@answers_group.command(name="list")
@click.option("--question-pack-id", type=str, help="Filter by question pack ID")
def list_cmd(question_pack_id: str = None):
    """List all AnswerPacks."""
    try:
        store = AnswerStore()
        packs = store.list_packs(question_pack_id=question_pack_id)

        if not packs:
            console.print("[yellow]No AnswerPacks found[/yellow]")
            return

        table = Table(title="AnswerPacks")
        table.add_column("Answer Pack ID", style="cyan")
        table.add_column("Question Pack ID", style="magenta")
        table.add_column("Intent ID", style="blue")
        table.add_column("Answers", justify="right")
        table.add_column("Provided At")

        for pack in packs:
            table.add_row(
                pack["answer_pack_id"],
                pack["question_pack_id"],
                pack["intent_id"],
                str(pack["answer_count"]),
                pack["provided_at"]
            )

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.Abort()
