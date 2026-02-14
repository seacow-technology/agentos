"""Curated cloud model catalogs per provider.

Rationale:
- Many cloud providers expose model lists only after credentials are configured.
- The WebUI should still be able to show "available models" as a product hint.

These catalogs are best-effort and may become stale. Live provider APIs remain
source-of-truth when credentials are configured.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class CatalogModel:
    id: str
    label: Optional[str] = None
    metadata: Optional[dict] = None


def _m(model_id: str, label: Optional[str] = None, **meta) -> CatalogModel:
    metadata = dict(meta) if meta else {}
    metadata.setdefault("catalog", True)
    return CatalogModel(id=model_id, label=label or model_id, metadata=metadata)


# NOTE: Keep these lists conservative and stable. Do not attempt to fully
# mirror every provider's dynamic catalog here.
CLOUD_MODEL_CATALOG: Dict[str, List[CatalogModel]] = {
    # OpenAI official model ids are dynamic; we list common stable families.
    "openai": [
        _m("gpt-4o", "GPT-4o"),
        _m("gpt-4o-mini", "GPT-4o mini"),
        _m("gpt-4.1", "GPT-4.1"),
        _m("gpt-4.1-mini", "GPT-4.1 mini"),
        _m("gpt-4.1-nano", "GPT-4.1 nano"),
        _m("o3", "o3"),
        _m("o3-mini", "o3-mini"),
        _m("o4-mini", "o4-mini"),
        _m("gpt-image-1", "GPT Image 1"),
        _m("text-embedding-3-small", "text-embedding-3-small"),
        _m("text-embedding-3-large", "text-embedding-3-large"),
    ],
    # Anthropic model ids are date-versioned.
    "anthropic": [
        _m("claude-opus-4-1-20250805", "Claude Opus 4.1"),
        _m("claude-opus-4-20250514", "Claude Opus 4"),
        _m("claude-sonnet-4-20250514", "Claude Sonnet 4"),
        _m("claude-3-7-sonnet-20250219", "Claude 3.7 Sonnet"),
        _m("claude-3-5-sonnet-20241022", "Claude 3.5 Sonnet"),
        _m("claude-3-5-haiku-20241022", "Claude 3.5 Haiku"),
        _m("claude-3-haiku-20240307", "Claude 3 Haiku"),
    ],
    # Google Gemini (model ids vary by API version; keep generic names).
    "google": [
        _m("gemini-2.5-pro", "Gemini 2.5 Pro"),
        _m("gemini-2.5-flash", "Gemini 2.5 Flash"),
        _m("gemini-2.5-flash-lite", "Gemini 2.5 Flash-Lite"),
        _m("gemini-2.0-flash", "Gemini 2.0 Flash"),
        _m("gemini-1.5-pro", "Gemini 1.5 Pro"),
        _m("gemini-1.5-flash", "Gemini 1.5 Flash"),
    ],
    # DeepSeek (documented stable ids).
    "deepseek": [
        _m("deepseek-chat", "DeepSeek Chat"),
        _m("deepseek-reasoner", "DeepSeek Reasoner"),
    ],
    # xAI Grok
    "xai": [
        _m("grok-3", "Grok 3"),
        _m("grok-3-latest", "Grok 3 (latest)"),
        _m("grok-3-fast", "Grok 3 Fast"),
        _m("grok-3-fast-latest", "Grok 3 Fast (latest)"),
        _m("grok-2", "Grok 2"),
        _m("grok-2-latest", "Grok 2 (latest)"),
    ],
    # Alibaba Cloud (DashScope / Qwen)
    "alibaba_cloud": [
        _m("qwen-plus", "Qwen Plus"),
        _m("qwen-plus-latest", "Qwen Plus (latest)"),
        _m("qwen-max", "Qwen Max"),
        _m("qwen-max-latest", "Qwen Max (latest)"),
        _m("qwen-turbo", "Qwen Turbo"),
        _m("qwen-turbo-latest", "Qwen Turbo (latest)"),
        _m("qwen-flash", "Qwen Flash"),
        _m("qwen-long-latest", "Qwen Long (latest)"),
    ],
    # Amazon Bedrock: use provider-specific model ids (very large catalog; keep representative)
    "amazon": [
        _m("amazon.nova-micro-v1:0", "Amazon Nova Micro"),
        _m("amazon.nova-lite-v1:0", "Amazon Nova Lite"),
        _m("amazon.nova-pro-v1:0", "Amazon Nova Pro"),
        _m("anthropic.claude-3-5-sonnet-20241022-v2:0", "Claude 3.5 Sonnet (Bedrock)"),
        _m("meta.llama3-1-70b-instruct-v1:0", "Llama 3.1 70B Instruct (Bedrock)"),
        _m("mistral.mistral-large-2407-v1:0", "Mistral Large (Bedrock)"),
    ],
    # Moonshot/Kimi (ids can change; include common examples)
    "moonshot": [
        _m("kimi-k2-thinking", "Kimi K2 Thinking"),
        _m("kimi-k2-thinking-turbo", "Kimi K2 Thinking Turbo"),
    ],
    # Microsoft is typically Azure OpenAI; availability varies per region/deployment.
    "microsoft": [
        _m("gpt-4o", "GPT-4o (Azure OpenAI)"),
        _m("gpt-4o-mini", "GPT-4o mini (Azure OpenAI)"),
        _m("gpt-4.1", "GPT-4.1 (Azure OpenAI)"),
        _m("o3", "o3 (Azure OpenAI)"),
        _m("o4-mini", "o4-mini (Azure OpenAI)"),
        _m("gpt-image-1", "GPT Image 1 (Azure OpenAI)"),
    ],
    # Meta is usually served via partners/hosting; keep family hints.
    "meta": [
        _m("llama-3.3-70b-instruct", "Llama 3.3 70B Instruct"),
        _m("llama-3.1-70b-instruct", "Llama 3.1 70B Instruct"),
        _m("llama-3.1-8b-instruct", "Llama 3.1 8B Instruct"),
    ],
    # Z.ai: keep minimal placeholders (provider-specific catalogs vary).
    "zai": [
        _m("glm-4.5", "GLM-4.5"),
        _m("glm-4", "GLM-4"),
    ],
}


def get_catalog(provider_id: str) -> List[CatalogModel]:
    return list(CLOUD_MODEL_CATALOG.get(provider_id, []))
