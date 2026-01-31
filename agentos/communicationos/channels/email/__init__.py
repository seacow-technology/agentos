"""Email Channel for AgentOS CommunicationOS.

This module provides email communication capabilities through multiple providers:
- Gmail with OAuth 2.0 (recommended for Gmail/Google Workspace)
- Outlook with OAuth 2.0 (recommended for Outlook/Microsoft 365)
- Generic SMTP/IMAP (works with any email provider)

Key Features:
- Thread-aware conversation tracking using RFC 5322 headers
- Polling mode for asynchronous message retrieval
- Support for HTML and plain text messages
- Attachment support (future enhancement)
- Proper Reply-To and References header handling

Architecture:
    EmailAdapter (adapter.py):
        - Implements ChannelAdapter protocol
        - Converts EmailEnvelope to InboundMessage
        - Converts OutboundMessage to email send requests
        - Manages polling loop and message deduplication

    IEmailProvider (providers/email/__init__.py):
        - Protocol interface for email providers
        - Implemented by GmailProvider, OutlookProvider, SmtpImapProvider

Threading Model:
    Email threads are tracked using Message-ID, References, and In-Reply-To headers.
    Each thread root becomes a unique conversation_key, allowing multiple parallel
    conversations with the same user.

    Example:
        User sends: "Question about pricing" → conversation_key: msg-001@example.com
        Agent replies: "We have three tiers..." → conversation_key: msg-001@example.com (same)
        User follows up: "Tell me more..." → conversation_key: msg-001@example.com (same)
        User starts NEW email: "Another topic" → conversation_key: msg-999@example.com (different)

Session Scope:
    session_scope = "user_conversation"
    - user_key: Sender email address (normalized to lowercase)
    - conversation_key: Thread root Message-ID (from References or In-Reply-To)
    - message_id: RFC 5322 Message-ID with "email_" prefix

See Also:
    - KEY_MAPPING_RULES.md: Detailed explanation of conversation threading
    - manifest.json: Channel configuration and setup instructions
    - providers/email/__init__.py: Provider protocol and data models
"""

from __future__ import annotations

from agentos.communicationos.channels.email.adapter import EmailAdapter, CursorStore

__all__ = ["EmailAdapter", "CursorStore"]
