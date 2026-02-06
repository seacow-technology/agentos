# Email Adapter Usage Guide

This guide demonstrates how to use the Email Channel Adapter with different providers and integrate it with the CommunicationOS MessageBus.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Configuration](#configuration)
3. [Provider Setup](#provider-setup)
4. [Integration with MessageBus](#integration-with-messagebus)
5. [Polling Configuration](#polling-configuration)
6. [Error Handling](#error-handling)
7. [Testing](#testing)

## Quick Start

### Basic Usage

```python
from agentos.communicationos.channels.email import EmailAdapter, CursorStore
from agentos.communicationos.providers.email.smtp_imap import SmtpImapProvider

# Create provider (example with SMTP/IMAP)
provider = SmtpImapProvider(
    email_address="agent@example.com",
    smtp_host="smtp.example.com",
    smtp_port=587,
    smtp_username="agent@example.com",
    smtp_password="your-password",
    smtp_use_tls=True,
    imap_host="imap.example.com",
    imap_port=993,
    imap_username="agent@example.com",
    imap_password="your-password",
    imap_use_ssl=True
)

# Validate credentials
result = provider.validate_credentials()
if not result.valid:
    print(f"Invalid credentials: {result.error_message}")
    exit(1)

# Create adapter
adapter = EmailAdapter(
    channel_id="email_support_001",
    provider=provider,
    poll_interval_seconds=60,
    mailbox_folder="INBOX"
)

# Start polling (background thread)
adapter.start_polling(use_thread=True)

# ... application runs ...

# Stop polling when done
adapter.stop_polling()
```

## Configuration

### Adapter Configuration

```python
adapter = EmailAdapter(
    channel_id="email_gmail_001",          # Unique channel identifier
    provider=gmail_provider,                # IEmailProvider implementation
    poll_interval_seconds=60,               # Polling interval (30-3600 seconds)
    mailbox_folder="INBOX",                 # IMAP folder to monitor
    cursor_store=None,                      # Optional: Custom CursorStore
    message_bus=None                        # Optional: MessageBus for routing
)
```

### Cursor Store Configuration

The cursor store tracks the last poll position to avoid re-processing messages:

```python
from agentos.communicationos.channels.email import CursorStore

# Default location (in AgentOS data directory)
cursor_store = CursorStore()

# Custom database location
cursor_store = CursorStore(db_path="/path/to/email_cursors.db")

# Use with adapter
adapter = EmailAdapter(
    channel_id="email_001",
    provider=provider,
    cursor_store=cursor_store
)
```

## Provider Setup

### Gmail Provider (OAuth 2.0)

```python
from agentos.communicationos.providers.email.gmail import GmailProvider

provider = GmailProvider(
    email_address="agent@gmail.com",
    oauth_client_id="123456789.apps.googleusercontent.com",
    oauth_client_secret="GOCSPX-...",
    oauth_refresh_token="1//0g..."
)

# Validate credentials
result = provider.validate_credentials()
if result.valid:
    print("Gmail credentials valid")
```

### Outlook Provider (OAuth 2.0)

```python
from agentos.communicationos.providers.email.outlook import OutlookProvider

provider = OutlookProvider(
    email_address="agent@outlook.com",
    oauth_client_id="abcd1234-...",
    oauth_client_secret="xyz789~...",
    oauth_refresh_token="0.AX..."
)
```

### Generic SMTP/IMAP Provider

```python
from agentos.communicationos.providers.email.smtp_imap import SmtpImapProvider

provider = SmtpImapProvider(
    email_address="agent@example.com",
    smtp_host="smtp.example.com",
    smtp_port=587,
    smtp_username="agent@example.com",
    smtp_password="app-specific-password",
    smtp_use_tls=True,
    imap_host="imap.example.com",
    imap_port=993,
    imap_username="agent@example.com",
    imap_password="app-specific-password",
    imap_use_ssl=True
)
```

## Integration with MessageBus

### Complete Integration Example

```python
import asyncio
from agentos.communicationos.message_bus import MessageBus
from agentos.communicationos.channels.email import EmailAdapter
from agentos.communicationos.providers.email.gmail import GmailProvider

# Create MessageBus
message_bus = MessageBus()

# Create Gmail provider
provider = GmailProvider(
    email_address="agent@gmail.com",
    oauth_client_id=os.getenv("GMAIL_CLIENT_ID"),
    oauth_client_secret=os.getenv("GMAIL_CLIENT_SECRET"),
    oauth_refresh_token=os.getenv("GMAIL_REFRESH_TOKEN")
)

# Create adapter with MessageBus integration
adapter = EmailAdapter(
    channel_id="email_gmail_support",
    provider=provider,
    poll_interval_seconds=60,
    message_bus=message_bus
)

# Register adapter with MessageBus
message_bus.register_adapter("email_gmail_support", adapter)

# Add inbound message handler
def handle_inbound_message(message):
    print(f"Received email from {message.user_key}")
    print(f"Subject: {message.metadata.get('subject')}")
    print(f"Thread: {message.conversation_key}")

    # Process message...
    # Generate response...

    # Send reply
    reply = OutboundMessage(
        channel_id=message.channel_id,
        user_key=message.user_key,
        conversation_key=message.conversation_key,
        reply_to_message_id=message.message_id,
        text="Thank you for your email. We will respond shortly.",
        metadata={"subject": message.metadata.get("subject")}
    )

    asyncio.create_task(message_bus.send_outbound(reply))

message_bus.add_inbound_handler(handle_inbound_message)

# Start polling
adapter.start_polling(use_thread=True)

# Keep application running
try:
    while True:
        asyncio.sleep(1)
except KeyboardInterrupt:
    adapter.stop_polling()
```

### Command Processing Integration

```python
from agentos.communicationos.commands import CommandProcessor

# Create command processor
command_processor = CommandProcessor()

def handle_inbound_with_commands(message):
    # Check if message is a command
    if message.text and command_processor.is_command(message.text):
        # Process command
        response = command_processor.process(
            command_text=message.text,
            channel_id=message.channel_id,
            user_key=message.user_key,
            conversation_key=message.conversation_key
        )

        # Send command response
        asyncio.create_task(message_bus.send_outbound(response))
    else:
        # Forward to chat/agent
        forward_to_agent(message)

message_bus.add_inbound_handler(handle_inbound_with_commands)
```

## Polling Configuration

### Polling Modes

**Background Thread (Recommended for most cases):**

```python
# Start polling in background thread
adapter.start_polling(use_thread=True)

# Advantages:
# - Simple to use
# - No event loop management required
# - Runs independently

# Stop when done
adapter.stop_polling()
```

**Asyncio Task (For async applications):**

```python
# Start polling as asyncio task
adapter.start_polling(use_thread=False)

# Advantages:
# - Better integration with async code
# - Shared event loop

# Stop when done
adapter.stop_polling()
```

### Manual Polling

```python
# Single poll operation
messages = await adapter.poll()
print(f"Received {len(messages)} new messages")

# Process messages
for msg in messages:
    print(f"From: {msg.user_key}")
    print(f"Subject: {msg.metadata.get('subject')}")
    print(f"Text: {msg.text}")
```

### Polling Interval Guidelines

```python
# Real-time-ish (30 seconds minimum)
adapter = EmailAdapter(
    channel_id="support",
    provider=provider,
    poll_interval_seconds=30  # Check every 30 seconds
)

# Standard (1 minute - recommended)
poll_interval_seconds=60

# Low-traffic (5 minutes)
poll_interval_seconds=300

# Batch processing (1 hour)
poll_interval_seconds=3600
```

## Error Handling

### Provider Errors

```python
import asyncio

async def poll_with_retry():
    max_retries = 3
    retry_count = 0

    while retry_count < max_retries:
        try:
            messages = await adapter.poll()
            print(f"Successfully polled {len(messages)} messages")
            return messages
        except Exception as e:
            retry_count += 1
            print(f"Poll failed (attempt {retry_count}/{max_retries}): {e}")

            if retry_count < max_retries:
                # Exponential backoff
                wait_seconds = 2 ** retry_count
                print(f"Retrying in {wait_seconds} seconds...")
                await asyncio.sleep(wait_seconds)
            else:
                print("Max retries reached, giving up")
                raise
```

### Send Errors

```python
def send_with_fallback(adapter, outbound_msg):
    """Send message with error handling and fallback."""
    try:
        success = adapter.send_message(outbound_msg)

        if success:
            print("Message sent successfully")
        else:
            print("Message send failed, queuing for retry")
            # Add to retry queue...

    except Exception as e:
        print(f"Exception sending message: {e}")
        # Log error, alert admin, etc.
```

### Credential Validation

```python
def setup_adapter_with_validation(provider_config):
    """Setup adapter with credential validation."""
    # Create provider
    provider = create_provider(provider_config)

    # Validate credentials before starting
    result = provider.validate_credentials()

    if not result.valid:
        print(f"Credential validation failed: {result.error_message}")
        print(f"Error code: {result.error_code}")

        # Handle specific errors
        if result.error_code == "invalid_credentials":
            print("Please check your username and password")
        elif result.error_code == "network_error":
            print("Network connection failed, check connectivity")
        elif result.error_code == "quota_exceeded":
            print("API quota exceeded, try again later")

        return None

    # Create adapter
    adapter = EmailAdapter(
        channel_id="email_001",
        provider=provider
    )

    return adapter
```

## Testing

### Unit Testing with Mock Provider

```python
import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone
from agentos.communicationos.channels.email import EmailAdapter
from agentos.communicationos.providers.email import EmailEnvelope

class MockProvider:
    def __init__(self):
        self.messages = []

    def validate_credentials(self):
        return ValidationResult(valid=True)

    def fetch_messages(self, folder="INBOX", since=None, limit=100):
        return self.messages

    def send_message(self, **kwargs):
        return SendResult(success=True, message_id="<test@example.com>")

    def mark_as_read(self, msg_id):
        return True

@pytest.mark.asyncio
async def test_polling():
    provider = MockProvider()
    provider.messages = [
        EmailEnvelope(
            provider_message_id="001",
            message_id="<test-001@example.com>",
            from_address="user@example.com",
            to_addresses=["agent@example.com"],
            subject="Test",
            date=datetime.now(timezone.utc),
            text_body="Hello"
        )
    ]

    adapter = EmailAdapter(
        channel_id="test",
        provider=provider
    )

    messages = await adapter.poll()
    assert len(messages) == 1
    assert messages[0].user_key == "user@example.com"
```

### Integration Testing

```python
import pytest
from agentos.communicationos.message_bus import MessageBus
from agentos.communicationos.channels.email import EmailAdapter

@pytest.mark.asyncio
async def test_end_to_end_flow():
    # Setup
    message_bus = MessageBus()
    adapter = EmailAdapter(
        channel_id="test",
        provider=mock_provider,
        message_bus=message_bus
    )
    message_bus.register_adapter("test", adapter)

    # Track processed messages
    processed = []
    message_bus.add_inbound_handler(lambda msg: processed.append(msg))

    # Add test message to provider
    mock_provider.messages = [create_test_envelope()]

    # Poll
    await adapter.poll()

    # Verify
    assert len(processed) == 1
    assert processed[0].channel_id == "test"
```

## Advanced Usage

### Multiple Mailbox Folders

```python
# Monitor multiple folders
folders = ["INBOX", "Support", "Sales"]

for folder in folders:
    adapter = EmailAdapter(
        channel_id=f"email_{folder.lower()}",
        provider=provider,
        mailbox_folder=folder,
        poll_interval_seconds=60
    )
    adapter.start_polling(use_thread=True)
```

### Dynamic Poll Interval

```python
class AdaptiveEmailAdapter(EmailAdapter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.base_interval = self.poll_interval_seconds
        self.message_count_history = []

    async def poll(self):
        messages = await super().poll()

        # Track message rate
        self.message_count_history.append(len(messages))
        if len(self.message_count_history) > 10:
            self.message_count_history.pop(0)

        # Adjust polling interval based on activity
        avg_messages = sum(self.message_count_history) / len(self.message_count_history)

        if avg_messages > 5:
            # High activity - poll more frequently
            self.poll_interval_seconds = max(30, self.base_interval // 2)
        elif avg_messages < 1:
            # Low activity - poll less frequently
            self.poll_interval_seconds = min(3600, self.base_interval * 2)
        else:
            # Normal activity
            self.poll_interval_seconds = self.base_interval

        return messages
```

## Best Practices

1. **Always validate credentials before starting polling**
   ```python
   result = provider.validate_credentials()
   if not result.valid:
       raise ValueError(f"Invalid credentials: {result.error_message}")
   ```

2. **Use appropriate poll intervals**
   - 30-60 seconds for active support channels
   - 5-15 minutes for low-traffic channels
   - Respect provider rate limits

3. **Implement proper error handling**
   - Log all errors
   - Don't let exceptions stop polling
   - Implement retry logic

4. **Use cursor store for persistence**
   - Prevents duplicate processing after restarts
   - Tracks progress reliably

5. **Clean shutdown**
   ```python
   try:
       adapter.start_polling(use_thread=True)
       # ... run application ...
   finally:
       adapter.stop_polling()
   ```

6. **Monitor polling health**
   ```python
   # Track last successful poll
   last_successful_poll = None

   async def monitored_poll():
       global last_successful_poll
       try:
           messages = await adapter.poll()
           last_successful_poll = datetime.now(timezone.utc)
           return messages
       except Exception as e:
           # Alert if polling has been failing for too long
           if last_successful_poll:
               time_since_success = datetime.now(timezone.utc) - last_successful_poll
               if time_since_success > timedelta(minutes=30):
                   alert_ops("Email polling has been failing for 30 minutes")
           raise
   ```

## Troubleshooting

### Messages Not Being Fetched

1. Check cursor position:
   ```python
   cursor_time = adapter.cursor_store.get_last_poll_time(adapter.channel_id)
   print(f"Last poll time: {cursor_time}")
   ```

2. Verify provider credentials:
   ```python
   result = adapter.provider.validate_credentials()
   print(f"Credentials valid: {result.valid}")
   ```

3. Check mailbox folder:
   ```python
   # Try fetching directly
   messages = adapter.provider.fetch_messages(folder="INBOX", limit=10)
   print(f"Found {len(messages)} messages in INBOX")
   ```

### Duplicate Messages

- Verify deduplication is working:
  ```python
  # Check seen message IDs
  print(f"Tracking {len(adapter._seen_message_ids)} message IDs")
  ```

### Polling Not Starting

- Check if already polling:
  ```python
  if adapter._is_polling:
      print("Polling already started")
  ```

- Verify no exceptions in thread:
  ```python
  # Check thread status
  if adapter._polling_thread:
      print(f"Thread alive: {adapter._polling_thread.is_alive()}")
  ```

---

**Last Updated:** 2026-02-01
**Version:** 1.0.0
**Status:** Production Ready
