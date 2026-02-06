"""CLI commands for auth profile management"""

import click
from pathlib import Path
from typing import Optional

from agentos.core.git.credentials import (
    CredentialsManager,
    AuthProfileType,
    TokenProvider,
)
from agentos.core.git.client import GitClientWithAuth


@click.group(name="auth")
def auth_group():
    """Manage Git authentication profiles"""
    pass


@auth_group.command(name="add")
@click.option("--name", required=True, help="Profile name (e.g., 'github-personal')")
@click.option(
    "--type",
    "auth_type",
    required=True,
    type=click.Choice(["ssh_key", "pat_token", "netrc"]),
    help="Authentication type",
)
@click.option("--key-path", help="SSH key path (for ssh_key type)")
@click.option("--passphrase", help="SSH key passphrase (optional)", hide_input=True)
@click.option("--token", help="Personal Access Token (for pat_token type)", hide_input=True)
@click.option(
    "--provider",
    type=click.Choice(["github", "gitlab", "bitbucket", "gitea", "other"]),
    help="Token provider (for pat_token type)",
)
@click.option("--machine", help="Machine name (for netrc type, e.g., github.com)")
@click.option("--login", help="Login username (for netrc type)")
@click.option("--password", help="Password (for netrc type)", hide_input=True)
def add_profile(
    name: str,
    auth_type: str,
    key_path: Optional[str],
    passphrase: Optional[str],
    token: Optional[str],
    provider: Optional[str],
    machine: Optional[str],
    login: Optional[str],
    password: Optional[str],
):
    """Add a new auth profile

    Examples:

        # Add SSH key profile
        agentos auth add --name work-ssh --type ssh_key --key-path ~/.ssh/id_rsa

        # Add GitHub PAT profile
        agentos auth add --name github-personal --type pat_token --token <token> --provider github

        # Add netrc profile
        agentos auth add --name gitlab-netrc --type netrc --machine gitlab.com --login user --password <pass>
    """
    manager = CredentialsManager()

    try:
        profile_type = AuthProfileType(auth_type)

        # Validate inputs based on type
        if profile_type == AuthProfileType.SSH_KEY:
            if not key_path:
                raise click.UsageError("--key-path is required for ssh_key type")

            # Expand and validate path
            key_path = str(Path(key_path).expanduser())
            if not Path(key_path).exists():
                raise click.UsageError(f"SSH key not found: {key_path}")

            profile = manager.create_profile(
                profile_name=name,
                profile_type=profile_type,
                ssh_key_path=key_path,
                ssh_passphrase=passphrase,
            )

        elif profile_type == AuthProfileType.PAT_TOKEN:
            if not token:
                raise click.UsageError("--token is required for pat_token type")
            if not provider:
                raise click.UsageError("--provider is required for pat_token type")

            profile = manager.create_profile(
                profile_name=name,
                profile_type=profile_type,
                token=token,
                token_provider=TokenProvider(provider),
            )

        elif profile_type == AuthProfileType.NETRC:
            if not all([machine, login, password]):
                raise click.UsageError("--machine, --login, and --password are required for netrc type")

            profile = manager.create_profile(
                profile_name=name,
                profile_type=profile_type,
                netrc_machine=machine,
                netrc_login=login,
                netrc_password=password,
            )

        click.echo(f"✅ Auth profile created: {name} (type={auth_type})")

        # Ask if user wants to validate
        if click.confirm("Validate credentials now?", default=True):
            git_client = GitClientWithAuth(manager)

            # For PAT tokens, we can validate automatically
            if profile_type == AuthProfileType.PAT_TOKEN:
                click.echo(f"🔄 Validating credentials for {provider}...")
                is_valid = git_client.validate_credentials(name)

                if is_valid:
                    click.echo(f"✅ Credentials validated successfully")
                else:
                    click.echo(f"❌ Credentials validation failed (check logs for details)")

            else:
                click.echo("ℹ️  Manual validation required for this auth type")
                click.echo("   Test with: agentos auth validate <profile-name> --url <git-url>")

    except Exception as e:
        click.echo(f"❌ Failed to create auth profile: {e}", err=True)
        raise click.Abort()


@auth_group.command(name="list")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed information")
def list_profiles(verbose: bool):
    """List all auth profiles"""
    manager = CredentialsManager()

    try:
        profiles = manager.list_profiles(include_sensitive=False)

        if not profiles:
            click.echo("No auth profiles found.")
            click.echo("\nAdd one with: agentos auth add --help")
            return

        click.echo(f"\n{'Profile Name':<20} {'Type':<12} {'Provider':<12} {'Status':<10} {'Last Validated':<20}")
        click.echo("=" * 90)

        for profile in profiles:
            provider = profile.token_provider.value if profile.token_provider else "-"
            status = profile.validation_status.value
            last_validated = profile.last_validated_at.strftime("%Y-%m-%d %H:%M") if profile.last_validated_at else "Never"

            click.echo(f"{profile.profile_name:<20} {profile.profile_type.value:<12} {provider:<12} {status:<10} {last_validated:<20}")

            if verbose:
                if profile.profile_type == AuthProfileType.SSH_KEY:
                    click.echo(f"  SSH Key: {profile.ssh_key_path}")
                elif profile.profile_type == AuthProfileType.NETRC:
                    click.echo(f"  Machine: {profile.netrc_machine}, Login: {profile.netrc_login}")

                if profile.validation_message:
                    click.echo(f"  Validation: {profile.validation_message}")

                click.echo()

        click.echo()

    except Exception as e:
        click.echo(f"❌ Failed to list auth profiles: {e}", err=True)
        raise click.Abort()


