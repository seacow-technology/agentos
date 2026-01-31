"""Voice Worker gRPC Client - Runs in Python 3.14 main process.

This client communicates with the Voice Worker Sidecar (Python 3.13) via gRPC
to perform voice processing while maintaining main process compatibility.

Features:
- Automatic sidecar process management (start/stop)
- Health check monitoring (every 10 seconds)
- Automatic fallback to embedded mode on failure
- Graceful shutdown
"""

import asyncio
import logging
import os
import signal
import subprocess
import time
from typing import AsyncIterator, Dict, Optional

import grpc

# Import generated gRPC stubs
try:
    from .sidecar import voice_worker_pb2, voice_worker_pb2_grpc
except ImportError:
    # Try alternative import path
    from agentos.core.communication.voice.sidecar import voice_worker_pb2, voice_worker_pb2_grpc

logger = logging.getLogger(__name__)


class VoiceWorkerClient:
    """gRPC client for communicating with Voice Worker Sidecar."""

    def __init__(
        self,
        python_path: str = "python3.13",
        port: int = 50051,
        auto_start: bool = True,
        fallback_to_embedded: bool = True
    ):
        """Initialize voice worker client.

        Args:
            python_path: Path to Python 3.13 executable
            port: gRPC server port
            auto_start: Automatically start sidecar if not running
            fallback_to_embedded: Fall back to embedded mode on sidecar failure
        """
        self.python_path = python_path
        self.port = port
        self.auto_start = auto_start
        self.fallback_to_embedded = fallback_to_embedded

        self.sidecar_process: Optional[subprocess.Popen] = None
        self.channel: Optional[grpc.aio.Channel] = None
        self.stub: Optional[voice_worker_pb2_grpc.VoiceWorkerStub] = None
        self.health_check_task: Optional[asyncio.Task] = None
        self.is_healthy = False

    async def start(self):
        """Start sidecar and connect gRPC channel."""
        if self.auto_start:
            await self._start_sidecar()

        # Connect to sidecar
        await self._connect()

        # Start health check loop
        self.health_check_task = asyncio.create_task(self._health_check_loop())

        logger.info("VoiceWorkerClient started successfully")

    async def _start_sidecar(self):
        """Start sidecar subprocess."""
        if self.sidecar_process is not None:
            logger.warning("Sidecar already running")
            return

        # Check if Python 3.13 is available
        try:
            result = subprocess.run(
                [self.python_path, "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode != 0:
                raise FileNotFoundError(f"Python 3.13 not found at {self.python_path}")

            logger.info(f"Found Python: {result.stdout.strip()}")
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            logger.error(f"Failed to find Python 3.13: {e}")
            if self.fallback_to_embedded:
                logger.warning("Will fall back to embedded mode")
                return
            raise

        # Start sidecar process
        cmd = [
            self.python_path,
            "-m",
            "agentos.core.communication.voice.sidecar.main",
            "--port",
            str(self.port),
        ]

        logger.info(f"Starting sidecar: {' '.join(cmd)}")

        try:
            self.sidecar_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid if hasattr(os, "setsid") else None
            )

            # Wait for sidecar to be ready
            await self._wait_for_ready(timeout_seconds=10)

            logger.info(f"Sidecar started (PID={self.sidecar_process.pid})")

        except Exception as e:
            logger.error(f"Failed to start sidecar: {e}", exc_info=True)
            if self.sidecar_process:
                self.sidecar_process.kill()
                self.sidecar_process = None

            if self.fallback_to_embedded:
                logger.warning("Will fall back to embedded mode")
                return
            raise

    async def _wait_for_ready(self, timeout_seconds: int = 10):
        """Wait for sidecar to be ready to accept connections."""
        start_time = time.time()

        while time.time() - start_time < timeout_seconds:
            try:
                # Try to connect
                channel = grpc.aio.insecure_channel(f"localhost:{self.port}")
                stub = voice_worker_pb2_grpc.VoiceWorkerStub(channel)

                # Call health check
                response = await stub.HealthCheck(
                    voice_worker_pb2.HealthCheckRequest(),
                    timeout=1
                )

                if response.status in ("OK", "DEGRADED"):
                    await channel.close()
                    logger.info(f"Sidecar ready (status={response.status})")
                    return

                await channel.close()

            except grpc.aio.AioRpcError:
                pass
            except Exception as e:
                logger.debug(f"Waiting for sidecar: {e}")

            await asyncio.sleep(0.5)

        raise TimeoutError(f"Sidecar not ready after {timeout_seconds}s")

    async def _connect(self):
        """Connect to sidecar gRPC server."""
        if self.channel is not None:
            logger.warning("Already connected")
            return

        self.channel = grpc.aio.insecure_channel(f"localhost:{self.port}")
        self.stub = voice_worker_pb2_grpc.VoiceWorkerStub(self.channel)

        logger.info(f"Connected to sidecar at localhost:{self.port}")

    async def _health_check_loop(self):
        """Periodically check sidecar health."""
        while True:
            try:
                await asyncio.sleep(10)

                if self.stub is None:
                    self.is_healthy = False
                    continue

                response = await self.stub.HealthCheck(
                    voice_worker_pb2.HealthCheckRequest(),
                    timeout=5
                )

                if response.status == "OK":
                    self.is_healthy = True
                elif response.status == "DEGRADED":
                    self.is_healthy = True
                    logger.warning(f"Sidecar health degraded: {response.metrics}")
                else:
                    self.is_healthy = False
                    logger.error(f"Sidecar unhealthy: {response.status}")

            except grpc.aio.AioRpcError as e:
                self.is_healthy = False
                logger.error(f"Health check failed: {e.code()}")
            except Exception as e:
                self.is_healthy = False
                logger.error(f"Health check error: {e}", exc_info=True)

    async def create_session(
        self,
        session_id: str,
        project_id: str,
        stt_provider: str,
        tts_provider: Optional[str] = None,
        tts_voice_id: Optional[str] = None,
        tts_speed: float = 1.0,
        config: Optional[Dict[str, str]] = None
    ) -> Dict:
        """Create a voice session in the sidecar.

        Args:
            session_id: Unique session identifier
            project_id: Project ID
            stt_provider: STT provider (whisper_local, google, etc.)
            tts_provider: Optional TTS provider (openai, elevenlabs, etc.)
            tts_voice_id: Optional TTS voice ID
            tts_speed: TTS speed multiplier (0.25 - 4.0)
            config: Additional configuration

        Returns:
            Session creation response as dict

        Raises:
            grpc.aio.AioRpcError: If sidecar is unavailable or session creation fails
        """
        if self.stub is None:
            raise RuntimeError("Not connected to sidecar")

        request = voice_worker_pb2.CreateSessionRequest(
            session_id=session_id,
            project_id=project_id,
            stt_provider=stt_provider,
            config=config or {}
        )

        if tts_provider:
            request.tts_provider = tts_provider
        if tts_voice_id:
            request.tts_voice_id = tts_voice_id
        if tts_speed != 1.0:
            request.tts_speed = tts_speed

        response = await self.stub.CreateSession(request, timeout=10)

        return {
            "session_id": response.session_id,
            "worker_id": response.worker_id,
            "buffer_size_bytes": response.buffer_size_bytes,
            "status": response.status,
        }

    async def process_audio_stream(
        self,
        session_id: str,
        audio_iterator: AsyncIterator[bytes]
    ) -> AsyncIterator[Dict]:
        """Process audio stream through sidecar (bidirectional).

        Args:
            session_id: Session ID
            audio_iterator: Async iterator yielding audio chunks (bytes)

        Yields:
            Audio events (STT results, TTS chunks, etc.) as dicts
        """
        if self.stub is None:
            raise RuntimeError("Not connected to sidecar")

        async def generate_audio_chunks():
            """Convert audio bytes to AudioChunk messages."""
            sequence = 0
            async for audio_data in audio_iterator:
                yield voice_worker_pb2.AudioChunk(
                    session_id=session_id,
                    audio_data=audio_data,
                    sample_rate=16000,  # Default to 16kHz
                    channels=1,
                    timestamp_ms=int(time.time() * 1000),
                    sequence_number=sequence
                )
                sequence += 1

        # Bidirectional streaming
        async for event in self.stub.ProcessAudio(generate_audio_chunks()):
            yield {
                "event_type": event.event_type,
                "session_id": event.session_id,
                "text": event.text if event.HasField("text") else None,
                "audio_data": event.audio_data if event.HasField("audio_data") else None,
                "timestamp_ms": event.timestamp_ms,
                "metadata": dict(event.metadata),
            }

    async def stop_session(self, session_id: str, reason: str = "user_requested", force: bool = False):
        """Stop a voice session in the sidecar.

        Args:
            session_id: Session ID to stop
            reason: Reason for stopping
            force: Whether to force immediate stop (skip buffer flush)

        Returns:
            Stop response as dict
        """
        if self.stub is None:
            raise RuntimeError("Not connected to sidecar")

        response = await self.stub.StopSession(
            voice_worker_pb2.StopSessionRequest(
                session_id=session_id,
                reason=reason,
                force=force
            ),
            timeout=5
        )

        return {
            "session_id": response.session_id,
            "status": response.status,
            "flushed_bytes": response.flushed_bytes,
        }

    async def stop(self):
        """Stop client and sidecar."""
        logger.info("Stopping VoiceWorkerClient...")

        # Cancel health check task
        if self.health_check_task:
            self.health_check_task.cancel()
            try:
                await self.health_check_task
            except asyncio.CancelledError:
                pass

        # Close gRPC channel
        if self.channel:
            await self.channel.close()
            self.channel = None
            self.stub = None

        # Stop sidecar process
        if self.sidecar_process:
            logger.info(f"Stopping sidecar (PID={self.sidecar_process.pid})...")
            try:
                # Send SIGTERM for graceful shutdown
                if hasattr(os, "killpg"):
                    os.killpg(os.getpgid(self.sidecar_process.pid), signal.SIGTERM)
                else:
                    self.sidecar_process.terminate()

                # Wait up to 5 seconds for graceful shutdown
                try:
                    self.sidecar_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    logger.warning("Sidecar did not stop gracefully, killing...")
                    self.sidecar_process.kill()
                    self.sidecar_process.wait()

                logger.info("Sidecar stopped")
            except Exception as e:
                logger.error(f"Error stopping sidecar: {e}", exc_info=True)
            finally:
                self.sidecar_process = None

        logger.info("VoiceWorkerClient stopped")
