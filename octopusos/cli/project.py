"""CLI project commands"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import click
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from ulid import ULID

from agentos.core.git import GitClientWithAuth, CredentialsManager
from agentos.core.project.repository import ProjectRepository
from agentos.schemas.project import RepoRole, RepoSpec
from agentos.store import get_db, get_db_path

console = Console()


@click.group()
def project_group():
    """Manage projects"""
    pass


# Import trace command
from agentos.cli.commands.project_trace import project_trace

# Add trace command to project group
project_group.add_command(project_trace, name="trace")


@project_group.command(name="add")
@click.argument("path", type=click.Path(exists=True))
@click.option("--id", "project_id", help="Project ID (default: directory name)")
def add_project(path: str, project_id: Optional[str]):
    """Register a project"""
    try:
        project_path = Path(path).resolve()
        
        if project_id is None:
            project_id = project_path.name
        
        db = get_db()
        cursor = db.cursor()
        
        # Check if already exists
        existing = cursor.execute(
            "SELECT id FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        
        if existing:
            console.print(f"⚠️  [yellow]Project '{project_id}' already registered[/yellow]")
            db.close()
            return
        
        # Insert project
        cursor.execute(
            "INSERT INTO projects (id, path) VALUES (?, ?)",
            (project_id, str(project_path))
        )
        db.commit()
        db.close()
        
        console.print(f"✅ Project registered: [green]{project_id}[/green] → {project_path}")
    except Exception as e:
        console.print(f"❌ [red]Failed to add project: {e}[/red]")
        raise click.Abort()


@project_group.command(name="list")
def list_projects():
    """List registered projects"""
    try:
        db = get_db()
        cursor = db.cursor()

        projects = cursor.execute(
            "SELECT id, path, added_at FROM projects ORDER BY added_at DESC"
        ).fetchall()

        db.close()

        if not projects:
            console.print("ℹ️  No projects registered yet")
            return

        table = Table(title="Registered Projects")
        table.add_column("ID", style="cyan")
        table.add_column("Path", style="green")
        table.add_column("Added At", style="yellow")

        for project in projects:
            table.add_row(project["id"], project["path"], project["added_at"])

        console.print(table)
    except Exception as e:
        console.print(f"❌ [red]Failed to list projects: {e}[/red]")
        raise click.Abort()


# ============================================================================
# Multi-Repo Import Command
# ============================================================================


class RepoConfig:
    """Repository configuration for CLI import"""

    def __init__(
        self,
        name: str,
        url: Optional[str] = None,
        path: str = ".",
        role: str = "code",
        writable: bool = True,
        branch: str = "main",
        auth_profile: Optional[str] = None,
    ):
        self.name = name
        self.url = url
        self.path = path
        self.role = role
        self.writable = writable
        self.branch = branch
        self.auth_profile = auth_profile

    @staticmethod
    def from_cli_option(option_str: str) -> "RepoConfig":
        """Parse from CLI --repo option string

        Format: name=backend,url=git@github.com:org/backend,path=./be,role=code,writable=true

        Args:
            option_str: Comma-separated key=value pairs

        Returns:
            RepoConfig instance

        Raises:
            ValueError: If required fields missing or invalid format
        """
        parts = {}
        for part in option_str.split(","):
            if "=" not in part:
                raise ValueError(f"Invalid repo option format: {part} (expected key=value)")
            key, value = part.split("=", 1)
            parts[key.strip()] = value.strip()

        # Validate required fields
        if "name" not in parts:
            raise ValueError("Repo 'name' is required")

        # Parse writable field
        writable = True
        if "writable" in parts:
            writable_str = parts["writable"].lower()
            if writable_str not in ("true", "false", "1", "0"):
                raise ValueError(f"Invalid writable value: {parts['writable']}")
            writable = writable_str in ("true", "1")

        return RepoConfig(
            name=parts["name"],
            url=parts.get("url"),
            path=parts.get("path", "."),
            role=parts.get("role", "code"),
            writable=writable,
            branch=parts.get("branch", "main"),
            auth_profile=parts.get("auth_profile"),
        )

    @staticmethod
    def from_dict(data: Dict) -> "RepoConfig":
        """Parse from dictionary (from YAML/JSON config)

        Args:
            data: Dictionary with repo configuration

        Returns:
            RepoConfig instance
        """
        return RepoConfig(
            name=data["name"],
            url=data.get("url"),
            path=data.get("path", "."),
            role=data.get("role", "code"),
            writable=data.get("writable", True),
            branch=data.get("branch", "main"),
            auth_profile=data.get("auth_profile"),
        )


def parse_config_file(config_path: Path) -> Tuple[str, Optional[str], List[RepoConfig]]:
    """Parse project configuration from YAML or JSON file

    Args:
        config_path: Path to configuration file

    Returns:
        Tuple of (project_name, description, list of RepoConfig)

    Raises:
        ValueError: If file format invalid or required fields missing
    """
    if not config_path.exists():
        raise ValueError(f"Config file not found: {config_path}")

    # Read file
    content = config_path.read_text()

    # Parse based on extension
    if config_path.suffix in (".yaml", ".yml"):
        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML format: {e}")
    elif config_path.suffix == ".json":
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format: {e}")
    else:
        raise ValueError(f"Unsupported file format: {config_path.suffix} (use .yaml, .yml, or .json)")

    # Validate required fields
    if "name" not in data:
        raise ValueError("Config file must have 'name' field")
    if "repos" not in data or not data["repos"]:
        raise ValueError("Config file must have 'repos' field with at least one repository")

    project_name = data["name"]
    description = data.get("description")
    repos = [RepoConfig.from_dict(repo) for repo in data["repos"]]

    return project_name, description, repos


def validate_repo_config(repo: RepoConfig) -> Tuple[bool, Optional[str]]:
    """Validate repository configuration

    Args:
        repo: Repository configuration

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Validate role
    try:
        RepoRole(repo.role)
    except ValueError:
        return False, f"Invalid role '{repo.role}' for repo '{repo.name}'"

    # Validate path format
    if repo.path and ".." in repo.path:
        # Allow relative paths like ../shared, but warn
        console.print(f"⚠️  [yellow]Warning: Repo '{repo.name}' uses parent directory path '{repo.path}'[/yellow]")

    return True, None


