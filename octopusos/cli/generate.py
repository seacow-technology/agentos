"""CLI generate commands"""

import json
from pathlib import Path

import click
from rich.console import Console

from agentos.core.generator import AgentSpecBuilder
from agentos.core.verify import MarkdownLinter, MarkdownRenderer
from agentos.store import get_db

console = Console()


@click.group()
def generate_group():
    """Generate artifacts"""
    pass


@generate_group.command(name="agent")
@click.argument("agent_type")
@click.option("--project", required=True, help="Project ID")
def generate_agent(agent_type: str, project: str):
    """Generate agent spec and markdown"""
    console.print(f"ℹ️  Generating {agent_type} for project: [cyan]{project}[/cyan]")
    
    try:
        # Find latest FactPack
        reports_dir = Path("reports") / project
        if not reports_dir.exists():
            console.print(f"❌ [red]No reports found for project '{project}'[/red]")
            console.print("💡 Run 'agentos scan {project}' first")
            raise click.Abort()
        
        # Get most recent factpack
        factpack_files = sorted(reports_dir.glob("*/factpack.json"), reverse=True)
        if not factpack_files:
            console.print(f"❌ [red]No FactPack found for project '{project}'[/red]")
            raise click.Abort()
        
        factpack_path = factpack_files[0]
        console.print(f"📋 Loading FactPack: {factpack_path}")
        
        with open(factpack_path, encoding="utf-8") as f:
            factpack = json.load(f)
        
        # Create run record
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO runs (project_id, type, status) VALUES (?, 'generate', 'RUNNING')",
            (project,)
        )
        run_id = cursor.lastrowid
        db.commit()
        
        try:
            # Generate AgentSpec
            console.print("🤖 Calling OpenAI to generate AgentSpec...")
            builder = AgentSpecBuilder()
            agent_spec = builder.generate(factpack, agent_type)
            
            # Save spec
            artifacts_dir = Path("artifacts") / project / "spec"
            artifacts_dir.mkdir(parents=True, exist_ok=True)
            
            spec_path = artifacts_dir / f"{agent_type}.json"
            with open(spec_path, "w", encoding="utf-8") as f:
                json.dump(agent_spec, f, indent=2)
            
            # Record artifact
            cursor.execute(
                "INSERT INTO artifacts (run_id, type, path) VALUES (?, 'agent_spec', ?)",
                (run_id, str(spec_path))
            )
            
            console.print(f"✅ AgentSpec saved: [green]{spec_path}[/green]")
            
            # Render Markdown
            console.print("📝 Rendering Markdown...")
            renderer = MarkdownRenderer()
            md_dir = Path("artifacts") / project / "agents"
            md_path = md_dir / f"{agent_type}.md"
            renderer.render_to_file(agent_spec, md_path)
            
            # Record markdown artifact
            cursor.execute(
                "INSERT INTO artifacts (run_id, type, path) VALUES (?, 'agent_md', ?)",
                (run_id, str(md_path))
            )
            
            console.print(f"✅ Markdown saved: [green]{md_path}[/green]")
            
            # Lint Markdown
            console.print("🔍 Linting Markdown...")
            linter = MarkdownLinter()
            is_valid, errors = linter.lint_file(md_path, factpack)
            
            if not is_valid:
                console.print("⚠️  [yellow]Markdown lint warnings:[/yellow]")
                for error in errors:
                    console.print(f"  • {error}")
            else:
                console.print("✅ Markdown lint passed")
            
            # Mark success
            cursor.execute(
                "UPDATE runs SET status = 'SUCCEEDED', completed_at = CURRENT_TIMESTAMP WHERE id = ?",
                (run_id,)
            )
            db.commit()
            db.close()
            
            console.print(f"\n🎉 [green]Agent generated successfully![/green]")
            console.print(f"   Spec: {spec_path}")
            console.print(f"   Docs: {md_path}")
            
        except click.Abort:
            raise
        except Exception as e:
            cursor.execute(
                "UPDATE runs SET status = 'FAILED', completed_at = CURRENT_TIMESTAMP, error = ? WHERE id = ?",
                (str(e), run_id)
            )
            db.commit()
            db.close()
            raise
        
    except click.Abort:
        raise
    except Exception as e:
        console.print(f"❌ [red]Generation failed: {e}[/red]")
        import traceback
        traceback.print_exc()
        raise click.Abort()
