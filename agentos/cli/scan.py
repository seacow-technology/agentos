"""CLI scan command"""

import json
from datetime import datetime
from pathlib import Path

import click
from rich.console import Console

from agentos.core.scanner import ScannerPipeline
from agentos.core.verify import validate_factpack
from agentos.store import get_db

console = Console()


@click.command()
@click.argument("project_id")
def scan_cmd(project_id: str):
    """Scan project and generate FactPack"""
    console.print(f"ℹ️  Scanning project: [cyan]{project_id}[/cyan]")
    
    try:
        # Get project path from database
        db = get_db()
        cursor = db.cursor()
        project = cursor.execute(
            "SELECT path FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        
        if not project:
            console.print(f"❌ [red]Project '{project_id}' not found[/red]")
            db.close()
            raise click.Abort()
        
        project_path = Path(project["path"])
        
        # Create run record
        cursor.execute(
            "INSERT INTO runs (project_id, type, status) VALUES (?, 'scan', 'RUNNING')",
            (project_id,)
        )
        run_id = cursor.lastrowid
        db.commit()
        
        try:
            # Run scanner
            console.print("🔍 Running scanner pipeline...")
            scanner = ScannerPipeline(project_id, project_path)
            factpack = scanner.scan()
            
            # Validate
            console.print("✓ Validating FactPack...")
            is_valid, errors = validate_factpack(factpack)
            
            if not is_valid:
                console.print("❌ [red]Generated FactPack is invalid![/red]")
                for error in errors:
                    console.print(f"  • {error}")
                
                cursor.execute(
                    "UPDATE runs SET status = 'FAILED', completed_at = CURRENT_TIMESTAMP, error = ? WHERE id = ?",
                    (f"Invalid FactPack: {errors[0]}", run_id)
                )
                db.commit()
                db.close()
                raise click.Abort()
            
            # Save to reports/
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_dir = Path("reports") / project_id / timestamp
            report_dir.mkdir(parents=True, exist_ok=True)
            
            factpack_path = report_dir / "factpack.json"
            with open(factpack_path, "w", encoding="utf-8") as f:
                json.dump(factpack, f, indent=2)
            
            # Record artifact
            cursor.execute(
                "INSERT INTO artifacts (run_id, type, path) VALUES (?, 'factpack', ?)",
                (run_id, str(factpack_path))
            )
            
            # Mark run as succeeded
            cursor.execute(
                "UPDATE runs SET status = 'SUCCEEDED', completed_at = CURRENT_TIMESTAMP WHERE id = ?",
                (run_id,)
            )
            db.commit()
            db.close()
            
            evidence_count = len(factpack.get("evidence", []))
            console.print(f"✅ FactPack saved: [green]{factpack_path}[/green]")
            console.print(f"📊 Evidence collected: {evidence_count} items")
            
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
        console.print(f"❌ [red]Scan failed: {e}[/red]")
        raise click.Abort()
