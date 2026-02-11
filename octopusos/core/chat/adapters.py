"""Chat model adapters - Wrapper for invoking LLMs in Chat Mode"""

from typing import List, Dict, Any, Optional, Iterator
import logging
import os

logger = logging.getLogger(__name__)


class ChatModelAdapter:
    """Base class for chat model adapters"""

    def generate(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        stream: bool = False,
        **kwargs: Any,
    ) -> tuple[str, Dict[str, Any]]:
        """Generate response from messages

        Args:
            messages: List of messages in OpenAI format
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            stream: Whether to stream the response

        Returns:
            Tuple of (generated_text, metadata)
            Metadata includes:
            - truncated: Whether response was truncated due to token limit
            - finish_reason: Raw finish reason from provider
            - tokens_used: Number of completion tokens used (if available)
        """
        raise NotImplementedError

    def generate_stream(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> Iterator[str]:
        """Generate response with streaming

        Args:
            messages: List of messages in OpenAI format
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Yields:
            Text chunks
        """
        raise NotImplementedError

    def health_check(self) -> tuple[bool, str]:
        """Check if adapter is available

        Returns:
            (is_available, status_message)
        """
        raise NotImplementedError

    def get_adaptive_max_tokens(
        self,
        messages: List[Dict[str, str]],
        budget_max_tokens: int = 2000,
        model_context_window: int = 128000
    ) -> int:
        """Calculate adaptive max_tokens based on input usage

        Adjusts generation length based on how much of the context window
        is already used by input messages, preventing context overflow.

        Algorithm:
        1. Estimate tokens used by messages
        2. Calculate available space: context_window - used_tokens
        3. Apply 10% safety margin
        4. Return min(budget_max_tokens, available_space)

        Args:
            messages: List of messages in OpenAI format
            budget_max_tokens: Budgeted generation limit
            model_context_window: Model's total context window

        Returns:
            Adaptive max_tokens value

        Example:
            >>> adapter = ChatModelAdapter()
            >>> messages = [{"role": "user", "content": "hello" * 1000}]
            >>> # If messages use 5000 tokens in a 8k window:
            >>> max_tokens = adapter.get_adaptive_max_tokens(messages, 2000, 8000)
            >>> # Returns min(2000, (8000 - 5000) * 0.9) = min(2000, 2700) = 2000
        """
        # Estimate tokens used by messages
        used_tokens = self._estimate_messages_tokens(messages)

        # Calculate available space with 10% safety margin
        available = model_context_window - used_tokens
        available_with_margin = int(available * 0.9)

        # Return minimum of budget and available
        adaptive_max = min(budget_max_tokens, available_with_margin)

        # Ensure at least 100 tokens for generation
        return max(adaptive_max, 100)

    def _estimate_messages_tokens(self, messages: List[Dict[str, str]]) -> int:
        """Estimate token count for messages

        Uses simple heuristic: 1.3 tokens per character (conservative estimate)

        Args:
            messages: List of messages in OpenAI format

        Returns:
            Estimated token count
        """
        total_chars = sum(len(msg.get("content", "")) for msg in messages)
        return int(total_chars * 1.3)


class OllamaChatAdapter(ChatModelAdapter):
    """Ollama adapter for Chat Mode (also used for llama.cpp and LM Studio)"""

    def __init__(self, model: str = "qwen2.5:14b", base_url: Optional[str] = None):
        """Initialize Ollama adapter

        Args:
            model: Model name
            base_url: Base URL (defaults to OLLAMA_HOST env var or http://localhost:11434)
        """
        self.model = model
        self.host = base_url or os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    
    def generate(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        stream: bool = False,
        **kwargs: Any,
    ) -> tuple[str, Dict[str, Any]]:
        """Generate response using Ollama"""
        try:
            import requests
        except ImportError:
            logger.error("requests library not installed")
            return "⚠️ Error: requests library required for Ollama", {}

        try:
            return self._chat_generate(
                requests=requests,
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

        except Exception as e:
            # Some local Ollama-compatible deployments may not expose /api/chat.
            # Retry once with /api/generate for better compatibility.
            if "404" in str(e):
                try:
                    fallback_url = f"{self.host}/api/generate"
                    response = requests.post(
                        fallback_url,
                        json={
                            "model": self.model,
                            "prompt": self._messages_to_prompt(messages),
                            "stream": False,
                            "options": {
                                "temperature": temperature,
                                "num_predict": max_tokens,
                            },
                        },
                        timeout=60,
                    )
                    response.raise_for_status()
                    result = response.json()
                    content = str(result.get("response") or "").strip()
                    done_reason = result.get("done_reason")
                    return content, {
                        "truncated": done_reason == "length",
                        "finish_reason": done_reason,
                        "tokens_used": result.get("eval_count"),
                    }
                except Exception as fallback_error:
                    auto_model = self._detect_first_available_model(requests)
                    if auto_model and auto_model != self.model:
                        try:
                            return self._chat_generate(
                                requests=requests,
                                model=auto_model,
                                messages=messages,
                                temperature=temperature,
                                max_tokens=max_tokens,
                            )
                        except Exception as auto_model_error:
                            logger.error(
                                "Ollama generation failed (chat+generate+model-fallback): %s",
                                auto_model_error,
                            )
                            return f"⚠️ Ollama error: {str(auto_model_error)}", {}
                    logger.error(f"Ollama generation failed (chat+generate fallback): {fallback_error}")
                    return f"⚠️ Ollama error: {str(fallback_error)}", {}

            logger.error(f"Ollama generation failed: {e}")
            return f"⚠️ Ollama error: {str(e)}", {}

    def _messages_to_prompt(self, messages: List[Dict[str, Any]]) -> str:
        lines: List[str] = []
        for m in messages:
            role = str(m.get("role") or "user").strip()
            content = str(m.get("content") or "").strip()
            if not content:
                continue
            lines.append(f"{role}: {content}")
        return "\n".join(lines) if lines else "user: "

    def _chat_generate(
        self,
        *,
        requests: Any,
        model: str,
        messages: List[Dict[str, Any]],
        temperature: float,
        max_tokens: int,
    ) -> tuple[str, Dict[str, Any]]:
        response = requests.post(
            f"{self.host}/api/chat",
            json={
                "model": model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                },
            },
            timeout=60,
        )
        response.raise_for_status()
        result = response.json()
        content = result.get("message", {}).get("content", "")
        done_reason = result.get("done_reason")
        return content, {
            "truncated": done_reason == "length",
            "finish_reason": done_reason,
            "tokens_used": result.get("eval_count"),
        }

    def _detect_first_available_model(self, requests: Any) -> Optional[str]:
        try:
            resp = requests.get(f"{self.host}/api/tags", timeout=8)
            resp.raise_for_status()
            models = resp.json().get("models", [])
            if not isinstance(models, list) or not models:
                return None
            first = models[0]
            if isinstance(first, dict):
                return str(first.get("name") or first.get("model") or "").strip() or None
            return None
        except Exception:
            return None

    def generate_stream(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> Iterator[str]:
        """Generate response with streaming"""
        try:
            import requests
        except ImportError:
            yield "⚠️ Error: requests library required"
            return

        try:
            url = f"{self.host}/api/chat"
            payload = {
                "model": self.model,
                "messages": messages,
                "stream": True,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens
                }
            }

            response = requests.post(url, json=payload, stream=True, timeout=60)
            response.raise_for_status()

            for line in response.iter_lines():
                if line:
                    try:
                        data = line.decode('utf-8')
                        import json
                        chunk = json.loads(data)
                        content = chunk.get("message", {}).get("content", "")
                        if content:
                            yield content
                    except Exception:
                        continue

        except Exception as e:
            logger.error(f"Ollama streaming failed: {e}")
            yield f"⚠️ Ollama error: {str(e)}"

    def health_check(self) -> tuple[bool, str]:
        """Check Ollama availability"""
        try:
            import requests
            response = requests.get(f"{self.host}/api/tags", timeout=5)

            if response.status_code == 200:
                models = response.json().get("models", [])
                model_names = [m["name"] for m in models]

                model_exists = any(
                    name == self.model or name.startswith(f"{self.model}:")
                    for name in model_names
                )

                if model_exists:
                    return True, f"✓ Ollama ({self.model})"
                else:
                    return False, f"✗ Model {self.model} not found"

            return False, f"✗ Ollama service error ({response.status_code})"

        except Exception as e:
            return False, f"✗ Ollama unreachable: {str(e)}"


def create_adapter(model_type: Optional[str] = None, provider: Optional[str] = None) -> ChatModelAdapter:
    """
    Factory for chat adapters.

    Defaults to Ollama adapter for local usage.
    """
    _ = model_type
    _ = provider
    return OllamaChatAdapter()


class OpenAIChatAdapter(ChatModelAdapter):
    """OpenAI adapter for Chat Mode"""
    
    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None
    ):
        """Initialize OpenAI adapter
        
        Args:
            model: OpenAI model name
            api_key: API key (defaults to OPENAI_API_KEY env var)
            base_url: Base URL (for OpenAI-compatible services)
        """
        self.model = model
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.base_url = base_url
    
    def generate(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        stream: bool = False,
        **kwargs: Any,
    ) -> tuple[str, Dict[str, Any]]:
        """Generate response using OpenAI"""
        try:
            import openai
        except ImportError:
            logger.error("openai library not installed")
            return "⚠️ Error: openai library required", {}

        # Only check API key for actual OpenAI (not for local services with custom base_url)
        if not self.api_key and not self.base_url:
            return "⚠️ Error: OPENAI_API_KEY not configured", {}

        try:
            client_kwargs = {"api_key": self.api_key}
            if self.base_url:
                client_kwargs["base_url"] = self.base_url

            logger.info(f"Creating OpenAI client with base_url={self.base_url}, model={self.model}")

            client = openai.OpenAI(**client_kwargs)

            request_kwargs: Dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": False,
            }
            if kwargs.get("tools"):
                request_kwargs["tools"] = kwargs.get("tools")
            if kwargs.get("tool_choice") is not None:
                request_kwargs["tool_choice"] = kwargs.get("tool_choice")

            response = client.chat.completions.create(
                **request_kwargs
            )

            message = response.choices[0].message
            content = message.content or ""

            # Check for truncation
            # OpenAI uses "finish_reason": "stop", "length", "content_filter", etc.
            finish_reason = response.choices[0].finish_reason
            truncated = finish_reason in ['length', 'max_tokens']

            metadata = {
                "truncated": truncated,
                "finish_reason": finish_reason,
                "tokens_used": response.usage.completion_tokens if hasattr(response, 'usage') else None
            }
            tool_calls = []
            raw_tool_calls = getattr(message, "tool_calls", None) or []
            if not isinstance(raw_tool_calls, list):
                try:
                    raw_tool_calls = list(raw_tool_calls)
                except Exception:
                    raw_tool_calls = []
            for call in raw_tool_calls:
                try:
                    arguments_json = call.function.arguments or "{}"
                    import json
                    try:
                        arguments = json.loads(arguments_json) if arguments_json else {}
                    except Exception:
                        arguments = {}
                    tool_calls.append(
                        {
                            "id": str(getattr(call, "id", "") or ""),
                            "name": str(call.function.name or ""),
                            "arguments": arguments if isinstance(arguments, dict) else {},
                            "arguments_json": arguments_json,
                        }
                    )
                except Exception:
                    continue
            if tool_calls:
                metadata["tool_calls"] = tool_calls

            return content, metadata

        except Exception as e:
            logger.error(f"OpenAI generation failed: {e}", exc_info=True)
            return f"⚠️ OpenAI error: {str(e)}", {}
    
    def generate_stream(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> Iterator[str]:
        """Generate response with streaming"""
        try:
            import openai
        except ImportError:
            yield "⚠️ Error: openai library required"
            return

        # Only check API key for actual OpenAI (not for local services with custom base_url)
        if not self.api_key and not self.base_url:
            yield "⚠️ Error: OPENAI_API_KEY not configured"
            return
        
        try:
            client_kwargs = {"api_key": self.api_key}
            if self.base_url:
                client_kwargs["base_url"] = self.base_url

            logger.info(f"Creating OpenAI client for streaming with base_url={self.base_url}, model={self.model}")

            client = openai.OpenAI(**client_kwargs)

            stream = client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True
            )

            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            logger.error(f"OpenAI streaming failed: {e}", exc_info=True)
            yield f"⚠️ OpenAI error: {str(e)}"
    
    def health_check(self) -> tuple[bool, str]:
        """Check OpenAI availability"""
        # For custom base_url (llama.cpp, lmstudio), check endpoint instead of API key
        if self.base_url:
            try:
                import requests
                # Try to list models
                health_url = self.base_url.replace("/v1", "/health") if "/v1" in self.base_url else f"{self.base_url}/health"
                logger.debug(f"Health check URL: {health_url}")
                response = requests.get(health_url, timeout=5)
                logger.debug(f"Health check status: {response.status_code}")
                if response.status_code == 200:
                    return True, f"✓ Local Model ({self.model})"

                # Fallback: try models endpoint
                models_url = f"{self.base_url}/models"
                logger.debug(f"Models check URL: {models_url}")
                response = requests.get(models_url, timeout=5)
                logger.debug(f"Models check status: {response.status_code}")
                if response.status_code == 200:
                    return True, f"✓ Local Model ({self.model})"

                logger.error(f"Health check failed: {response.status_code} - {response.text[:200]}")
                return False, f"✗ Service error ({response.status_code})"
            except Exception as e:
                logger.error(f"Health check exception: {e}", exc_info=True)
                return False, f"✗ Service unreachable: {str(e)}"

        # For OpenAI API
        if not self.api_key:
            return False, "✗ OPENAI_API_KEY not configured"

        # Basic validation
        if not self.api_key.startswith("sk-"):
            return False, "✗ Invalid API key format"

        return True, f"✓ OpenAI ({self.model})"