@auth_group.command(name="remove")
@click.argument("profile_name")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
def remove_profile(profile_name: str, yes: bool):
    """Remove an auth profile

    Example:
        agentos auth remove github-personal
    """
    manager = CredentialsManager()

    try:
        # Check if profile exists
        profile = manager.get_profile(profile_name)
        if not profile:
            click.echo(f"❌ Auth profile not found: {profile_name}", err=True)
            raise click.Abort()

        # Confirm deletion
        if not yes:
            click.echo(f"Profile: {profile_name} (type={profile.profile_type.value})")
            if not click.confirm("Are you sure you want to delete this profile?"):
                click.echo("Cancelled.")
                return

        # Delete profile
        manager.delete_profile(profile_name)
        click.echo(f"✅ Auth profile removed: {profile_name}")

    except Exception as e:
        click.echo(f"❌ Failed to remove auth profile: {e}", err=True)
        raise click.Abort()


@auth_group.command(name="validate")
@click.argument("profile_name")
@click.option("--url", help="Git URL to test (optional for PAT profiles)")
def validate_profile(profile_name: str, url: Optional[str]):
    """Validate auth profile credentials

    Examples:

        # Validate GitHub PAT (uses default URL)
        agentos auth validate github-personal

        # Validate SSH key with custom URL
        agentos auth validate work-ssh --url git@github.com:org/repo.git
    """
    manager = CredentialsManager()
    git_client = GitClientWithAuth(manager)

    try:
        profile = manager.get_profile(profile_name)
        if not profile:
            click.echo(f"❌ Auth profile not found: {profile_name}", err=True)
            raise click.Abort()

        click.echo(f"🔄 Validating credentials: {profile_name} (type={profile.profile_type.value})")

        # For non-PAT profiles, URL is required
        if profile.profile_type != AuthProfileType.PAT_TOKEN and not url:
            click.echo("❌ --url is required for this auth type", err=True)
            raise click.Abort()

        is_valid = git_client.validate_credentials(profile_name, test_url=url)

        if is_valid:
            click.echo(f"✅ Credentials validated successfully")
        else:
            click.echo(f"❌ Credentials validation failed")

            # Show validation message
            profile_updated = manager.get_profile(profile_name)
            if profile_updated.validation_message:
                click.echo(f"   Error: {profile_updated.validation_message}")

    except Exception as e:
        click.echo(f"❌ Failed to validate auth profile: {e}", err=True)
        raise click.Abort()


@auth_group.command(name="show")
@click.argument("profile_name")
def show_profile(profile_name: str):
    """Show detailed information about an auth profile

    Example:
        agentos auth show github-personal
    """
    manager = CredentialsManager()

    try:
        profile = manager.get_profile(profile_name)
        if not profile:
            click.echo(f"❌ Auth profile not found: {profile_name}", err=True)
            raise click.Abort()

        click.echo(f"\n{'='*60}")
        click.echo(f"Auth Profile: {profile.profile_name}")
        click.echo(f"{'='*60}")
        click.echo(f"Profile ID:       {profile.profile_id}")
        click.echo(f"Type:             {profile.profile_type.value}")

        if profile.profile_type == AuthProfileType.SSH_KEY:
            click.echo(f"SSH Key Path:     {profile.ssh_key_path}")
            click.echo(f"Has Passphrase:   {'Yes' if profile.ssh_passphrase else 'No'}")

        elif profile.profile_type == AuthProfileType.PAT_TOKEN:
            click.echo(f"Provider:         {profile.token_provider.value}")
            if profile.token_scopes:
                click.echo(f"Scopes:           {', '.join(profile.token_scopes)}")
            click.echo(f"Token:            {'*' * 40}")

        elif profile.profile_type == AuthProfileType.NETRC:
            click.echo(f"Machine:          {profile.netrc_machine}")
            click.echo(f"Login:            {profile.netrc_login}")
            click.echo(f"Password:         {'*' * 20}")

        click.echo(f"\nCreated:          {profile.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        click.echo(f"Updated:          {profile.updated_at.strftime('%Y-%m-%d %H:%M:%S')}")
        click.echo(f"Validation:       {profile.validation_status.value}")

        if profile.last_validated_at:
            click.echo(f"Last Validated:   {profile.last_validated_at.strftime('%Y-%m-%d %H:%M:%S')}")

        if profile.validation_message:
            click.echo(f"Validation Msg:   {profile.validation_message}")

        if profile.metadata:
            click.echo(f"\nMetadata:")
            for key, value in profile.metadata.items():
                click.echo(f"  {key}: {value}")

        click.echo(f"{'='*60}\n")

    except Exception as e:
        click.echo(f"❌ Failed to show auth profile: {e}", err=True)
        raise click.Abort()


# Register the group
cli = auth_group
