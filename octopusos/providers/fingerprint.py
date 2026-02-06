"""
Provider Fingerprint Detection

Identifies provider services by protocol fingerprints rather than port numbers.

Two-layer detection:
- Layer A: Port availability (TCP/HTTP ping)
- Layer B: Service fingerprint (protocol-specific probe)

Sprint B+ Provider Architecture Refactor
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from enum import Enum

import httpx

logger = logging.getLogger(__name__)


class FingerprintResult(str, Enum):
    """Fingerprint detection results"""
    OLLAMA = "ollama"
    LMSTUDIO = "lmstudio"  # Or generic OpenAI-compatible
    LLAMACPP = "llamacpp"
    OPENAI_COMPATIBLE = "openai_compatible"  # Generic OpenAI API
    UNKNOWN = "unknown"
    NO_SERVICE = "no_service"
    ERROR = "error"


async def probe_port(endpoint: str, timeout: float = 1.0) -> bool:
    """
    Layer A: Check if port has service listening

    Fast TCP/HTTP connectivity check
    """
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            # Try HEAD request first (fastest)
            response = await client.head(endpoint, follow_redirects=False)
            return True
    except httpx.ConnectError:
        return False
    except httpx.TimeoutException:
        return False
    except Exception as e:
        logger.debug(f"Port probe error for {endpoint}: {e}")
        return False


async def fingerprint_ollama(endpoint: str, timeout: float = 1.5) -> tuple[bool, Optional[Dict[str, Any]]]:
    """
    Detect Ollama service (STRONG fingerprint)

    Fingerprint: GET /api/tags returns JSON with 'models' field
    BUT must exclude llama-server which also implements this endpoint

    llama-server distinguishing features:
    - /api/tags contains "owned_by": "llamacpp" in data array
    - /health endpoint exists
    """
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(f"{endpoint}/api/tags")

            if response.status_code == 200:
                data = response.json()

                # Check basic structure
                if not isinstance(data, dict) or "models" not in data:
                    return False, None

                # CRITICAL: Exclude llama-server pretending to be Ollama
                # llama-server adds "data" array with "owned_by": "llamacpp"
                if "data" in data and isinstance(data["data"], list):
                    for item in data["data"]:
                        if isinstance(item, dict) and item.get("owned_by") == "llamacpp":
                            # This is llama-server, NOT Ollama
                            logger.debug(f"Rejected Ollama fingerprint: found llamacpp ownership")
                            return False, None

                # Also check if /health exists (llama-server specific)
                try:
                    health_resp = await client.get(f"{endpoint}/health", timeout=0.5)
                    if health_resp.status_code == 200:
                        logger.debug(f"Rejected Ollama fingerprint: /health endpoint exists")
                        return False, None
                except:
                    pass

                # Passed all checks - this is genuine Ollama
                return True, {"models_count": len(data.get("models", []))}

    except Exception as e:
        logger.debug(f"Ollama fingerprint failed for {endpoint}: {e}")

    return False, None


async def fingerprint_openai_compatible(endpoint: str, timeout: float = 1.5) -> tuple[bool, Optional[Dict[str, Any]]]:
    """
    Detect OpenAI-compatible service (LM Studio, llama.cpp with OpenAI compat, etc.)

    Fingerprint: GET /v1/models returns JSON with 'data' array (OpenAI schema)
    """
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(f"{endpoint}/v1/models")

            if response.status_code == 200:
                data = response.json()
                # OpenAI schema: {"object": "list", "data": [...]}
                if isinstance(data, dict) and "data" in data:
                    models_data = data.get("data", [])
                    return True, {
                        "models_count": len(models_data),
                        "object": data.get("object"),
                    }
    except Exception as e:
        logger.debug(f"OpenAI-compatible fingerprint failed for {endpoint}: {e}")

    return False, None


async def fingerprint_llamacpp_native(endpoint: str, timeout: float = 1.5) -> tuple[bool, Optional[Dict[str, Any]]]:
    """
    Detect native llama.cpp server (llama-server)

    Multi-candidate probe:
    - GET /health
    - GET / (root might return server info)
    - Check Server header
    """
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            # Try /health endpoint
            try:
                response = await client.get(f"{endpoint}/health")
                if response.status_code == 200:
                    # llama-server health endpoint exists
                    return True, {"endpoint": "/health"}
            except:
                pass

            # Try root endpoint
            try:
                response = await client.get(f"{endpoint}/")
                if response.status_code in [200, 404]:
                    # Check Server header
                    server_header = response.headers.get("server", "").lower()
                    if "llama" in server_header or "cpp" in server_header:
                        return True, {"server_header": server_header}

                    # Some llama-server return HTML with specific markers
                    content = response.text.lower()
                    if "llama" in content or "completion" in content:
                        return True, {"endpoint": "/"}
            except:
                pass

    except Exception as e:
        logger.debug(f"llama.cpp native fingerprint failed for {endpoint}: {e}")

    return False, None


async def detect_service_fingerprint(endpoint: str, timeout: float = 1.5) -> tuple[FingerprintResult, Optional[Dict[str, Any]]]:
    """
    Layer B: Identify service by fingerprint

    Returns (fingerprint_result, metadata)

    Priority order (FIXED for llama-server detection):
    1. Ollama (most specific, with llama-server exclusion)
    2. llama.cpp native (check /health first - strongest discriminator)
    3. OpenAI-compatible (fallback for LM Studio)
    4. Unknown (service exists but unrecognized)

    CRITICAL: llama-server implements both /health AND /v1/models,
    so we must check native features BEFORE OpenAI-compatible.
    """
    # Check if port has service first
    has_service = await probe_port(endpoint, timeout=timeout * 0.5)
    if not has_service:
        return FingerprintResult.NO_SERVICE, None

    # Try fingerprints in priority order

    # 1. Ollama (with strong exclusion of llama-server)
    is_ollama, ollama_meta = await fingerprint_ollama(endpoint, timeout)
    if is_ollama:
        return FingerprintResult.OLLAMA, ollama_meta

    # 2. Native llama.cpp (BEFORE OpenAI check!)
    # This catches llama-server which has /health endpoint
    is_llamacpp, llamacpp_meta = await fingerprint_llamacpp_native(endpoint, timeout)
    if is_llamacpp:
        return FingerprintResult.LLAMACPP, llamacpp_meta

    # 3. OpenAI-compatible (LM Studio, or other OpenAI-compatible servers)
    # Only reaches here if /health doesn't exist
    is_openai, openai_meta = await fingerprint_openai_compatible(endpoint, timeout)
    if is_openai:
        return FingerprintResult.OPENAI_COMPATIBLE, openai_meta

    # Service exists but unrecognized
    return FingerprintResult.UNKNOWN, {"note": "Service responded but fingerprint unrecognized"}


async def verify_expected_fingerprint(
    endpoint: str,
    expected: FingerprintResult,
    timeout: float = 1.5,
) -> tuple[bool, FingerprintResult, Optional[Dict[str, Any]]]:
    """
    Verify if endpoint matches expected provider fingerprint

    Returns:
        (matches, detected_fingerprint, metadata)

    Use this in Provider.probe() to validate the service identity
    """
    detected, metadata = await detect_service_fingerprint(endpoint, timeout)

    # Special handling for OpenAI-compatible
    # Both LM Studio and llama.cpp (OpenAI mode) will show as OPENAI_COMPATIBLE
    if expected == FingerprintResult.LMSTUDIO and detected == FingerprintResult.OPENAI_COMPATIBLE:
        matches = True
    elif expected == FingerprintResult.LLAMACPP and detected == FingerprintResult.OPENAI_COMPATIBLE:
        matches = True
    else:
        matches = (detected == expected)

    return matches, detected, metadata
