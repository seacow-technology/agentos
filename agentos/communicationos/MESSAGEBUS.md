# MessageBus and Middleware Documentation

## Overview

The MessageBus is the central routing and processing engine for CommunicationOS. It provides a middleware-based architecture for processing inbound and outbound messages through a chain of composable components.

## Architecture

```
External Channel -> Adapter -> [Middleware Chain] -> Business Logic
Business Logic -> [Middleware Chain] -> Adapter -> External Channel
```

### Key Components

1. **MessageBus**: Central router that coordinates message flow
2. **Middleware**: Pluggable processing components (deduplication, rate limiting, audit)
3. **ChannelAdapter**: Interface for channel-specific message sending

## MessageBus

The MessageBus routes messages through a chain of middleware before delivering them to handlers (inbound) or adapters (outbound).

### Basic Usage

```python
from agentos.communicationos import (
    MessageBus,
    DedupeStore, DedupeMiddleware,
    RateLimitStore, RateLimitMiddleware,
    AuditStore, AuditMiddleware,
)

# Initialize stores
dedupe_store = DedupeStore()
rate_limit_store = RateLimitStore()
audit_store = AuditStore()

# Create middleware instances
dedupe = DedupeMiddleware(dedupe_store)
rate_limiter = RateLimitMiddleware(rate_limit_store)
auditor = AuditMiddleware(audit_store)

# Create and configure the bus
bus = MessageBus()
bus.add_middleware(dedupe)      # First: deduplicate
bus.add_middleware(rate_limiter) # Second: rate limit
bus.add_middleware(auditor)      # Third: audit log

# Register channel adapters
bus.register_adapter("whatsapp_001", whatsapp_adapter)
bus.register_adapter("telegram_002", telegram_adapter)

# Add inbound message handlers
bus.add_inbound_handler(handle_user_message)

# Process an inbound message
context = await bus.process_inbound(inbound_message)

# Send an outbound message
context = await bus.send_outbound(outbound_message)
```

### Processing Status

Messages can have the following statuses:

- **CONTINUE**: Processing should continue to next middleware
- **STOP**: Processing should stop (message handled)
- **REJECT**: Message should be rejected (duplicate, rate limited)
- **ERROR**: Error occurred during processing

### Processing Context

The `ProcessingContext` carries state through the middleware chain:

```python
@dataclass
class ProcessingContext:
    message_id: str
    channel_id: str
    metadata: Dict[str, Any]
    status: ProcessingStatus = ProcessingStatus.CONTINUE
    error: Optional[str] = None
```

## Middleware Components

### 1. Deduplication Middleware

Prevents duplicate message processing based on message_id.

**Features:**
- SQLite-based persistent storage
- Per-channel deduplication
- Configurable TTL for cleanup
- Statistics tracking

**Usage:**

```python
from agentos.communicationos import DedupeStore, DedupeMiddleware

store = DedupeStore()
middleware = DedupeMiddleware(
    store,
    ttl_ms=24 * 60 * 60 * 1000,  # 24 hours
    cleanup_interval_ms=60 * 60 * 1000  # 1 hour
)

bus.add_middleware(middleware)
```

**Database Schema:**

```sql
CREATE TABLE message_dedupe (
    message_id TEXT NOT NULL,
    channel_id TEXT NOT NULL,
    first_seen_ms INTEGER NOT NULL,
    last_seen_ms INTEGER NOT NULL,
    count INTEGER DEFAULT 1,
    metadata TEXT,
    PRIMARY KEY (message_id, channel_id)
)
```

**Statistics:**

```python
stats = store.get_stats()
# {
#     "total_messages": 1234,
#     "messages_with_duplicates": 56,
#     "total_duplicates_blocked": 102
# }
```

### 2. Rate Limiting Middleware

Prevents message flooding using sliding window rate limiting.

**Features:**
- Per-user and per-channel rate limits
- Sliding window algorithm
- Configurable limits and windows
- Automatic cleanup of old events

**Usage:**

```python
from agentos.communicationos import RateLimitStore, RateLimitMiddleware

store = RateLimitStore()
middleware = RateLimitMiddleware(
    store,
    window_ms=60 * 1000,  # 60 seconds
    max_requests=20,      # 20 requests per window
    cleanup_interval_ms=10 * 60 * 1000  # 10 minutes
)

bus.add_middleware(middleware)
```

**Database Schema:**

```sql
CREATE TABLE rate_limit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id TEXT NOT NULL,
    user_key TEXT NOT NULL,
    timestamp_ms INTEGER NOT NULL
)
```

**How it works:**

The sliding window algorithm counts requests in the last `window_ms` milliseconds:

1. New message arrives
2. Count existing events in window for (channel_id, user_key)
3. If count < max_requests: Allow and record event
4. If count >= max_requests: Reject message

**Statistics:**

```python
stats = store.get_stats()
# {
#     "total_events": 5678,
#     "unique_users": 234
# }

# Channel-specific stats
stats = store.get_stats(channel_id="whatsapp_001")
```

### 3. Audit Logging Middleware

Logs message metadata for audit trail and compliance.

**Features:**
- Privacy-first: Only logs metadata, never content
- Session tracking
- Query by user, session, or time
- Configurable retention period

**Usage:**

