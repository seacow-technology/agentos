"""Vector Reranker - 向量重排序

负责:
- 基于向量相似度对候选结果重新排序
- 融合关键词分数和向量分数
- 更新 explanation (审计)
"""

import numpy as np

from agentos.core.project_kb.config import VectorRerankConfig
from agentos.core.project_kb.embedding.manager import EmbeddingManager
from agentos.core.project_kb.embedding.provider import IEmbeddingProvider
from agentos.core.project_kb.types import ChunkResult


class VectorReranker:
    """向量重排序器"""

    def __init__(self, embedding_manager: EmbeddingManager, provider: IEmbeddingProvider):
        """初始化 reranker

        Args:
            embedding_manager: Embedding 管理器
            provider: Embedding provider
        """
        self.embedding_manager = embedding_manager
        self.provider = provider

    def rerank(
        self,
        query: str,
        candidates: list[ChunkResult],
        config: VectorRerankConfig,
    ) -> list[ChunkResult]:
        """向量重排序

        流程:
        1. 生成 query embedding
        2. 获取候选 embeddings
        3. 计算 cosine 相似度
        4. 融合 keyword + vector 分数
        5. 重新排序
        6. 更新 explanation

        Args:
            query: 查询字符串
            candidates: 候选结果列表
            config: VectorRerankConfig

        Returns:
            重排序后的结果列表
        """
        if not candidates:
            return []

        # 1. 生成 query embedding
        try:
            query_vec = self.provider.embed_query(query)
        except Exception as e:
            print(f"⚠️  Failed to generate query embedding: {e}")
            return candidates[: config.final_k]

        # 2. 获取候选 embeddings
        chunk_ids = [c.chunk_id for c in candidates]
        embeddings = self.embedding_manager.get_embeddings(chunk_ids)

        # 3-5. 计算相似度、融合分数、更新结果
        updated_candidates = []
        for candidate, emb in zip(candidates, embeddings):
            if emb is None:
                # 缺失 embedding，保持原分数
                candidate.explanation.keyword_score = candidate.score
                candidate.explanation.vector_score = None
                candidate.explanation.alpha = config.alpha
                candidate.explanation.final_score = candidate.score
                updated_candidates.append(candidate)
                continue

            # 计算向量相似度
            vector_score = self._cosine_similarity(query_vec, emb)

            # 归一化关键词分数 (0-1)
            keyword_norm = self._normalize_keyword_score(candidate.score, candidates)

            # 融合分数
            final_score = (1 - config.alpha) * keyword_norm + config.alpha * vector_score

            # 更新 explanation
            candidate.explanation.keyword_score = candidate.score
            candidate.explanation.vector_score = float(vector_score)
            candidate.explanation.alpha = config.alpha
            candidate.explanation.final_score = float(final_score)

            # 更新候选分数
            candidate.score = final_score
            updated_candidates.append(candidate)

        # 6. 重新排序
        sorted_results = sorted(updated_candidates, key=lambda x: x.score, reverse=True)

        # 7. 更新 rerank_delta 和 final_rank
        for new_rank, result in enumerate(sorted_results, 1):
            old_rank = candidates.index(result) + 1
            result.explanation.rerank_delta = old_rank - new_rank
            result.explanation.final_rank = new_rank

        return sorted_results[: config.final_k]

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """计算 cosine 相似度

        Args:
            vec1: 向量1
            vec2: 向量2

        Returns:
            相似度 (-1 到 1)
        """
        # 归一化
        vec1_norm = vec1 / (np.linalg.norm(vec1) + 1e-8)
        vec2_norm = vec2 / (np.linalg.norm(vec2) + 1e-8)

        # 点积
        similarity = np.dot(vec1_norm, vec2_norm)

        # 映射到 0-1 范围
        return (similarity + 1) / 2

    def _normalize_keyword_score(
        self, score: float, all_candidates: list[ChunkResult]
    ) -> float:
        """归一化关键词分数到 0-1 范围

        使用 min-max 归一化。

        Args:
            score: 原始分数
            all_candidates: 所有候选结果

        Returns:
            归一化分数 (0-1)
        """
        if not all_candidates:
            return 0.0

        scores = [c.score for c in all_candidates]
        min_score = min(scores)
        max_score = max(scores)

        if max_score == min_score:
            return 1.0

        return (score - min_score) / (max_score - min_score)
