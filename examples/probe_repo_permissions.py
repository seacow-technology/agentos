#!/usr/bin/env python3
"""Example: Probe repository permissions

This script demonstrates how to use GitClientWithAuth to probe read/write
permissions for Git repositories.

Usage:
    python examples/probe_repo_permissions.py
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agentos.core.git import (
    GitClientWithAuth,
    AuthProfile,
    AuthProfileType,
    TokenProvider,
    CredentialsManager,
)


def probe_public_repo():
    """Example: Probe a public GitHub repository"""
    print("=" * 60)
    print("Example 1: Probe public repository (no auth)")
    print("=" * 60)

    git_client = GitClientWithAuth()

    # Probe a public repository (no auth needed)
    result = git_client.probe(
        "https://github.com/torvalds/linux",
        profile=None,
        use_cache=False,
    )

    print(f"\nRepository: https://github.com/torvalds/linux")
    print(f"Read access: {'✓' if result.can_read else '✗'}")
    print(f"Write access: {'✓' if result.can_write else '✗'}")

    if result.error_message:
        print(f"Error: {result.error_message.splitlines()[0]}")

    if result.remote_info:
        branches = result.remote_info.get("branches", [])
        tags = result.remote_info.get("tags", [])
        print(f"\nRemote info:")
        print(f"  Branches: {len(branches)} (examples: {', '.join(branches[:5])})")
        print(f"  Tags: {len(tags)} (examples: {', '.join(tags[:5])})")

    print()


def probe_with_ssh_key():
    """Example: Probe with SSH key authentication"""
    print("=" * 60)
    print("Example 2: Probe with SSH key (simulated)")
    print("=" * 60)

    # Create a mock SSH profile (not actually used for probing)
    ssh_profile = AuthProfile(
        profile_id="demo-ssh",
        profile_name="demo-ssh",
        profile_type=AuthProfileType.SSH_KEY,
        ssh_key_path="~/.ssh/id_rsa",
    )

    git_client = GitClientWithAuth()

    # Note: This will fail unless you have SSH key set up and added to GitHub
    result = git_client.probe(
        "git@github.com:your-org/your-repo",  # Replace with your repo
        profile=ssh_profile,
        use_cache=False,
    )

    print(f"\nRepository: git@github.com:your-org/your-repo")
    print(f"Auth method: SSH Key ({ssh_profile.ssh_key_path})")
    print(f"Read access: {'✓' if result.can_read else '✗'}")
    print(f"Write access: {'✓' if result.can_write else '✗'}")

    if result.error_message:
        print(f"\nDiagnosis:")
        print(result.error_message)

    print()


def probe_with_pat_token():
    """Example: Probe with GitHub PAT token"""
    print("=" * 60)
    print("Example 3: Probe with GitHub PAT token (simulated)")
    print("=" * 60)

    # Create a mock PAT profile
    # In real usage, you would create this with CredentialsManager
    github_profile = AuthProfile(
        profile_id="demo-github",
        profile_name="demo-github",
        profile_type=AuthProfileType.PAT_TOKEN,
        token="ghp_your_token_here",  # Replace with real token
        token_provider=TokenProvider.GITHUB,
        token_scopes=["repo", "workflow"],  # Has write access
    )

    git_client = GitClientWithAuth()

    # Note: This will fail unless you provide a valid PAT token
    result = git_client.probe(
        "https://github.com/your-org/your-repo",  # Replace with your repo
        profile=github_profile,
        use_cache=False,
    )

    print(f"\nRepository: https://github.com/your-org/your-repo")
    print(f"Auth method: GitHub PAT token")
    print(f"Token scopes: {github_profile.token_scopes}")
    print(f"Read access: {'✓' if result.can_read else '✗'}")
    print(f"Write access: {'✓' if result.can_write else '✗'}")

    if result.error_message:
        print(f"\nDiagnosis:")
        print(result.error_message)

    print()


def demonstrate_caching():
    """Example: Demonstrate probe result caching"""
    print("=" * 60)
    print("Example 4: Probe result caching (15 min TTL)")
    print("=" * 60)

    git_client = GitClientWithAuth()

    import time

    # First probe
    print("\nFirst probe (uncached)...")
    start = time.time()
    result1 = git_client.probe(
        "https://github.com/torvalds/linux",
        use_cache=True,
    )
    duration1 = time.time() - start

    # Second probe (should use cache)
    print("Second probe (cached)...")
    start = time.time()
    result2 = git_client.probe(
        "https://github.com/torvalds/linux",
        use_cache=True,
    )
    duration2 = time.time() - start

    print(f"\nFirst probe duration: {duration1:.3f}s")
    print(f"Second probe duration: {duration2:.3f}s (should be much faster)")
    print(f"Speedup: {duration1/duration2:.1f}x")

    # Verify both results are the same
    assert result1.can_read == result2.can_read
    assert result1.can_write == result2.can_write
    print("\nCache hit verified! Both results are identical.")

    print()


def demonstrate_error_diagnosis():
    """Example: Demonstrate error diagnosis for different scenarios"""
    print("=" * 60)
    print("Example 5: Error diagnosis")
    print("=" * 60)

    git_client = GitClientWithAuth()

    # Test scenarios
    scenarios = [
        {
            "url": "https://github.com/nonexistent-user-12345/nonexistent-repo-67890",
            "description": "Non-existent repository (404)",
            "profile": None,
        },
        {
            "url": "git@github.com:test/test",
            "description": "SSH without valid key",
            "profile": AuthProfile(
                profile_id="test-ssh",
                profile_name="test-ssh",
                profile_type=AuthProfileType.SSH_KEY,
                ssh_key_path="~/.ssh/id_rsa",
            ),
        },
    ]

    for scenario in scenarios:
        print(f"\n{scenario['description']}:")
        print(f"URL: {scenario['url']}")

        result = git_client.probe(
            scenario['url'],
            profile=scenario['profile'],
            use_cache=False,
        )

        print(f"Read access: {'✓' if result.can_read else '✗'}")
        print(f"Write access: {'✓' if result.can_write else '✗'}")

        if result.error_message:
            print(f"\nError diagnosis:")
            # Print first 3 lines of error message
            lines = result.error_message.splitlines()[:3]
            for line in lines:
                print(f"  {line}")

    print()


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Git Repository Permission Probing Examples")
    print("=" * 60 + "\n")

    try:
        # Run examples
        probe_public_repo()

        # Uncomment to run other examples (require authentication setup)
        # probe_with_ssh_key()
        # probe_with_pat_token()

        demonstrate_caching()
        demonstrate_error_diagnosis()

        print("=" * 60)
        print("Examples completed!")
        print("=" * 60)

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        print(f"\n\nError: {e}")
        import traceback
        traceback.print_exc()
