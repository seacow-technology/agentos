# Gmail Provider Quick Reference

Quick reference for developers using the Gmail Provider.

## Installation

```bash
pip install requests  # Only dependency required
```

## Basic Setup

### 1. Get OAuth Credentials

```python
from agentos.communicationos.providers.email import generate_auth_url

# Generate authorization URL
auth_url = generate_auth_url(
    client_id="YOUR_CLIENT_ID.apps.googleusercontent.com",
    redirect_uri="http://localhost:8080/oauth2callback"
)

print(f"Visit: {auth_url}")
# User visits URL, authorizes, gets redirected with code parameter
```

### 2. Exchange Code for Tokens

```python
from agentos.communicationos.providers.email import exchange_code_for_tokens

tokens = exchange_code_for_tokens(
    client_id="YOUR_CLIENT_ID",
    client_secret="YOUR_CLIENT_SECRET",
    code="AUTHORIZATION_CODE_FROM_REDIRECT"
)

refresh_token = tokens["refresh_token"]  # Store this securely!
```

### 3. Initialize Provider

```python
from agentos.communicationos.providers.email import GmailProvider

provider = GmailProvider(
    client_id="YOUR_CLIENT_ID",
    client_secret="YOUR_CLIENT_SECRET",
    refresh_token="YOUR_REFRESH_TOKEN",
    email_address="your_email@gmail.com"
)
```

## Common Operations

### Validate Credentials

```python
result = provider.validate_credentials()

if result.valid:
    print("✅ Credentials valid")
else:
    print(f"❌ Error: {result.error_message}")
```

### Fetch Unread Messages

```python
# Fetch last 10 unread messages
messages = provider.fetch_messages(limit=10)

for msg in messages:
    print(f"From: {msg.from_address}")
    print(f"Subject: {msg.subject}")
    print(f"Body: {msg.text_body[:100]}...")
    print(f"Thread root: {msg.compute_thread_root()}")
    print("---")
```

### Fetch Messages Since Date

```python
from datetime import datetime, timezone, timedelta

since = datetime.now(timezone.utc) - timedelta(hours=24)
messages = provider.fetch_messages(since=since, limit=50)
```

### Send New Message

```python
result = provider.send_message(
    to_addresses=["recipient@example.com"],
    subject="Hello from AgentOS",
    text_body="This is a plain text message."
)

if result.success:
    print(f"✅ Sent! Message-ID: {result.message_id}")
else:
    print(f"❌ Failed: {result.error_message}")
```

### Send HTML Message

```python
result = provider.send_message(
    to_addresses=["recipient@example.com"],
    subject="HTML Message",
    text_body="Plain text fallback",
    html_body="<h1>Hello</h1><p>This is <strong>HTML</strong>!</p>"
)
```

### Send Reply (with Threading)

```python
# Get reply headers from original message
original_msg = messages[0]
reply_headers = original_msg.get_reply_headers()

# Send reply
result = provider.send_message(
    to_addresses=[original_msg.from_address],
    subject=f"Re: {original_msg.subject}",
    text_body="Thank you for your message!",
    in_reply_to=reply_headers["In-Reply-To"],
    references=reply_headers["References"]
)
```

### Send with CC

```python
result = provider.send_message(
    to_addresses=["primary@example.com"],
    cc_addresses=["cc1@example.com", "cc2@example.com"],
    subject="Meeting Notes",
    text_body="Here are the meeting notes..."
)
```

### Mark as Read

```python
msg = messages[0]
success = provider.mark_as_read(msg.provider_message_id)

if success:
    print("✅ Marked as read")
```

## Email Threading

### Understanding Thread Detection

```python
# Thread detection algorithm:
# 1. If References exists → use first Message-ID (thread root)
# 2. Else if In-Reply-To exists → use that (parent)
# 3. Else → current message_id (new thread)

thread_root = msg.compute_thread_root()
# Returns: "msg-001@example.com" (without angle brackets)
```

### Getting Reply Headers

```python
reply_headers = msg.get_reply_headers()
# Returns: {
#   "In-Reply-To": "<msg-001@example.com>",
#   "References": "<msg-001@example.com> <msg-002@example.com>"
# }
```

## Error Handling

### Credential Errors

```python
result = provider.validate_credentials()

if not result.valid:
    if result.error_code == "token_refresh_failed":
        print("Refresh token expired - regenerate it")
    elif result.error_code == "validation_failed":
        print("Credentials invalid - check client ID/secret")
```

### Send Errors

```python
result = provider.send_message(...)

if not result.success:
    if result.error_code == "send_failed":
        print("Gmail API error - check quota/permissions")
    elif result.error_code == "rate_limit":
        print("Rate limited - wait and retry")
```

### Fetch Errors

```python
from agentos.communicationos.providers.email.gmail_client import GmailAPIError

try:
    messages = provider.fetch_messages()
except GmailAPIError as e:
    print(f"Error: {e}")
    print(f"Error code: {e.error_code}")
    print(f"Status code: {e.status_code}")
```

## EmailEnvelope Reference

