-- Migration v0.58.0: Voice Sessions and Transcripts
-- Description: Add persistent storage for voice sessions and transcripts
-- Purpose: Remove in-memory session storage, enable voice session persistence
-- Target: Task #11 (Wave A1) - Voice STT real service integration
--
-- Background:
--   - Previously voice sessions were stored in memory (_sessions dict)
--   - Need persistent storage for production usage
--   - Store session metadata and transcript history
--
-- Tables:
--   1. voice_sessions: Session lifecycle and metadata
--   2. voice_transcripts: Individual transcription records
--
-- target_db: agentos

PRAGMA foreign_keys = OFF;

-- =============================================================================
-- Voice Sessions Table
-- =============================================================================
-- Stores voice session lifecycle and configuration

CREATE TABLE IF NOT EXISTS voice_sessions (
    -- Primary key
    session_id TEXT PRIMARY KEY,

    -- Session configuration
    project_id TEXT,  -- Optional: Link to project context
    provider TEXT NOT NULL,  -- Voice provider: local, openai, azure
    stt_provider TEXT NOT NULL,  -- STT provider: whisper_local, openai, azure, mock

    -- Session state
    state TEXT NOT NULL,  -- ACTIVE, STOPPED, ERROR

    -- Lifecycle timestamps (epoch milliseconds)
    created_at_ms INTEGER NOT NULL,
    updated_at_ms INTEGER NOT NULL,
    stopped_at_ms INTEGER,  -- NULL if not stopped

    -- Session metadata (JSON)
    metadata TEXT,  -- Store additional session data (audio_format, etc.)

    -- Resource tracking
    total_bytes_received INTEGER DEFAULT 0,
    total_transcripts INTEGER DEFAULT 0,

    -- Constraints
    CHECK (state IN ('ACTIVE', 'STOPPED', 'ERROR')),
    CHECK (created_at_ms > 0),
    CHECK (updated_at_ms >= created_at_ms),
    CHECK (stopped_at_ms IS NULL OR stopped_at_ms >= created_at_ms)
);

-- Index for querying active sessions
CREATE INDEX IF NOT EXISTS idx_voice_sessions_state
ON voice_sessions(state, created_at_ms DESC);

-- Index for project-scoped queries
CREATE INDEX IF NOT EXISTS idx_voice_sessions_project
ON voice_sessions(project_id, created_at_ms DESC)
WHERE project_id IS NOT NULL;


-- =============================================================================
-- Voice Transcripts Table
-- =============================================================================
-- Stores individual transcription records for each session

CREATE TABLE IF NOT EXISTS voice_transcripts (
    -- Primary key
    id TEXT PRIMARY KEY,

    -- Foreign key to session
    session_id TEXT NOT NULL,

    -- Transcription data
    transcript TEXT NOT NULL,  -- Transcribed text
    confidence REAL,  -- Confidence score (0.0 - 1.0), NULL if not available
    language TEXT,  -- Detected or specified language code

    -- Timing
    audio_timestamp_ms INTEGER NOT NULL,  -- Client-side audio timestamp
    created_at_ms INTEGER NOT NULL,  -- Server-side creation timestamp

    -- Audio metadata
    audio_duration_ms INTEGER,  -- Duration of audio segment
    audio_bytes INTEGER,  -- Size of audio data

    -- Provider info
    provider TEXT,  -- STT provider used for this transcript

    -- Constraints
    FOREIGN KEY (session_id) REFERENCES voice_sessions(session_id) ON DELETE CASCADE,
    CHECK (confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)),
    CHECK (audio_timestamp_ms >= 0),
    CHECK (created_at_ms > 0),
    CHECK (audio_duration_ms IS NULL OR audio_duration_ms >= 0),
    CHECK (audio_bytes IS NULL OR audio_bytes >= 0)
);

-- Index for session-based transcript queries
CREATE INDEX IF NOT EXISTS idx_voice_transcripts_session
ON voice_transcripts(session_id, audio_timestamp_ms ASC);

-- Index for time-based queries
CREATE INDEX IF NOT EXISTS idx_voice_transcripts_created
ON voice_transcripts(created_at_ms DESC);


-- =============================================================================
-- Update Schema Version
-- =============================================================================

PRAGMA foreign_keys = ON;

INSERT OR REPLACE INTO schema_version (version, applied_at_ms, description)
VALUES ('0.58.0', (strftime('%s', 'now') * 1000), 'Voice Sessions and Transcripts');
