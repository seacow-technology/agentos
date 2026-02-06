# Channel Adapters

This directory contains channel adapter implementations for CommunicationOS.

## WhatsApp Twilio Adapter

The WhatsApp Twilio adapter enables WhatsApp messaging through Twilio's Business API.

### Features

- **Webhook Parsing**: Converts Twilio webhook data to unified InboundMessage format
- **Message Sending**: Sends OutboundMessage via Twilio API
- **Signature Verification**: Validates webhook authenticity using HMAC-SHA256
- **Media Support**: Handles images, audio, video, and document attachments
- **Security**: Signature verification required for all webhooks

### Configuration

Required fields:
- `account_sid`: Twilio Account SID (starts with AC)
- `auth_token`: Twilio Auth Token (secret)
- `phone_number`: WhatsApp-enabled phone number in E.164 format (+1234567890)
- `messaging_service_sid`: Optional Messaging Service SID

### Usage

```python
from agentos.communicationos.channels import WhatsAppTwilioAdapter

# Create adapter
adapter = WhatsAppTwilioAdapter(
    channel_id="whatsapp_001",
    account_sid="ACxxxxx...",
    auth_token="your_auth_token",
    phone_number="+14155238886"
)

# Parse webhook
webhook_data = {
    "MessageSid": "SM123",
    "From": "whatsapp:+1234567890",
    "Body": "Hello"
}
inbound_message = adapter.parse_event(webhook_data)

# Send message
outbound_message = OutboundMessage(
    channel_id="whatsapp_001",
    user_key="+1234567890",
    conversation_key="+1234567890",
    text="Hello from AgentOS!"
)
success = adapter.send_message(outbound_message)
```

### Webhook Endpoint

The webhook endpoint is automatically registered at:
```
POST /api/channels/whatsapp_twilio/webhook
```

Configure this URL in your Twilio Console under WhatsApp settings.

### Security

The adapter implements Twilio's signature verification:

1. Webhook requests include `X-Twilio-Signature` header
2. Signature is computed using HMAC-SHA256 of URL + sorted parameters
3. Signature must match or webhook is rejected with 400 Bad Request

### Message Flow

#### Inbound Messages

1. Twilio sends webhook POST request
2. Signature verification
3. Parse to InboundMessage
4. Process through MessageBus middleware (dedupe, rate limit, audit)
5. Check for commands (/session, /help)
6. If command: Process and send response
7. If not command: Forward to AgentOS chat

#### Outbound Messages

1. Create OutboundMessage
2. Process through MessageBus middleware
3. Send via Twilio API
4. Return success/failure status

### Testing

Run integration tests:

```bash
pytest tests/integration/communicationos/test_whatsapp_twilio.py -v
```

### Dependencies

```bash
pip install twilio
```

### Limitations

- Only supports 1-on-1 conversations (no group support in this version)
- One media attachment per message (Twilio WhatsApp limitation)
- Rate limits apply per Twilio account tier

### References

- [Twilio WhatsApp API Docs](https://www.twilio.com/docs/whatsapp)
- [Webhook Signature Verification](https://www.twilio.com/docs/usage/security#validating-requests)
