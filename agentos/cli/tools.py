"""CLI commands for Tool integration operations."""

import json
import click
from pathlib import Path
from rich.console import Console
from typing import Optional

console = Console()


@click.group(name="tool")
def tool_group():
    """Tool integration commands for external execution."""
    pass


@tool_group.command(name="pack")
@click.option("--from", "exec_req_path", required=True, type=click.Path(exists=True),
              help="Path to execution_request.json")
@click.option("--tool", required=True, type=click.Choice(["claude", "opencode"]),
              help="Tool type")
@click.option("--out", "output_path", required=True, type=click.Path(),
              help="Output path for tool_task_pack.json")
def pack_cmd(exec_req_path: str, tool: str, output_path: str):
    """Pack execution request into tool task pack."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from agentos.ext.tools import ClaudeCliAdapter, OpenCodeAdapter
    from agentos.core.infra.git_client import GitClientFactory
    
    try:
        # Load execution request
        with open(exec_req_path, "r", encoding="utf-8") as f:
            exec_request = json.load(f)
        
        # Get repo state using GitClient
        repo_state = {
            "branch": "main",
            "commit_hash": "0" * 40,
            "is_dirty": False
        }
        
        try:
            git_client = GitClientFactory.get_client(Path.cwd())
            status = git_client.status()
            repo_state["branch"] = status["branch"]
            repo_state["commit_hash"] = git_client.get_current_commit()
            repo_state["is_dirty"] = status["is_dirty"]
        except:
            pass
        
        # Select adapter
        if tool == "claude":
            adapter = ClaudeCliAdapter()
        else:
            adapter = OpenCodeAdapter()
        
        # Pack
        task_pack = adapter.pack(exec_request, repo_state)
        
        # Save
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(task_pack, f, indent=2)
        
        console.print(f"[green]✓ Tool task pack created: {output_file}[/green]")
        console.print(f"  ID: {task_pack['tool_task_pack_id']}")
        console.print(f"  Tool: {task_pack['tool_type']}")
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.Abort()


@tool_group.command(name="dispatch")
@click.option("--pack", "pack_path", required=True, type=click.Path(exists=True),
              help="Path to tool_task_pack.json")
def dispatch_cmd(pack_path: str):
    """Generate dispatch command for tool execution."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from agentos.ext.tools import ClaudeCliAdapter, OpenCodeAdapter
    
    try:
        # Load task pack
        with open(pack_path, "r", encoding="utf-8") as f:
            task_pack = json.load(f)
        
        tool_type = task_pack["tool_type"]
        output_dir = Path(pack_path).parent
        
        # Select adapter
        if tool_type == "claude_cli":
            adapter = ClaudeCliAdapter()
        elif tool_type == "opencode":
            adapter = OpenCodeAdapter()
        else:
            console.print(f"[red]Unknown tool type: {tool_type}[/red]")
            raise click.Abort()
        
        # Generate dispatch command
        command = adapter.dispatch(task_pack, output_dir)
        
        console.print("[cyan]Tool Dispatch Command:[/cyan]\n")
        console.print(command)
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.Abort()


@tool_group.command(name="collect")
@click.option("--run", "task_pack_id", required=True, help="Task pack ID")
@click.option("--in", "input_dir", required=True, type=click.Path(exists=True),
              help="Tool output directory")
@click.option("--out", "output_path", required=True, type=click.Path(),
              help="Output path for tool_result_pack.json")
def collect_cmd(task_pack_id: str, input_dir: str, output_path: str):
    """Collect tool execution results."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from agentos.ext.tools import ClaudeCliAdapter
    
    try:
        adapter = ClaudeCliAdapter()
        
        # Collect results
        result_pack = adapter.collect(task_pack_id, Path(input_dir))
        
        # Save
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result_pack, f, indent=2)
        
        console.print(f"[green]✓ Tool result pack created: {output_file}[/green]")
        console.print(f"  ID: {result_pack['tool_result_pack_id']}")
        console.print(f"  Status: {result_pack['status']}")
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.Abort()


@tool_group.command(name="verify")
@click.option("--result", "result_path", required=True, type=click.Path(exists=True),
              help="Path to tool_result_pack.json")
def verify_cmd(result_path: str):
    """Verify tool execution results."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from agentos.ext.tools import ClaudeCliAdapter
    
    try:
        # Load result pack
        with open(result_path, "r", encoding="utf-8") as f:
            result_pack = json.load(f)
        
        tool_type = result_pack["tool_type"]
        
        # Select adapter
        if tool_type == "claude_cli":
            adapter = ClaudeCliAdapter()
        else:
            adapter = ClaudeCliAdapter()  # fallback
        
        # Verify
        is_valid, errors = adapter.verify(result_pack)
        
        if is_valid:
            console.print("[green]✅ Tool result verification PASSED[/green]")
        else:
            console.print("[red]❌ Tool result verification FAILED[/red]")
            for error in errors:
                console.print(f"  - {error}")
            raise click.Abort()
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.Abort()


