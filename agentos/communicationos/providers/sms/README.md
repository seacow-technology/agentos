# SMS Provider Protocol

This package defines the provider-agnostic interface for SMS sending.

## Overview

The SMS provider protocol (`ISmsProvider`) enables AgentOS to work with multiple SMS providers without changing adapter code. This follows the dependency inversion principle - the high-level SMS adapter depends on the abstract protocol, not concrete provider implementations.

## Architecture

```
┌─────────────────────┐
│   SmsAdapter        │  (High-level logic)
└──────────┬──────────┘
           │ depends on
           ↓
┌─────────────────────┐
│   ISmsProvider      │  (Protocol/Interface)
└──────────┬──────────┘
           │ implemented by
    ┌──────┴──────┬──────────┬─────────┐
    ↓             ↓          ↓         ↓
┌─────────┐  ┌─────────┐  ┌─────┐  ┌─────────┐
│ Twilio  │  │ AWS SNS │  │ ... │  │ Custom  │
└─────────┘  └─────────┘  └─────┘  └─────────┘
```

## Protocol Definition

```python
from typing import Protocol, Optional
from dataclasses import dataclass

@dataclass
class SendResult:
    """Result of SMS send operation."""
    success: bool
    message_sid: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    timestamp: Optional[int] = None
    segments_count: int = 1
    cost: Optional[float] = None

class ISmsProvider(Protocol):
    """SMS provider interface."""

    def send_sms(
        self,
        to_number: str,
        message_text: str,
        from_number: Optional[str] = None,
        max_segments: int = 3,
    ) -> SendResult:
        """Send SMS message."""
        ...

    def validate_config(self) -> tuple[bool, Optional[str]]:
        """Validate provider configuration."""
        ...

    def test_connection(
        self,
        test_to_number: Optional[str] = None
    ) -> tuple[bool, Optional[str]]:
        """Test API connection."""
        ...
```

## Implementing a Provider

### Step 1: Create Provider Class

```python
# agentos/communicationos/providers/sms/twilio.py

from agentos.communicationos.providers.sms import ISmsProvider, SendResult

class TwilioSmsProvider:
    """Twilio SMS provider implementation."""

    def __init__(
        self,
        account_sid: str,
        auth_token: str,
        from_number: str
    ):
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.from_number = from_number

    def send_sms(
        self,
        to_number: str,
        message_text: str,
        from_number: Optional[str] = None,
        max_segments: int = 3,
    ) -> SendResult:
        """Send SMS via Twilio API."""
        # Validate inputs
        if not to_number or not message_text:
            return SendResult(
                success=False,
                error_message="to_number and message_text are required"
            )

        # Truncate message to max_segments
        max_len = max_segments * 160
        if len(message_text) > max_len:
            message_text = message_text[:max_len]

        # Use default from_number if not provided
        sender = from_number or self.from_number

        # Call Twilio API
        try:
            from twilio.rest import Client
            client = Client(self.account_sid, self.auth_token)

            message = client.messages.create(
                to=to_number,
                from_=sender,
                body=message_text
            )

            return SendResult(
                success=True,
                message_sid=message.sid,
                segments_count=message.num_segments,
                cost=float(message.price) if message.price else None
            )

        except Exception as e:
            return SendResult(
                success=False,
                error_message=str(e)
            )

    def validate_config(self) -> tuple[bool, Optional[str]]:
        """Validate Twilio credentials format."""
        # Check Account SID format
        if not self.account_sid.startswith("AC"):
            return False, "Account SID must start with 'AC'"
        if len(self.account_sid) != 34:
            return False, "Account SID must be 34 characters"

        # Check Auth Token format
        if len(self.auth_token) != 32:
            return False, "Auth Token must be 32 characters"

        # Check from_number E.164 format
        import re
        if not re.match(r'^\+[1-9]\d{1,14}$', self.from_number):
            return False, "from_number must be in E.164 format"

        return True, None

    def test_connection(
        self,
        test_to_number: Optional[str] = None
    ) -> tuple[bool, Optional[str]]:
        """Test Twilio API access."""
        try:
            from twilio.rest import Client
            client = Client(self.account_sid, self.auth_token)

            # If test number provided, send real test SMS
            if test_to_number:
                message = client.messages.create(
                    to=test_to_number,
                    from_=self.from_number,
                    body="AgentOS SMS Channel Test"
                )
                return True, None

            # Otherwise, just validate credentials via API
            account = client.api.accounts(self.account_sid).fetch()
            if account.status == "active":
                return True, None
            else:
                return False, f"Account status: {account.status}"

        except Exception as e:
            return False, str(e)
```

