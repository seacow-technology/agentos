# Discord Channel for CommunicationOS

## Quick Start

```python
from agentos.communicationos.channels.discord import DiscordClient

# Initialize client
client = DiscordClient(
    application_id="YOUR_APPLICATION_ID",
    bot_token="YOUR_BOT_TOKEN"
)

# Edit interaction response
await client.edit_original_response(
    interaction_token="token_from_discord",
    content="Hello from AgentOS!"
)
```

## Setup

### 1. Get Discord Credentials

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application or select existing one
3. Note the **Application ID**
4. Go to "Bot" tab and get the **Bot Token**

### 2. Install Dependencies

```bash
pip install httpx
```

### 3. Configure Bot Permissions

Required permissions:
- Send Messages
- Use Slash Commands

## API Reference

### DiscordClient

#### Constructor
```python
DiscordClient(
    application_id: str,
    bot_token: str,
    max_message_length: Optional[int] = 2000
)
```

#### Methods

##### `edit_original_response(interaction_token: str, content: str) -> None`
Edit the original interaction response.

**Parameters**:
- `interaction_token`: Token from Discord interaction (valid for 15 minutes)
- `content`: New message content (auto-truncated if too long)

**Raises**:
- `DiscordInteractionExpiredError`: Interaction expired (>15 min)
- `DiscordAuthError`: Invalid bot token
- `DiscordRateLimitError`: Rate limit exceeded
- `DiscordClientError`: Other API errors

**Example**:
```python
try:
    await client.edit_original_response(
        interaction_token="abc123...",
        content="Updated message"
    )
except DiscordInteractionExpiredError:
    # Handle expired interaction
    pass
```

##### `get_current_bot_user() -> Dict[str, Any]`
Get current bot user information.

**Returns**:
Dictionary with bot user data:
- `id`: Bot user ID
- `username`: Bot username
- `discriminator`: Bot discriminator
- `bot`: True (indicates bot account)

**Example**:
```python
bot_user = await client.get_current_bot_user()
print(f"Bot: {bot_user['username']}#{bot_user['discriminator']}")
```

## Error Handling

```python
from agentos.communicationos.channels.discord import (
    DiscordClient,
    DiscordClientError,
    DiscordInteractionExpiredError,
    DiscordRateLimitError,
    DiscordAuthError,
)

try:
    await client.edit_original_response(token, content)
except DiscordInteractionExpiredError:
    # Interaction is >15 minutes old
    logging.error("Interaction expired")
except DiscordRateLimitError as e:
    # Rate limit hit, retry later
    retry_after = extract_retry_after(str(e))
    await asyncio.sleep(retry_after)
except DiscordAuthError:
    # Invalid bot token
    logging.error("Authentication failed")
except DiscordClientError as e:
    # Other errors
    logging.error(f"Discord API error: {e}")
```

## Message Truncation

Messages longer than `max_message_length` (default: 2000) are automatically truncated:

```python
# Long message
content = "A" * 3000

# Automatically truncated to 2000 chars with "...(truncated)" suffix
await client.edit_original_response(token, content)
```

**Audit Logging**: Truncation events are logged with original and truncated lengths.

## Configuration

### Environment Variables
```bash
export DISCORD_APPLICATION_ID="your_app_id"
export DISCORD_BOT_TOKEN="your_bot_token"
```

### Code
```python
import os

client = DiscordClient(
    application_id=os.getenv("DISCORD_APPLICATION_ID"),
    bot_token=os.getenv("DISCORD_BOT_TOKEN"),
    max_message_length=2000  # Optional
)
```

## Rate Limits

Discord API rate limits:
- Global: 50 requests/second
- Per-endpoint: Varies by endpoint
- Edit message: 5 requests/second per channel

**Best Practices**:
- Implement exponential backoff
- Handle 429 responses
- Use `retry_after` from response

```python
import asyncio

async def edit_with_retry(client, token, content, max_retries=3):
    for attempt in range(max_retries):
        try:
            await client.edit_original_response(token, content)
            return
        except DiscordRateLimitError as e:
            if attempt == max_retries - 1:
                raise
            # Extract retry_after from error message
            retry_after = extract_retry_after(str(e))
            await asyncio.sleep(retry_after)
```

## Common Issues

### Issue: "Interaction token has expired"
**Solution**: Interaction tokens are valid for 15 minutes. Respond to interactions within this window.

### Issue: "Authentication failed"
**Solution**:
1. Verify bot token is correct
2. Ensure token doesn't have "Bot " prefix when passed to DiscordClient
3. Check bot permissions in Discord Developer Portal

### Issue: "Rate limit exceeded"
**Solution**:
1. Implement rate limiting in your application
2. Handle 429 responses with exponential backoff
3. Use `retry_after` value from error message

## Testing

Run the demo script:
```bash
python3 examples/discord_client_demo.py
```

Test cases:
- ✅ Bot token validation
- ✅ Edit interaction response
- ✅ Message truncation
- ✅ Error handling
- ✅ Initialization validation

## Architecture

```
discord/
├── __init__.py          # Public exports
├── client.py            # Core Discord API client (Hour 5) ✅
├── adapter.py           # CommunicationOS adapter (Hour 8)
├── handler.py           # Interaction handler (Hour 7)
└── README.md            # This file
```

## Links

- [Discord Developer Portal](https://discord.com/developers/applications)
- [Discord API Documentation](https://discord.com/developers/docs)
- [Interactions Guide](https://discord.com/developers/docs/interactions/receiving-and-responding)
- [Bot Setup Guide](https://discord.com/developers/docs/getting-started)

## Support

For issues or questions:
1. Check [Discord API Documentation](https://discord.com/developers/docs)
2. Review error messages for specific guidance
3. Run demo script to verify setup
4. Check bot permissions in Discord Developer Portal
