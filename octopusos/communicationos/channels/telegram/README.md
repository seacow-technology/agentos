# Telegram Channel Adapter

This directory contains the Telegram Bot API integration for CommunicationOS.

## Overview

The Telegram adapter enables AgentOS to receive and send messages via Telegram Bot API. It provides:

- **Webhook-based message reception**: Receives Telegram updates via webhooks
- **Unified message format**: Converts Telegram updates to InboundMessage
- **Message sending**: Sends replies through Telegram Bot API
- **Security**: Secret token verification for webhook authenticity
- **Bot loop protection**: Automatically ignores messages from bots

## Components

### adapter.py

The `TelegramAdapter` class implements the core adapter logic:

- `parse_update()`: Converts Telegram update JSON to InboundMessage
- `send_message()`: Sends OutboundMessage via Telegram Bot API
- `verify_secret()`: Verifies X-Telegram-Bot-Api-Secret-Token header

### client.py

HTTP client for Telegram Bot API:

- `send_message()`: Send text messages
- `set_webhook()`: Configure webhook URL
- `get_webhook_info()`: Get current webhook status
- `delete_webhook()`: Remove webhook configuration

## Message Mapping

### Inbound Messages (Telegram → AgentOS)

| Telegram Field | InboundMessage Field | Notes |
|----------------|---------------------|-------|
| update_id | message_id (part) | Combined with message_id as `tg_{update_id}_{message_id}` |
| message.from.id | user_key | Telegram user ID as string |
| message.chat.id | conversation_key | Chat ID as string |
| message.date | timestamp | Unix timestamp converted to UTC datetime |
| message.text | text | Plain text content |
| message.photo | attachments | Largest photo selected |
| message.document | attachments | File attachment |
| message.audio/voice | attachments | Audio/voice note |
| message.video | attachments | Video file |
| message.location | location | Geographic coordinates |
| message.caption | text | Caption for media messages |

### Message Types

- **TEXT**: Plain text messages
- **IMAGE**: Photo messages
- **AUDIO**: Audio files and voice notes
- **VIDEO**: Video files
- **FILE**: Document files
- **LOCATION**: Location sharing

### Bot Loop Protection

Messages where `from.is_bot == true` are automatically ignored to prevent bot-to-bot loops.

## Configuration

Required configuration fields (from manifest):

```json
{
  "bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
  "webhook_secret": "your_secure_random_string_here"
}
```

### Getting Bot Token

1. Open Telegram and search for `@BotFather`
2. Send `/newbot` command
3. Follow prompts to create bot
4. Copy the bot token provided

### Generating Webhook Secret

Generate a secure random string (32+ characters):

```bash
openssl rand -hex 32
```

## Security

### Webhook Verification

The adapter verifies the `X-Telegram-Bot-Api-Secret-Token` header on all webhook requests using constant-time comparison to prevent timing attacks.

### Rate Limiting

Rate limiting is applied via MessageBus middleware (default: 30 messages/minute per user).

### Chat-Only Mode

By default, the adapter operates in chat-only mode (no code execution) for security.

## API Endpoint

**POST** `/api/channels/telegram/webhook`

**Headers:**
- `X-Telegram-Bot-Api-Secret-Token`: Required secret token

**Body:**
- JSON-encoded Telegram update

**Response:**
- Always returns `200 OK` to prevent Telegram retries
- Internal errors are logged but don't affect response

## Usage Example

### Setting up a channel

```python
from agentos.communicationos.channels.telegram import TelegramAdapter
from agentos.communicationos.channels.telegram.client import set_webhook

# Create adapter
adapter = TelegramAdapter(
    channel_id="my_telegram_bot",
    bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
    webhook_secret="my_secure_secret_token"
)

# Set webhook URL
webhook_url = "https://your-domain.com/api/channels/telegram/webhook"
success, error = set_webhook(
    bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
    webhook_url=webhook_url,
    secret_token="my_secure_secret_token"
)

if success:
    print("Webhook configured successfully")
else:
    print(f"Failed to set webhook: {error}")
```

### Parsing incoming messages

```python
# Telegram webhook data
update_data = {
    "update_id": 123456789,
    "message": {
        "message_id": 1,
        "from": {"id": 987654321, "is_bot": False, "username": "user"},
        "chat": {"id": 987654321, "type": "private"},
        "date": 1609459200,
        "text": "Hello!"
    }
}

# Parse to InboundMessage
message = adapter.parse_update(update_data)

if message:
    print(f"Received from {message.user_key}: {message.text}")
```

### Sending messages

```python
from agentos.communicationos.models import OutboundMessage, MessageType

# Create outbound message
outbound = OutboundMessage(
    channel_id="my_telegram_bot",
    user_key="987654321",
    conversation_key="987654321",
    type=MessageType.TEXT,
    text="Hello from AgentOS!"
)

# Send via adapter
success = adapter.send_message(outbound)
```

## Testing

Run unit tests:

```bash
python3 -m pytest tests/unit/communicationos/channels/test_telegram_adapter.py -v
```

Test coverage includes:
- Secret token verification
- Text message parsing
- Media message parsing (photos, documents, audio, video)
- Location message parsing
- Bot loop protection
- Error handling

## References

- [Telegram Bot API Documentation](https://core.telegram.org/bots/api)
- [Webhook Setup Guide](https://core.telegram.org/bots/api#setwebhook)
- [Update Object Reference](https://core.telegram.org/bots/api#update)
- [Message Object Reference](https://core.telegram.org/bots/api#message)

## Limitations

- Only handles regular messages (not edited_messages, channel_posts, etc.)
- File URLs are stored as file_id (actual URL retrieval requires additional API call)
- Single text message per response (no message batching)
- Group chat support is basic (no admin features)

## Future Enhancements

- Support for inline keyboards and interactive buttons
- File download and upload capabilities
- Group chat admin features
- Message editing and deletion
- Sticker and GIF support
- Poll and quiz support
