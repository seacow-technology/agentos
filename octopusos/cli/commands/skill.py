"""
Skill management CLI commands.

Commands:
- agentos skill list: List all skills
- agentos skill info <skill_id>: Show skill details
- agentos skill import <source>: Import skill from local path or GitHub
- agentos skill enable <skill_id>: Enable skill (requires admin token)
- agentos skill disable <skill_id>: Disable skill (requires admin token)
"""

import click
from typing import Optional
import logging

from agentos.skills.registry import SkillRegistry
from agentos.skills.importer.local_importer import LocalImporter
from agentos.skills.importer.github_importer import GitHubImporter, GitHubFetchError


logger = logging.getLogger(__name__)


@click.group()
def skill():
    """Skill management commands."""
    pass


@skill.command()
@click.option('--status', type=click.Choice(['enabled', 'disabled', 'imported_disabled', 'all']),
              default='all', help='Filter by status')
def list(status):
    """List all imported skills."""
    registry = SkillRegistry()

    filter_status = None if status == 'all' else status
    skills = registry.list_skills(status=filter_status)

    if not skills:
        click.echo("No skills found.")
        return

    click.echo(f"\n{'Status':<20} {'Skill ID':<30} {'Version':<15} {'Description'}")
    click.echo("-" * 100)

    for s in skills:
        status_display = s.get('status', 'unknown')
        status_icon = {
            'enabled': '✓',
            'disabled': '○',
            'imported_disabled': '⊗'
        }.get(status_display, '?')

        skill_id = s.get('skill_id', 'unknown')
        version = s.get('version', 'unknown')
        manifest = s.get('manifest_json', {})
        description = manifest.get('description', 'No description')[:50]

        click.echo(f"{status_icon} {status_display:<17} {skill_id:<30} {version:<15} {description}")

    click.echo(f"\nTotal: {len(skills)} skills")


@skill.command()
@click.argument('skill_id')
def info(skill_id):
    """Show detailed information about a skill."""
    registry = SkillRegistry()
    skill = registry.get_skill(skill_id)

    if not skill:
        click.echo(f"❌ Skill not found: {skill_id}", err=True)
        return

    click.echo(f"\n{'='*60}")
    click.echo(f"Skill: {skill.get('skill_id')}")
    click.echo(f"{'='*60}")
    click.echo(f"Version:      {skill.get('version')}")
    click.echo(f"Status:       {skill.get('status')}")
    click.echo(f"Repo Hash:    {skill.get('repo_hash', 'N/A')}")
    click.echo(f"Imported At:  {skill.get('imported_at', 'N/A')}")
    click.echo(f"Enabled At:   {skill.get('enabled_at', 'N/A')}")

    manifest = skill.get('manifest_json', {})
    if manifest:
        click.echo(f"\nManifest:")
        click.echo(f"  Name:        {manifest.get('name')}")
        click.echo(f"  Author:      {manifest.get('author')}")
        click.echo(f"  Description: {manifest.get('description')}")

        capabilities = manifest.get('capabilities', {})
        if capabilities:
            click.echo(f"\n  Capabilities:")
            click.echo(f"    Class: {capabilities.get('class')}")
            tags = capabilities.get('tags', [])
            if tags:
                click.echo(f"    Tags:  {', '.join(tags)}")

        requires = manifest.get('requires', {})
        if requires:
            click.echo(f"\n  Requires:")
            click.echo(f"    Phase: {requires.get('phase')}")

            permissions = requires.get('permissions', {})
            if permissions:
                click.echo(f"    Permissions:")
                if permissions.get('net'):
                    domains = permissions['net'].get('allow_domains', [])
                    click.echo(f"      Network:  {', '.join(domains)}")
                if permissions.get('fs'):
                    fs_perms = []
                    if permissions['fs'].get('read'):
                        fs_perms.append('read')
                    if permissions['fs'].get('write'):
                        fs_perms.append('write')
                    click.echo(f"      Filesystem: {', '.join(fs_perms)}")
                if permissions.get('actions'):
                    if permissions['actions'].get('write_state'):
                        click.echo(f"      Actions:  write_state")

    click.echo()


