"""Generated protocol buffer code for voice_worker.proto.

This is a mock implementation for testing purposes.
In production, this file should be generated using:
    python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. voice_worker.proto
"""

# Mock message classes for testing


class CreateSessionRequest:
    """Mock CreateSessionRequest message."""
    def __init__(self, session_id="", project_id="", stt_provider="",
                 tts_provider=None, tts_voice_id=None, tts_speed=None, config=None):
        self.session_id = session_id
        self.project_id = project_id
        self.stt_provider = stt_provider
        self._tts_provider = tts_provider
        self._tts_voice_id = tts_voice_id
        self._tts_speed = tts_speed
        self.config = config or {}

    @property
    def tts_provider(self):
        return self._tts_provider

    @property
    def tts_voice_id(self):
        return self._tts_voice_id

    @property
    def tts_speed(self):
        return self._tts_speed if self._tts_speed is not None else 1.0

    def HasField(self, field):
        """Check if optional field is set."""
        if field == "tts_provider":
            return self._tts_provider is not None
        elif field == "tts_voice_id":
            return self._tts_voice_id is not None
        elif field == "tts_speed":
            return self._tts_speed is not None
        return False


class CreateSessionResponse:
    """Mock CreateSessionResponse message."""
    def __init__(self, session_id="", worker_id="", buffer_size_bytes=0, status=""):
        self.session_id = session_id
        self.worker_id = worker_id
        self.buffer_size_bytes = buffer_size_bytes
        self.status = status


class AudioChunk:
    """Mock AudioChunk message."""
    def __init__(self, session_id="", audio_data=b'', sample_rate=16000,
                 channels=1, timestamp_ms=0, sequence_number=0):
        self.session_id = session_id
        self.audio_data = audio_data
        self.sample_rate = sample_rate
        self.channels = channels
        self.timestamp_ms = timestamp_ms
        self.sequence_number = sequence_number


class AudioEvent:
    """Mock AudioEvent message."""
    def __init__(self, event_type="", session_id="", text=None,
                 audio_data=None, timestamp_ms=0, metadata=None):
        self.event_type = event_type
        self.session_id = session_id
        self._text = text
        self._audio_data = audio_data
        self.timestamp_ms = timestamp_ms
        self.metadata = metadata or {}

    @property
    def text(self):
        return self._text

    @property
    def audio_data(self):
        return self._audio_data

    def HasField(self, field):
        """Check if optional field is set."""
        if field == "text":
            return self._text is not None
        elif field == "audio_data":
            return self._audio_data is not None
        return False


class StopSessionRequest:
    """Mock StopSessionRequest message."""
    def __init__(self, session_id="", reason="", force=False):
        self.session_id = session_id
        self.reason = reason
        self.force = force


class StopSessionResponse:
    """Mock StopSessionResponse message."""
    def __init__(self, session_id="", status="", flushed_bytes=0):
        self.session_id = session_id
        self.status = status
        self.flushed_bytes = flushed_bytes


class HealthCheckRequest:
    """Mock HealthCheckRequest message."""
    def __init__(self, timeout_ms=None):
        self._timeout_ms = timeout_ms

    @property
    def timeout_ms(self):
        return self._timeout_ms

    def HasField(self, field):
        """Check if optional field is set."""
        if field == "timeout_ms":
            return self._timeout_ms is not None
        return False


class HealthCheckResponse:
    """Mock HealthCheckResponse message."""
    def __init__(self, status="", active_sessions=0, memory_usage_bytes=0,
                 uptime_seconds=0, metrics=None):
        self.status = status
        self.active_sessions = active_sessions
        self.memory_usage_bytes = memory_usage_bytes
        self.uptime_seconds = uptime_seconds
        self.metrics = metrics or {}
