# Email Channel Key Mapping Rules

This document defines how email messages are mapped to CommunicationOS's unified message model, with special focus on conversation threading and key generation.

## Overview

Email is fundamentally different from real-time messaging channels (Telegram, Slack) due to:
- **Asynchronous nature**: No persistent connections, messages are polled
- **Thread-based conversations**: Multiple conversations can occur with the same user
- **Standard headers**: RFC 5322 defines Message-ID, References, In-Reply-To for threading
- **Email addresses as identifiers**: No platform-specific user IDs

## Key Mapping Rules

### 1. user_key: Sender Email Address

The `user_key` identifies who sent the message, mapped from the `From` header.

**Mapping:**
```python
user_key = from_address.lower()  # Normalize to lowercase
```

**Examples:**
- From: `john.doe@example.com` → user_key: `john.doe@example.com`
- From: `John Doe <john.doe@example.com>` → user_key: `john.doe@example.com`
- From: `JANE@COMPANY.COM` → user_key: `jane@company.com`

**Normalization Rules:**
- Always lowercase
- Strip display name (keep only email address)
- Trim whitespace

### 2. conversation_key: Email Thread Root

The `conversation_key` identifies which conversation thread the message belongs to. This is critical for maintaining context across multiple emails with the same user.

**Thread Detection Algorithm:**

```python
def compute_conversation_key(envelope: EmailEnvelope) -> str:
    """
    1. If References header exists:
       - Parse space/newline-separated Message-IDs
       - Return the FIRST Message-ID (oldest in thread)

    2. Else if In-Reply-To header exists:
       - Return the In-Reply-To Message-ID (direct parent)

    3. Else (no threading headers):
       - Return current message's Message-ID (new thread)
    """
    if envelope.references:
        refs = envelope.references.strip().split()
        if refs:
            return refs[0].strip('<>')

    if envelope.in_reply_to:
        return envelope.in_reply_to.strip('<>')

    return envelope.message_id.strip('<>')
```

**Examples:**

**Example 1: New Thread**
```
Message-ID: <CABcD1234567890@mail.gmail.com>
In-Reply-To: (none)
References: (none)

→ conversation_key: "CABcD1234567890@mail.gmail.com"
```

**Example 2: Reply (First Response)**
```
Message-ID: <CABcD9876543210@mail.gmail.com>
In-Reply-To: <CABcD1234567890@mail.gmail.com>
References: <CABcD1234567890@mail.gmail.com>

→ conversation_key: "CABcD1234567890@mail.gmail.com"
```

**Example 3: Reply in Long Thread**
```
Message-ID: <CABcD5555555555@mail.gmail.com>
In-Reply-To: <CABcD9876543210@mail.gmail.com>
References: <CABcD1234567890@mail.gmail.com> <CABcD9876543210@mail.gmail.com>

→ conversation_key: "CABcD1234567890@mail.gmail.com"
```

**Key Property:**
- All messages in the same thread have the **same conversation_key**
- Multiple threads with the same user have **different conversation_keys**
- This enables parallel conversations with the same person

### 3. message_id: RFC 5322 Message-ID

The `message_id` uniquely identifies this specific message globally.

**Mapping:**
```python
message_id = f"email_{message_id_header.strip('<>')}"
```

**Examples:**
- Message-ID: `<CABcD1234567890@mail.gmail.com>`
  → message_id: `email_CABcD1234567890@mail.gmail.com`
- Message-ID: `20260201103000.12345@smtp.example.com`
  → message_id: `email_20260201103000.12345@smtp.example.com`

**Properties:**
- Globally unique (RFC 5322 guarantees uniqueness)
- Used for deduplication
- Used for reply threading (In-Reply-To, References)

### 4. provider_message_id: Provider-Specific ID

The `provider_message_id` is the internal ID used by the email provider to track the message. This is used for operations like marking as read, deleting, etc.

**Provider-Specific Mappings:**

| Provider | ID Type | Example |
|----------|---------|---------|
| Gmail API | Message ID (hex) | `18d4c2f1a2b3c4d5` |
| Outlook Graph API | Message ID (base64) | `AAMkAGI2T...` |
| IMAP | UID (integer) | `12345` |

**Usage:**
- Mark message as read: `provider.mark_as_read(provider_message_id)`
- Delete message: `provider.delete_message(provider_message_id)`
- Fetch message details: `provider.get_message(provider_message_id)`

## Complete Example: Email Thread Tracking

### Scenario: Three-Message Thread

**Message 1: Initial Email (from user)**
```yaml
From: john.doe@example.com
To: agent@example.com
Subject: Question about pricing
Message-ID: <msg-001@mail.example.com>
In-Reply-To: (none)
References: (none)
Body: "What are your pricing plans?"

Mapping:
  user_key: "john.doe@example.com"
  conversation_key: "msg-001@mail.example.com"
  message_id: "email_msg-001@mail.example.com"
```

