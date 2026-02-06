"""结果解释器 - 生成人类可读的检索结果解释

核心功能:
- 将 Explanation 对象转换为可读文本
- 解释为什么该结果被返回
- 符合审计要求 (可追溯、可理解)
"""

from agentos.core.project_kb.types import ChunkResult, Explanation


class ResultExplainer:
    """结果解释器 - 审计关键组件"""

    def explain_result(self, result: ChunkResult) -> str:
        """生成单个结果的解释

        Args:
            result: ChunkResult 对象

        Returns:
            人类可读的解释文本
        """
        exp = result.explanation
        lines = []

        # 标题
        lines.append(f"📄 {result.path}")
        if result.heading:
            lines.append(f"   Section: {result.heading}")
        lines.append(f"   Lines: {result.lines}")
        lines.append(f"   Score: {result.score:.2f}")
        lines.append("")

        # 匹配词
        if exp.matched_terms:
            lines.append(f"✓ Matched terms: {', '.join(exp.matched_terms)}")
            lines.append(f"  Frequencies: {self._format_frequencies(exp.term_frequencies)}")

        # 权重加成
        boosts = []
        if exp.document_boost != 1.0:
            boosts.append(f"doc_type={exp.document_boost:.2f}x")
        if exp.recency_boost != 1.0:
            boosts.append(f"recency={exp.recency_boost:.2f}x")
        if boosts:
            lines.append(f"  Boosts: {', '.join(boosts)}")

        # [P2] 向量评分 (如果有)
        if exp.vector_score is not None:
            lines.append(f"  Vector score: {exp.vector_score:.3f}")
            if exp.rerank_delta is not None:
                direction = "↑" if exp.rerank_delta > 0 else "↓"
                lines.append(f"  Rerank: {direction} {abs(exp.rerank_delta)} positions")

        return "\n".join(lines)

    def explain_results(self, results: list[ChunkResult], query: str) -> str:
        """生成多个结果的汇总解释

        Args:
            results: ChunkResult 列表
            query: 原始查询

        Returns:
            人类可读的汇总解释
        """
        if not results:
            return f"No results found for: {query}"

        lines = []
        lines.append(f"🔍 Search: {query}")
        lines.append(f"Found {len(results)} result(s)\n")
        lines.append("=" * 60)

        for i, result in enumerate(results, start=1):
            lines.append(f"\n[{i}] {self.explain_result(result)}")
            lines.append("=" * 60)

        return "\n".join(lines)

    def _format_frequencies(self, term_frequencies: dict[str, int]) -> str:
        """格式化词频

        Args:
            term_frequencies: 词 -> 频次映射

        Returns:
            格式化字符串
        """
        items = [f"{term}({count})" for term, count in term_frequencies.items()]
        return ", ".join(items)

    def explain_to_json(self, result: ChunkResult) -> dict:
        """将解释转换为 JSON 格式 (用于 API)

        Args:
            result: ChunkResult 对象

        Returns:
            JSON-serializable 字典
        """
        return result.to_dict()

    def explain_scoring(self, explanation: Explanation) -> str:
        """详细解释评分计算过程

        Args:
            explanation: Explanation 对象

        Returns:
            评分计算解释
        """
        lines = []
        lines.append("Scoring breakdown:")

        # 基础分
        if explanation.keyword_score is not None:
            lines.append(f"  Base (keyword): {explanation.keyword_score:.2f}")
        
        # 文档权重
        if explanation.document_boost != 1.0:
            lines.append(f"  × Document boost: {explanation.document_boost:.2f}")
        
        # 新鲜度权重
        if explanation.recency_boost != 1.0:
            lines.append(f"  × Recency boost: {explanation.recency_boost:.2f}")
        
        # 向量评分 (P2)
        if explanation.vector_score is not None:
            lines.append(f"  + Vector score: {explanation.vector_score:.3f}")
        
        return "\n".join(lines)
