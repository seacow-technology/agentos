"""Voice Worker Sidecar - Entry point for standalone Python 3.13 process.

Usage:
    python -m agentos.core.communication.voice.sidecar.main --port 50051

Requirements:
    - Python 3.13
    - faster-whisper
    - grpcio

Environment Variables:
    VOICE_SIDECAR_PORT: gRPC server port (default: 50051)
    VOICE_SIDECAR_LOG_LEVEL: Logging level (default: INFO)
"""

import argparse
import asyncio
import logging
import os
import sys

# Verify Python version
if sys.version_info < (3, 13):
    print(f"❌ Voice Sidecar requires Python 3.13+, got {sys.version_info.major}.{sys.version_info.minor}",
          file=sys.stderr)
    sys.exit(1)

from .worker_service import serve

logger = logging.getLogger(__name__)


def main():
    """Main entry point for voice worker sidecar."""
    parser = argparse.ArgumentParser(description="Voice Worker Sidecar (Python 3.13)")
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("VOICE_SIDECAR_PORT", "50051")),
        help="gRPC server port (default: 50051)"
    )
    parser.add_argument(
        "--log-level",
        default=os.getenv("VOICE_SIDECAR_LOG_LEVEL", "INFO"),
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)"
    )
    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

    logger.info("=" * 60)
    logger.info("Voice Worker Sidecar")
    logger.info("=" * 60)
    logger.info(f"Python version: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    logger.info(f"gRPC port: {args.port}")
    logger.info(f"Log level: {args.log_level}")
    logger.info("=" * 60)

    # Start gRPC server
    try:
        asyncio.run(serve(port=args.port))
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
