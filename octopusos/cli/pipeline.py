"""CLI command for pipeline management (including resume)."""

import click
from pathlib import Path
from rich.console import Console

console = Console()


@click.group(name="pipeline")
def pipeline_group():
    """Pipeline management commands."""
    pass


@pipeline_group.command(name="resume")
@click.option("--run", "run_dir", required=True, type=click.Path(exists=True),
              help="Path to blocked pipeline run directory")
@click.option("--answers", "answer_pack_path", required=True, type=click.Path(exists=True),
              help="Path to answer_pack.json file")
@click.option("--dry-run", is_flag=True, help="Show what would be done without executing")
def resume_cmd(run_dir: str, answer_pack_path: str, dry_run: bool):
    """Resume a BLOCKED pipeline with AnswerPack."""
    import json
    import sys
    from agentos.core.answers import apply_answer_pack, validate_answer_pack

    try:
        run_path = Path(run_dir)
        answer_pack_file = Path(answer_pack_path)

        console.print(f"[cyan]Resuming pipeline: {run_path.name}[/cyan]")
        console.print(f"Using AnswerPack: {answer_pack_file.name}\n")

        # Load answer pack
        with open(answer_pack_file, "r", encoding="utf-8") as f:
            answer_pack = json.load(f)

        # Load question pack for validation
        question_pack_path = run_path / "01_intent" / "question_pack.json"
        if not question_pack_path.exists():
            console.print("[red]Error: question_pack.json not found in pipeline run[/red]")
            raise click.Abort()

        with open(question_pack_path, "r", encoding="utf-8") as f:
            question_pack = json.load(f)

        # Validate answer pack
        console.print("[cyan]Validating AnswerPack...[/cyan]")
        valid, errors = validate_answer_pack(answer_pack, question_pack)
        if not valid:
            console.print("[red]Validation failed:[/red]")
            for error in errors:
                console.print(f"  - {error}")
            raise click.Abort()

        console.print("[green]✓ AnswerPack validated[/green]\n")

        if dry_run:
            console.print("[yellow]DRY RUN - would apply answers and resume pipeline[/yellow]")
            return

        # Apply answers
        console.print("[cyan]Applying AnswerPack to pipeline...[/cyan]")
        resume_context = apply_answer_pack(run_path, answer_pack)

        console.print(f"[green]✓ Answers applied[/green]")
        console.print(f"  Resume from: {resume_context.get('resume_from_step')}\n")

        # Get NL request path
        nl_request_path = run_path / "01_intent" / f"{run_path.name}_nl_request.json"
        if not nl_request_path.exists():
            # Try alternate naming
            nl_files = list((run_path / "01_intent").glob("*_nl_request.json"))
            if nl_files:
                nl_request_path = nl_files[0]
            else:
                console.print("[red]Error: NL request file not found[/red]")
                raise click.Abort()

        # Re-run pipeline with the enriched intent
        console.print("[cyan]Re-running pipeline...[/cyan]\n")
        
        # Import and call pipeline directly instead of subprocess
        sys.path.insert(0, str(Path.cwd() / "scripts" / "pipeline"))
        try:
            from run_nl_to_pr_artifacts import run_pipeline
            
            success = run_pipeline(
                nl_path=nl_request_path,
                output_dir=run_path,
                resume=True
            )
            
            if success:
                console.print("[green]✓ Pipeline resumed successfully[/green]")
            else:
                console.print("[red]✗ Pipeline failed[/red]")
                raise click.Abort()
        finally:
            sys.path.pop(0)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.Abort()