def validate_workspace_conflicts(repos: List[RepoConfig]) -> Tuple[bool, List[str]]:
    """Check for workspace path conflicts between repositories

    Args:
        repos: List of repository configurations

    Returns:
        Tuple of (is_valid, list of error messages)
    """
    errors = []
    seen_paths = {}

    for repo in repos:
        normalized_path = os.path.normpath(repo.path)

        # Check for exact duplicates
        if normalized_path in seen_paths:
            errors.append(
                f"Path conflict: repos '{seen_paths[normalized_path]}' and '{repo.name}' "
                f"both use path '{repo.path}'"
            )
        else:
            seen_paths[normalized_path] = repo.name

    return len(errors) == 0, errors


def validate_auth_profiles(repos: List[RepoConfig]) -> Tuple[bool, List[str]]:
    """Check if auth profiles exist for repositories that need them

    Args:
        repos: List of repository configurations

    Returns:
        Tuple of (is_valid, list of error messages)
    """
    errors = []
    creds_manager = CredentialsManager()

    for repo in repos:
        if repo.auth_profile:
            # Check if profile exists
            profile = creds_manager.get_profile(repo.auth_profile)
            if not profile:
                errors.append(
                    f"Repo '{repo.name}' references non-existent auth profile '{repo.auth_profile}'. "
                    f"Run 'agentos auth add' to create it."
                )
        elif repo.url and (repo.url.startswith("git@") or repo.url.startswith("https://")):
            # Warn if URL requires auth but no profile specified
            console.print(
                f"⚠️  [yellow]Warning: Repo '{repo.name}' has URL but no auth_profile specified. "
                f"You may need to configure authentication.[/yellow]"
            )

    return len(errors) == 0, errors


def test_remote_url(url: str, auth_profile: Optional[str] = None) -> Tuple[bool, Optional[str]]:
    """Test if remote URL is accessible (with read/write probe)

    Args:
        url: Git remote URL
        auth_profile: Optional auth profile name

    Returns:
        Tuple of (is_accessible, error_message)
    """
    try:
        git_client = GitClientWithAuth()

        # Get auth profile if specified
        profile = None
        if auth_profile:
            profile = git_client.credentials.get_profile(auth_profile)
            if not profile:
                return False, f"Auth profile '{auth_profile}' not found"

        # Probe repository permissions
        result = git_client.probe(url, profile=profile, use_cache=True)

        if result.can_read:
            return True, None
        else:
            return False, result.error_message or "Unable to access remote URL"

    except Exception as e:
        return False, f"Unexpected error: {e}"


