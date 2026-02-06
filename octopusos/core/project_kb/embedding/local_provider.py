"""Local Embedding Provider - 基于 sentence-transformers

使用本地模型生成 embeddings，不依赖外部 API。

依赖: pip install agentos[vector]
"""

import numpy as np

from agentos.core.project_kb.embedding.provider import IEmbeddingProvider


class LocalEmbeddingProvider(IEmbeddingProvider):
    """本地 Embedding Provider (sentence-transformers)"""

    def __init__(self, model_name: str):
        """初始化本地 provider

        Args:
            model_name: SentenceTransformer 模型名称

        Raises:
            ImportError: 如果 sentence-transformers 未安装
        """
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError(
                "sentence-transformers not installed. "
                "Install with: pip install agentos[vector]"
            )

        self.model = SentenceTransformer(model_name)
        self._model_name = model_name

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        """批量生成 embeddings

        Args:
            texts: 文本列表

        Returns:
            numpy array, shape: (len(texts), dims)
        """
        if not texts:
            return np.array([])

        embeddings = self.model.encode(
            texts,
            convert_to_numpy=True,
            show_progress_bar=False,
            batch_size=32,
        )
        return embeddings

    def embed_query(self, query: str) -> np.ndarray:
        """生成单个查询 embedding

        Args:
            query: 查询字符串

        Returns:
            numpy array, shape: (dims,)
        """
        embedding = self.model.encode(
            [query],
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return embedding[0]

    @property
    def dims(self) -> int:
        """Embedding 维度"""
        return self.model.get_sentence_embedding_dimension()

    @property
    def model_name(self) -> str:
        """模型名称"""
        return self._model_name
