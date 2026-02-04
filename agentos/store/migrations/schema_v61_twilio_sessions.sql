-- Schema v61: Twilio Voice Sessions - Persistent Storage
-- Task #12 (Wave A2): Migrate Twilio voice sessions from memory to database
--
-- Design Goals:
-- - Replace in-memory _twilio_sessions dict with persistent storage
-- - Survive service restarts and recover session state
-- - Audit trail for all Twilio voice interactions
-- - Support session lifecycle tracking and analytics
--
-- References:
-- - agentos/webui/api/voice_twilio.py (line 46) - Original memory storage
-- - agentos/core/communication/voice/models.py - VoiceSession model

-- ===================================================================
-- 1. Twilio Sessions Table
-- ===================================================================

-- Core session state for Twilio voice calls
CREATE TABLE IF NOT EXISTS twilio_sessions (
    session_id TEXT PRIMARY KEY,                  -- Format: "twilio-{CallSid}"
    call_sid TEXT UNIQUE NOT NULL,                -- Twilio Call SID (unique identifier)
    from_number TEXT NOT NULL,                    -- Caller phone number (E.164 format)
    to_number TEXT NOT NULL,                      -- Recipient phone number (E.164 format)

    -- Session state
    status TEXT NOT NULL DEFAULT 'created',       -- created, active, stopping, stopped, failed
    state TEXT NOT NULL DEFAULT 'created',        -- Alias for status (compatibility)

    -- Timestamps (epoch_ms for consistency with v44+)
    started_at INTEGER NOT NULL,                  -- Session creation time (epoch_ms)
    ended_at INTEGER NULL,                        -- Session end time (epoch_ms)
    last_activity_at INTEGER NOT NULL,            -- Last activity timestamp (epoch_ms)
    created_at INTEGER NOT NULL,                  -- Record creation time (epoch_ms)
    updated_at INTEGER NOT NULL,                  -- Last update time (epoch_ms)

    -- Metrics
    duration_seconds INTEGER NULL,                -- Total call duration (calculated on end)
    audio_chunks_received INTEGER DEFAULT 0,      -- Count of audio chunks processed
    transcripts_generated INTEGER DEFAULT 0,      -- Count of STT transcripts

    -- Project and context
    project_id TEXT NOT NULL DEFAULT 'default',   -- Associated project ID

    -- Transport metadata (JSON-encoded)
    stream_sid TEXT NULL,                         -- Twilio Media Stream SID
    transport_metadata TEXT NULL,                 -- JSON: {call_sid, stream_sid, ...}

    -- Voice providers
    stt_provider TEXT NOT NULL DEFAULT 'whisper_local', -- Speech-to-text provider
    tts_provider TEXT NULL,                       -- Text-to-speech provider (optional)

    -- Governance and audit
    risk_tier TEXT NOT NULL DEFAULT 'LOW',        -- LOW, MEDIUM, HIGH, CRITICAL
    policy_verdict TEXT NOT NULL DEFAULT 'APPROVED', -- APPROVED, DENIED, REVIEW
    audit_trace_id TEXT NULL,                     -- Audit trace ID for evidence chain

    -- Additional metadata (JSON-encoded)
    metadata TEXT NULL,                           -- JSON: custom fields

    CHECK (status IN ('created', 'active', 'stopping', 'stopped', 'failed', 'completed')),
    CHECK (state IN ('created', 'active', 'stopping', 'stopped', 'failed', 'completed')),
    CHECK (risk_tier IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL'))
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_twilio_sessions_call_sid
    ON twilio_sessions(call_sid);

CREATE INDEX IF NOT EXISTS idx_twilio_sessions_status
    ON twilio_sessions(status);

CREATE INDEX IF NOT EXISTS idx_twilio_sessions_created_at
    ON twilio_sessions(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_twilio_sessions_project
    ON twilio_sessions(project_id, created_at DESC);

-- Index for active sessions
CREATE INDEX IF NOT EXISTS idx_twilio_sessions_active
    ON twilio_sessions(status, last_activity_at DESC)
    WHERE status IN ('created', 'active');

-- ===================================================================
-- 2. Twilio Call Logs Table
-- ===================================================================

-- Event log for detailed call lifecycle tracking
CREATE TABLE IF NOT EXISTS twilio_call_logs (
    id TEXT PRIMARY KEY,                          -- Event ID (UUID)
    session_id TEXT NOT NULL,                     -- Foreign key to twilio_sessions
    event_type TEXT NOT NULL,                     -- Event type (see below)
    event_data TEXT NULL,                         -- JSON-encoded event data
    timestamp INTEGER NOT NULL,                   -- Event timestamp (epoch_ms)

    FOREIGN KEY (session_id) REFERENCES twilio_sessions(session_id) ON DELETE CASCADE
);

-- Event Types:
-- - 'incoming': Inbound call webhook received
-- - 'stream_started': Media Stream WebSocket connected
-- - 'stream_connected': Media Stream fully initialized
-- - 'audio_received': Audio chunk received (periodic)
-- - 'transcript': STT transcript generated
-- - 'assistant_response': Assistant response sent
-- - 'stream_stopped': Media Stream disconnected
-- - 'stream_error': Error during stream processing
-- - 'hangup': Call ended

-- Indexes for log queries
CREATE INDEX IF NOT EXISTS idx_twilio_call_logs_session
    ON twilio_call_logs(session_id, timestamp);

CREATE INDEX IF NOT EXISTS idx_twilio_call_logs_event_type
    ON twilio_call_logs(event_type, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_twilio_call_logs_timestamp
    ON twilio_call_logs(timestamp DESC);

-- ===================================================================
-- 3. Schema Version Update
-- ===================================================================

-- Record migration
INSERT INTO schema_version (version, description, applied_at)
VALUES ('0.61.0', 'Twilio Voice Sessions - Persistent Storage', strftime('%s', 'now') * 1000);
