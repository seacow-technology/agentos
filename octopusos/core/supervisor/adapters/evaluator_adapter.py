"""
Evaluator Adapter

封装对评估引擎的调用。
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from ...evaluator.engine import EvaluatorEngine
from ...evaluator.conflict_detector import ConflictDetector
from ...evaluator.risk_comparator import RiskComparator

logger = logging.getLogger(__name__)


class EvaluatorAdapter:
    """
    Evaluator Adapter

    职责：
    - 封装评估引擎调用
    - 提供简化的接口供 Supervisor policies 使用
    """

    def __init__(self):
        """初始化 Evaluator Adapter"""
        self.engine = EvaluatorEngine()
        self.conflict_detector = ConflictDetector()
        self.risk_comparator = RiskComparator()

        logger.info("EvaluatorAdapter initialized")

    def evaluate_intent_set(
        self,
        intent_set_path: Path,
        policy: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        评估 intent set

        Args:
            intent_set_path: Intent set 文件路径
            policy: 可选的 policy 覆盖

        Returns:
            评估结果字典
        """
        try:
            result = self.engine.evaluate(str(intent_set_path), policy)
            return result.to_dict() if hasattr(result, 'to_dict') else result

        except Exception as e:
            logger.error(f"Intent set evaluation failed: {e}", exc_info=True)
            raise

    def detect_conflicts(self, intents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        检测意图冲突

        Args:
            intents: 意图列表

        Returns:
            冲突列表
        """
        try:
            conflicts = self.conflict_detector.detect_all(intents)
            return [c.to_dict() if hasattr(c, 'to_dict') else c for c in conflicts]

        except Exception as e:
            logger.error(f"Conflict detection failed: {e}", exc_info=True)
            return []

    def compare_risks(self, intents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        比较意图风险

        Args:
            intents: 意图列表

        Returns:
            风险矩阵
        """
        try:
            risk_matrix = self.risk_comparator.build_risk_matrix(intents)
            return risk_matrix.to_dict() if hasattr(risk_matrix, 'to_dict') else risk_matrix

        except Exception as e:
            logger.error(f"Risk comparison failed: {e}", exc_info=True)
            return {"entries": [], "dominance": [], "incomparable": []}

    def get_highest_risk(self, risk_matrix: Dict[str, Any]) -> Optional[str]:
        """
        从风险矩阵获取最高风险等级

        Args:
            risk_matrix: 风险矩阵

        Returns:
            最高风险等级（low/medium/high/critical）或 None
        """
        entries = risk_matrix.get("entries", [])
        if not entries:
            return None

        risk_order = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        max_risk = "low"

        for entry in entries:
            overall_risk = entry.get("overall_risk", "low")
            if risk_order.get(overall_risk, 0) > risk_order.get(max_risk, 0):
                max_risk = overall_risk

        return max_risk

    def has_critical_conflicts(self, conflicts: List[Dict[str, Any]]) -> bool:
        """
        检查是否有严重冲突

        Args:
            conflicts: 冲突列表

        Returns:
            是否有严重冲突（critical/high）
        """
        for conflict in conflicts:
            severity = conflict.get("severity", "low")
            if severity in ["critical", "high"]:
                return True
        return False