def get_adapter(provider: str, model: Optional[str] = None) -> ChatModelAdapter:
    """Get chat model adapter

    Args:
        provider: Provider ID (e.g., "ollama", "llamacpp", "llamacpp:instance-name")
        model: Optional model name override

    Returns:
        ChatModelAdapter instance
    """
    # Parse provider:instance format
    if ":" in provider:
        provider_type, instance_id = provider.split(":", 1)
    else:
        provider_type = provider
        instance_id = None

    # Handle Ollama
    if provider_type == "ollama":
        model = model or "qwen2.5:14b"
        base_url = None

        # Get actual endpoint from registry
        try:
            from octopusos.providers.registry import ProviderRegistry
            registry = ProviderRegistry.get_instance()

            if instance_id:
                # Specific instance requested
                provider_obj = registry.get(f"ollama:{instance_id}")
                if provider_obj and hasattr(provider_obj, 'endpoint'):
                    base_url = provider_obj.endpoint
                    logger.info(f"Using ollama instance endpoint: {base_url}")
            else:
                # No instance specified - find any available ollama instance
                from octopusos.providers.base import ProviderState
                all_providers = registry.list_all()
                first_ollama_endpoint = None
                for p in all_providers:
                    if p.id.startswith("ollama:") or p.id == "ollama":
                        if first_ollama_endpoint is None and hasattr(p, "endpoint"):
                            first_ollama_endpoint = p.endpoint
                        status = p.get_cached_status()
                        if status and status.state == ProviderState.READY:
                            base_url = p.endpoint
                            logger.info(f"Auto-selected ollama instance: {p.id} at {base_url}")
                            break
                if not base_url and first_ollama_endpoint:
                    base_url = first_ollama_endpoint
                    logger.info(f"Selected ollama instance without cached status: {base_url}")

            if not base_url:
                base_url = "http://127.0.0.1:11434"
                logger.warning(f"No ollama instance found, using default: {base_url}")

        except Exception as e:
            logger.warning(f"Failed to get ollama endpoint: {e}", exc_info=True)
            base_url = "http://127.0.0.1:11434"

        return OllamaChatAdapter(model=model, base_url=base_url)

    # Handle llama.cpp (OpenAI-compatible)
    elif provider_type == "llamacpp":
        model = model or "local-model"
        base_url = None

        # Get actual endpoint from registry
        try:
            from octopusos.providers.registry import ProviderRegistry
            registry = ProviderRegistry.get_instance()

            if instance_id:
                # Specific instance requested
                provider_obj = registry.get(f"llamacpp:{instance_id}")
                if provider_obj and hasattr(provider_obj, 'endpoint'):
                    base_url = provider_obj.endpoint
                    logger.info(f"Using llamacpp instance endpoint: {base_url}")
            else:
                # No instance specified - find instance that has this model
                from octopusos.providers.base import ProviderState
                import asyncio
                import requests
                all_providers = registry.list_all()

                # Filter llamacpp instances
                llamacpp_providers = [p for p in all_providers if p.id.startswith("llamacpp:")]

                # If model is specified, find instance that has this model
                if model:
                    logger.info(f"Looking for llamacpp instance with model: {model}")
                    for p in llamacpp_providers:
                        # Check if provider is ready
                        status = p.get_cached_status()
                        if not status:
                            try:
                                status = asyncio.run(p.probe())
                            except:
                                continue

                        if not status or status.state != ProviderState.READY:
                            continue

                        # Check if this instance has the model
                        try:
                            response = requests.get(f"{p.endpoint}/v1/models", timeout=2)
                            if response.status_code == 200:
                                data = response.json()
                                models = [m.get("id") for m in data.get("data", [])]
                                logger.debug(f"Instance {p.id} has models: {models}")

                                if model in models:
                                    base_url = p.endpoint
                                    logger.info(f"✓ Found model '{model}' in instance: {p.id} at {base_url}")
                                    break
                        except Exception as e:
                            logger.debug(f"Failed to check models for {p.id}: {e}")
                            continue

                # Fallback: select first available instance
                if not base_url:
                    logger.warning(f"Model '{model}' not found in any instance, using first available")
                    for p in llamacpp_providers:
                        status = p.get_cached_status()
                        if not status:
                            try:
                                status = asyncio.run(p.probe())
                            except:
                                continue

                        if status and status.state == ProviderState.READY:
                            base_url = p.endpoint
                            logger.info(f"Auto-selected llamacpp instance: {p.id} at {base_url}")
                            break

            if not base_url:
                # Fallback to default port
                base_url = "http://127.0.0.1:8080"
                logger.warning(f"No llamacpp instance found, using default: {base_url}")

        except Exception as e:
            logger.warning(f"Failed to get llamacpp endpoint: {e}", exc_info=True)
            base_url = "http://127.0.0.1:8080"

        # llama.cpp uses OpenAI-compatible API
        return OpenAIChatAdapter(model=model, base_url=f"{base_url}/v1", api_key="dummy")

    # Handle LM Studio (OpenAI-compatible)
    elif provider_type == "lmstudio":
        model = model or "local-model"
        base_url = None

        # Get actual endpoint from registry
        try:
            from octopusos.providers.registry import ProviderRegistry
            registry = ProviderRegistry.get_instance()

            if instance_id:
                # Specific instance requested
                provider_obj = registry.get(f"lmstudio:{instance_id}")
                if provider_obj and hasattr(provider_obj, 'endpoint'):
                    base_url = provider_obj.endpoint
                    logger.info(f"Using lmstudio instance endpoint: {base_url}")
            else:
                # No instance specified - find any available lmstudio instance
                from octopusos.providers.base import ProviderState
                import asyncio
                all_providers = registry.list_all()
                for p in all_providers:
                    if p.id.startswith("lmstudio:") or p.id == "lmstudio":
                        status = p.get_cached_status()
                        if not status:
                            try:
                                status = asyncio.run(p.probe())
                            except:
                                continue

                        if status and status.state == ProviderState.READY:
                            base_url = p.endpoint
                            logger.info(f"Auto-selected lmstudio instance: {p.id} at {base_url}")
                            break

            if not base_url:
                base_url = "http://127.0.0.1:1234"
                logger.warning(f"No lmstudio instance found, using default: {base_url}")

        except Exception as e:
            logger.warning(f"Failed to get lmstudio endpoint: {e}", exc_info=True)
            base_url = "http://127.0.0.1:1234"

        return OpenAIChatAdapter(model=model, base_url=f"{base_url}/v1", api_key="dummy")

    # Handle OpenAI
    elif provider_type == "openai" or provider_type == "cloud":
        model = model or "gpt-4o-mini"
        return OpenAIChatAdapter(model=model)

    else:
        raise ValueError(f"Unknown provider: {provider}")
