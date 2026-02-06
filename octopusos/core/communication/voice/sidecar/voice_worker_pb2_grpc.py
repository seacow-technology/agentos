"""Generated gRPC service code for voice_worker.proto.

This is a mock implementation for testing purposes.
In production, this file should be generated using:
    python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. voice_worker.proto
"""

# Mock gRPC service classes for testing


class VoiceWorkerServicer:
    """Base class for VoiceWorker service implementation."""

    async def CreateSession(self, request, context):
        """Create a new voice session."""
        raise NotImplementedError("Method not implemented!")

    async def ProcessAudio(self, request_iterator, context):
        """Process audio stream."""
        raise NotImplementedError("Method not implemented!")

    async def StopSession(self, request, context):
        """Stop a voice session."""
        raise NotImplementedError("Method not implemented!")

    async def HealthCheck(self, request, context):
        """Health check."""
        raise NotImplementedError("Method not implemented!")


class VoiceWorkerStub:
    """Mock client stub for VoiceWorker service."""

    def __init__(self, channel):
        """Initialize stub with gRPC channel."""
        self.channel = channel

    async def CreateSession(self, request, timeout=None):
        """Create session RPC."""
        raise NotImplementedError("Mock stub - not implemented")

    async def ProcessAudio(self, request_iterator, timeout=None):
        """Process audio RPC."""
        raise NotImplementedError("Mock stub - not implemented")

    async def StopSession(self, request, timeout=None):
        """Stop session RPC."""
        raise NotImplementedError("Mock stub - not implemented")

    async def HealthCheck(self, request, timeout=None):
        """Health check RPC."""
        raise NotImplementedError("Mock stub - not implemented")


def add_VoiceWorkerServicer_to_server(servicer, server):
    """Add VoiceWorker servicer to gRPC server."""
    # Mock implementation for testing
    pass
