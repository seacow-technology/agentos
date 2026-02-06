-- Schema v65: Channel Messages - Inbound/Outbound Message Audit Trail
-- Task: Wave C2 - Channels Forwarding Real Implementation
--
-- Design Goals:
-- - Complete audit trail for all inbound and outbound channel messages
-- - Support multiple channel types (Twilio SMS, Slack, Discord, etc.)
-- - Link messages to chat sessions for conversation context
-- - Track message delivery status and lifecycle
-- - Enable message history queries and analytics
--
-- References:
-- - agentos/communicationos/channels/sms/adapter.py - SMS channel implementation
-- - agentos/communicationos/channels/whatsapp_twilio.py - WhatsApp channel
-- - agentos/store/migrations/v61_twilio_sessions.sql - Voice session audit trail
--
-- Architecture:
-- - message_id: UUID v7 for time-ordered unique IDs
-- - direction: 'inbound' (received from user) or 'outbound' (sent to user)
-- - channel_type: Provider identifier (twilio_sms, slack, discord, etc.)
-- - channel_id: Specific channel instance (phone number, channel ID, etc.)
-- - status: Message lifecycle (pending → delivered/failed)
-- - timestamps: received_at (inbound), sent_at/delivered_at (outbound)

-- ===================================================================
-- 1. Channel Messages Table - Core Audit Trail
-- ===================================================================

CREATE TABLE IF NOT EXISTS channel_messages (
    -- Identifiers
    message_id TEXT PRIMARY KEY,                  -- UUID v7 format for time-ordered IDs
    channel_type TEXT NOT NULL,                   -- 'twilio_sms', 'slack', 'discord', 'telegram', etc.
    channel_id TEXT NOT NULL,                     -- Channel-specific identifier (phone number, channel ID)

    -- Message flow direction
    direction TEXT NOT NULL,                      -- 'inbound' or 'outbound'

    -- Participants (channel-specific identifiers)
    from_identifier TEXT NOT NULL,                -- Sender identifier (phone number, user_id, username)
    to_identifier TEXT NOT NULL,                  -- Recipient identifier

    -- Content
    content TEXT NOT NULL,                        -- Message text content (may be empty for media-only)
    metadata TEXT,                                -- JSON metadata (attachments, channel-specific fields)

    -- Timestamps (epoch_ms for consistency with v44+)
    received_at INTEGER,                          -- When message was received (for inbound), epoch_ms
    sent_at INTEGER,                              -- When message was sent (for outbound), epoch_ms
    delivered_at INTEGER,                         -- When delivery was confirmed, epoch_ms

    -- Status tracking
    status TEXT NOT NULL DEFAULT 'pending',       -- 'pending', 'delivered', 'failed', 'read'
    error_message TEXT,                           -- Error details if status = 'failed'

    -- Session linking
    session_id TEXT,                              -- Link to chat session (for conversation context)

    -- Audit timestamps
    created_at INTEGER NOT NULL,                  -- Record creation time (epoch_ms)
    updated_at INTEGER NOT NULL,                  -- Last update time (epoch_ms)

    -- Constraints
    CHECK (direction IN ('inbound', 'outbound')),
    CHECK (status IN ('pending', 'delivered', 'failed', 'read')),
    CHECK (
        -- Inbound: received_at is required, sent_at/delivered_at are NULL
        (direction = 'inbound' AND received_at IS NOT NULL AND sent_at IS NULL) OR
        -- Outbound: sent_at is required, received_at is NULL
        (direction = 'outbound' AND sent_at IS NOT NULL AND received_at IS NULL)
    )
);

-- ===================================================================
-- 2. Performance Indexes
-- ===================================================================

-- Primary query: Get messages by channel
CREATE INDEX IF NOT EXISTS idx_channel_messages_channel
    ON channel_messages(channel_type, channel_id, created_at DESC);

-- Session linking: Get all messages for a conversation
CREATE INDEX IF NOT EXISTS idx_channel_messages_session
    ON channel_messages(session_id, created_at DESC)
    WHERE session_id IS NOT NULL;

-- Time-based queries: Recent messages
CREATE INDEX IF NOT EXISTS idx_channel_messages_received
    ON channel_messages(received_at DESC)
    WHERE direction = 'inbound' AND received_at IS NOT NULL;

-- Status tracking: Pending outbound messages (for retry logic)
CREATE INDEX IF NOT EXISTS idx_channel_messages_pending
    ON channel_messages(status, sent_at DESC)
    WHERE direction = 'outbound' AND status = 'pending';

-- User history: All messages for a specific user
CREATE INDEX IF NOT EXISTS idx_channel_messages_user
    ON channel_messages(channel_type, from_identifier, created_at DESC);

-- Analytics: Message counts by channel type
CREATE INDEX IF NOT EXISTS idx_channel_messages_analytics
    ON channel_messages(channel_type, direction, status, created_at);

-- ===================================================================
-- 3. Schema Version Update
-- ===================================================================

-- Record migration
INSERT INTO schema_version (version, description, applied_at)
VALUES ('0.65.0', 'Channel Messages - Inbound/Outbound Audit Trail', strftime('%s', 'now') * 1000);
