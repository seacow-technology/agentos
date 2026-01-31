"""
Discord Client Demo

This script demonstrates the usage of the DiscordClient for editing interaction responses.

Usage:
    python examples/discord_client_demo.py

Requirements:
    - Valid Discord application_id and bot_token
    - Active interaction_token (from a recent Discord interaction)
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agentos.communicationos.channels.discord.client import (
    DiscordClient,
    DiscordAuthError,
    DiscordClientError,
    DiscordInteractionExpiredError,
    DiscordRateLimitError
)


async def demo_bot_validation():
    """Demonstrate bot token validation."""
    print("\n" + "="*60)
    print("Demo 1: Bot Token Validation")
    print("="*60)

    # Initialize client (use placeholder credentials for demo)
    client = DiscordClient(
        application_id="YOUR_APPLICATION_ID",
        bot_token="YOUR_BOT_TOKEN"
    )

    try:
        bot_user = await client.get_current_bot_user()
        print(f"✓ Bot authenticated successfully")
        print(f"  Username: {bot_user.get('username')}")
        print(f"  Bot ID: {bot_user.get('id')}")
        print(f"  Discriminator: {bot_user.get('discriminator')}")
        return True
    except DiscordAuthError as e:
        print(f"✗ Authentication failed: {e}")
        print("  → Please update credentials in this script")
        return False
    except DiscordClientError as e:
        print(f"✗ Error: {e}")
        return False


async def demo_edit_response():
    """Demonstrate editing an interaction response."""
    print("\n" + "="*60)
    print("Demo 2: Edit Interaction Response")
    print("="*60)

    client = DiscordClient(
        application_id="YOUR_APPLICATION_ID",
        bot_token="YOUR_BOT_TOKEN"
    )

    # In real usage, this comes from a Discord interaction
    interaction_token = "YOUR_INTERACTION_TOKEN"

    messages = [
        "Hello from AgentOS!",
        "This is a test of the Discord integration.",
        "The bot can edit its previous responses."
    ]

    for i, msg in enumerate(messages, 1):
        try:
            print(f"\nAttempting to edit response (message {i}/3)...")
            await client.edit_original_response(
                interaction_token=interaction_token,
                content=msg
            )
            print(f"✓ Response updated: {msg[:50]}...")
            await asyncio.sleep(1)  # Rate limit protection

        except DiscordInteractionExpiredError:
            print("✗ Interaction expired (>15 minutes old)")
            print("  → Get a fresh interaction_token from Discord")
            break
        except DiscordRateLimitError as e:
            print(f"✗ Rate limited: {e}")
            print("  → Wait before retrying")
            break
        except DiscordAuthError as e:
            print(f"✗ Auth error: {e}")
            break
        except DiscordClientError as e:
            print(f"✗ Error: {e}")
            break


async def demo_truncation():
    """Demonstrate automatic message truncation."""
    print("\n" + "="*60)
    print("Demo 3: Message Truncation")
    print("="*60)

    client = DiscordClient(
        application_id="YOUR_APPLICATION_ID",
        bot_token="YOUR_BOT_TOKEN",
        max_message_length=100  # Use small limit for demo
    )

    # Create a message that exceeds the limit
    long_message = "A" * 150 + " This part will be truncated!"

    print(f"Original message length: {len(long_message)} chars")
    print(f"Max allowed: {client.max_message_length} chars")

    # The client will automatically truncate
    truncated, was_truncated = client._truncate_content(long_message)

    print(f"\nTruncated: {was_truncated}")
    print(f"Final length: {len(truncated)} chars")
    print(f"Preview: {truncated[:80]}...")


async def demo_error_handling():
    """Demonstrate error handling for various scenarios."""
    print("\n" + "="*60)
    print("Demo 4: Error Handling")
    print("="*60)

    test_cases = [
        {
            "name": "Missing application_id",
            "application_id": "",
            "bot_token": "test_token",
            "expected": ValueError
        },
        {
            "name": "Missing bot_token",
            "application_id": "test_app_id",
            "bot_token": "",
            "expected": ValueError
        },
        {
            "name": "Valid initialization",
            "application_id": "test_app_id",
            "bot_token": "test_token",
            "expected": None
        }
    ]

    for test in test_cases:
        print(f"\nTest: {test['name']}")
        try:
            client = DiscordClient(
                application_id=test["application_id"],
                bot_token=test["bot_token"]
            )
            if test["expected"] is None:
                print(f"  ✓ Client initialized successfully")
            else:
                print(f"  ✗ Expected {test['expected'].__name__} but got success")
        except Exception as e:
            if isinstance(e, test["expected"]):
                print(f"  ✓ Caught expected {type(e).__name__}: {e}")
            else:
                print(f"  ✗ Unexpected error: {type(e).__name__}: {e}")


async def main():
    """Run all demos."""
    print("\n" + "#"*60)
    print("# Discord Client Demo")
    print("#"*60)

    # Demo 1: Bot validation (requires real credentials)
    # Uncomment to test with real Discord credentials
    # await demo_bot_validation()

    # Demo 2: Edit response (requires real credentials and interaction)
    # Uncomment to test with real Discord interaction
    # await demo_edit_response()

    # Demo 3: Truncation (works without credentials)
    await demo_truncation()

    # Demo 4: Error handling (works without credentials)
    await demo_error_handling()

    print("\n" + "#"*60)
    print("# Demo Complete")
    print("#"*60)
    print("\nNote: To test live Discord API calls:")
    print("1. Get your application_id and bot_token from Discord Developer Portal")
    print("2. Update the credentials in this script")
    print("3. Uncomment the demo_bot_validation() and demo_edit_response() calls")
    print("4. For edit_response, you need a recent interaction_token (<15 min old)")
    print("\nReferences:")
    print("- Discord Developer Portal: https://discord.com/developers/applications")
    print("- Bot Setup Guide: https://discord.com/developers/docs/getting-started")


if __name__ == "__main__":
    asyncio.run(main())
