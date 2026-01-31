# Voice Communication Backend

Complete backend skeleton for AgentOS voice communication system.

## Quick Start

```python
from agentos.core.communication.voice import (
    VoiceService,
    VoiceProvider,
    STTProvider,
)

# Create service
service = VoiceService()

# Create voice session
session = service.create_session(
    project_id="my-project",
    provider=VoiceProvider.LOCAL,
    stt_provider=STTProvider.WHISPER,
    metadata={"user_id": "user123"}
)

# Dispatch audio
audio_data = b"..." # Raw audio bytes
service.dispatch_audio_chunk(session.session_id, audio_data)

# Stop session
service.stop_session(session.session_id)
```

## Architecture

### Directory Structure

```
voice/
├── __init__.py          # Main exports
├── models.py            # Data models and enums
├── policy.py            # Security policy engine
├── service.py           # Main service implementation
└── providers/           # Provider implementations
    ├── __init__.py
    ├── base.py          # IVoiceProvider interface
    ├── local.py         # Local WebSocket provider
    └── twilio.py        # Twilio PSTN provider (MVP stub)
```

## Models

### VoiceSession

Represents an active voice communication session.

**Fields:**
- `session_id`: Unique identifier
- `project_id`: Associated project
- `provider`: Voice provider (LOCAL, TWILIO)
- `stt_provider`: STT provider (WHISPER, GOOGLE, AZURE, AWS)
- `state`: Session state (CREATED, ACTIVE, STOPPING, STOPPED)
- `created_at`: UTC timestamp
- `last_activity_at`: UTC timestamp
- `risk_tier`: Risk assessment (LOW, MEDIUM, HIGH, CRITICAL)
- `policy_verdict`: Policy evaluation result
- `audit_trace_id`: Audit trail identifier
- `metadata`: Additional session data

### VoiceEvent

Tracks significant events within a voice session.

**Fields:**
- `event_id`: Unique identifier
- `session_id`: Associated session
- `event_type`: Event type enum
- `payload`: Event-specific data
- `timestamp_ms`: Epoch milliseconds
- `metadata`: Additional event data

## Policy Engine

`VoicePolicy` provides security governance for voice operations.

**Features:**
- Default risk tier: LOW (no admin token required)
- Risk escalation based on provider and metadata
- Parameter validation
- Admin token interface for high-risk operations

**Risk Factors:**
- Provider type (LOCAL < TWILIO)
- Sensitive data handling
- International calling
- Recording enabled

## Providers

### IVoiceProvider Interface

All providers must implement:
- `get_session_metadata()`: Provider capabilities
- `validate_config()`: Configuration validation
- `on_session_created()`: Optional lifecycle hook
- `on_session_stopped()`: Optional lifecycle hook

### LocalProvider

WebSocket-based voice for browser interfaces.

**Transport:** WebSocket
**Risk Level:** LOW
**External Deps:** None

### TwilioProvider (MVP Stub)

PSTN connectivity via Twilio Voice API.

**Transport:** PSTN/SIP
**Risk Level:** MEDIUM
**Status:** Stub (requires Twilio SDK)

**Configuration:**
- `TWILIO_ACCOUNT_SID`: Account identifier
- `TWILIO_AUTH_TOKEN`: Authentication token
- `TWILIO_TWIML_APP_SID`: TwiML application SID

## Service API

### VoiceService.create_session()

Creates a new voice session with policy evaluation and audit logging.

```python
session = service.create_session(
    project_id="proj-123",
    provider=VoiceProvider.LOCAL,
    stt_provider=STTProvider.WHISPER,
    metadata={"caller_id": "+1234567890"}
)
```

**Returns:** `VoiceSession` object
**Raises:** `ValueError`, `PermissionError`

### VoiceService.stop_session()

Gracefully stops an active session.

```python
success = service.stop_session(session_id)
```

**Returns:** `bool` (True if stopped, False if not found)

### VoiceService.dispatch_audio_chunk()

Dispatches audio data for processing (placeholder for STT integration).

```python
service.dispatch_audio_chunk(session_id, audio_bytes)
```

**Raises:** `ValueError` if session not found or invalid state

## Audit & Compliance

All operations are logged via `EvidenceLogger`:
- Session creation/stopping logged as evidence records
- Each operation includes audit_trace_id
- Risk tier tracked in all evidence
- ConnectorType.CUSTOM used for voice operations

## Time Contract Compliance

All timestamps follow AgentOS time contract:
- Uses `agentos.core.time.utc_now()` for datetime
- Uses `utc_now_ms()` for epoch milliseconds
- No direct `datetime.now()` or `datetime.utcnow()` calls
- ISO 8601 formatting via `.isoformat()`

## Testing

Run comprehensive tests:

```bash
python3 << 'EOF'
from agentos.core.communication.voice import VoiceService, VoiceProvider, STTProvider

service = VoiceService()
session = service.create_session(
    project_id="test",
    provider=VoiceProvider.LOCAL,
    stt_provider=STTProvider.WHISPER
)
print(f"Session created: {session.session_id}")
service.stop_session(session.session_id)
print("Session stopped successfully")
EOF
```

## Future Enhancements

1. **TwilioProvider Production**: Integrate Twilio SDK for real PSTN calls
2. **STT Integration**: Connect dispatch_audio_chunk to actual STT service
3. **WebSocket Server**: Implement real-time audio streaming
4. **Recording**: Add session recording with storage backend
5. **Transcription**: Store and query transcripts
6. **Analytics**: Session duration, quality metrics, usage statistics

## Dependencies

- `agentos.core.time`: Time utilities
- `agentos.core.communication.evidence`: Audit logging
- `agentos.core.communication.models`: Base communication models

## License

Internal AgentOS component - proprietary.