```python
from agentos.communicationos import AuditStore, AuditMiddleware

store = AuditStore()
middleware = AuditMiddleware(
    store,
    retention_days=30,  # 30 days
    cleanup_interval_ms=24 * 60 * 60 * 1000  # 24 hours
)

bus.add_middleware(middleware)
```

**Database Schema:**

```sql
CREATE TABLE message_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id TEXT NOT NULL,
    direction TEXT NOT NULL,  -- 'inbound' or 'outbound'
    channel_id TEXT NOT NULL,
    user_key TEXT NOT NULL,
    conversation_key TEXT,
    session_id TEXT,
    timestamp_ms INTEGER NOT NULL,
    processing_status TEXT,
    metadata TEXT,  -- JSON
    created_at_ms INTEGER NOT NULL
)
```

**What is logged:**

✅ Logged:
- Message ID
- Channel ID
- User key
- Conversation key
- Session ID
- Timestamp
- Processing status
- Metadata (dedupe status, rate limit info, etc.)

❌ NOT Logged:
- Message text
- Attachments
- Location data
- Any user-generated content

**Querying audit logs:**

```python
# Query by user
logs = store.query_by_user("whatsapp_001", "+1234567890")

# Query by session
logs = store.query_by_session("session_abc123")

# Get statistics
stats = store.get_stats()
# {
#     "total_messages": 12345,
#     "inbound_count": 8000,
#     "outbound_count": 4345,
#     "unique_channels": 3,
#     "unique_users": 567,
#     "unique_sessions": 234
# }
```

## Creating Custom Middleware

To create custom middleware, extend the `Middleware` base class:

```python
from agentos.communicationos.message_bus import (
    Middleware,
    ProcessingContext,
    ProcessingStatus
)
from agentos.communicationos.models import InboundMessage, OutboundMessage

class CustomMiddleware(Middleware):
    """Custom middleware implementation."""

    async def process_inbound(
        self,
        message: InboundMessage,
        context: ProcessingContext
    ) -> ProcessingContext:
        """Process inbound message."""
        # Your logic here

        # To reject a message:
        # context.status = ProcessingStatus.REJECT
        # context.metadata["reason"] = "rejected"

        # To signal error:
        # context.status = ProcessingStatus.ERROR
        # context.error = "error message"

        # To continue processing:
        context.metadata["custom_check"] = True
        return context

    async def process_outbound(
        self,
        message: OutboundMessage,
        context: ProcessingContext
    ) -> ProcessingContext:
        """Process outbound message."""
        # Your logic here
        return context
```

## Best Practices

### Middleware Order

Order matters! Recommended order:

1. **Deduplication** - First to avoid wasted processing
2. **Rate Limiting** - Protect system resources
3. **Audit** - Log everything that passes validation
4. **Custom** - Your business logic

### Error Handling

- Middleware should catch exceptions and set context.status = ERROR
- Don't let middleware exceptions break the pipeline
- Log errors for debugging

### Performance

- Keep middleware lightweight
- Use async operations where possible
- Batch database operations when feasible
- Implement efficient cleanup strategies

### Testing

Test middleware in isolation:

```python
@pytest.mark.asyncio
async def test_my_middleware():
    middleware = MyMiddleware()

    message = InboundMessage(...)
    context = ProcessingContext(
        message_id=message.message_id,
        channel_id=message.channel_id,
        metadata={}
    )

    result = await middleware.process_inbound(message, context)

    assert result.status == ProcessingStatus.CONTINUE
    assert result.metadata["my_check"] is True
```

## Database Storage

All middleware stores use the `communicationos` component database:

- Path: `~/.agentos/store/communicationos/db.sqlite`
- WAL mode enabled for concurrent access
- Foreign keys enabled
- Automatic schema initialization

## Configuration

### Deduplication

- `ttl_ms`: Time to keep dedupe records (default: 24 hours)
- `cleanup_interval_ms`: How often to cleanup (default: 1 hour)

### Rate Limiting

- `window_ms`: Time window for counting (default: 60 seconds)
- `max_requests`: Maximum requests per window (default: 20)
- `cleanup_interval_ms`: How often to cleanup (default: 10 minutes)

### Audit

- `retention_days`: How long to keep audit logs (default: 30 days)
- `cleanup_interval_ms`: How often to cleanup (default: 24 hours)

## Monitoring

Monitor middleware health:

```python
# Deduplication stats
dedupe_stats = dedupe_store.get_stats()
print(f"Blocked {dedupe_stats['total_duplicates_blocked']} duplicates")

# Rate limiting stats
rate_stats = rate_limit_store.get_stats()
print(f"Total events: {rate_stats['total_events']}")

# Audit stats
audit_stats = audit_store.get_stats()
print(f"Total messages: {audit_stats['total_messages']}")
print(f"Inbound: {audit_stats['inbound_count']}")
print(f"Outbound: {audit_stats['outbound_count']}")
```

## Security Considerations

1. **Privacy**: Audit logs never store message content
2. **Rate Limiting**: Prevents abuse and DoS attacks
3. **Deduplication**: Prevents replay attacks
4. **Database Security**: Uses SQLite with file permissions

## See Also

- [CommunicationOS README](README.md) - Overall architecture
- [Channel Registry](REGISTRY.md) - Channel management
- [Session Management](session_router.py) - Session handling
- [Message Models](models.py) - Message specifications
