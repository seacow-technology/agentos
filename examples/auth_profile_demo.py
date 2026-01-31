"""Auth Profile Demo - Complete Workflow Example

This demo shows how to use the Auth Profile system for secure Git credential management.

Run this script to see:
1. Creating auth profiles
2. Validating credentials
3. Cloning private repositories
4. Listing and managing profiles

Prerequisites:
- AgentOS database initialized (agentos init)
- Migration v19 applied (agentos migrate)
"""

import os
import sys
from pathlib import Path
import tempfile

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from agentos.core.git.credentials import (
    CredentialsManager,
    AuthProfileType,
    TokenProvider,
)
from agentos.core.git.client import GitClientWithAuth


def demo_create_profiles():
    """Demo: Creating different types of auth profiles"""
    print("\n" + "="*60)
    print("DEMO 1: Creating Auth Profiles")
    print("="*60)

    manager = CredentialsManager()

    # Example 1: GitHub PAT Token
    print("\n1. Creating GitHub PAT profile...")
    try:
        github_profile = manager.create_profile(
            profile_name="demo-github-pat",
            profile_type=AuthProfileType.PAT_TOKEN,
            token="ghp_demo_token_not_real",
            token_provider=TokenProvider.GITHUB,
            token_scopes=["repo", "workflow"],
            metadata={"description": "Demo GitHub token for testing"},
        )
        print(f"   ✅ Created: {github_profile.profile_name}")
        print(f"   Profile ID: {github_profile.profile_id}")
        print(f"   Provider: {github_profile.token_provider.value}")
        print(f"   Token: {'*' * 40} (encrypted at rest)")
    except Exception as e:
        print(f"   ❌ Failed: {e}")

    # Example 2: SSH Key
    print("\n2. Creating SSH Key profile...")
    try:
        # Create a dummy SSH key file for demo
        ssh_key_path = Path(tempfile.gettempdir()) / "demo_ssh_key"
        ssh_key_path.write_text("DEMO SSH KEY - NOT REAL")

        ssh_profile = manager.create_profile(
            profile_name="demo-ssh-key",
            profile_type=AuthProfileType.SSH_KEY,
            ssh_key_path=str(ssh_key_path),
            ssh_passphrase="demo-passphrase",
            metadata={"description": "Demo SSH key for testing"},
        )
        print(f"   ✅ Created: {ssh_profile.profile_name}")
        print(f"   Key Path: {ssh_profile.ssh_key_path}")
        print(f"   Passphrase: {'*' * 15} (encrypted at rest)")
    except Exception as e:
        print(f"   ❌ Failed: {e}")

    # Example 3: Netrc
    print("\n3. Creating Netrc profile...")
    try:
        netrc_profile = manager.create_profile(
            profile_name="demo-gitlab-netrc",
            profile_type=AuthProfileType.NETRC,
            netrc_machine="gitlab.com",
            netrc_login="demo-user",
            netrc_password="demo-password",
            metadata={"description": "Demo GitLab netrc credentials"},
        )
        print(f"   ✅ Created: {netrc_profile.profile_name}")
        print(f"   Machine: {netrc_profile.netrc_machine}")
        print(f"   Login: {netrc_profile.netrc_login}")
        print(f"   Password: {'*' * 15} (encrypted at rest)")
    except Exception as e:
        print(f"   ❌ Failed: {e}")