@skill.command(name='import')
@click.argument('source')
def import_(source):
    """
    Import a skill from local path or GitHub.

    Examples:
        agentos skill import /path/to/skill

        agentos skill import github:owner/repo

        agentos skill import github:owner/repo#main

        agentos skill import github:owner/repo#v1.0.0:skills/example
    """
    registry = SkillRegistry()

    try:
        if source.startswith('github:'):
            # Parse GitHub URL
            source_str = source[7:]  # Remove 'github:' prefix

            # Parse subdir (after ':')
            if ':' in source_str and source_str.count(':') == 1:
                repo_part, subdir = source_str.rsplit(':', 1)
            else:
                repo_part = source_str
                subdir = None

            # Parse ref (after '#')
            if '#' in repo_part:
                repo_path, ref = repo_part.split('#', 1)
            else:
                repo_path = repo_part
                ref = None

            # Parse owner/repo
            if '/' not in repo_path:
                click.echo("❌ Invalid GitHub URL format. Expected: github:owner/repo", err=True)
                click.echo("   Examples:")
                click.echo("     github:owner/repo")
                click.echo("     github:owner/repo#main")
                click.echo("     github:owner/repo#v1.0.0:skills/example")
                return

            parts = repo_path.split('/', 1)
            owner, repo = parts[0], parts[1]

            # Import from GitHub
            click.echo(f"📦 Importing from GitHub: {owner}/{repo}" +
                      (f"@{ref}" if ref else "@main") +
                      (f":{subdir}" if subdir else ""))

            importer = GitHubImporter(registry)
            skill_id = importer.import_from_github(owner, repo, ref, subdir)

            click.echo(f"✅ Successfully imported skill: {skill_id}")
            click.echo(f"   Status: imported_disabled")
            click.echo(f"\n💡 To enable this skill, run:")
            click.echo(f"   agentos skill enable {skill_id} --token <your-admin-token>")

        else:
            # Import from local path
            click.echo(f"📁 Importing from local path: {source}")

            importer = LocalImporter(registry)
            skill_id = importer.import_from_path(source)

            click.echo(f"✅ Successfully imported skill: {skill_id}")
            click.echo(f"   Status: imported_disabled")
            click.echo(f"\n💡 To enable this skill, run:")
            click.echo(f"   agentos skill enable {skill_id} --token <your-admin-token>")

    except FileNotFoundError as e:
        click.echo(f"❌ File/manifest not found: {e}", err=True)
    except ValueError as e:
        if "Manifest validation failed" in str(e):
            click.echo(f"❌ Manifest validation failed:", err=True)
            click.echo(f"   {e}", err=True)
        else:
            click.echo(f"❌ Error: {e}", err=True)
    except GitHubFetchError as e:
        click.echo(f"❌ GitHub fetch error: {e}", err=True)
    except Exception as e:
        click.echo(f"❌ Import failed: {e}", err=True)
        logger.exception("Import failed with exception")


@skill.command()
@click.argument('skill_id')
@click.option('--token', envvar='AGENTOS_ADMIN_TOKEN', required=False,
              help='Admin token (or set AGENTOS_ADMIN_TOKEN environment variable)')
def enable(skill_id, token):
    """Enable a skill (requires admin token)."""
    if not token:
        click.echo("❌ Admin token required. Provide via --token or AGENTOS_ADMIN_TOKEN env var.", err=True)
        click.echo("\n💡 Example:")
        click.echo("   export AGENTOS_ADMIN_TOKEN='your-token-here'")
        click.echo("   agentos skill enable my-skill")
        return

    # Validate token
    try:
        from agentos.core.capabilities.admin_token import validate_admin_token

        if not validate_admin_token(token):
            click.echo("❌ Invalid admin token", err=True)
            return
    except ImportError:
        click.echo("⚠️  Warning: Admin token validation not available, proceeding anyway...", err=True)

    # Enable skill
    registry = SkillRegistry()
    skill = registry.get_skill(skill_id)

    if not skill:
        click.echo(f"❌ Skill not found: {skill_id}", err=True)
        return

    registry.set_status(skill_id, 'enabled')
    click.echo(f"✅ Skill enabled: {skill_id}")


@skill.command()
@click.argument('skill_id')
@click.option('--token', envvar='AGENTOS_ADMIN_TOKEN', required=False,
              help='Admin token (or set AGENTOS_ADMIN_TOKEN environment variable)')
def disable(skill_id, token):
    """Disable a skill (requires admin token)."""
    if not token:
        click.echo("❌ Admin token required. Provide via --token or AGENTOS_ADMIN_TOKEN env var.", err=True)
        return

    # Validate token
    try:
        from agentos.core.capabilities.admin_token import validate_admin_token

        if not validate_admin_token(token):
            click.echo("❌ Invalid admin token", err=True)
            return
    except ImportError:
        click.echo("⚠️  Warning: Admin token validation not available, proceeding anyway...", err=True)

    # Disable skill
    registry = SkillRegistry()
    skill = registry.get_skill(skill_id)

    if not skill:
        click.echo(f"❌ Skill not found: {skill_id}", err=True)
        return

    registry.set_status(skill_id, 'disabled')
    click.echo(f"✅ Skill disabled: {skill_id}")


__all__ = ["skill"]