@tool_group.command(name="health")
@click.option("--provider", help="Only check specific provider")
def health_cmd(provider: Optional[str] = None):
    """
    Check health status of all registered tool adapters.
    
    Step 4: Multi-Model Health Check
    
    Reports status for each adapter:
    - connected: Adapter is ready to use
    - not_configured: Missing API key / endpoint
    - invalid_token: Authentication failed
    - unreachable: Service not accessible
    - model_missing: Local model not found
    - schema_mismatch: Response format mismatch
    """
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from agentos.ext.tools import (
        ClaudeCliAdapter,
        OpenAIChatAdapter,
        OllamaAdapter,
        LMStudioAdapter,
        LlamaCppAdapter
    )
    from rich.table import Table
    
    try:
        # Define adapters to check
        adapters_to_check = [
            ("claude_cli", ClaudeCliAdapter(), "cloud"),
            ("openai_chat", OpenAIChatAdapter(model_id="gpt-4o"), "cloud"),
            ("ollama", OllamaAdapter(model_id="llama3"), "local"),
            # Step 4 扩展：LM Studio + llama.cpp
            ("lmstudio", LMStudioAdapter(), "local"),
            ("llamacpp", LlamaCppAdapter(), "local"),
        ]
        
        # 如果指定 --provider，只检查该 provider
        if provider:
            adapters_to_check = [a for a in adapters_to_check if a[0] == provider]
            if not adapters_to_check:
                console.print(f"[red]Unknown provider: {provider}[/red]")
                raise click.Abort()
        
        # Create table
        table = Table(title="🔧 Tool Adapters Health Status")
        table.add_column("Adapter", style="cyan")
        table.add_column("Provider", style="magenta")
        table.add_column("Status", style="bold")
        table.add_column("Details", style="dim")
        
        connected_count = 0
        total_count = len(adapters_to_check)
        
        for adapter_name, adapter, provider_type in adapters_to_check:
            try:
                health = adapter.health_check()
                
                # Status color
                if health.status == "connected":
                    status_text = f"[green]✓ {health.status}[/green]"
                    connected_count += 1
                elif health.status in ["not_configured", "model_missing"]:
                    status_text = f"[yellow]⚠ {health.status}[/yellow]"
                else:
                    status_text = f"[red]✗ {health.status}[/red]"
                
                table.add_row(
                    adapter_name,
                    provider_type,
                    status_text,
                    health.details[:60] + "..." if len(health.details) > 60 else health.details
                )
                
            except Exception as e:
                table.add_row(
                    adapter_name,
                    provider_type,
                    "[red]✗ error[/red]",
                    str(e)[:60]
                )
        
        console.print(table)
        console.print(f"\n[bold]Summary:[/bold] {connected_count}/{total_count} adapters connected")
        
        if connected_count == 0:
            console.print("\n[yellow]⚠ No adapters are connected. Configure at least one:[/yellow]")
            console.print("  - Claude CLI: Install from https://claude.ai/download")
            console.print("  - OpenAI: Set OPENAI_API_KEY environment variable")
            console.print("  - Ollama: Start Ollama service (http://localhost:11434)")
            console.print("  - LM Studio: Start LM Studio with Local Server (http://localhost:1234)")
            console.print("  - llama.cpp: Start llama-server (http://localhost:8080)")
        
    except Exception as e:
        console.print(f"[red]Error checking health: {e}[/red]")
        raise click.Abort()


@tool_group.command(name="auth")
@click.argument("action", type=click.Choice(["set", "status", "clear"]))
@click.option("--provider", help="Provider name (lmstudio / llamacpp / openai / ollama)")
@click.option("--api-key", help="API key to set")
def auth_cmd(action: str, provider: Optional[str] = None, api_key: Optional[str] = None):
    """
    Manage tool adapter authentication.
    
    Step 4 扩展：LM Studio + llama.cpp 凭证管理
    
    Actions:
    - set: Set API key for a provider
    - status: Show authentication status for all providers
    - clear: Clear credentials for a provider
    
    Examples:
      agentos tool auth set --provider lmstudio --api-key lm-studio
      agentos tool auth status
      agentos tool auth clear --provider lmstudio
    """
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from agentos.core.infra.credentials_manager import CredentialsManager
    from rich.table import Table
    
    try:
        creds_manager = CredentialsManager()
        
        if action == "set":
            if not provider:
                console.print("[red]Error: --provider is required for 'set' action[/red]")
                raise click.Abort()
            
            if not api_key:
                console.print("[red]Error: --api-key is required for 'set' action[/red]")
                raise click.Abort()
            
            # 存储凭证
            creds_manager.set_credential(provider, "api_key", api_key)
            console.print(f"[green]✓ API key set for provider: {provider}[/green]")
            console.print(f"  Stored in: {creds_manager.creds_file}")
            
        elif action == "status":
            # 显示所有 provider 的认证状态
            providers = creds_manager.list_providers()
            
            if not providers:
                console.print("[yellow]No credentials configured[/yellow]")
                console.print("\nConfigure credentials with:")
                console.print("  agentos tool auth set --provider <name> --api-key <key>")
                return
            
            table = Table(title="🔐 Authentication Status")
            table.add_column("Provider", style="cyan")
            table.add_column("Keys Configured", style="green")
            
            for prov, keys in providers.items():
                table.add_row(prov, ", ".join(keys.keys()))
            
            console.print(table)
            console.print(f"\nCredentials file: {creds_manager.creds_file}")
            
        elif action == "clear":
            if not provider:
                console.print("[red]Error: --provider is required for 'clear' action[/red]")
                raise click.Abort()
            
            # 清除凭证
            creds_manager.clear_credential(provider)
            console.print(f"[green]✓ Credentials cleared for provider: {provider}[/green]")
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.Abort()
