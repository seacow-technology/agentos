# SMS Channel Key Mapping Rules

This document defines how SMS channel maps phone numbers and message identifiers to CommunicationOS unified keys.

## Overview

SMS v1 is a **send-only channel**. It does not process inbound messages or track conversation state. Key mapping is simplified compared to bidirectional channels like Telegram or Slack.

## Key Mapping Schema

### User Key

**Format**: `{phone_number}` (E.164 format)

**Example**: `+15551234567`

**Mapping Rule**:
```python
user_key = to_number  # Recipient phone number in E.164 format
```

**Notes**:
- User key is the recipient's phone number
- Must be in E.164 format: `+{country_code}{national_number}`
- No prefix like `sms:` or `tel:` - just the raw E.164 number
- Leading `+` is required
- No spaces, dashes, or parentheses

**Examples**:
- US: `+15551234567`
- UK: `+447911123456`
- China: `+8613800138000`

### Conversation Key

**Format**: `N/A` (not used in v1)

**Mapping Rule**:
```python
conversation_key = user_key  # Same as user_key for send-only
```

**Notes**:
- v1 is send-only, so no conversation tracking
- For consistency with CommunicationOS data model, conversation_key = user_key
- No threads, no multi-participant conversations
- Each send is independent, no state between sends

### Message ID

**Format**: `{provider_message_sid}`

**Example**: `SM1234567890abcdef1234567890abcdef`

**Mapping Rule**:
```python
message_id = send_result.message_sid  # Provider's message SID
```

**Notes**:
- Message ID is the provider's unique identifier (e.g., Twilio SID)
- Format depends on provider:
  - Twilio: `SM{32 hex chars}` (e.g., `SM1234567890abcdef1234567890abcdef`)
  - AWS SNS: UUID format (e.g., `a1b2c3d4-e5f6-7890-abcd-ef1234567890`)
- Used for audit trail and debugging
- Not used for threading or conversation tracking in v1

### Channel ID

**Format**: `sms_{instance_suffix}`

**Example**: `sms_001`, `sms_prod`, `sms_notifications`

**Mapping Rule**:
```python
channel_id = f"sms_{suffix}"  # Configured per channel instance
```

**Notes**:
- Channel ID identifies the SMS channel instance in AgentOS
- Multiple SMS channel instances can coexist (e.g., different Twilio accounts)
- Suffix is user-defined during channel setup
- Used to route outbound messages to correct provider credentials

## Comparison with Other Channels

| Channel | User Key Format | Conversation Key Format | Supports Inbound? |
|---------|----------------|------------------------|-------------------|
| **SMS (v1)** | `+15551234567` | `+15551234567` (same as user) | No (send-only) |
| Telegram | `{user_id}` | `{chat_id}` | Yes |
| Slack | `{user_id}` | `{channel_id}:{thread_ts}` | Yes |
| WhatsApp | `+15551234567` | `+15551234567` | Yes |
| Email (v1) | `user@domain.com` | `user@domain.com` (send-only) | No (send-only) |

## E.164 Phone Number Format

**Standard**: ITU-T E.164

**Structure**: `+{CC}{NDC}{SN}`
- `+`: Plus sign (required)
- `CC`: Country Code (1-3 digits)
- `NDC`: National Destination Code (area code)
- `SN`: Subscriber Number

**Length**: 1-15 digits (excluding `+`)

**Validation Regex**:
```regex
^\+[1-9]\d{1,14}$
```

**Examples**:
- United States: `+15551234567` (CC=1, NDC=555, SN=1234567)
- United Kingdom: `+447911123456` (CC=44, NDC=7911, SN=123456)
- China: `+8613800138000` (CC=86, NDC=138, SN=00138000)
- Germany: `+4915123456789` (CC=49, NDC=151, SN=23456789)

**Invalid Examples**:
- Missing `+`: `15551234567` ❌
- Contains spaces: `+1 555 123 4567` ❌
- Contains dashes: `+1-555-123-4567` ❌
- Too short: `+1` ❌
- Too long: `+12345678901234567` ❌
- Starts with 0: `+01551234567` ❌

## Future v2 Enhancements

When SMS v2 adds inbound support, key mapping will be extended:

### Conversation Key (v2)
```python
# v2: Separate conversation per unique sender-recipient pair
conversation_key = f"{from_number}:{to_number}"
```

**Example**: `+15551234567:+15559876543`

This enables:
- Tracking conversation state
- Multi-turn dialogues
- Reply context
- Conversation-scoped rate limiting

### Message ID (v2)
```python
# v2: Include direction in message ID
message_id = f"{direction}:{provider_sid}"
```

**Examples**:
- Outbound: `out:SM1234567890abcdef1234567890abcdef`
- Inbound: `in:SM9876543210fedcba9876543210fedcba`

## Provider-Specific Notes

### Twilio
- Message SID format: `SM{32 hex chars}`
- From number must be Twilio-provisioned
- To number must be E.164 format
- Trial accounts: To number must be verified in Twilio Console

### AWS SNS (Future)
- Message ID format: UUID (e.g., `a1b2c3d4-e5f6-7890-abcd-ef1234567890`)
- From number: Sender ID (string, not E.164)
- To number must be E.164 format
- Requires origination number or short code

### Other Providers
- Implement ISmsProvider protocol
- Return message ID in SendResult.message_sid
- Ensure phone numbers are validated to E.164 format

## Testing

Validate key mapping with these test cases:

```python
# Valid user keys
assert validate_e164("+15551234567") == True
assert validate_e164("+447911123456") == True
assert validate_e164("+8613800138000") == True

# Invalid user keys
assert validate_e164("15551234567") == False  # Missing +
assert validate_e164("+1 555 123 4567") == False  # Contains spaces
assert validate_e164("+1-555-123-4567") == False  # Contains dashes
assert validate_e164("+01551234567") == False  # Starts with 0

# v1: conversation_key equals user_key
user_key = "+15551234567"
conversation_key = user_key
assert conversation_key == user_key

# message_id is provider SID
message_id = "SM1234567890abcdef1234567890abcdef"
assert message_id.startswith("SM")
assert len(message_id) == 34
```

## References

- [E.164 International Numbering Plan](https://www.itu.int/rec/T-REC-E.164/)
- [Twilio Phone Number Formatting](https://www.twilio.com/docs/glossary/what-e164)
- [CommunicationOS Unified Message Models](../../../models.py)
- [SMS Provider Protocol](../../providers/sms/__init__.py)
