"""Embedding Provider Factory

根据配置创建对应的 provider 实例。
"""

from agentos.core.project_kb.config import VectorRerankConfig
from agentos.core.project_kb.embedding.provider import IEmbeddingProvider


def create_provider(config: VectorRerankConfig) -> IEmbeddingProvider:
    """根据配置创建 embedding provider

    Args:
        config: VectorRerankConfig 配置

    Returns:
        IEmbeddingProvider 实例

    Raises:
        ValueError: 如果 provider 类型未知
        ImportError: 如果依赖未安装
    """
    if config.provider == "local":
        try:
            from agentos.core.project_kb.embedding.local_provider import (
                LocalEmbeddingProvider,
            )

            return LocalEmbeddingProvider(config.model)
        except ImportError as e:
            raise ImportError(
                f"Local embedding provider requires sentence-transformers. "
                f"Install with: pip install agentos[vector]\n"
                f"Original error: {e}"
            )
    elif config.provider == "openai":
        # TODO: 实现 OpenAI provider (P3)
        raise NotImplementedError("OpenAI provider not yet implemented")
    else:
        raise ValueError(f"Unknown provider: {config.provider}")
