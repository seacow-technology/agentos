# Slack Channel Adapter

## Overview

The Slack Channel Adapter enables AgentOS to communicate with users via Slack, supporting direct messages, channel messages, mentions, and threaded conversations.

## Features

- ✅ **Slack Events API Integration**: Receive messages via webhooks
- ✅ **Signature Verification**: HMAC-SHA256 security with timestamp validation
- ✅ **URL Verification**: Automatic challenge response
- ✅ **Thread Support**: Full threaded conversation isolation
- ✅ **Bot Loop Protection**: Dual bot detection (bot_id + subtype)
- ✅ **Idempotency**: Automatic retry handling
- ✅ **Trigger Policies**: Flexible message filtering (dm_only, mention_or_dm, all_messages)
- ✅ **3-Second Response**: Meets Slack's webhook timeout requirements

## Quick Start

### 1. Installation

The Slack adapter is included in AgentOS. No additional installation required.

### 2. Configure Slack App

Create a Slack App at https://api.slack.com/apps:

**Bot Token Scopes** (OAuth & Permissions):
- `chat:write` - Send messages
- `channels:history` - Read channel messages (if using all_messages policy)
- `groups:history` - Read private channel messages
- `im:history` - Read DM messages
- `app_mentions:read` - Read mentions

**Event Subscriptions**:
- Request URL: `https://your-domain.com/webhooks/slack`
- Subscribe to bot events:
  - `message.im` - Direct messages
  - `app_mention` - Bot mentions
  - `message.channels` - Channel messages (if using all_messages policy)

**Install to Workspace**: Install the app to get Bot User OAuth Token

### 3. Initialize Adapter

```python
from agentos.communicationos.channels.slack import SlackAdapter
from agentos.communicationos.message_bus import MessageBus

# Create adapter
adapter = SlackAdapter(
    channel_id="slack_workspace_001",
    bot_token="xoxb-your-bot-token",
    signing_secret="your-signing-secret",
    trigger_policy="mention_or_dm"  # dm_only, mention_or_dm, or all_messages
)

# Register with MessageBus
bus = MessageBus()
bus.register_adapter("slack_workspace_001", adapter)
```

### 4. Webhook Endpoint

```python
from fastapi import FastAPI, Request, Response
import asyncio

app = FastAPI()

@app.post("/webhooks/slack")
async def slack_webhook(request: Request):
    # Get headers and body
    timestamp = request.headers.get("X-Slack-Request-Timestamp")
    signature = request.headers.get("X-Slack-Signature")
    body = await request.body()
    body_str = body.decode("utf-8")

    # Verify signature
    if not adapter.verify_signature(timestamp, body_str, signature):
        return Response(status_code=401, content="Invalid signature")

    # Parse JSON
    event_data = await request.json()

    # Handle URL verification
    challenge = adapter.handle_url_verification(event_data)
    if challenge:
        return {"challenge": challenge}

    # Parse event (non-blocking)
    inbound_message = adapter.parse_event(event_data)

    if inbound_message:
        # Process asynchronously (don't wait for completion)
        asyncio.create_task(bus.process_inbound(inbound_message))

    # Return 200 immediately (< 3 seconds)
    return Response(status_code=200, content="OK")
```

## Trigger Policies

### `dm_only`
Only respond to direct messages. Ignores all channel messages and mentions.

**Use Case**: Personal assistant bot, 1-on-1 support bot

```python
adapter = SlackAdapter(
    channel_id="slack_support",
    bot_token="xoxb-...",
    signing_secret="...",
    trigger_policy="dm_only"
)
```

### `mention_or_dm` (Default)
Respond to direct messages and @mentions. Ignores regular channel messages.

**Use Case**: Team collaboration bot, Q&A bot

```python
adapter = SlackAdapter(
    channel_id="slack_team",
    bot_token="xoxb-...",
    signing_secret="...",
    trigger_policy="mention_or_dm"
)
```

### `all_messages`
Respond to all messages (DMs, mentions, and regular channel messages).

**Use Case**: Monitoring bot, analytics bot, moderation bot

**⚠️ Warning**: Requires `channels:history` scope. Can generate high message volume.

```python
adapter = SlackAdapter(
    channel_id="slack_monitor",
    bot_token="xoxb-...",
    signing_secret="...",
    trigger_policy="all_messages"
)
```

## Thread Handling

The adapter automatically handles threaded conversations with proper isolation:

### Conversation Key Format

- **Non-thread message**: `conversation_key = "{channel_id}"`
- **Thread message**: `conversation_key = "{channel_id}:{thread_ts}"`

### Example

```python
# User sends message in channel C123
# conversation_key = "C123"

# User replies in thread with thread_ts = "1234567890.123456"
# conversation_key = "C123:1234567890.123456"

# Different thread in same channel: thread_ts = "1234567891.000000"
# conversation_key = "C123:1234567891.000000"
```

Each thread maintains a separate session and context.

## Security

### Signature Verification

Always verify Slack signatures to prevent spoofing:

```python
# Required headers
timestamp = request.headers.get("X-Slack-Request-Timestamp")
signature = request.headers.get("X-Slack-Signature")
body = await request.body()

# Verify
if not adapter.verify_signature(timestamp, body.decode(), signature):
    return Response(status_code=401)
```

