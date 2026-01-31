"""
Environment compatibility checker for Voice capability.

Validates that the runtime environment meets Voice requirements before startup.
"""

import logging
import sys
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


def check_python_version() -> Tuple[bool, Optional[str]]:
    """
    Check if Python version is compatible with Voice requirements.

    Returns:
        (is_compatible, reason_code)
        - (True, None) if compatible
        - (False, reason_code) if incompatible
    """
    version_info = sys.version_info

    # Voice requires Python 3.13+
    if version_info < (3, 13):
        return False, "PYTHON_VERSION_TOO_OLD"

    # Python 3.14+ may have dependency issues with onnxruntime
    if version_info >= (3, 14):
        # Try to import onnxruntime to verify compatibility
        try:
            import onnxruntime  # noqa: F401
        except ImportError:
            return False, "PYTHON_314_ONNXRUNTIME_UNAVAILABLE"

    return True, None


def check_voice_dependencies() -> Tuple[bool, Optional[str]]:
    """
    Check if required Voice dependencies are available.

    Returns:
        (is_available, reason_code)
        - (True, None) if all dependencies available
        - (False, reason_code) if missing critical dependency
    """
    missing = []

    try:
        import numpy  # noqa: F401
    except ImportError:
        missing.append("numpy")

    try:
        import webrtcvad  # noqa: F401
    except ImportError:
        missing.append("webrtcvad")

    try:
        from faster_whisper import WhisperModel  # noqa: F401
    except ImportError:
        missing.append("faster-whisper")

    if missing:
        reason_code = f"MISSING_DEPENDENCIES_{'+'.join(missing).replace('-', '_').upper()}"
        return False, reason_code

    return True, None


def check_voice_environment() -> Tuple[bool, Optional[str], str]:
    """
    Perform complete environment check for Voice capability.

    Returns:
        (is_ready, reason_code, message)
        - (True, None, "OK") if environment is ready
        - (False, reason_code, message) if environment has issues
    """
    # Check Python version
    py_ok, py_reason = check_python_version()
    if not py_ok:
        version_str = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

        if py_reason == "PYTHON_VERSION_TOO_OLD":
            return False, py_reason, (
                f"Voice requires Python 3.13+. Current: {version_str}. "
                f"Please upgrade Python or disable Voice capability."
            )
        elif py_reason == "PYTHON_314_ONNXRUNTIME_UNAVAILABLE":
            return False, py_reason, (
                f"Python {version_str} detected. onnxruntime is not available for Python 3.14+. "
                f"Recommended: Use Python 3.13. "
                f"See docs/voice/MVP.md#environment-requirements"
            )

    # Check dependencies
    deps_ok, deps_reason = check_voice_dependencies()
    if not deps_ok:
        return False, deps_reason, (
            f"Voice dependencies missing: {deps_reason}. "
            f"Install with: pip install numpy webrtcvad faster-whisper. "
            f"See docs/voice/MVP.md#quick-start"
        )

    return True, None, "Voice environment check passed"


def log_environment_status():
    """Log Voice environment compatibility status."""
    is_ready, reason_code, message = check_voice_environment()

    if is_ready:
        logger.info(f"✅ Voice environment ready: {message}")
    else:
        logger.warning(
            f"⚠️ Voice environment incompatible: {reason_code} - {message}"
        )

    return is_ready, reason_code, message
