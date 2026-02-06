# SMS Channel (v1: Send-only)

Send SMS notifications via Twilio or other SMS providers.

## Overview

The SMS Channel enables one-way SMS notification delivery from AgentOS to mobile phones. Version 1 is **send-only** - it sends SMS messages but does not process replies. This is ideal for alerts, notifications, status updates, and one-way communications.

## Features

- **Send-only**: Outbound SMS delivery (no inbound processing in v1)
- **Provider-agnostic**: Supports Twilio with extensible provider interface
- **E.164 compliance**: International phone number format support
- **Segment tracking**: Automatic SMS concatenation for long messages
- **Cost tracking**: Optional cost reporting from provider
- **No webhook required**: Simplified setup (no public URL needed)

## Version 1 Limitations

- **No inbound messages**: Recipient replies are not processed
- **No conversation state**: Each send is independent
- **No threading**: No multi-turn dialogues
- **Send-only API**: Only `send_message()` operation

These limitations will be addressed in v2 with inbound webhook support.

## Architecture

```
AgentOS Application
        ↓
    OutboundMessage
        ↓
    SmsAdapter (Task #23)
        ↓
    ISmsProvider (protocol)
        ↓
    TwilioSmsProvider (Task #23)
        ↓
    Twilio SMS API
        ↓
    Recipient Phone
```

## Configuration

Required fields:
- `twilio_account_sid`: Twilio Account SID (starts with AC)
- `twilio_auth_token`: Twilio Auth Token (secret)
- `twilio_from_number`: Sender phone number (E.164 format)
- `sms_max_len`: Max message length (default 480 chars)
- `test_to_number`: Test recipient (optional)

See `manifest.json` for full configuration schema.

## Phone Number Format

All phone numbers must use **E.164 international format**:

```
Format: +{CountryCode}{Number}
Examples:
  US: +15551234567
  UK: +447911123456
  China: +8613800138000
```

See `KEY_MAPPING.md` for detailed format rules.

## Usage (Task #23)

```python
from agentos.communicationos.channels.sms import SmsAdapter
from agentos.communicationos.models import OutboundMessage

# Create adapter
adapter = SmsAdapter(
    channel_id="sms_001",
    account_sid="AC...",
    auth_token="...",
    from_number="+15551234567"
)

# Send SMS
message = OutboundMessage(
    channel_id="sms_001",
    user_key="+15559876543",
    conversation_key="+15559876543",  # Same as user_key in v1
    text="Hello from AgentOS!",
    metadata={}
)

result = adapter.send_message(message)
if result.success:
    print(f"SMS sent: {result.message_sid}")
else:
    print(f"Failed: {result.error_message}")
```

## Provider Interface

The SMS channel uses a provider-agnostic interface:

```python
from agentos.communicationos.providers.sms import ISmsProvider, SendResult

class TwilioSmsProvider(ISmsProvider):
    def send_sms(
        self,
        to_number: str,
        message_text: str,
        from_number: Optional[str] = None,
        max_segments: int = 3
    ) -> SendResult:
        # Send via Twilio API
        ...

    def validate_config(self) -> tuple[bool, Optional[str]]:
        # Validate credentials
        ...

    def test_connection(
        self,
        test_to_number: Optional[str] = None
    ) -> tuple[bool, Optional[str]]:
        # Test API access
        ...
```

See `agentos/communicationos/providers/sms/__init__.py` for full protocol definition.

## Setup Wizard

The manifest includes a 6-step setup wizard:

1. **Create Twilio Account**: Sign up and verify
2. **Get Credentials**: Copy Account SID and Auth Token
3. **Get Phone Number**: Buy SMS-capable number
4. **Verify Test Recipient**: For trial accounts
5. **Configure in AgentOS**: Enter credentials
6. **Test Connection**: Send test SMS

See `manifest.json` for detailed setup instructions.

## Cost Considerations

- Each SMS segment incurs Twilio charges
- Standard SMS: 160 chars = 1 segment
- Extended SMS: 161-480 chars = 3 segments (default)
- Concatenated SMS: 481-1600 chars = up to 10 segments
- International rates vary by country
- Trial accounts: Free credits for testing

Configure `sms_max_len` to control cost.

## Security

- **Credentials encrypted**: Account SID and Auth Token stored securely
- **No webhook**: No public endpoint (reduced attack surface)
- **Rate limiting**: Configurable per-channel rate limits
- **No inbound processing**: No risk of malicious inbound messages in v1

## Key Mapping

See `KEY_MAPPING.md` for detailed rules:

- **User Key**: `+15551234567` (E.164 phone number)
- **Conversation Key**: Same as user_key (v1 send-only)
- **Message ID**: Provider's message SID (e.g., Twilio SID)

## Testing

Integration tests (Task #24):

```bash
pytest tests/integration/communicationos/channels/test_sms_channel.py -v
```

Unit tests for provider:

```bash
pytest tests/unit/communicationos/providers/test_twilio_sms.py -v
```

## Dependencies

```bash
pip install twilio  # For Twilio provider
```

## Comparison: SMS vs Email (Both Send-only v1)

| Feature | SMS | Email |
|---------|-----|-------|
| Delivery Speed | Instant (seconds) | Fast (minutes) |
| Character Limit | 480 (default) | 64KB (default) |
| Cost per Message | $0.0075-$0.10/segment | Free (SMTP) |
| Read Rate | 90%+ (high) | 20-30% (medium) |
| User Key Format | `+15551234567` | `user@domain.com` |
| Best Use Case | Urgent alerts | Detailed reports |

## Future: v2 Roadmap

Planned features for v2:

- **Inbound SMS processing**: Webhook support for replies
- **Conversation tracking**: Multi-turn dialogue state
- **Two-way commands**: Process commands from recipients
- **Auto-responses**: Configurable reply templates
- **Keywords**: Trigger actions based on keywords
- **Opt-out handling**: Automatic STOP/UNSUBSCRIBE

## Files

- `manifest.json`: Channel configuration and setup wizard
- `KEY_MAPPING.md`: Phone number and message ID mapping rules
- `__init__.py`: Package exports
- `README.md`: This file
- `adapter.py`: (Task #23) Message sending adapter
- `provider.py`: (Task #23) Twilio provider implementation

## Related Documentation

- [CommunicationOS Overview](../../README.md)
- [Channel Manifest Specification](../../manifest.py)
- [SMS Provider Protocol](../../providers/sms/__init__.py)
- [Unified Message Models](../../models.py)

## References

- [Twilio SMS API Docs](https://www.twilio.com/docs/sms)
- [E.164 Phone Number Format](https://www.itu.int/rec/T-REC-E.164/)
- [SMS Concatenation](https://en.wikipedia.org/wiki/Concatenated_SMS)

## Support

For issues or questions:
- Check Task #24 acceptance report
- Review manifest.json setup steps
- See Twilio documentation for provider-specific issues