**Security Features**:
- HMAC-SHA256 signature
- Timestamp validation (5-minute window)
- Constant-time comparison (timing attack prevention)

### Bot Loop Protection

The adapter automatically ignores bot messages:

- Messages with `bot_id` field
- Messages with `subtype=bot_message`

This prevents infinite loops when multiple bots are in the same channel.

## Idempotency

Slack may retry webhooks if your endpoint doesn't respond within 3 seconds or returns an error.

**Built-in Protection**:
- Event IDs are tracked to prevent duplicate processing
- Same `event_id` returns `None` on second parse
- Memory-efficient: LRU cleanup keeps last 10,000 event IDs

**Retry Header**: Check `X-Slack-Retry-Num` header to detect retries (informational only).

## Performance

### Webhook Response Time

Slack requires webhooks to respond within **3 seconds**. Best practices:

```python
@app.post("/webhooks/slack")
async def slack_webhook(request: Request):
    # 1. Verify signature (< 10ms)
    if not verify_signature(...):
        return 401

    # 2. Handle URL verification (< 1ms)
    if challenge := handle_url_verification(...):
        return {"challenge": challenge}

    # 3. Parse event (< 10ms)
    message = adapter.parse_event(event_data)

    # 4. Process asynchronously (DON'T AWAIT)
    asyncio.create_task(bus.process_inbound(message))

    # 5. Return 200 immediately (< 50ms total)
    return Response(status_code=200)
```

**Measured Performance**:
- Signature verification: ~5ms
- Event parsing: ~2ms
- URL verification: <1ms
- **Total**: ~10-50ms (well under 3 seconds)

## Message Types

Currently supported:
- ✅ Text messages
- ✅ Direct messages (DMs)
- ✅ Channel messages
- ✅ Thread replies
- ✅ App mentions

Future support:
- 🔜 File attachments
- 🔜 Interactive components (buttons, modals)
- 🔜 Block Kit rich formatting
- 🔜 Slash commands

## Error Handling

### Missing Required Fields

Returns `None` instead of raising exceptions:

```python
message = adapter.parse_event(event_data)
if message is None:
    # Invalid event, bot message, or filtered by policy
    logger.debug("Event ignored")
```

### Send Failure

Returns `False` on failure:

```python
success = adapter.send_message(outbound_message)
if not success:
    logger.error("Failed to send message")
    # Retry logic here
```

## Testing

### Unit Tests

```bash
pytest tests/unit/communicationos/channels/test_slack_adapter.py -v
```

**Coverage**: 31 tests, 81% adapter coverage

### Integration Tests

```bash
pytest tests/integration/communicationos/test_slack_integration.py -v
```

**Coverage**: 18 tests, full integration flow

### Manual Testing

Use Slack's **Request URL Verification** in Event Subscriptions settings to test your webhook endpoint.

## Comparison with Other Adapters

| Feature | Telegram | Slack | WhatsApp |
|---------|----------|-------|----------|
| Signature Verification | Secret token | HMAC-SHA256 | HMAC-SHA256 |
| Thread Support | ❌ | ✅ | ❌ |
| Webhook Timeout | None | 3 seconds | 30 seconds |
| Built-in Retry | ❌ | ✅ | ✅ |
| Bot Loop Protection | is_bot flag | bot_id + subtype | N/A |

## Troubleshooting

### Webhook Returns 401

**Cause**: Invalid signature
**Solution**: Check signing secret, verify timestamp is within 5 minutes

### Messages Not Received

**Cause**: Missing event subscriptions or scopes
**Solution**:
1. Check Event Subscriptions settings
2. Verify bot scopes in OAuth & Permissions
3. Reinstall app to workspace

### Bot Responds to Own Messages

**Cause**: Bot loop protection not working
**Solution**: Verify `bot_id` field is present in bot messages. Check Slack App settings.

### Thread Replies Go to Channel

**Cause**: `thread_ts` not preserved
**Solution**: Ensure `conversation_key` contains thread_ts. Check adapter logic.

### Slow Response / Timeout

**Cause**: Synchronous processing blocks webhook
**Solution**: Use `asyncio.create_task()` for async processing. Don't await business logic.

## API Reference

### SlackAdapter

```python
class SlackAdapter:
    def __init__(
        self,
        channel_id: str,
        bot_token: str,
        signing_secret: str,
        trigger_policy: str = "mention_or_dm"
    ):
        """Initialize Slack adapter."""

    def verify_signature(
        self,
        timestamp: str,
        body: str,
        signature: str
    ) -> bool:
        """Verify webhook signature."""

    def handle_url_verification(
        self,
        event_data: Dict[str, Any]
    ) -> Optional[str]:
        """Handle URL verification challenge."""

    def parse_event(
        self,
        event_data: Dict[str, Any]
    ) -> Optional[InboundMessage]:
        """Parse Slack event into InboundMessage."""

    def send_message(
        self,
        message: OutboundMessage
    ) -> bool:
        """Send message via Slack API."""

    def get_channel_id(self) -> str:
        """Get channel identifier."""
```

## Resources

- [Slack API Documentation](https://api.slack.com/)
- [Events API Guide](https://api.slack.com/apis/connections/events-api)
- [Signature Verification](https://api.slack.com/authentication/verifying-requests-from-slack)
- [Block Kit Builder](https://app.slack.com/block-kit-builder)

## License

Part of AgentOS. See main LICENSE file.