def demo_list_profiles():
    """Demo: Listing all auth profiles"""
    print("\n" + "="*60)
    print("DEMO 2: Listing Auth Profiles")
    print("="*60)

    manager = CredentialsManager()

    profiles = manager.list_profiles(include_sensitive=False)

    if not profiles:
        print("\nNo profiles found.")
        return

    print(f"\nFound {len(profiles)} profile(s):\n")

    for profile in profiles:
        print(f"Profile: {profile.profile_name}")
        print(f"  Type: {profile.profile_type.value}")

        if profile.profile_type == AuthProfileType.PAT_TOKEN:
            print(f"  Provider: {profile.token_provider.value}")
            print(f"  Token: [REDACTED]")

        elif profile.profile_type == AuthProfileType.SSH_KEY:
            print(f"  Key Path: {profile.ssh_key_path}")
            print(f"  Passphrase: [REDACTED]")

        elif profile.profile_type == AuthProfileType.NETRC:
            print(f"  Machine: {profile.netrc_machine}")
            print(f"  Login: {profile.netrc_login}")
            print(f"  Password: [REDACTED]")

        print(f"  Validation Status: {profile.validation_status.value}")
        print(f"  Created: {profile.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        print()


def demo_retrieve_profile():
    """Demo: Retrieving a profile with decrypted credentials"""
    print("\n" + "="*60)
    print("DEMO 3: Retrieving Profile (with Decryption)")
    print("="*60)

    manager = CredentialsManager()

    profile_name = "demo-github-pat"

    print(f"\nRetrieving profile: {profile_name}...")
    profile = manager.get_profile(profile_name)

    if not profile:
        print(f"   ❌ Profile not found: {profile_name}")
        return

    print(f"   ✅ Profile retrieved successfully")
    print(f"\n   Profile Name: {profile.profile_name}")
    print(f"   Type: {profile.profile_type.value}")
    print(f"   Provider: {profile.token_provider.value}")
    print(f"   Token (decrypted): {profile.token}")
    print(f"   Scopes: {profile.token_scopes}")
    print(f"\n   ⚠️  Note: Token is decrypted in memory only")
    print(f"   Stored encrypted in database")


def demo_validation():
    """Demo: Validating credentials"""
    print("\n" + "="*60)
    print("DEMO 4: Credential Validation")
    print("="*60)

    client = GitClientWithAuth()

    profile_name = "demo-github-pat"

    print(f"\nValidating credentials: {profile_name}...")
    print("   (This will fail since token is fake)")

    try:
        is_valid = client.validate_credentials(profile_name)

        if is_valid:
            print(f"   ✅ Credentials are valid")
        else:
            print(f"   ❌ Credentials validation failed")

            # Check validation message
            manager = CredentialsManager()
            profile = manager.get_profile(profile_name)
            if profile.validation_message:
                print(f"   Error: {profile.validation_message}")
    except Exception as e:
        print(f"   ❌ Validation error: {e}")


def demo_environment_fallback():
    """Demo: Environment variable fallback"""
    print("\n" + "="*60)
    print("DEMO 5: Environment Variable Fallback")
    print("="*60)

    manager = CredentialsManager()

    print("\nChecking for environment tokens...")

    for provider in TokenProvider:
        token = manager.get_from_env(provider)
        if token:
            print(f"   ✅ {provider.value}: Found (length={len(token)})")
        else:
            print(f"   ⚠️  {provider.value}: Not set")

    print("\nExample usage:")
    print("   export GITHUB_TOKEN=ghp_your_token_here")
    print("   # Clone will automatically use token if no profile specified")


def demo_audit_log():
    """Demo: Viewing audit logs"""
    print("\n" + "="*60)
    print("DEMO 6: Audit Logs")
    print("="*60)

    from agentos.store import get_db

    conn = get_db()
    cursor = conn.cursor()

    print("\nRecent credential usage:")

    try:
        logs = cursor.execute("""
            SELECT
                ap.profile_name,
                apu.operation,
                apu.status,
                apu.used_at
            FROM auth_profile_usage apu
            JOIN auth_profiles ap ON apu.profile_id = ap.profile_id
            ORDER BY apu.used_at DESC
            LIMIT 10
        """).fetchall()

        if not logs:
            print("   No usage logs found")
        else:
            for log in logs:
                print(f"   {log['used_at']}: {log['profile_name']} - {log['operation']} - {log['status']}")

    finally:
        conn.close()


def demo_cleanup():
    """Demo: Cleaning up demo profiles"""
    print("\n" + "="*60)
    print("DEMO 7: Cleanup")
    print("="*60)

    manager = CredentialsManager()

    demo_profiles = [
        "demo-github-pat",
        "demo-ssh-key",
        "demo-gitlab-netrc",
    ]

    print("\nCleaning up demo profiles...")

    for profile_name in demo_profiles:
        try:
            deleted = manager.delete_profile(profile_name)
            if deleted:
                print(f"   ✅ Deleted: {profile_name}")
            else:
                print(f"   ⚠️  Not found: {profile_name}")
        except Exception as e:
            print(f"   ❌ Failed to delete {profile_name}: {e}")

    # Clean up demo SSH key file
    try:
        ssh_key_path = Path(tempfile.gettempdir()) / "demo_ssh_key"
        if ssh_key_path.exists():
            ssh_key_path.unlink()
            print(f"   ✅ Deleted demo SSH key file")
    except Exception as e:
        print(f"   ⚠️  Failed to delete SSH key: {e}")


def main():
    """Run all demos"""
    print("\n" + "="*60)
    print("Auth Profile System Demo")
    print("="*60)
    print("\nThis demo shows the complete auth profile workflow:")
    print("1. Creating different types of profiles")
    print("2. Listing profiles")
    print("3. Retrieving with decryption")
    print("4. Validating credentials")
    print("5. Environment variable fallback")
    print("6. Viewing audit logs")
    print("7. Cleanup")

    input("\nPress Enter to start demo...")

    try:
        demo_create_profiles()
        input("\nPress Enter to continue...")

        demo_list_profiles()
        input("\nPress Enter to continue...")

        demo_retrieve_profile()
        input("\nPress Enter to continue...")

        demo_validation()
        input("\nPress Enter to continue...")

        demo_environment_fallback()
        input("\nPress Enter to continue...")

        demo_audit_log()
        input("\nPress Enter to cleanup...")

        demo_cleanup()

    except KeyboardInterrupt:
        print("\n\n❌ Demo interrupted. Cleaning up...")
        demo_cleanup()
        sys.exit(0)

    except Exception as e:
        print(f"\n\n❌ Demo error: {e}")
        print("Cleaning up...")
        demo_cleanup()
        sys.exit(1)

    print("\n" + "="*60)
    print("Demo Complete!")
    print("="*60)
    print("\nFor more information:")
    print("  - Documentation: docs/auth/AUTH_PROFILE_QUICKSTART.md")
    print("  - CLI help: agentos auth --help")
    print("  - Python API: from agentos.core.git import CredentialsManager")
    print()


if __name__ == "__main__":
    main()
