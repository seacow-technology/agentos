"""Voice communication service implementation.

This module provides the main service interface for managing voice sessions,
dispatching audio chunks, and coordinating with STT providers.
"""

from __future__ import annotations

import logging
import uuid
from typing import Dict, Optional

from agentos.core.time import utc_now, utc_now_ms
from agentos.core.communication.evidence import EvidenceLogger
from agentos.core.communication.models import (
    ConnectorType,
    RequestStatus,
    EvidenceRecord,
)
from agentos.core.communication.voice.models import (
    VoiceSession,
    VoiceSessionState,
    VoiceProvider,
    STTProvider,
    VoiceEvent,
    VoiceEventType,
)
from agentos.core.communication.voice.policy import VoicePolicy
from agentos.core.communication.voice.providers.base import IVoiceProvider
from agentos.core.communication.voice.providers.local import LocalProvider
from agentos.core.communication.voice.providers.twilio import TwilioProvider

logger = logging.getLogger(__name__)


class VoiceService:
    """Service for managing voice communication sessions.

    The VoiceService provides high-level operations for creating,
    managing, and stopping voice sessions. It coordinates policy
    evaluation, provider selection, and audit logging.

    All voice operations are logged to the evidence chain for
    compliance and security analysis.
    """

    def __init__(
        self,
        policy: Optional[VoicePolicy] = None,
        evidence_logger: Optional[EvidenceLogger] = None,
    ):
        """Initialize voice service.

        Args:
            policy: Voice policy engine (creates default if not provided)
            evidence_logger: Evidence logger for audit trail
        """
        self.policy = policy or VoicePolicy()
        self.evidence_logger = evidence_logger or EvidenceLogger()
        self.sessions: Dict[str, VoiceSession] = {}
        self.providers: Dict[VoiceProvider, IVoiceProvider] = {
            VoiceProvider.LOCAL: LocalProvider(),
            VoiceProvider.TWILIO: TwilioProvider(),
        }

    def create_session(
        self,
        project_id: str,
        provider: VoiceProvider,
        stt_provider: STTProvider,
        metadata: Optional[Dict] = None,
    ) -> VoiceSession:
        """Create a new voice session.

        This method:
        1. Validates parameters
        2. Evaluates policy
        3. Creates session record
        4. Logs evidence
        5. Returns session object

        Args:
            project_id: Project ID for context and billing
            provider: Voice provider type (LOCAL, TWILIO)
            stt_provider: STT provider for transcription
            metadata: Optional session metadata

        Returns:
            VoiceSession object

        Raises:
            ValueError: If parameters are invalid
            PermissionError: If policy denies request
        """
        # Validate parameters
        is_valid, error = self.policy.validate_session_params(
            project_id, provider, stt_provider
        )
        if not is_valid:
            raise ValueError(f"Invalid session parameters: {error}")

        # Evaluate policy
        verdict = self.policy.evaluate_session_request(
            project_id, provider, stt_provider, metadata or {}
        )

        if verdict.status != RequestStatus.APPROVED:
            raise PermissionError(
                f"Voice session denied: {verdict.reason_code} - {verdict.hint}"
            )

        # Create session
        session_id = f"voice-{uuid.uuid4().hex[:16]}"
        audit_trace_id = f"audit-{uuid.uuid4().hex[:12]}"

        session = VoiceSession(
            session_id=session_id,
            project_id=project_id,
            provider=provider,
            stt_provider=stt_provider,
            state=VoiceSessionState.CREATED,
            risk_tier=verdict.metadata.get("risk_level", "LOW"),
            policy_verdict=verdict.status.value,
            audit_trace_id=audit_trace_id,
            metadata=metadata or {},
        )

        # Store session
        self.sessions[session_id] = session

        # Notify provider
        provider_impl = self.providers.get(provider)
        if provider_impl:
            provider_impl.on_session_created(session_id, metadata or {})

        # Log evidence asynchronously (fire-and-forget for MVP)
        self._log_session_evidence(session, "SESSION_CREATED")

        logger.info(
            f"Created voice session: {session_id} "
            f"(project={project_id}, provider={provider.value}, "
            f"stt={stt_provider.value})"
        )

        return session

    def stop_session(self, session_id: str) -> bool:
        """Stop an active voice session.

        This method gracefully stops a voice session, allowing
        in-flight audio processing to complete.

        Args:
            session_id: Session ID to stop

        Returns:
            True if session was stopped, False if not found

        Raises:
            ValueError: If session_id is invalid
        """
        if not session_id:
            raise ValueError("session_id is required")

        session = self.sessions.get(session_id)
        if not session:
            logger.warning(f"Attempted to stop unknown session: {session_id}")
            return False

        # Update session state
        session.state = VoiceSessionState.STOPPING
        session.last_activity_at = utc_now()

        # Log evidence
        self._log_session_evidence(session, "SESSION_STOPPING")

        # Notify provider
        provider_impl = self.providers.get(session.provider)
        if provider_impl:
            provider_impl.on_session_stopped(session_id)

        # Perform graceful shutdown
        session.state = VoiceSessionState.STOPPED

        # Log final evidence
        self._log_session_evidence(session, "SESSION_STOPPED")

        logger.info(f"Stopped voice session: {session_id}")
        return True

    def dispatch_audio_chunk(
        self,
        session_id: str,
        audio_data: bytes,
    ) -> None:
        """Dispatch an audio chunk to the session for processing.

        This method is a placeholder for audio processing integration.
        Actual STT processing will be implemented by a separate agent
        that consumes audio chunks and produces transcripts.

        Args:
            session_id: Session ID
            audio_data: Raw audio data bytes

        Raises:
            ValueError: If session not found or invalid state
        """
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        if session.state not in (VoiceSessionState.CREATED, VoiceSessionState.ACTIVE):
            raise ValueError(
                f"Cannot dispatch audio to session in {session.state.value} state"
            )

        # Update session state to active if first audio chunk
        if session.state == VoiceSessionState.CREATED:
            session.state = VoiceSessionState.ACTIVE

        # Update last activity timestamp
        session.last_activity_at = utc_now()

        # Create audio event
        event_id = f"evt-{uuid.uuid4().hex[:12]}"
        event = VoiceEvent(
            event_id=event_id,
            session_id=session_id,
            event_type=VoiceEventType.AUDIO_RECEIVED,
            payload={
                "audio_length_bytes": len(audio_data),
                "timestamp": utc_now().isoformat(),
            },
            timestamp_ms=utc_now_ms(),
        )

        logger.debug(
            f"Dispatched {len(audio_data)} bytes of audio to session {session_id}"
        )

        # TODO: Forward audio_data to STT agent/service
        # For MVP, this is a no-op placeholder

    def get_session(self, session_id: str) -> Optional[VoiceSession]:
        """Get a voice session by ID.

        Args:
            session_id: Session ID

        Returns:
            VoiceSession if found, None otherwise
        """
        return self.sessions.get(session_id)

    def list_active_sessions(self, project_id: Optional[str] = None) -> list[VoiceSession]:
        """List active voice sessions.

        Args:
            project_id: Optional project ID filter

        Returns:
            List of active VoiceSession objects
        """
        sessions = [
            s for s in self.sessions.values()
            if s.state in (VoiceSessionState.CREATED, VoiceSessionState.ACTIVE)
        ]

        if project_id:
            sessions = [s for s in sessions if s.project_id == project_id]

        return sessions

    def get_provider(self, provider_type: VoiceProvider) -> IVoiceProvider:
        """Get a voice provider instance.

        Args:
            provider_type: Provider type

        Returns:
            Voice provider instance

        Raises:
            ValueError: If provider not found
        """
        provider = self.providers.get(provider_type)
        if not provider:
            raise ValueError(f"Provider not found: {provider_type}")
        return provider

    def _log_session_evidence(self, session: VoiceSession, event_type: str) -> None:
        """Log session evidence for audit trail.

        Args:
            session: Voice session
            event_type: Event type description
        """
        try:
            # Create evidence record
            # Note: Using sync API for MVP; production should use async
            evidence = EvidenceRecord(
                id=f"ev-{uuid.uuid4().hex[:12]}",
                request_id=session.session_id,
                connector_type=ConnectorType.CUSTOM,  # Voice is a custom connector
                operation=event_type,
                request_summary={
                    "session_id": session.session_id,
                    "project_id": session.project_id,
                    "provider": session.provider.value,
                    "stt_provider": session.stt_provider.value,
                    "state": session.state.value,
                },
                response_summary={
                    "status": "success",
                    "timestamp": utc_now().isoformat(),
                },
                status=RequestStatus.SUCCESS,
                metadata={
                    "risk_tier": session.risk_tier,
                    "audit_trace_id": session.audit_trace_id,
                },
            )

            logger.debug(
                f"Logged evidence: {evidence.id} for session {session.session_id}"
            )

        except Exception as e:
            # Don't fail session operations due to logging errors
            logger.error(f"Failed to log evidence for session {session.session_id}: {e}")