**Message 2: Agent Reply**
```yaml
From: agent@example.com
To: john.doe@example.com
Subject: Re: Question about pricing
Message-ID: <msg-002@agent.example.com>
In-Reply-To: <msg-001@mail.example.com>
References: <msg-001@mail.example.com>
Body: "We have three tiers: Basic, Pro, Enterprise..."

Mapping:
  user_key: "agent@example.com"  # Outbound message
  conversation_key: "msg-001@mail.example.com"  # Same thread!
  message_id: "email_msg-002@agent.example.com"
```

**Message 3: User Follow-up**
```yaml
From: john.doe@example.com
To: agent@example.com
Subject: Re: Question about pricing
Message-ID: <msg-003@mail.example.com>
In-Reply-To: <msg-002@agent.example.com>
References: <msg-001@mail.example.com> <msg-002@agent.example.com>
Body: "Tell me more about the Pro tier"

Mapping:
  user_key: "john.doe@example.com"
  conversation_key: "msg-001@mail.example.com"  # Same thread!
  message_id: "email_msg-003@mail.example.com"
```

**Result:**
- All three messages share `conversation_key: "msg-001@mail.example.com"`
- AgentOS maintains full conversation context across the thread
- If user starts a NEW email (not a reply), it gets a different conversation_key

## Comparison with Other Channels

| Channel | user_key | conversation_key | message_id |
|---------|----------|------------------|------------|
| **Email** | `from_address` | `thread_root_message_id` | `email_{message_id}` |
| **Telegram** | `user_id` (int) | `chat_id` (int) | `tg_{update_id}_{msg_id}` |
| **Slack** | `user_id` (U123) | `channel_id` or `channel_id:thread_ts` | `slack_{event_id}` |

**Key Differences:**
- Email uses email addresses (strings) instead of numeric IDs
- Email has explicit thread tracking via RFC 5322 headers
- Email threads are identified by Message-ID, not chat/channel IDs

## Threading Edge Cases

### Case 1: Missing References Header
Some email clients only set `In-Reply-To` without `References`:
```
Message-ID: <msg-003@mail.example.com>
In-Reply-To: <msg-002@agent.example.com>
References: (missing)
```

**Solution:** Use `In-Reply-To` as conversation_key:
```python
conversation_key = "msg-002@agent.example.com"
```

**Note:** This may not track back to the original thread root, but it maintains immediate reply context.

### Case 2: Forwarded Emails
Forwarded emails typically start a new thread:
```
Message-ID: <fwd-123@mail.example.com>
In-Reply-To: (none)
References: (none)
Subject: Fwd: Original subject
```

**Solution:** Treat as new thread:
```python
conversation_key = "fwd-123@mail.example.com"
```

### Case 3: Multiple Recipients (Group Emails)
Email sent to multiple people:
```
From: john@example.com
To: agent@example.com, support@example.com
```

**Solution:** Each recipient tracks the thread independently:
- Agent sees: `conversation_key = thread_root_message_id`
- Support sees: Same `conversation_key` (shared thread)

**Note:** Both agents see the same conversation context.

## Implementation Considerations

### Polling Strategy
Email channels use polling (not webhooks):
```python
poll_interval_seconds = 60  # Default: 60 seconds
```

**Best Practices:**
- Minimum interval: 30 seconds (avoid rate limits)
- Maximum interval: 3600 seconds (1 hour for low-traffic)
- Track last poll timestamp to only fetch new messages

### Deduplication
Use `message_id` for deduplication:
```python
seen_message_ids = set()

for envelope in provider.fetch_messages(since=last_poll):
    msg_id = f"email_{envelope.message_id.strip('<>')}"
    if msg_id in seen_message_ids:
        continue  # Skip duplicate
    seen_message_ids.add(msg_id)
    # Process message...
```

### Reply Headers
When sending a reply, include proper threading headers:
```python
reply_headers = envelope.get_reply_headers()
# Returns:
# {
#     "In-Reply-To": "<original-message-id>",
#     "References": "<thread-root> <parent-message-id>"
# }

provider.send_message(
    to_addresses=[envelope.from_address],
    subject=f"Re: {envelope.subject}",
    text_body="Your reply here",
    in_reply_to=reply_headers["In-Reply-To"],
    references=reply_headers["References"]
)
```

## Testing Checklist

- [ ] New email creates new conversation_key
- [ ] Reply to email uses same conversation_key as original
- [ ] Long thread (5+ messages) maintains same conversation_key
- [ ] Multiple threads with same user have different conversation_keys
- [ ] Message-ID deduplication works correctly
- [ ] Missing References header falls back to In-Reply-To
- [ ] Missing both headers treats as new thread
- [ ] Email address normalization (lowercase, trim)
- [ ] Display name stripping works correctly
- [ ] Forwarded emails create new threads

## References

- [RFC 5322: Internet Message Format](https://datatracker.ietf.org/doc/html/rfc5322)
- [RFC 2822: Message-ID](https://datatracker.ietf.org/doc/html/rfc2822#section-3.6.4)
- [RFC 5256: Threading](https://datatracker.ietf.org/doc/html/rfc5256)
- [Gmail API Threading](https://developers.google.com/gmail/api/guides/threads)
- [Microsoft Graph API Messages](https://learn.microsoft.com/en-us/graph/api/resources/message)
