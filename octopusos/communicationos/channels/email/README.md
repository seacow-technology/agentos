# Email Channel for AgentOS CommunicationOS

## Overview

The Email Channel provides asynchronous communication capabilities through standard email protocols. It supports multiple providers (Gmail OAuth, Outlook OAuth, Generic SMTP/IMAP) and maintains conversation context using RFC 5322 email threading headers.

## Quick Start

### 1. Choose Your Provider

| Provider | Security | Setup Complexity | Best For |
|----------|----------|------------------|----------|
| **Gmail (OAuth)** | ⭐⭐⭐⭐⭐ | Medium | Gmail and Google Workspace accounts |
| **Outlook (OAuth)** | ⭐⭐⭐⭐⭐ | Medium | Outlook.com and Microsoft 365 accounts |
| **SMTP/IMAP** | ⭐⭐⭐ | Low | Any other email provider |

### 2. Configure Your Channel

1. Navigate to AgentOS Communication Channels
2. Click "Add Channel" → "Email"
3. Select your provider
4. Fill in the required credentials
5. Test connection

### 3. Start Receiving Messages

The Email Channel operates in polling mode:
- Default interval: 60 seconds
- Minimum interval: 30 seconds (to avoid rate limits)
- Maximum interval: 3600 seconds (1 hour)

## Features

### Core Capabilities

- ✅ **Inbound Text**: Receive plain text and HTML emails
- ✅ **Outbound Text**: Send plain text and HTML emails
- ✅ **Thread Tracking**: Maintain conversation context across email threads
- 🚧 **Attachments**: Support for email attachments (planned)
- ✅ **HTML Formatting**: Rich text email support

### Email Threading

The channel automatically tracks email threads using standard RFC 5322 headers:
- **Message-ID**: Unique identifier for each email
- **In-Reply-To**: ID of the email being replied to
- **References**: Full thread history

**Example:**
```
User sends: "Question about pricing"
  → Creates new thread: conversation_key = msg-001@example.com

Agent replies: "We have three tiers..."
  → Same thread: conversation_key = msg-001@example.com

User follows up: "Tell me more..."
  → Same thread: conversation_key = msg-001@example.com

User sends NEW email: "Another topic"
  → New thread: conversation_key = msg-999@example.com
```

### Multi-User Support

The channel supports multiple parallel conversations with the same user:
- Each email thread has a unique `conversation_key`
- Multiple threads can be active simultaneously
- Full context isolation between threads

## Configuration

### Gmail (OAuth)

**Required:**
- Email address
- OAuth Client ID (from Google Cloud Console)
- OAuth Client Secret (from Google Cloud Console)
- OAuth Refresh Token (generated during setup)

**Setup Steps:**
1. Create Google Cloud project
2. Enable Gmail API
3. Configure OAuth consent screen
4. Create OAuth 2.0 credentials
5. Generate refresh token

**Scopes Required:**
- `https://www.googleapis.com/auth/gmail.readonly`
- `https://www.googleapis.com/auth/gmail.send`

### Outlook (OAuth)

**Required:**
- Email address
- OAuth Client ID (Application ID from Azure)
- OAuth Client Secret (from Azure)
- OAuth Refresh Token (generated during setup)

**Setup Steps:**
1. Register app in Azure Portal
2. Configure API permissions (Mail.Read, Mail.Send)
3. Create client secret
4. Generate refresh token

### Generic SMTP/IMAP

**Required:**
- Email address
- SMTP server and port
- SMTP username and password
- IMAP server and port
- IMAP username and password

**Common Providers:**

| Provider | SMTP Server | SMTP Port | IMAP Server | IMAP Port |
|----------|-------------|-----------|-------------|-----------|
| Gmail | smtp.gmail.com | 587 (TLS) | imap.gmail.com | 993 (SSL) |
| Outlook | smtp-mail.outlook.com | 587 (TLS) | outlook.office365.com | 993 (SSL) |
| Yahoo | smtp.mail.yahoo.com | 587 (TLS) | imap.mail.yahoo.com | 993 (SSL) |

**Note:** Many providers require app-specific passwords for SMTP/IMAP access.

## Architecture

### Components

```
Email Channel
├── manifest.json              # Channel configuration and metadata
├── adapter.py                 # EmailAdapter implementation (Task #19)
├── KEY_MAPPING_RULES.md       # Thread detection documentation
└── README.md                  # This file

Email Providers
├── providers/email/
    ├── __init__.py            # IEmailProvider protocol
    ├── gmail.py               # GmailProvider (Task #20)
    ├── outlook.py             # OutlookProvider (Task #20)
    └── smtp_imap.py           # SmtpImapProvider (Task #20)
```

### Data Flow