@project_group.command(name="import")
@click.argument("project_name", required=False)
@click.option("--from", "config_file", type=click.Path(exists=True), help="Import from config file (YAML/JSON)")
@click.option("--repo", "repos", multiple=True, help="Add repository (can be repeated)")
@click.option("--description", help="Project description")
@click.option("--skip-validation", is_flag=True, help="Skip validation checks")
@click.option("--require-write", is_flag=True, help="Require write permissions for writable repos (fails import if missing)")
@click.option("--dry-run", is_flag=True, help="Preview operations without making changes")
@click.option("--force", is_flag=True, help="Force overwrite existing directories (WARNING: destructive)")
@click.option("--workspace-root", type=click.Path(), help="Workspace root directory (default: current directory)")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompts")
@click.option("--no-gitignore", is_flag=True, help="Skip automatic .gitignore creation")
def import_project(
    project_name: Optional[str],
    config_file: Optional[str],
    repos: Tuple[str, ...],
    description: Optional[str],
    skip_validation: bool,
    require_write: bool,
    dry_run: bool,
    force: bool,
    workspace_root: Optional[str],
    yes: bool,
    no_gitignore: bool,
):
    """Import a multi-repository project

    \b
    Examples:
        # Import from config file
        agentos project import --from project.yaml

        # Import with inline repo definitions
        agentos project import my-app \\
          --repo name=backend,url=git@github.com:org/backend,path=./be,role=code,writable=true \\
          --repo name=frontend,url=git@github.com:org/frontend,path=./fe,role=code \\
          --repo name=docs,url=git@github.com:org/docs,path=./docs,role=docs,writable=false

        # Import with auth profiles
        agentos project import my-app \\
          --repo name=backend,url=git@github.com:org/backend,path=./be,auth_profile=github-ssh

        # Preview operations without making changes
        agentos project import --from project.yaml --dry-run

        # Force overwrite existing directories
        agentos project import --from project.yaml --force
    """
    try:
        # Parse configuration
        if config_file:
            # Import from file
            config_path = Path(config_file)
            project_name, file_description, repo_configs = parse_config_file(config_path)
            if file_description and not description:
                description = file_description
            console.print(f"📄 Loading config from: [cyan]{config_path}[/cyan]")
        elif repos:
            # Import from CLI options
            if not project_name:
                console.print("❌ [red]Error: project_name is required when using --repo options[/red]")
                raise click.Abort()

            repo_configs = []
            for repo_str in repos:
                try:
                    repo_config = RepoConfig.from_cli_option(repo_str)
                    repo_configs.append(repo_config)
                except ValueError as e:
                    console.print(f"❌ [red]Error parsing repo option: {e}[/red]")
                    raise click.Abort()
        else:
            console.print("❌ [red]Error: Must specify either --from or --repo options[/red]")
            console.print("\nUsage:")
            console.print("  agentos project import --from project.yaml")
            console.print("  agentos project import <name> --repo name=backend,url=...,path=./be")
            raise click.Abort()

        if not repo_configs:
            console.print("❌ [red]Error: At least one repository is required[/red]")
            raise click.Abort()

        # Validate unique repo names
        repo_names = [r.name for r in repo_configs]
        if len(repo_names) != len(set(repo_names)):
            console.print("❌ [red]Error: Duplicate repository names found[/red]")
            raise click.Abort()

        # Display summary
        console.print(f"\n📦 [bold]Project:[/bold] {project_name}")
        if description:
            console.print(f"📝 [bold]Description:[/bold] {description}")
        console.print(f"📚 [bold]Repositories:[/bold] {len(repo_configs)}")
        console.print()

        table = Table(title="Repositories to Import")
        table.add_column("Name", style="cyan")
        table.add_column("Path", style="green")
        table.add_column("Role", style="yellow")
        table.add_column("Writable", style="magenta")
        table.add_column("URL", style="blue", no_wrap=False)

        for repo in repo_configs:
            table.add_row(
                repo.name,
                repo.path,
                repo.role,
                "Yes" if repo.writable else "No",
                repo.url or "-",
            )

        console.print(table)
        console.print()

        # Initialize workspace layout
        from agentos.core.workspace import WorkspaceLayout, WorkspaceValidator

        ws_root = Path(workspace_root) if workspace_root else Path.cwd()
        layout = WorkspaceLayout(ws_root)
        validator = WorkspaceValidator()

        # Convert RepoConfig to RepoSpec for validation
        repo_specs = [
            RepoSpec(
                repo_id=str(ULID()),
                project_id=project_name,
                name=repo.name,
                remote_url=repo.url,
                default_branch=repo.branch,
                workspace_relpath=repo.path,
                role=RepoRole(repo.role),
                is_writable=repo.writable,
                auth_profile=repo.auth_profile,
            )
            for repo in repo_configs
        ]

        # Validation
        if not skip_validation:
            console.print("🔍 [bold]Running validation checks...[/bold]\n")

            # Validate individual repo configs
            for repo in repo_configs:
                is_valid, error = validate_repo_config(repo)
                if not is_valid:
                    console.print(f"❌ [red]{error}[/red]")
                    raise click.Abort()

            # Check workspace conflicts
            is_valid, errors = validate_workspace_conflicts(repo_configs)
            if not is_valid:
                console.print("❌ [red]Workspace path conflicts detected:[/red]")
                for error in errors:
                    console.print(f"   • {error}")
                raise click.Abort()
            else:
                console.print("✅ [green]No workspace conflicts[/green]")

            # Check auth profiles
            is_valid, errors = validate_auth_profiles(repo_configs)
            if not is_valid:
                console.print("❌ [red]Auth profile validation failed:[/red]")
                for error in errors:
                    console.print(f"   • {error}")
                raise click.Abort()
            else:
                console.print("✅ [green]Auth profiles validated[/green]")

            # Check workspace conflicts
            console.print("📁 [bold]Checking workspace layout...[/bold]")

            # Check for idempotency
            db = get_db()
            cursor = db.cursor()
            existing_project = cursor.execute("SELECT id FROM projects WHERE id = ?", (project_name,)).fetchone()
            db.close()

            existing_repos = None
            if existing_project:
                repo_crud = ProjectRepository(get_db_path())
                existing_repos = repo_crud.list_repos(project_name)

            idempotency_result = validator.check_idempotency(project_name, repo_specs, existing_repos)

            if not idempotency_result.is_valid:
                console.print("❌ [red]Project already exists with different configuration[/red]")
                for conflict in idempotency_result.conflicts:
                    console.print(conflict.format_error())
                console.print()
                raise click.Abort()
            elif idempotency_result.warnings:
                for warning in idempotency_result.warnings:
                    console.print(f"   ⚠️  [yellow]{warning}[/yellow]")

            # Validate workspace (unless force mode)
            if not force:
                workspace_result = validator.validate_workspace(
                    project_name,
                    repo_specs,
                    layout,
                    check_existing=True,
                )

                if not workspace_result.is_valid:
                    console.print("❌ [red]Workspace conflicts detected[/red]")
                    console.print()
                    for conflict in workspace_result.conflicts:
                        console.print(conflict.format_error())
                        console.print()

                    console.print("[yellow]Use --force to overwrite existing directories (WARNING: destructive)[/yellow]")
                    raise click.Abort()
                else:
                    console.print("✅ [green]No workspace conflicts[/green]")

                if workspace_result.warnings:
                    for warning in workspace_result.warnings:
                        console.print(f"   ⚠️  [yellow]{warning}[/yellow]")
            else:
                console.print("⚠️  [yellow]Force mode: skipping conflict checks[/yellow]")

            console.print()

            # Test remote URLs and permissions
            should_probe = require_write or click.confirm("\n🌐 Test remote URL accessibility and permissions?", default=False)
            if should_probe:
                console.print()
                git_client = GitClientWithAuth()
                permission_errors = []

                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=console,
                ) as progress:
                    for repo in repo_configs:
                        if repo.url:
                            task = progress.add_task(f"Probing {repo.name}...", total=None)

                            # Get auth profile
                            profile = None
                            if repo.auth_profile:
                                profile = git_client.credentials.get_profile(repo.auth_profile)

                            # Probe permissions
                            try:
                                probe_result = git_client.probe(repo.url, profile=profile, use_cache=True)
                                progress.remove_task(task)

                                # Check read access
                                if not probe_result.can_read:
                                    console.print(f"❌ [red]{repo.name}: Read access denied[/red]")
                                    if probe_result.error_message:
                                        console.print(f"    [dim]{probe_result.error_message.splitlines()[0]}[/dim]")
                                    permission_errors.append(f"Repo '{repo.name}' has no read access")

                                # Check write access if required
                                elif repo.writable:
                                    if probe_result.can_write:
                                        console.print(f"✅ [green]{repo.name}: Read + Write access[/green]")
                                    else:
                                        if require_write:
                                            console.print(f"❌ [red]{repo.name}: Write access required but not available[/red]")
                                            if probe_result.error_message:
                                                console.print(f"    [dim]{probe_result.error_message.splitlines()[0]}[/dim]")
                                            permission_errors.append(f"Repo '{repo.name}' requires write access but only has read")
                                        else:
                                            console.print(f"⚠️  [yellow]{repo.name}: Read-only access (write requested but not available)[/yellow]")
                                            if probe_result.error_message:
                                                console.print(f"    [dim]{probe_result.error_message.splitlines()[0]}[/dim]")
                                else:
                                    # Read-only repo with read access
                                    console.print(f"✅ [green]{repo.name}: Read access (read-only repo)[/green]")

                            except Exception as e:
                                progress.remove_task(task)
                                console.print(f"❌ [red]{repo.name}: {e}[/red]")
                                permission_errors.append(f"Repo '{repo.name}' probe failed: {e}")

                console.print()

                # Fail import if permission errors and require_write is set
                if permission_errors and require_write:
                    console.print("❌ [red]Permission validation failed:[/red]")
                    for error in permission_errors:
                        console.print(f"   • {error}")
                    raise click.Abort()

        # Dry-run mode: exit after validation
        if dry_run:
            console.print()
            console.print(Panel.fit(
                f"✅ [bold green]Dry-run validation passed![/bold green]\n\n"
                f"Project: [cyan]{project_name}[/cyan]\n"
                f"Repositories: [cyan]{len(repo_configs)}[/cyan]\n"
                f"Workspace root: [cyan]{layout.workspace_root.root_path}[/cyan]\n\n"
                f"[yellow]No changes were made (--dry-run mode)[/yellow]\n\n"
                f"Remove --dry-run to proceed with import.",
                title="Dry-Run Complete",
                border_style="green",
            ))
            return

        # Confirmation
        if not yes:
            if not click.confirm(f"\n✨ Import project '{project_name}' with {len(repo_configs)} repositories?"):
                console.print("Cancelled.")
                return

        # Create project
        db = get_db()
        cursor = db.cursor()

        # Check if project already exists
        existing = cursor.execute("SELECT id FROM projects WHERE id = ?", (project_name,)).fetchone()
        if existing:
            console.print(f"❌ [red]Project '{project_name}' already exists[/red]")
            db.close()
            raise click.Abort()

        # Insert project
        console.print(f"\n📝 Creating project '{project_name}'...")
        cursor.execute(
            "INSERT INTO projects (id, path, metadata) VALUES (?, ?, ?)",
            (project_name, None, json.dumps({"description": description} if description else {})),
        )

        # Add repositories
        repo_crud = ProjectRepository(get_db_path())

        console.print(f"📚 Adding {len(repo_specs)} repositories...")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            for repo_spec in repo_specs:
                task = progress.add_task(f"Adding {repo_spec.name}...", total=None)

                repo_crud.add_repo(repo_spec)
                progress.remove_task(task)

        db.commit()
        db.close()

        # Create .gitignore files if requested
        if not no_gitignore:
            console.print("\n📝 [bold]Creating .gitignore files...[/bold]")
            from agentos.core.git import GitignoreManager
            gitignore_mgr = GitignoreManager()

            gitignore_count = 0
            for repo_spec in repo_specs:
                repo_path = layout.get_repo_path(project_name, repo_spec)

                # Only create .gitignore if repo path exists
                if repo_path.exists():
                    try:
                        was_modified = gitignore_mgr.ensure_gitignore(repo_path, dry_run=False)
                        if was_modified:
                            console.print(f"   ✅ [green]{repo_spec.name}: Created/updated .gitignore[/green]")
                            gitignore_count += 1
                        else:
                            console.print(f"   ⊘  [dim]{repo_spec.name}: .gitignore already up to date[/dim]")
                    except Exception as e:
                        console.print(f"   ⚠️  [yellow]{repo_spec.name}: Failed to create .gitignore: {e}[/yellow]")
                else:
                    console.print(f"   ⊘  [dim]{repo_spec.name}: Repo path does not exist yet[/dim]")

            if gitignore_count > 0:
                console.print(f"\n   Created/updated {gitignore_count} .gitignore file(s)")

        console.print()
        console.print(Panel.fit(
            f"✅ [bold green]Project imported successfully![/bold green]\n\n"
            f"Project: [cyan]{project_name}[/cyan]\n"
            f"Repositories: [cyan]{len(repo_configs)}[/cyan]\n\n"
            f"Next steps:\n"
            f"  • View repos: [yellow]agentos project repos list {project_name}[/yellow]\n"
            f"  • Validate setup: [yellow]agentos project validate {project_name}[/yellow]",
            title="Import Complete",
            border_style="green",
        ))

    except click.Abort:
        raise
    except Exception as e:
        console.print(f"\n❌ [red]Failed to import project: {e}[/red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise click.Abort()


# ============================================================================
# Project Repos Subcommands
# ============================================================================


@project_group.group(name="repos")
def repos_group():
    """Manage project repositories"""
    pass


@repos_group.command(name="list")
@click.argument("project_id")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed information")
def list_repos(project_id: str, verbose: bool):
    """List all repositories in a project

    \b
    Example:
        agentos project repos list my-app
        agentos project repos list my-app --verbose
    """
    try:
        repo_crud = ProjectRepository(get_db_path())
        repos = repo_crud.list_repos(project_id)

        if not repos:
            console.print(f"ℹ️  No repositories found for project '{project_id}'")
            console.print(f"\nAdd one with: [yellow]agentos project repos add {project_id}[/yellow]")
            return

        console.print(f"\n📚 [bold]Project:[/bold] {project_id}")
        console.print(f"📦 [bold]Repositories:[/bold] {len(repos)}\n")

        table = Table(title=f"Repositories in '{project_id}'")
        table.add_column("Name", style="cyan")
        table.add_column("Path", style="green")
        table.add_column("Role", style="yellow")
        table.add_column("Writable", style="magenta")

        if verbose:
            table.add_column("URL", style="blue", no_wrap=False)
            table.add_column("Branch", style="dim")
            table.add_column("Auth Profile", style="dim")

        for repo in repos:
            row = [
                repo.name,
                repo.workspace_relpath,
                repo.role.value,
                "✓" if repo.is_writable else "✗",
            ]

            if verbose:
                row.extend([
                    repo.remote_url or "-",
                    repo.default_branch,
                    repo.auth_profile or "-",
                ])

            table.add_row(*row)

        console.print(table)
        console.print()

    except FileNotFoundError as e:
        console.print(f"❌ [red]{e}[/red]")
        raise click.Abort()
    except Exception as e:
        console.print(f"❌ [red]Failed to list repositories: {e}[/red]")
        raise click.Abort()


@repos_group.command(name="add")
@click.argument("project_id")
@click.option("--name", required=True, help="Repository name")
@click.option("--url", help="Remote URL")
@click.option("--path", default=".", help="Workspace relative path (default: .)")
@click.option("--role", default="code", type=click.Choice(["code", "docs", "infra", "mono-subdir"]), help="Repository role")
@click.option("--writable/--read-only", default=True, help="Writable flag")
@click.option("--branch", default="main", help="Default branch")
@click.option("--auth-profile", help="Auth profile name")
def add_repo(
    project_id: str,
    name: str,
    url: Optional[str],
    path: str,
    role: str,
    writable: bool,
    branch: str,
    auth_profile: Optional[str],
):
    """Add a repository to a project

    \b
    Example:
        agentos project repos add my-app \\
          --name frontend \\
          --url git@github.com:org/frontend \\
          --path ./fe \\
          --role code \\
          --writable
    """
    try:
        repo_crud = ProjectRepository(get_db_path())

        # Check if repo name already exists
        existing = repo_crud.get_repo_by_name(project_id, name)
        if existing:
            console.print(f"❌ [red]Repository '{name}' already exists in project '{project_id}'[/red]")
            raise click.Abort()

        # Create RepoSpec
        repo_spec = RepoSpec(
            repo_id=str(ULID()),
            project_id=project_id,
            name=name,
            remote_url=url,
            default_branch=branch,
            workspace_relpath=path,
            role=RepoRole(role),
            is_writable=writable,
            auth_profile=auth_profile,
        )

        # Add to database
        repo_crud.add_repo(repo_spec)

        console.print(f"✅ [green]Repository added:[/green] {name}")
        console.print(f"   Path: {path}")
        console.print(f"   Role: {role}")
        console.print(f"   Writable: {'Yes' if writable else 'No'}")

    except Exception as e:
        console.print(f"❌ [red]Failed to add repository: {e}[/red]")
        raise click.Abort()


@repos_group.command(name="remove")
@click.argument("project_id")
@click.argument("repo_name")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
def remove_repo(project_id: str, repo_name: str, yes: bool):
    """Remove a repository from a project

    \b
    Example:
        agentos project repos remove my-app frontend
        agentos project repos remove my-app frontend --yes
    """
    try:
        repo_crud = ProjectRepository(get_db_path())

        # Get repo by name
        repo = repo_crud.get_repo_by_name(project_id, repo_name)
        if not repo:
            console.print(f"❌ [red]Repository '{repo_name}' not found in project '{project_id}'[/red]")
            raise click.Abort()

        # Confirm deletion
        if not yes:
            console.print(f"Repository: {repo.name} (path={repo.workspace_relpath}, role={repo.role.value})")
            if not click.confirm(f"Remove repository '{repo_name}' from project '{project_id}'?"):
                console.print("Cancelled.")
                return

        # Remove from database
        removed = repo_crud.remove_repo(project_id, repo.repo_id)

        if removed:
            console.print(f"✅ [green]Repository removed:[/green] {repo_name}")
        else:
            console.print(f"❌ [red]Failed to remove repository[/red]")

    except Exception as e:
        console.print(f"❌ [red]Failed to remove repository: {e}[/red]")
        raise click.Abort()


@repos_group.command(name="update")
@click.argument("project_id")
@click.argument("repo_name")
@click.option("--url", help="Update remote URL")
@click.option("--path", help="Update workspace path")
@click.option("--branch", help="Update default branch")
@click.option("--writable/--read-only", default=None, help="Update writable flag")
@click.option("--auth-profile", help="Update auth profile")
def update_repo(
    project_id: str,
    repo_name: str,
    url: Optional[str],
    path: Optional[str],
    branch: Optional[str],
    writable: Optional[bool],
    auth_profile: Optional[str],
):
    """Update repository configuration

    \b
    Example:
        agentos project repos update my-app backend --url git@github.com:org/new-backend
        agentos project repos update my-app docs --read-only
    """
    try:
        repo_crud = ProjectRepository(get_db_path())

        # Get existing repo
        repo = repo_crud.get_repo_by_name(project_id, repo_name)
        if not repo:
            console.print(f"❌ [red]Repository '{repo_name}' not found in project '{project_id}'[/red]")
            raise click.Abort()

        # Update fields
        if url is not None:
            repo.remote_url = url
        if path is not None:
            repo.workspace_relpath = path
        if branch is not None:
            repo.default_branch = branch
        if writable is not None:
            repo.is_writable = writable
        if auth_profile is not None:
            repo.auth_profile = auth_profile

        # Save to database
        updated = repo_crud.update_repo(repo)

        if updated:
            console.print(f"✅ [green]Repository updated:[/green] {repo_name}")
        else:
            console.print(f"❌ [red]Failed to update repository[/red]")

    except Exception as e:
        console.print(f"❌ [red]Failed to update repository: {e}[/red]")
        raise click.Abort()


# ============================================================================
# Project Validate Command
# ============================================================================


@project_group.command(name="validate")
@click.argument("project_id")
@click.option("--check-urls", is_flag=True, help="Test remote URL accessibility")
@click.option("--check-auth", is_flag=True, help="Validate auth profiles")
@click.option("--check-paths", is_flag=True, help="Check workspace path conflicts")
@click.option("--all", "check_all", is_flag=True, help="Run all checks")
def validate_project(
    project_id: str,
    check_urls: bool,
    check_auth: bool,
    check_paths: bool,
    check_all: bool,
):
    """Validate project configuration

    \b
    Examples:
        # Basic validation
        agentos project validate my-app

        # Full validation with all checks
        agentos project validate my-app --all

        # Specific checks
        agentos project validate my-app --check-urls --check-auth
    """
    try:
        repo_crud = ProjectRepository(get_db_path())
        repos = repo_crud.list_repos(project_id)

        if not repos:
            console.print(f"❌ [red]Project '{project_id}' has no repositories[/red]")
            raise click.Abort()

        console.print(f"\n🔍 [bold]Validating project:[/bold] {project_id}")
        console.print(f"📚 [bold]Repositories:[/bold] {len(repos)}\n")

        # Determine which checks to run
        if check_all:
            check_urls = check_auth = check_paths = True

        all_passed = True

        # Check 1: Workspace path conflicts
        if check_paths or check_all or (not check_urls and not check_auth):
            console.print("📁 [bold]Checking workspace paths...[/bold]")
            repo_configs = [
                RepoConfig(
                    name=r.name,
                    path=r.workspace_relpath,
                    role=r.role.value,
                    writable=r.is_writable,
                    url=r.remote_url,
                    auth_profile=r.auth_profile,
                )
                for r in repos
            ]
            is_valid, errors = validate_workspace_conflicts(repo_configs)
            if is_valid:
                console.print("   ✅ [green]No path conflicts[/green]")
            else:
                console.print("   ❌ [red]Path conflicts detected:[/red]")
                for error in errors:
                    console.print(f"      • {error}")
                all_passed = False
            console.print()

        # Check 2: Auth profiles
        if check_auth or check_all:
            console.print("🔐 [bold]Checking auth profiles...[/bold]")
            repo_configs = [
                RepoConfig(
                    name=r.name,
                    path=r.workspace_relpath,
                    role=r.role.value,
                    writable=r.is_writable,
                    url=r.remote_url,
                    auth_profile=r.auth_profile,
                )
                for r in repos
            ]
            is_valid, errors = validate_auth_profiles(repo_configs)
            if is_valid:
                console.print("   ✅ [green]Auth profiles validated[/green]")
            else:
                console.print("   ❌ [red]Auth validation failed:[/red]")
                for error in errors:
                    console.print(f"      • {error}")
                all_passed = False
            console.print()

        # Check 3: Remote URLs with permission probes
        if check_urls or check_all:
            console.print("🌐 [bold]Testing remote URLs and permissions...[/bold]")
            git_client = GitClientWithAuth()

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                for repo in repos:
                    if repo.remote_url:
                        task = progress.add_task(f"Probing {repo.name}...", total=None)

                        # Get auth profile
                        profile = None
                        if repo.auth_profile:
                            profile = git_client.credentials.get_profile(repo.auth_profile)

                        # Probe permissions
                        try:
                            probe_result = git_client.probe(repo.remote_url, profile=profile, use_cache=True)
                            progress.remove_task(task)

                            # Format output based on permissions
                            read_icon = "✓" if probe_result.can_read else "✗"
                            write_icon = "✓" if probe_result.can_write else "✗"

                            if probe_result.can_read and probe_result.can_write:
                                status_color = "green"
                                status_text = f"Read: {read_icon} Write: {write_icon}"
                            elif probe_result.can_read:
                                status_color = "yellow"
                                status_text = f"Read: {read_icon} Write: {write_icon} (read-only)"
                            else:
                                status_color = "red"
                                status_text = f"Read: {read_icon} Write: {write_icon}"
                                all_passed = False

                            console.print(f"   [{status_color}]{repo.name}[/{status_color}] ({repo.remote_url}) - {status_text}")

                            # Show error details if access failed
                            if probe_result.error_message and not probe_result.can_read:
                                console.print(f"      [dim]{probe_result.error_message.splitlines()[0]}[/dim]")

                        except Exception as e:
                            progress.remove_task(task)
                            console.print(f"   ❌ [red]{repo.name}: {e}[/red]")
                            all_passed = False
                    else:
                        console.print(f"   ⊘  [dim]{repo.name}: No remote URL[/dim]")
            console.print()

        # Summary
        if all_passed:
            console.print(Panel.fit(
                "✅ [bold green]All validation checks passed![/bold green]",
                border_style="green",
            ))
        else:
            console.print(Panel.fit(
                "⚠️  [bold yellow]Some validation checks failed[/bold yellow]\n\n"
                "Please review the errors above and fix configuration issues.",
                border_style="yellow",
            ))
            sys.exit(1)

    except Exception as e:
        console.print(f"\n❌ [red]Validation failed: {e}[/red]")
        raise click.Abort()


# ============================================================================
# Workspace Commands
# ============================================================================


@project_group.group(name="workspace")
def workspace_group():
    """Manage project workspaces"""
    pass


@workspace_group.command(name="check")
@click.argument("project_id")
@click.option("--workspace-root", type=click.Path(), help="Workspace root directory (default: current directory)")
def check_workspace(project_id: str, workspace_root: Optional[str]):
    """Check workspace layout and detect conflicts

    \b
    Example:
        agentos project workspace check my-app
        agentos project workspace check my-app --workspace-root /path/to/workspace
    """
    try:
        from agentos.core.workspace import WorkspaceLayout, WorkspaceValidator

        # Initialize workspace
        ws_root = Path(workspace_root) if workspace_root else Path.cwd()
        layout = WorkspaceLayout(ws_root)
        validator = WorkspaceValidator()

        # Get project repos
        repo_crud = ProjectRepository(get_db_path())
        repos = repo_crud.list_repos(project_id)

        if not repos:
            console.print(f"❌ [red]Project '{project_id}' has no repositories[/red]")
            raise click.Abort()

        console.print(f"\n🔍 [bold]Checking workspace:[/bold] {project_id}")
        console.print(f"📂 [bold]Workspace root:[/bold] {layout.workspace_root.root_path}")
        console.print(f"📍 [bold]Project root:[/bold] {layout.get_project_root(project_id)}")
        console.print(f"📚 [bold]Repositories:[/bold] {len(repos)}\n")

        # Validate workspace
        result = validator.validate_workspace(
            project_id,
            repos,
            layout,
            check_existing=True,
        )

        # Display results
        if result.is_valid:
            console.print("✅ [green]Workspace is valid[/green]\n")

            # Show repository paths
            table = Table(title="Repository Paths")
            table.add_column("Name", style="cyan")
            table.add_column("Path", style="green")
            table.add_column("Exists", style="yellow")
            table.add_column("Git Repo", style="magenta")

            for repo in repos:
                repo_path = layout.get_repo_path(project_id, repo)
                exists = "Yes" if repo_path.exists() else "No"
                is_git = "Yes" if (repo_path / ".git").exists() else "No"

                table.add_row(
                    repo.name,
                    str(repo_path),
                    exists,
                    is_git,
                )

            console.print(table)
        else:
            console.print("❌ [red]Workspace validation failed[/red]\n")
            console.print(result.format_report())
            sys.exit(1)

        if result.warnings:
            console.print("\n⚠️  [yellow]Warnings:[/yellow]")
            for warning in result.warnings:
                console.print(f"   • {warning}")

    except Exception as e:
        console.print(f"❌ [red]Failed to check workspace: {e}[/red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise click.Abort()


@workspace_group.command(name="clean")
@click.argument("project_id")
@click.option("--workspace-root", type=click.Path(), help="Workspace root directory (default: current directory)")
@click.option("--dry-run", is_flag=True, help="Preview operations without making changes")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompts")
def clean_workspace(project_id: str, workspace_root: Optional[str], dry_run: bool, yes: bool):
    """Clean workspace by removing untracked files

    \b
    WARNING: This is a destructive operation. Use --dry-run first.

    \b
    Example:
        agentos project workspace clean my-app --dry-run
        agentos project workspace clean my-app --yes
    """
    try:
        from agentos.core.workspace import WorkspaceLayout

        # Initialize workspace
        ws_root = Path(workspace_root) if workspace_root else Path.cwd()
        layout = WorkspaceLayout(ws_root)

        # Get project repos
        repo_crud = ProjectRepository(get_db_path())
        repos = repo_crud.list_repos(project_id)

        if not repos:
            console.print(f"❌ [red]Project '{project_id}' has no repositories[/red]")
            raise click.Abort()

        console.print(f"\n🧹 [bold]Cleaning workspace:[/bold] {project_id}")
        console.print(f"📂 [bold]Workspace root:[/bold] {layout.workspace_root.root_path}\n")

        # Find untracked files in each repo
        untracked_files = {}

        for repo in repos:
            repo_path = layout.get_repo_path(project_id, repo)

            if not repo_path.exists() or not (repo_path / ".git").exists():
                console.print(f"⊘  [dim]{repo.name}: Not a git repository, skipping[/dim]")
                continue

            try:
                # Get untracked files
                result = subprocess.run(
                    ["git", "-C", str(repo_path), "ls-files", "--others", "--exclude-standard"],
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=10,
                )

                files = [line for line in result.stdout.strip().split("\n") if line]

                if files:
                    untracked_files[repo.name] = files
                    console.print(f"📄 [cyan]{repo.name}[/cyan]: {len(files)} untracked files")

            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                console.print(f"⚠️  [yellow]{repo.name}: Failed to list untracked files: {e}[/yellow]")

        if not untracked_files:
            console.print("\n✅ [green]No untracked files found[/green]")
            return

        # Display untracked files
        console.print(f"\n📋 [bold]Untracked files:[/bold]")
        for repo_name, files in untracked_files.items():
            console.print(f"\n  [cyan]{repo_name}[/cyan]:")
            for file in files[:10]:  # Show first 10
                console.print(f"    • {file}")
            if len(files) > 10:
                console.print(f"    ... and {len(files) - 10} more")

        # Dry-run mode
        if dry_run:
            console.print(f"\n[yellow]Dry-run mode: No files were deleted[/yellow]")
            return

        # Confirmation
        total_files = sum(len(files) for files in untracked_files.values())
        if not yes:
            if not click.confirm(f"\n⚠️  Delete {total_files} untracked files?"):
                console.print("Cancelled.")
                return

        # Clean untracked files
        console.print(f"\n🧹 Cleaning {total_files} files...")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            for repo_name, files in untracked_files.items():
                task = progress.add_task(f"Cleaning {repo_name}...", total=None)

                repo_path = layout.get_repo_path(project_id, repo_crud.get_repo_by_name(project_id, repo_name))

                try:
                    # Use git clean to remove untracked files
                    subprocess.run(
                        ["git", "-C", str(repo_path), "clean", "-f"],
                        check=True,
                        capture_output=True,
                        timeout=30,
                    )
                    progress.remove_task(task)
                    console.print(f"✅ [green]{repo_name}: Cleaned {len(files)} files[/green]")

                except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                    progress.remove_task(task)
                    console.print(f"❌ [red]{repo_name}: Failed to clean: {e}[/red]")

        console.print(f"\n✅ [green]Workspace cleaned successfully[/green]")

    except Exception as e:
        console.print(f"❌ [red]Failed to clean workspace: {e}[/red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise click.Abort()


# ============================================================================
# Change Validation Commands
# ============================================================================


@project_group.command(name="check-changes")
@click.argument("task_id")
@click.option("--repo", "repo_name", help="Check specific repository only")
@click.option("--strict", is_flag=True, help="Use strict security rules")
def check_changes(task_id: str, repo_name: Optional[str], strict: bool):
    """Check if task changes comply with security rules

    Validates that file changes:
    - Are within path_filters scope
    - Don't modify forbidden files (credentials, .git/, etc.)
    - Pass security checks

    \b
    Examples:
        # Check all changes for a task
        agentos project check-changes task_01HX123ABC

        # Check changes in specific repo
        agentos project check-changes task_01HX123ABC --repo backend

        # Use strict security rules
        agentos project check-changes task_01HX123ABC --strict
    """
    try:
        from agentos.core.git import ChangeGuardRails, create_strict_guard_rails
        from agentos.core.task.manager import TaskManager
        from agentos.core.task.repo_context import TaskRepoContext
        from agentos.core.project.repository import ProjectRepository
        from agentos.core.workspace import WorkspaceLayout

        # Get task from database
        task_mgr = TaskManager(get_db_path())
        task = task_mgr.get_task(task_id)

        if not task:
            console.print(f"❌ [red]Task not found: {task_id}[/red]")
            raise click.Abort()

        console.print(f"\n🔍 [bold]Checking changes for task:[/bold] {task_id}")
        console.print(f"📋 [bold]Title:[/bold] {task.title}\n")

        # Get task repo scopes
        from agentos.core.task.task_repo_service import TaskRepoService
        task_repo_service = TaskRepoService(get_db_path())
        repo_scopes = task_repo_service.list_repo_scopes(task_id)

        if not repo_scopes:
            console.print("⚠️  [yellow]No repository scopes found for this task[/yellow]")
            return

        # Initialize guard rails
        if strict:
            guard_rails = create_strict_guard_rails()
            console.print("🔒 [bold]Using strict security rules[/bold]\n")
        else:
            guard_rails = ChangeGuardRails()
            console.print("🔒 [bold]Using default security rules[/bold]\n")

        # Get project and workspace
        repo_crud = ProjectRepository(get_db_path())

        all_valid = True
        total_checked = 0

        for scope in repo_scopes:
            # Filter by repo name if specified
            if repo_name:
                repo_spec = repo_crud.get_repo(scope.repo_id)
                if not repo_spec or repo_spec.name != repo_name:
                    continue

            # Get repo spec
            repo_spec = repo_crud.get_repo(scope.repo_id)
            if not repo_spec:
                console.print(f"⚠️  [yellow]Repository not found: {scope.repo_id}[/yellow]")
                continue

            console.print(f"📁 [cyan]{repo_spec.name}[/cyan] ({scope.scope.value})")

            # Get workspace layout
            # Note: We need project_id - try to get from repo_spec
            project_id = repo_spec.project_id
            ws_layout = WorkspaceLayout(Path.cwd())
            repo_path = ws_layout.get_repo_path(project_id, repo_spec)

            if not repo_path.exists():
                console.print(f"   ⚠️  [yellow]Repository path does not exist: {repo_path}[/yellow]\n")
                continue

            # Create TaskRepoContext
            task_context = TaskRepoContext(
                repo_id=scope.repo_id,
                task_id=task_id,
                name=repo_spec.name,
                path=repo_path,
                remote_url=repo_spec.remote_url,
                branch=repo_spec.default_branch,
                writable=repo_spec.is_writable,
                scope=scope.scope,
                path_filters=scope.path_filters,
            )

            # Get changed files from git
            try:
                result = subprocess.run(
                    ["git", "-C", str(repo_path), "diff", "--name-only", "HEAD"],
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=10,
                )

                changed_files = [line.strip() for line in result.stdout.split("\n") if line.strip()]

                if not changed_files:
                    console.print(f"   ℹ️  [dim]No changes detected[/dim]\n")
                    continue

                console.print(f"   📝 {len(changed_files)} changed file(s)")

                # Validate changes
                validation_result = guard_rails.validate_changes(task_context, changed_files)
                total_checked += validation_result.checked_files

                if validation_result.is_valid:
                    console.print(f"   ✅ [green]All changes are valid[/green]\n")
                else:
                    console.print(f"   ❌ [red]{len(validation_result.violations)} violation(s) found[/red]\n")
                    for violation in validation_result.violations:
                        console.print(f"      {violation.format_error()}\n")
                    all_valid = False

                if validation_result.warnings:
                    for warning in validation_result.warnings:
                        console.print(f"   ⚠️  [yellow]{warning}[/yellow]")

            except subprocess.CalledProcessError as e:
                console.print(f"   ❌ [red]Failed to get changes: {e.stderr}[/red]\n")
                all_valid = False

            except subprocess.TimeoutExpired:
                console.print(f"   ❌ [red]Git command timed out[/red]\n")
                all_valid = False

        # Summary
        console.print()
        if all_valid:
            console.print(Panel.fit(
                f"✅ [bold green]All changes passed validation![/bold green]\n\n"
                f"Checked {total_checked} file(s) across {len(repo_scopes)} repository(ies)\n"
                f"No security violations detected",
                border_style="green",
            ))
        else:
            console.print(Panel.fit(
                f"⚠️  [bold yellow]Validation failed[/bold yellow]\n\n"
                f"Some changes violate security rules\n"
                f"Review violations above and fix before committing",
                border_style="yellow",
            ))
            sys.exit(1)

    except click.Abort:
        raise
    except Exception as e:
        console.print(f"\n❌ [red]Failed to check changes: {e}[/red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise click.Abort()
