"""Gmail Provider Demo Script.

This script demonstrates how to use the Gmail Provider for email communication
in AgentOS CommunicationOS.

Features demonstrated:
- OAuth 2.0 setup and token generation
- Credential validation
- Fetching unread messages
- Parsing email threading headers
- Sending replies with proper threading
- Marking messages as read

Usage:
    1. First time setup (generate refresh token):
        python examples/gmail_provider_demo.py setup

    2. Fetch and display messages:
        python examples/gmail_provider_demo.py fetch

    3. Send a test email:
        python examples/gmail_provider_demo.py send

    4. Interactive reply mode:
        python examples/gmail_provider_demo.py reply

Requirements:
    - Google Cloud project with Gmail API enabled
    - OAuth 2.0 credentials (client ID and secret)
    - pip install requests
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from agentos.communicationos.providers.email.gmail_provider import (
    GmailProvider,
    generate_auth_url,
    exchange_code_for_tokens
)
from agentos.communicationos.providers.email import parse_email_address


# Configuration file path
CONFIG_FILE = Path.home() / ".agentos" / "gmail_config.json"


def load_config():
    """Load Gmail configuration from file."""
    if not CONFIG_FILE.exists():
        return {}

    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Error loading config: {e}")
        return {}


def save_config(config):
    """Save Gmail configuration to file."""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        # Set restrictive permissions
        os.chmod(CONFIG_FILE, 0o600)
        print(f"✅ Configuration saved to {CONFIG_FILE}")
    except Exception as e:
        print(f"❌ Error saving config: {e}")


def setup_oauth():
    """Interactive OAuth 2.0 setup to generate refresh token."""
    print("=" * 60)
    print("Gmail Provider OAuth 2.0 Setup")
    print("=" * 60)
    print()

    # Get OAuth credentials
    print("First, you need OAuth 2.0 credentials from Google Cloud Console.")
    print("See GMAIL_SETUP.md for detailed instructions.")
    print()

    client_id = input("Enter OAuth Client ID: ").strip()
    if not client_id:
        print("❌ Client ID is required")
        return

    client_secret = input("Enter OAuth Client Secret: ").strip()
    if not client_secret:
        print("❌ Client Secret is required")
        return

    email_address = input("Enter your Gmail address: ").strip()
    if not email_address:
        print("❌ Email address is required")
        return

    # Generate authorization URL
    print("\n📋 Generating authorization URL...")
    auth_url = generate_auth_url(
        client_id=client_id,
        redirect_uri="http://localhost:8080/oauth2callback"
    )

    print("\n" + "=" * 60)
    print("STEP 1: Authorize the application")
    print("=" * 60)
    print("\nVisit this URL in your browser:")
    print(auth_url)
    print("\nAfter authorization, you'll be redirected to a URL like:")
    print("http://localhost:8080/oauth2callback?code=4/0Xxx...")
    print()

    # Get authorization code
    auth_code = input("Enter the authorization code (the part after 'code='): ").strip()
    if not auth_code:
        print("❌ Authorization code is required")
        return

    # Exchange code for tokens
    print("\n🔄 Exchanging authorization code for tokens...")
    try:
        tokens = exchange_code_for_tokens(
            client_id=client_id,
            client_secret=client_secret,
            code=auth_code,
            redirect_uri="http://localhost:8080/oauth2callback"
        )

        refresh_token = tokens["refresh_token"]
        access_token = tokens["access_token"]

        print("✅ Successfully obtained tokens!")

        # Save configuration
        config = {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "email_address": email_address
        }
        save_config(config)

        # Test credentials
        print("\n🔍 Validating credentials...")
        provider = GmailProvider(
            client_id=client_id,
            client_secret=client_secret,
            refresh_token=refresh_token,
            email_address=email_address,
            access_token=access_token
        )

        result = provider.validate_credentials()
        if result.valid:
            print("✅ Credentials validated successfully!")
            print(f"   Email: {email_address}")
        else:
            print(f"❌ Validation failed: {result.error_message}")
            return

        print("\n" + "=" * 60)
        print("Setup Complete!")
        print("=" * 60)
        print("\nYou can now use the following commands:")
        print("  python examples/gmail_provider_demo.py fetch")
        print("  python examples/gmail_provider_demo.py send")
        print("  python examples/gmail_provider_demo.py reply")

    except Exception as e:
        print(f"❌ Token exchange failed: {e}")
        return


def get_provider():
    """Create GmailProvider from saved configuration."""
    config = load_config()

    if not config:
        print("❌ No configuration found. Run setup first:")
        print("   python examples/gmail_provider_demo.py setup")
        return None

    required_keys = ["client_id", "client_secret", "refresh_token", "email_address"]
    if not all(key in config for key in required_keys):
        print("❌ Incomplete configuration. Run setup again:")
        print("   python examples/gmail_provider_demo.py setup")
        return None

    return GmailProvider(
        client_id=config["client_id"],
        client_secret=config["client_secret"],
        refresh_token=config["refresh_token"],
        email_address=config["email_address"]
    )


def fetch_messages():
    """Fetch and display recent unread messages."""
    provider = get_provider()
    if not provider:
        return

    print("=" * 60)
    print("Fetching Unread Messages")
    print("=" * 60)
    print()

    # Fetch messages from last 24 hours
    since = datetime.now(timezone.utc) - timedelta(hours=24)

    try:
        print(f"📬 Fetching unread messages since {since.strftime('%Y-%m-%d %H:%M:%S UTC')}...")
        messages = provider.fetch_messages(since=since, limit=10)

        if not messages:
            print("📭 No unread messages found.")
            return

        print(f"✅ Found {len(messages)} message(s)\n")

        for i, msg in enumerate(messages, 1):
            print(f"{'=' * 60}")
            print(f"Message {i} of {len(messages)}")
            print(f"{'=' * 60}")
            print(f"📧 Provider ID: {msg.provider_message_id}")
            print(f"🆔 Message-ID: {msg.message_id}")
            print(f"👤 From: {msg.from_name} <{msg.from_address}>")
            print(f"📨 To: {', '.join(msg.to_addresses)}")
            if msg.cc_addresses:
                print(f"📋 CC: {', '.join(msg.cc_addresses)}")
            print(f"📅 Date: {msg.date.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            print(f"📝 Subject: {msg.subject}")

            # Show threading info
            if msg.in_reply_to or msg.references:
                print("\n🧵 Threading:")
                if msg.in_reply_to:
                    print(f"   In-Reply-To: {msg.in_reply_to}")
                if msg.references:
                    print(f"   References: {msg.references}")
                thread_root = msg.compute_thread_root()
                print(f"   Thread Root: {thread_root}")

            # Show body preview
            print("\n📄 Body:")
            if msg.text_body:
                preview = msg.text_body[:200].replace("\n", " ")
                print(f"   {preview}")
                if len(msg.text_body) > 200:
                    print(f"   ... ({len(msg.text_body)} characters total)")
            elif msg.html_body:
                print("   (HTML message - text version not available)")
            else:
                print("   (No body content)")

            print()

    except Exception as e:
        print(f"❌ Error fetching messages: {e}")
        import traceback
        traceback.print_exc()


def send_message():
    """Send a test email message."""
    provider = get_provider()
    if not provider:
        return

    print("=" * 60)
    print("Send Email Message")
    print("=" * 60)
    print()

    # Get recipient
    recipient = input("To (email address): ").strip()
    if not recipient:
        print("❌ Recipient is required")
        return

    # Get subject
    subject = input("Subject: ").strip()
    if not subject:
        subject = "Test message from AgentOS"

    # Get body
    print("Body (press Ctrl+D or Ctrl+Z when done):")
    lines = []
    try:
        while True:
            line = input()
            lines.append(line)
    except EOFError:
        pass

    text_body = "\n".join(lines)
    if not text_body.strip():
        text_body = "This is a test message from AgentOS Gmail Provider."

    print("\n📤 Sending message...")

    try:
        result = provider.send_message(
            to_addresses=[recipient],
            subject=subject,
            text_body=text_body
        )

        if result.success:
            print("✅ Message sent successfully!")
            print(f"   Message ID: {result.message_id}")
            print(f"   Provider ID: {result.provider_message_id}")
        else:
            print(f"❌ Send failed: {result.error_message}")

    except Exception as e:
        print(f"❌ Error sending message: {e}")


def reply_to_messages():
    """Interactive mode to reply to unread messages."""
    provider = get_provider()
    if not provider:
        return

    print("=" * 60)
    print("Reply to Messages")
    print("=" * 60)
    print()

    # Fetch unread messages
    since = datetime.now(timezone.utc) - timedelta(hours=24)

    try:
        print("📬 Fetching unread messages...")
        messages = provider.fetch_messages(since=since, limit=10)

        if not messages:
            print("📭 No unread messages to reply to.")
            return

        print(f"✅ Found {len(messages)} message(s)\n")

        # Display messages
        for i, msg in enumerate(messages, 1):
            print(f"{i}. From: {msg.from_name} <{msg.from_address}>")
            print(f"   Subject: {msg.subject}")
            print(f"   Date: {msg.date.strftime('%Y-%m-%d %H:%M:%S')}")
            preview = (msg.text_body or msg.html_body or "")[:100]
            print(f"   Preview: {preview.replace(chr(10), ' ')}...")
            print()

        # Select message
        choice = input(f"Select message to reply to (1-{len(messages)}, or 'q' to quit): ").strip()

        if choice.lower() == 'q':
            return

        try:
            index = int(choice) - 1
            if index < 0 or index >= len(messages):
                print("❌ Invalid selection")
                return
        except ValueError:
            print("❌ Invalid selection")
            return

        original_msg = messages[index]

        # Show original message
        print("\n" + "=" * 60)
        print("Original Message")
        print("=" * 60)
        print(f"From: {original_msg.from_name} <{original_msg.from_address}>")
        print(f"Subject: {original_msg.subject}")
        print(f"Body:\n{original_msg.text_body or original_msg.html_body or '(empty)'}")
        print()

        # Compose reply
        print("=" * 60)
        print("Compose Reply")
        print("=" * 60)
        print("(Press Ctrl+D or Ctrl+Z when done)")
        print()

        lines = []
        try:
            while True:
                line = input()
                lines.append(line)
        except EOFError:
            pass

        reply_body = "\n".join(lines)
        if not reply_body.strip():
            print("❌ Reply body is empty")
            return

        # Get reply headers
        reply_headers = original_msg.get_reply_headers()

        # Send reply
        print("\n📤 Sending reply...")

        result = provider.send_message(
            to_addresses=[original_msg.from_address],
            subject=f"Re: {original_msg.subject}",
            text_body=reply_body,
            in_reply_to=reply_headers["In-Reply-To"],
            references=reply_headers["References"]
        )

        if result.success:
            print("✅ Reply sent successfully!")
            print(f"   Message ID: {result.message_id}")

            # Mark original as read
            print("\n📖 Marking original message as read...")
            if provider.mark_as_read(original_msg.provider_message_id):
                print("✅ Marked as read")
            else:
                print("⚠️  Could not mark as read")
        else:
            print(f"❌ Send failed: {result.error_message}")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Gmail Provider Demo for AgentOS",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python examples/gmail_provider_demo.py setup   # First time OAuth setup
  python examples/gmail_provider_demo.py fetch   # Fetch unread messages
  python examples/gmail_provider_demo.py send    # Send a test message
  python examples/gmail_provider_demo.py reply   # Reply to messages

For detailed setup instructions, see:
  agentos/communicationos/providers/email/GMAIL_SETUP.md
        """
    )

    parser.add_argument(
        "command",
        choices=["setup", "fetch", "send", "reply"],
        help="Command to execute"
    )

    args = parser.parse_args()

    if args.command == "setup":
        setup_oauth()
    elif args.command == "fetch":
        fetch_messages()
    elif args.command == "send":
        send_message()
    elif args.command == "reply":
        reply_to_messages()


if __name__ == "__main__":
    main()