```
Inbound Message Flow:
1. Provider polls email server (IMAP/API)
2. Provider converts to EmailEnvelope
3. Adapter converts to InboundMessage
4. Message routed to appropriate conversation

Outbound Message Flow:
1. Adapter receives OutboundMessage
2. Adapter converts to email format
3. Provider sends via SMTP/API
4. Provider adds threading headers
```

### Session Scope

**session_scope:** `"user_conversation"`

| Key | Source | Example |
|-----|--------|---------|
| `user_key` | Sender email (From header) | `john@example.com` |
| `conversation_key` | Thread root Message-ID | `msg-001@example.com` |
| `message_id` | RFC 5322 Message-ID | `email_msg-001@example.com` |

## Security

### OAuth Providers (Recommended)

- ✅ No password storage
- ✅ Fine-grained permissions
- ✅ Revocable access tokens
- ✅ Automatic token refresh

### SMTP/IMAP

- ⚠️ Password storage required
- ✅ Encrypted at rest
- 💡 Use app-specific passwords when possible
- 💡 Enable 2FA on email account

### Privacy Features

- ✅ Local credential storage
- ✅ Encrypted secrets
- ✅ Polling mode (no webhooks)
- ✅ Thread isolation
- ✅ User-conversation session scope

## Testing

### Manual Testing

1. **New Thread Test**
   - Send email to configured address
   - Verify message appears in AgentOS
   - Check conversation_key is created

2. **Reply Test**
   - Reply from AgentOS
   - Verify reply has correct threading headers
   - Verify conversation_key matches original

3. **Thread Isolation Test**
   - Send NEW email (not reply)
   - Verify different conversation_key
   - Verify context isolation

4. **Multi-Message Thread Test**
   - Reply to agent's reply
   - Continue conversation
   - Verify all messages share conversation_key

### Automated Tests

```bash
# Unit tests
pytest tests/unit/communicationos/channels/email/

# Integration tests
pytest tests/integration/communicationos/channels/email/

# E2E tests
pytest tests/e2e/communicationos/channels/email/
```

## Troubleshooting

### Common Issues

**Problem: Messages not appearing in AgentOS**
- Check poll interval setting
- Verify credentials are valid
- Check IMAP folder name (default: INBOX)
- Review provider API quotas

**Problem: Replies not maintaining thread**
- Verify In-Reply-To header is set
- Verify References header is set
- Check email client threading support

**Problem: OAuth token expired**
- Regenerate refresh token
- Check OAuth scope permissions
- Verify client secret hasn't changed

**Problem: SMTP authentication failed**
- Verify username/password
- Check if app-specific password is required
- Verify SMTP port and TLS settings

## Limitations

- **Polling Delay**: 30-60 second delay typical (not real-time)
- **Rate Limits**: Provider-specific (Gmail: 250/day, Outlook: varies)
- **Attachment Size**: Limited by provider (Gmail: 25MB, Outlook: 150MB)
- **Thread Detection**: Depends on proper RFC 5322 headers

## Roadmap

### Phase A (Current)
- [x] Manifest and provider architecture
- [ ] Email adapter implementation
- [ ] Gmail provider implementation
- [ ] Outlook provider implementation
- [ ] SMTP/IMAP provider implementation

### Phase B (Future)
- [ ] Attachment support (send/receive)
- [ ] HTML template rendering
- [ ] Email signature support
- [ ] Auto-reply detection
- [ ] IMAP IDLE support (real-time notifications)

## References

### Documentation
- [manifest.json](./manifest.json) - Channel configuration
- [KEY_MAPPING_RULES.md](./KEY_MAPPING_RULES.md) - Thread detection algorithm
- [Provider Protocol](../../providers/email/__init__.py) - IEmailProvider interface

### Standards
- [RFC 5322: Internet Message Format](https://datatracker.ietf.org/doc/html/rfc5322)
- [RFC 2822: Message-ID](https://datatracker.ietf.org/doc/html/rfc2822#section-3.6.4)
- [RFC 5256: Email Threading](https://datatracker.ietf.org/doc/html/rfc5256)

### Provider APIs
- [Gmail API](https://developers.google.com/gmail/api)
- [Microsoft Graph Mail API](https://learn.microsoft.com/en-us/graph/api/resources/message)
- [Python smtplib](https://docs.python.org/3/library/smtplib.html)
- [Python imaplib](https://docs.python.org/3/library/imaplib.html)

## Support

For issues or questions:
1. Check this README and KEY_MAPPING_RULES.md
2. Review manifest.json for configuration details
3. Check logs for error messages
4. Consult provider-specific documentation

---

**Last Updated:** 2026-02-01
**Version:** 1.0.0
**Status:** Implementation in progress (Phase A)