### Step 2: Register Provider

```python
# agentos/communicationos/providers/sms/__init__.py

from agentos.communicationos.providers.sms.twilio import TwilioSmsProvider

__all__ = [
    "ISmsProvider",
    "SendResult",
    "TwilioSmsProvider",  # Export concrete provider
]
```

### Step 3: Use in Adapter

```python
# agentos/communicationos/channels/sms/adapter.py

from agentos.communicationos.providers.sms import ISmsProvider, TwilioSmsProvider

class SmsAdapter:
    def __init__(self, provider: ISmsProvider):
        self.provider = provider

    def send_message(self, message: OutboundMessage) -> bool:
        result = self.provider.send_sms(
            to_number=message.user_key,
            message_text=message.text
        )
        return result.success

# Usage
provider = TwilioSmsProvider(
    account_sid="AC...",
    auth_token="...",
    from_number="+15551234567"
)
adapter = SmsAdapter(provider=provider)
```

## Provider Comparison

| Feature | Twilio | AWS SNS | Nexmo/Vonage |
|---------|--------|---------|--------------|
| **API Type** | REST | AWS SDK | REST |
| **Auth** | Basic Auth | IAM | API Key/Secret |
| **Message SID** | SM{32 hex} | UUID | UUID |
| **Segment Tracking** | Yes (num_segments) | No | Yes |
| **Cost Reporting** | Yes (price field) | Via CloudWatch | Yes |
| **Trial** | Free credits | Pay-as-you-go | Free credits |
| **Global Coverage** | 180+ countries | 200+ countries | 200+ countries |

## Testing Providers

```python
import pytest
from agentos.communicationos.providers.sms import ISmsProvider, SendResult

def test_provider_protocol(provider: ISmsProvider):
    """Test that provider implements ISmsProvider protocol."""

    # Test config validation
    is_valid, error = provider.validate_config()
    assert is_valid, f"Config validation failed: {error}"

    # Test connection (no SMS sent)
    success, error = provider.test_connection()
    assert success, f"Connection test failed: {error}"

    # Test SMS sending
    result = provider.send_sms(
        to_number="+15551234567",  # Mock number
        message_text="Test message"
    )
    assert isinstance(result, SendResult)
    assert result.success or result.error_message is not None

# Test Twilio provider
def test_twilio_provider():
    provider = TwilioSmsProvider(
        account_sid="AC" + "0" * 32,
        auth_token="0" * 32,
        from_number="+15551234567"
    )
    test_provider_protocol(provider)
```

## Error Handling

Providers should handle errors gracefully:

```python
def send_sms(self, to_number: str, message_text: str, ...) -> SendResult:
    try:
        # Validate inputs
        if not self._validate_e164(to_number):
            return SendResult(
                success=False,
                error_code="INVALID_PHONE_NUMBER",
                error_message="Phone number must be in E.164 format"
            )

        # Call provider API
        ...

    except AuthenticationError as e:
        return SendResult(
            success=False,
            error_code="AUTH_FAILED",
            error_message="Invalid credentials"
        )

    except RateLimitError as e:
        return SendResult(
            success=False,
            error_code="RATE_LIMIT_EXCEEDED",
            error_message=f"Rate limit: {e.retry_after}s"
        )

    except Exception as e:
        return SendResult(
            success=False,
            error_code="UNKNOWN_ERROR",
            error_message=str(e)
        )
```

## Best Practices

1. **Validate Early**: Check inputs before API call
2. **Truncate Messages**: Respect max_segments limit
3. **Return Details**: Include message_sid, segments_count, cost
4. **Handle Errors**: Return structured error info
5. **Log Appropriately**: Debug logs for troubleshooting
6. **Timeout**: Set reasonable API timeout (10-30s)
7. **Retry Logic**: Optional retry for transient failures

## Future Providers

Planned implementations:

- **AWS SNS**: For AWS-native deployments
- **Vonage/Nexmo**: Alternative to Twilio
- **Plivo**: Another alternative
- **MessageBird**: European focus
- **Africa's Talking**: African markets
- **Custom SMPP**: Direct carrier integration

## References

- [Twilio SMS API](https://www.twilio.com/docs/sms/api)
- [AWS SNS SMS](https://docs.aws.amazon.com/sns/latest/dg/sms_publish-to-phone.html)
- [Vonage SMS API](https://developer.vonage.com/messaging/sms/overview)
- [E.164 Phone Format](https://www.itu.int/rec/T-REC-E.164/)
- [Python Protocols (PEP 544)](https://www.python.org/dev/peps/pep-0544/)
