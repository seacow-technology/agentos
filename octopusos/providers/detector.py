"""
Local Provider Detector - Detect local model environments
"""

import shutil
import asyncio
import httpx
from typing import Dict, Any, List
from dataclasses import dataclass


@dataclass
class DetectionResult:
    """Detection result for a local provider"""
    id: str
    cli_found: bool
    service_reachable: bool
    endpoint: str
    models_count: int
    details: Dict[str, Any]
    state: str
    hint: str | None = None


class LocalProviderDetector:
    """Detect local model provider environments"""

    @staticmethod
    async def detect_ollama() -> DetectionResult:
        """Detect Ollama environment"""
        endpoint = "http://127.0.0.1:11434"

        # Check CLI
        cli_found = shutil.which("ollama") is not None

        # Check service
        service_reachable = False
        models_count = 0
        details = {}
        state = "DISCONNECTED"
        hint = None

        try:
            async with httpx.AsyncClient(timeout=1.5) as client:
                # Check tags endpoint
                response = await client.get(f"{endpoint}/api/tags")
                if response.status_code == 200:
                    service_reachable = True
                    data = response.json()
                    models_count = len(data.get("models", []))

                    # Try to get version
                    try:
                        version_response = await client.get(f"{endpoint}/api/version")
                        if version_response.status_code == 200:
                            details["version"] = version_response.json().get("version", "unknown")
                    except Exception:
                        pass

                    state = "READY"
                    hint = None if models_count > 0 else "Ollama is running but no models installed. Run: ollama pull <model>"

        except httpx.ConnectError:
            if cli_found:
                state = "DISCONNECTED"
                hint = "Ollama CLI found but service not running. Run: ollama serve"
            else:
                state = "DISCONNECTED"
                hint = "Ollama not installed. Visit: https://ollama.ai/download"
        except Exception as e:
            state = "ERROR"
            hint = f"Error detecting Ollama: {str(e)}"

        return DetectionResult(
            id="ollama",
            cli_found=cli_found,
            service_reachable=service_reachable,
            endpoint=endpoint,
            models_count=models_count,
            details=details,
            state=state,
            hint=hint,
        )

    @staticmethod
    async def detect_lmstudio(endpoint: str = "http://127.0.0.1:1234") -> DetectionResult:
        """Detect LM Studio environment"""
        # LM Studio is GUI-based, no CLI to check
        cli_found = False

        service_reachable = False
        models_count = 0
        details = {}
        state = "DISCONNECTED"
        hint = None

        try:
            async with httpx.AsyncClient(timeout=1.5) as client:
                # Check OpenAI-compatible models endpoint
                response = await client.get(f"{endpoint}/v1/models")
                if response.status_code == 200:
                    service_reachable = True
                    data = response.json()
                    models_count = len(data.get("data", []))

                    state = "READY"
                    hint = None if models_count > 0 else "LM Studio server running but no model loaded"

        except httpx.ConnectError:
            state = "DISCONNECTED"
            hint = "Open LM Studio → Local Server → Start, then verify endpoint /v1/models"
        except Exception as e:
            state = "ERROR"
            hint = f"Error detecting LM Studio: {str(e)}"

        return DetectionResult(
            id="lmstudio",
            cli_found=cli_found,
            service_reachable=service_reachable,
            endpoint=endpoint,
            models_count=models_count,
            details=details,
            state=state,
            hint=hint,
        )

    @staticmethod
    async def detect_llamacpp(endpoint: str = "http://127.0.0.1:8080") -> DetectionResult:
        """Detect llama.cpp environment"""
        # Check for llama-server binary
        cli_found = shutil.which("llama-server") is not None

        service_reachable = False
        models_count = 0
        details = {}
        state = "DISCONNECTED"
        hint = None

        try:
            async with httpx.AsyncClient(timeout=1.5) as client:
                # Try OpenAI-compatible endpoint first
                try:
                    response = await client.get(f"{endpoint}/v1/models")
                    if response.status_code == 200:
                        service_reachable = True
                        data = response.json()
                        models_count = len(data.get("data", []))
                        state = "READY"
                        hint = None
                        return DetectionResult(
                            id="llamacpp",
                            cli_found=cli_found,
                            service_reachable=service_reachable,
                            endpoint=endpoint,
                            models_count=models_count,
                            details=details,
                            state=state,
                            hint=hint,
                        )
                except httpx.HTTPStatusError:
                    pass

                # Fallback: try /health
                response = await client.get(f"{endpoint}/health")
                if response.status_code == 200:
                    service_reachable = True
                    models_count = 1  # Health ok means model loaded
                    state = "READY"
                    hint = "llama-server running (no model list endpoint, using /health)"

        except httpx.ConnectError:
            if cli_found:
                state = "DISCONNECTED"
                hint = "llama-server binary found but service not running. Run: llama-server -m <model.gguf>"
            else:
                state = "DISCONNECTED"
                hint = "llama-server not found. Install llama.cpp from: https://github.com/ggerganov/llama.cpp"
        except Exception as e:
            state = "ERROR"
            hint = f"Error detecting llama.cpp: {str(e)}"

        return DetectionResult(
            id="llamacpp",
            cli_found=cli_found,
            service_reachable=service_reachable,
            endpoint=endpoint,
            models_count=models_count,
            details=details,
            state=state,
            hint=hint,
        )

    @staticmethod
    async def detect_all() -> List[DetectionResult]:
        """Detect all local providers concurrently"""
        results = await asyncio.gather(
            LocalProviderDetector.detect_ollama(),
            LocalProviderDetector.detect_lmstudio(),
            LocalProviderDetector.detect_llamacpp(),
            return_exceptions=True,
        )

        # Filter out exceptions
        valid_results = []
        for result in results:
            if isinstance(result, DetectionResult):
                valid_results.append(result)
            elif isinstance(result, Exception):
                # Log but don't crash
                pass

        return valid_results
