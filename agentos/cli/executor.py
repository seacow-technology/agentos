"""CLI commands for Executor operations."""

import json
import click
from pathlib import Path
from rich.console import Console
from datetime import datetime, timezone

console = Console()


@click.group(name="exec")
def exec_group():
    """Executor commands for controlled execution."""
    pass


@exec_group.command(name="plan")
@click.option("--from", "dry_result_path", required=True, type=click.Path(exists=True),
              help="Path to dry_execution_result.json")
@click.option("--out", "output_path", required=True, type=click.Path(),
              help="Output path for execution_request.json")
def plan_cmd(dry_result_path: str, output_path: str):
    """Create execution request from dry run result."""
    try:
        # Load dry execution result
        with open(dry_result_path, "r", encoding="utf-8") as f:
            dry_result = json.load(f)
        
        exec_req_id = f"exec_req_{dry_result.get('dry_execution_result_id', 'unknown')}"
        
        execution_request = {
            "execution_request_id": exec_req_id,
            "schema_version": "0.11.1",
            "dry_execution_result_id": dry_result.get("dry_execution_result_id"),
            "intent_id": dry_result.get("intent_id", "unknown"),
            "execution_mode": "controlled",
            "allowed_operations": ["file_write", "file_update", "lint", "test"],
            "requires_review": dry_result.get("requires_review", False),
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Save
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(execution_request, f, indent=2)
        
        console.print(f"[green]✓ Execution request created: {output_file}[/green]")
        console.print(f"  ID: {exec_req_id}")
        console.print(f"  Requires review: {execution_request['requires_review']}")
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.Abort()


@exec_group.command(name="run")
@click.option("--request", "request_path", required=True, type=click.Path(exists=True),
              help="Path to execution_request.json")
@click.option("--policy", "policy_path", required=True, type=click.Path(exists=True),
              help="Path to sandbox_policy.json")
@click.option("--repo", default=".", help="Repository path")
@click.option("--out", "output_dir", default="outputs/executor", help="Output directory")
def run_cmd(request_path: str, policy_path: str, repo: str, output_dir: str):
    """Run execution with controlled sandbox."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from agentos.core.executor import ExecutorEngine
    from agentos.core.executor.sandbox_policy import load_sandbox_policy
    from agentos.core.executor.run_tape import create_run_tape
    
    try:
        console.print("[cyan]Starting controlled execution...[/cyan]\n")
        
        # Load and validate policy
        console.print(f"[cyan]Loading sandbox policy: {policy_path}[/cyan]")
        try:
            policy = load_sandbox_policy(Path(policy_path))
            console.print(f"[green]✓ Policy validated: {policy.policy_id}[/green]")
            console.print(f"  Version: {policy.schema_version}")
            console.print(f"  Allowed operations: {policy.allowlist.get('file_operations', [])}")
            console.print(f"  Max files: {policy.get_max_files()}")
            console.print()
        except Exception as e:
            console.print(f"[red]✗ Policy validation failed: {e}[/red]")
            raise click.Abort()
        
        # Load request
        with open(request_path, "r", encoding="utf-8") as f:
            execution_request = json.load(f)
        
        console.print(f"[cyan]Execution request: {execution_request['execution_request_id']}[/cyan]")
        console.print(f"  Requires review: {execution_request.get('requires_review', False)}")
        console.print()
        
        # Create output directory
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        
        # 不再在 CLI 层初始化 RunTape（交给 ExecutorEngine 处理）
        
        # Initialize engine
        engine = ExecutorEngine(
            repo_path=Path(repo),
            output_dir=out_path
        )
        
        # Execute (pass policy_path for P0-RT1)
        result = engine.execute(
            execution_request,
            policy.to_dict(),  # 向后兼容
            policy_path=Path(policy_path)  # P0-RT1: 新参数
        )
        
        # Display result
        if result["status"] == "success":
            console.print(f"[green]✓ Execution completed successfully[/green]")
        elif result["status"] == "denied":
            console.print(f"[red]✗ Execution denied by policy[/red]")
            if "policy_denied" in result:
                console.print(f"  Operation: {result['policy_denied'].get('operation')}")
                console.print(f"  Reason: {result['policy_denied'].get('reason')}")
        else:
            console.print(f"[red]✗ Execution failed: {result.get('error', 'Unknown error')}[/red]")
        
        console.print(f"\nResult ID: {result['execution_result_id']}")
        console.print(f"Status: {result['status']}")
        console.print(f"Operations: {len(result.get('operations_executed', []))}")
        
        # P0-RT3: 显示 worktree 证据
        if result["status"] == "success":
            console.print(f"Commits brought back: {result.get('commits_brought_back', 0)}")
            console.print(f"Patches generated: {result.get('patches_generated', 0)}")
        
        # P0-RT1: 根据状态返回正确的 exit code
        if result["status"] != "success":
            raise click.Abort()
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.Abort()


@exec_group.command(name="status")
@click.option("--run", "run_id", required=True, help="Execution run ID")
@click.option("--out", "output_dir", default="outputs/executor", help="Output directory")
def status_cmd(run_id: str, output_dir: str):
    """Check execution status."""
    try:
        run_dir = Path(output_dir) / run_id
        
        if not run_dir.exists():
            console.print(f"[red]Run not found: {run_id}[/red]")
            return
        
        # Load result
        result_file = run_dir / "execution_result.json"
        if result_file.exists():
            with open(result_file, "r", encoding="utf-8") as f:
                result = json.load(f)
            
            console.print(f"[cyan]Execution Status: {run_id}[/cyan]\n")
            console.print(f"Status: {result['status']}")
            console.print(f"Started: {result['started_at']}")
            console.print(f"Completed: {result['completed_at']}")
            console.print(f"Operations: {len(result.get('operations_executed', []))}")
        else:
            console.print(f"[yellow]Execution in progress or failed to generate result[/yellow]")
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.Abort()


@exec_group.command(name="rollback")
@click.option("--run", "run_dir_path", required=True, help="Execution run directory")
@click.option("--to", "target_step", help="Target step to rollback to (e.g., step_03)")
@click.option("--repo", default=".", help="Repository path")
def rollback_cmd(run_dir_path: str, target_step: str, repo: str):
    """Rollback failed execution."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from agentos.core.executor.rollback import RollbackManager
    from agentos.core.executor.run_tape import RunTape
    
    try:
        console.print(f"[cyan]Rolling back execution...[/cyan]\n")
        
        run_dir = Path(run_dir_path)
        if not run_dir.exists():
            console.print(f"[red]Run directory not found: {run_dir}[/red]")
            return
        
        # Initialize managers
        manager = RollbackManager(Path(repo))
        run_tape = RunTape(run_dir)
        
        # Get target snapshot
        if target_step:
            snapshot = run_tape.get_snapshot(target_step)
            if not snapshot:
                console.print(f"[red]Snapshot not found for {target_step}[/red]")
                return
            
            console.print(f"[cyan]Target: {target_step}[/cyan]")
            console.print(f"  Files: {snapshot.get('file_count', 0)}")
            console.print()
        else:
            # Use latest rollback point
            rollback_points = manager.get_rollback_points()
            if not rollback_points:
                console.print(f"[red]No rollback points available[/red]")
                return
            snapshot = rollback_points[-1]
        
        # Perform rollback
        console.print("[cyan]Performing rollback...[/cyan]")
        result = manager.rollback_to(snapshot, verify_checksums=True)
        
        if result["success"]:
            console.print(f"[green]✓ Rollback successful[/green]")
            console.print(f"  Checksums match: {result['checksums_match']}")
            
            # Generate rollback proof
            proof_file = run_dir / "rollback_proof.json"
            manager.generate_rollback_proof(result, proof_file)
            console.print(f"  Proof saved: {proof_file}")
        else:
            console.print(f"[red]✗ Rollback failed: {result.get('error', 'Unknown')}[/red]")
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        import traceback
        traceback.print_exc()
        raise click.Abort()
        
        # Perform rollback
        manager = RollbackManager(Path(repo))
        success = manager.rollback_to(rollback_point)
        
        if success:
            console.print(f"[green]✓ Rollback successful[/green]")
        else:
            console.print(f"[red]✗ Rollback failed[/red]")
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.Abort()
