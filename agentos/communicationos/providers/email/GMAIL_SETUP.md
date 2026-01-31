# Gmail Provider Setup Guide

Complete guide to setting up Gmail Provider for AgentOS CommunicationOS.

## Overview

The Gmail Provider uses Gmail API with OAuth 2.0 for secure email communication. It provides:
- ✅ No password storage (OAuth tokens only)
- ✅ Fine-grained permissions
- ✅ Automatic token refresh
- ✅ Proper email threading support
- ✅ Read and send capabilities

## Prerequisites

- Gmail or Google Workspace account
- Google Cloud Console access
- Python 3.9+
- `requests` library (`pip install requests`)

## Setup Steps

### Step 1: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click "Create Project"
3. Name: "AgentOS Email" (or your preferred name)
4. Click "Create"

### Step 2: Enable Gmail API

1. In Google Cloud Console, go to "APIs & Services" → "Library"
2. Search for "Gmail API"
3. Click "Enable"

### Step 3: Configure OAuth Consent Screen

1. Go to "APIs & Services" → "OAuth consent screen"
2. Select "External" (or "Internal" for Google Workspace)
3. Fill in required fields:
   - App name: "AgentOS"
   - User support email: Your email
   - Developer contact: Your email
4. Click "Save and Continue"
5. Add scopes:
   - `https://www.googleapis.com/auth/gmail.readonly`
   - `https://www.googleapis.com/auth/gmail.send`
6. Click "Save and Continue"
7. Add test users (your Gmail address)
8. Click "Save and Continue"

### Step 4: Create OAuth 2.0 Credentials

