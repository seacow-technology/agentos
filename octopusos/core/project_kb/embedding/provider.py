"""Embedding Provider 抽象接口

定义 embedding 生成的统一接口，支持多种实现。
"""

from abc import ABC, abstractmethod

import numpy as np


class IEmbeddingProvider(ABC):
    """Embedding Provider 接口"""

    @abstractmethod
    def embed_texts(self, texts: list[str]) -> np.ndarray:
        """批量生成文本 embeddings

        Args:
            texts: 文本列表

        Returns:
            numpy array, shape: (len(texts), dims)
        """
        pass

    @abstractmethod
    def embed_query(self, query: str) -> np.ndarray:
        """生成单个查询 embedding

        Args:
            query: 查询字符串

        Returns:
            numpy array, shape: (dims,)
        """
        pass

    @property
    @abstractmethod
    def dims(self) -> int:
        """Embedding 维度"""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """模型名称"""
        pass
