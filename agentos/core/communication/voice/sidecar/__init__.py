"""Voice Worker Sidecar - Python 3.13 compatible voice processing service.

This package contains the gRPC-based voice processing sidecar that runs
in a separate Python 3.13 process to maintain compatibility with libraries
like faster-whisper.

Architecture:
- Main process (Python 3.14): gRPC client
- Sidecar process (Python 3.13): gRPC server + Whisper + TTS

Communication:
- Bidirectional gRPC streaming for low-latency audio processing
- Health checks every 10 seconds
- Automatic fallback to embedded mode on failure
"""

__all__ = []