1. Go to "APIs & Services" → "Credentials"
2. Click "Create Credentials" → "OAuth client ID"
3. Application type: "Desktop app"
4. Name: "AgentOS Desktop Client"
5. Click "Create"
6. **Save the Client ID and Client Secret** (you'll need these)

### Step 5: Generate Refresh Token

#### Option A: Using Python Script (Recommended)

```python
from agentos.communicationos.providers.email.gmail_provider import (
    generate_auth_url,
    exchange_code_for_tokens
)

# Your OAuth credentials from Step 4
CLIENT_ID = "xxx.apps.googleusercontent.com"
CLIENT_SECRET = "your_client_secret"

# Generate authorization URL
auth_url = generate_auth_url(
    client_id=CLIENT_ID,
    redirect_uri="http://localhost:8080/oauth2callback"
)

print("Visit this URL to authorize:")
print(auth_url)
print()

# User visits URL, authorizes app, gets redirected to:
# http://localhost:8080/oauth2callback?code=4/0Xxx...
# Copy the 'code' parameter

auth_code = input("Enter the authorization code: ")

# Exchange code for tokens
tokens = exchange_code_for_tokens(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    code=auth_code,
    redirect_uri="http://localhost:8080/oauth2callback"
)

print("\nYour refresh token:")
print(tokens["refresh_token"])
print("\n⚠️  Store this securely! You'll need it to configure the provider.")
```

#### Option B: Using OAuth Playground

1. Go to [Google OAuth 2.0 Playground](https://developers.google.com/oauthplayground/)
2. Click settings (gear icon), check "Use your own OAuth credentials"
3. Enter your Client ID and Client Secret
4. Select scopes:
   - `https://www.googleapis.com/auth/gmail.readonly`
   - `https://www.googleapis.com/auth/gmail.send`
5. Click "Authorize APIs"
6. Click "Exchange authorization code for tokens"
7. Copy the "Refresh token"

### Step 6: Configure AgentOS

Add the Gmail provider configuration to your AgentOS setup:

```python
from agentos.communicationos.providers.email.gmail_provider import GmailProvider

provider = GmailProvider(
    client_id="xxx.apps.googleusercontent.com",
    client_secret="your_client_secret",
    refresh_token="your_refresh_token",
    email_address="your_email@gmail.com"
)

# Test credentials
result = provider.validate_credentials()
if result.valid:
    print("✅ Gmail provider configured successfully!")
else:
    print(f"❌ Configuration failed: {result.error_message}")
```

## Usage Examples

### Fetch Unread Messages

```python
from datetime import datetime, timezone, timedelta

# Fetch messages from last hour
since = datetime.now(timezone.utc) - timedelta(hours=1)
messages = provider.fetch_messages(since=since, limit=10)

for msg in messages:
    print(f"From: {msg.from_name} <{msg.from_address}>")
    print(f"Subject: {msg.subject}")
    print(f"Date: {msg.date}")
    print(f"Body: {msg.text_body[:100]}...")
    print("---")
```

### Send Reply with Threading

```python
# Get reply headers from original message
original_message = messages[0]
reply_headers = original_message.get_reply_headers()

# Send reply
result = provider.send_message(
    to_addresses=[original_message.from_address],
    subject=f"Re: {original_message.subject}",
    text_body="Thank you for your message!",
    in_reply_to=reply_headers["In-Reply-To"],
    references=reply_headers["References"]
)

if result.success:
    print(f"✅ Reply sent! Message ID: {result.message_id}")
else:
    print(f"❌ Send failed: {result.error_message}")
```

### Send New Email

```python
result = provider.send_message(
    to_addresses=["recipient@example.com"],
    subject="Hello from AgentOS",
    text_body="This is a plain text message.",
    html_body="<p>This is an <strong>HTML</strong> message.</p>",
    cc_addresses=["cc@example.com"]
)
```

### Mark as Read

```python
# Mark message as read after processing
success = provider.mark_as_read(messages[0].provider_message_id)
if success:
    print("✅ Message marked as read")
```

## Security Best Practices

### 1. Token Storage

**DO:**
- Store refresh token in encrypted configuration
- Use environment variables or secure vaults
- Restrict file permissions (chmod 600)

**DON'T:**
- Commit tokens to version control
- Store in plain text files
- Share tokens in logs or error messages

### 2. Scope Minimization

Only request necessary scopes:
- Read-only: Use only `gmail.readonly`
- Send-only: Use only `gmail.send`
- Both: Use both scopes (default)

### 3. Token Rotation

- Refresh tokens don't expire automatically
- Revoke access in Google Account settings if compromised
- Generate new tokens periodically (recommended: every 6 months)

## Troubleshooting

### Error: "invalid_grant" during token refresh

**Cause:** Refresh token expired or revoked

**Solution:**
1. Revoke access in Google Account → Security → Third-party apps
2. Generate new refresh token (Step 5)
3. Update configuration

### Error: "insufficientPermissions"

**Cause:** Missing required OAuth scopes

**Solution:**
1. Check OAuth consent screen has correct scopes
2. Regenerate refresh token with proper scopes
3. Ensure user authorized both read and send permissions

### Error: "quotaExceeded" or 429 Rate Limit

**Cause:** Too many API requests

**Solution:**
- Gmail API quota: 1 billion quota units/day
- Typical read: 5 units, send: 100 units
- Implement exponential backoff (built into provider)
- Consider caching message IDs to avoid redundant fetches

### Error: "authError" or 401 Unauthorized

**Cause:** Access token expired

**Solution:**
- Provider automatically refreshes tokens (built-in)
- If persists, regenerate refresh token
- Check client secret hasn't changed

## Rate Limits and Quotas

### Gmail API Quotas

| Operation | Cost (units) | Daily Limit |
|-----------|-------------|-------------|
| List messages | 5 | 200M requests |
| Get message | 5 | 200M requests |
| Send message | 100 | 10M requests |
| Modify message | 5 | 200M requests |

**Daily quota:** 1,000,000,000 units

### Recommended Polling Intervals

- High activity: 30-60 seconds
- Normal activity: 2-5 minutes
- Low activity: 10-15 minutes

## Advanced Configuration

### Custom Redirect URI

For production deployments, use a real web server:

```python
auth_url = generate_auth_url(
    client_id=CLIENT_ID,
    redirect_uri="https://yourdomain.com/oauth/gmail/callback"
)
```

### Custom Scopes

For additional functionality:

```python
from agentos.communicationos.providers.email.gmail_provider import generate_auth_url

auth_url = generate_auth_url(
    client_id=CLIENT_ID,
    redirect_uri=REDIRECT_URI,
    scopes=[
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.send",
        "https://www.googleapis.com/auth/gmail.modify"  # Additional scope
    ]
)
```

### Token Caching

The provider automatically handles token refresh, but you can implement caching:

```python
class CachedGmailProvider(GmailProvider):
    def __init__(self, *args, cache_file="tokens.json", **kwargs):
        super().__init__(*args, **kwargs)
        self.cache_file = cache_file
        self._load_cached_token()

    def _load_cached_token(self):
        try:
            with open(self.cache_file, 'r') as f:
                data = json.load(f)
                self.client.access_token = data.get("access_token")
                # Load expiry, etc.
        except FileNotFoundError:
            pass

    def _save_token(self):
        with open(self.cache_file, 'w') as f:
            json.dump({
                "access_token": self.client.access_token,
                "expires_at": self.client.token_expiry.isoformat()
            }, f)
```

## Support

### Documentation
- [Gmail API Reference](https://developers.google.com/gmail/api)
- [OAuth 2.0 Guide](https://developers.google.com/identity/protocols/oauth2)
- [IEmailProvider Protocol](/agentos/communicationos/providers/email/__init__.py)

### Common Issues
- Check Google Cloud Console for API errors
- Review OAuth consent screen status
- Verify scopes match requirements
- Check quota usage in Cloud Console

### Getting Help
1. Check logs for detailed error messages
2. Review this guide's troubleshooting section
3. Consult Gmail API documentation
4. Check AgentOS CommunicationOS documentation

---

**Last Updated:** 2026-02-01
**Version:** 1.0.0
**Status:** Production Ready