```python
class EmailEnvelope:
    provider_message_id: str     # Gmail message ID
    message_id: str              # RFC 5322 Message-ID
    in_reply_to: Optional[str]   # In-Reply-To header
    references: Optional[str]    # References header
    from_address: str            # Sender email
    from_name: Optional[str]     # Sender display name
    to_addresses: List[str]      # Recipients
    cc_addresses: List[str]      # CC recipients
    subject: str                 # Email subject
    date: datetime               # Sent date (UTC)
    text_body: Optional[str]     # Plain text body
    html_body: Optional[str]     # HTML body
    attachments: List[Dict]      # Attachments (empty for now)
    raw_headers: Dict            # All headers
    thread_hint: Optional[str]   # Thread hint (optional)
```

## Rate Limits

### Gmail API Quotas

- **Daily quota:** 1,000,000,000 units
- **List messages:** 5 units/request
- **Get message:** 5 units/request
- **Send message:** 100 units/request
- **Modify message:** 5 units/request

### Recommended Polling

| Activity | Interval | Daily Calls | Daily Units |
|----------|----------|-------------|-------------|
| High     | 30s      | 2,880       | 14,400      |
| Normal   | 2m       | 720         | 3,600       |
| Low      | 10m      | 144         | 720         |

## Security Best Practices

### Token Storage

```python
# ✅ DO: Store with restricted permissions
import os
import json

token_file = os.path.expanduser("~/.agentos/gmail_tokens.json")
os.makedirs(os.path.dirname(token_file), exist_ok=True)

with open(token_file, 'w') as f:
    json.dump({"refresh_token": refresh_token}, f)

os.chmod(token_file, 0o600)  # Only owner can read/write
```

```python
# ❌ DON'T: Commit tokens to version control
# Add to .gitignore:
# .agentos/
# *tokens.json
# *credentials.json
```

### Error Messages

```python
# ✅ DO: Log errors without tokens
logger.error(f"Validation failed: {result.error_message}")

# ❌ DON'T: Log sensitive data
logger.error(f"Token: {refresh_token}")  # Never do this!
```

## Troubleshooting

### "invalid_grant" Error

**Cause:** Refresh token expired or revoked

**Solution:**
1. Regenerate refresh token
2. Update configuration
3. Revoke old access in Google Account settings

### "insufficientPermissions" Error

**Cause:** Missing OAuth scopes

**Solution:**
1. Check OAuth consent screen has correct scopes
2. Regenerate refresh token with proper scopes
3. Required scopes:
   - `https://www.googleapis.com/auth/gmail.readonly`
   - `https://www.googleapis.com/auth/gmail.send`

### Rate Limit (429) Error

**Provider handles automatically with retry**

If persistent:
1. Check quota usage in Google Cloud Console
2. Increase polling interval
3. Implement message ID caching

### Connection Timeout

**Provider retries automatically (exponential backoff)**

If persistent:
1. Check network connectivity
2. Check firewall settings
3. Try increasing timeout (modify client code)

## Demo Script

```bash
# Interactive OAuth setup
python examples/gmail_provider_demo.py setup

# Fetch unread messages
python examples/gmail_provider_demo.py fetch

# Send test message
python examples/gmail_provider_demo.py send

# Reply to messages
python examples/gmail_provider_demo.py reply
```

## Complete Example

```python
#!/usr/bin/env python3
from datetime import datetime, timezone, timedelta
from agentos.communicationos.providers.email import GmailProvider

# Initialize provider
provider = GmailProvider(
    client_id="YOUR_CLIENT_ID",
    client_secret="YOUR_CLIENT_SECRET",
    refresh_token="YOUR_REFRESH_TOKEN",
    email_address="your_email@gmail.com"
)

# Validate credentials
print("Validating credentials...")
result = provider.validate_credentials()
if not result.valid:
    print(f"❌ Validation failed: {result.error_message}")
    exit(1)

print("✅ Credentials valid")

# Fetch messages from last hour
print("\nFetching messages...")
since = datetime.now(timezone.utc) - timedelta(hours=1)
messages = provider.fetch_messages(since=since, limit=10)

print(f"Found {len(messages)} message(s)\n")

# Process each message
for msg in messages:
    print(f"From: {msg.from_name} <{msg.from_address}>")
    print(f"Subject: {msg.subject}")
    print(f"Date: {msg.date}")
    print(f"Thread: {msg.compute_thread_root()}")

    # Send auto-reply
    reply_headers = msg.get_reply_headers()
    result = provider.send_message(
        to_addresses=[msg.from_address],
        subject=f"Re: {msg.subject}",
        text_body="Thank you for your message! I'll get back to you soon.",
        in_reply_to=reply_headers["In-Reply-To"],
        references=reply_headers["References"]
    )

    if result.success:
        print(f"✅ Reply sent: {result.message_id}")

        # Mark original as read
        if provider.mark_as_read(msg.provider_message_id):
            print("✅ Marked as read")
    else:
        print(f"❌ Reply failed: {result.error_message}")

    print("---\n")
```

## See Also

- **Setup Guide:** `GMAIL_SETUP.md` - Detailed setup instructions
- **Implementation Report:** `docs/TASK_20_GMAIL_PROVIDER_IMPLEMENTATION.md`
- **Demo Script:** `examples/gmail_provider_demo.py`
- **Protocol Interface:** `agentos/communicationos/providers/email/__init__.py`
- **Tests:** `tests/unit/communicationos/providers/email/test_gmail_provider.py`

---

**Last Updated:** 2026-02-01
**Version:** 1.0.0
