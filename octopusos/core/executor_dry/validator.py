"""
Dry Executor Validator - RED LINE Enforcement (DE1-DE6)

This is Layer 3 validation: Execution Safety Layer.

职责边界：
- ✅ 安全约束
- ✅ 执行前防线
- ✅ 审计与冻结

不应该做的：
- ❌ 业务语义检查（那是 OpenPlanVerifier 的职责）
- ❌ 结构校验（那是 SchemaValidator 的职责）

Architecture Decision:
    DE 和 BR 不对齐是设计选择，不是缺陷。
    见：docs/architecture/VALIDATION_LAYERS.md
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .utils import enforce_red_lines


@dataclass
class DeViolation:
    """Dry Executor RED LINE 违规记录"""

    violation_id: str  # DE1-DE6
    severity: str  # critical, high, medium
    message: str
    node_id: Optional[str] = None
    file_path: Optional[str] = None
    evidence: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """序列化为 dict"""
        return {
            "violation_id": self.violation_id,
            "severity": self.severity,
            "message": self.message,
            "node_id": self.node_id,
            "file_path": self.file_path,
            "evidence": self.evidence,
        }


@dataclass
class DeValidationResult:
    """Dry Executor 验证结果"""

    valid: bool
    violations: List[DeViolation]
    layer: str = "dry_executor"  # 明确标注验证层

    def to_dict(self) -> Dict[str, Any]:
        """序列化为 dict"""
        return {
            "valid": self.valid,
            "layer": self.layer,
            "violations": [v.to_dict() for v in self.violations],
        }


class DryExecutorValidator:
    """
    Dry Executor RED LINE 验证器（统一入口）

    这是 Layer 3 验证的唯一入口。所有 DE1-DE6 检查从这里触发。

    RED LINE 概览：
        - DE1: 禁止执行（subprocess/exec）
        - DE2: 禁止写项目文件
        - DE3: 禁止编造路径（必须来自 intent/evidence）
        - DE4: 所有节点必须有 evidence_refs
        - DE5: 高/致命风险必须 requires_review
        - DE6: 必须有 checksum + lineage

    Usage:
        validator = DryExecutorValidator()
        result = validator.validate(dry_execution_result)

        if not result.valid:
            for violation in result.violations:
                print(f"{violation.violation_id}: {violation.message}")
    """

    # RED LINE 定义（文档化）
    RED_LINES = {
        "DE1": "禁止执行 - No subprocess/exec/eval",
        "DE2": "禁止写项目文件 - Only write to output dir",
        "DE3": "禁止编造路径 - Paths must be from intent/evidence",
        "DE4": "所有节点必须有 evidence_refs",
        "DE5": "高/致命风险必须 requires_review",
        "DE6": "必须有 checksum + lineage",
    }

    def __init__(self):
        """初始化 DryExecutorValidator"""
        pass

    def validate(
        self,
        result_data: Dict[str, Any],
        intent_data: Optional[Dict[str, Any]] = None,
    ) -> DeValidationResult:
        """
        验证 Dry Execution Result 是否符合 RED LINE

        Args:
            result_data: DryExecutionResult dict
            intent_data: Optional ExecutionIntent dict (用于 DE3 校验)

        Returns:
            DeValidationResult with violations
        """
        violations = []

        # 使用现有的 enforce_red_lines 逻辑
        violation_messages = enforce_red_lines(result_data)

        for msg in violation_messages:
            # 解析 violation message 提取 DE 编号
            violation_id = self._extract_violation_id(msg)

            violations.append(
                DeViolation(
                    violation_id=violation_id,
                    severity=self._get_severity(violation_id),
                    message=msg,
                )
            )

        # DE3: 路径伪造检测（如果提供了 intent）
        if intent_data:
            de3_violations = self._check_path_fabrication(result_data, intent_data)
            violations.extend(de3_violations)

        return DeValidationResult(valid=len(violations) == 0, violations=violations)

    def _extract_violation_id(self, message: str) -> str:
        """从错误信息中提取 DE 编号"""
        if "DE4" in message:
            return "DE4"
        elif "DE5" in message:
            return "DE5"
        elif "DE6" in message:
            return "DE6"
        else:
            return "UNKNOWN"

    def _get_severity(self, violation_id: str) -> str:
        """获取违规严重程度"""
        severity_map = {
            "DE1": "critical",
            "DE2": "critical",
            "DE3": "high",
            "DE4": "high",
            "DE5": "critical",
            "DE6": "medium",
        }
        return severity_map.get(violation_id, "medium")

    def _check_path_fabrication(
        self, result_data: Dict[str, Any], intent_data: Dict[str, Any]
    ) -> List[DeViolation]:
        """
        DE3: 检查路径伪造

        Args:
            result_data: DryExecutionResult
            intent_data: ExecutionIntent

        Returns:
            List of DE3 violations
        """
        violations = []

        from .utils import validate_path_in_intent

        # 检查 patch_plan 中的所有路径
        patch_plan = result_data.get("patch_plan", {})
        for file_entry in patch_plan.get("files", []):
            file_path = file_entry.get("path")

            if not validate_path_in_intent(file_path, intent_data):
                violations.append(
                    DeViolation(
                        violation_id="DE3",
                        severity="high",
                        message=f"Path fabrication detected: '{file_path}' not in intent or evidence",
                        file_path=file_path,
                        evidence={"intent_id": intent_data.get("id")},
                    )
                )

        return violations

    def validate_result_file(self, result_file_path: str) -> DeValidationResult:
        """
        验证 DryExecutionResult JSON 文件

        Args:
            result_file_path: Path to result JSON file

        Returns:
            DeValidationResult
        """
        import json
        from pathlib import Path

        try:
            with open(result_file_path, encoding="utf-8") as f:
                result_data = json.load(f)

            return self.validate(result_data)

        except FileNotFoundError:
            return DeValidationResult(
                valid=False,
                violations=[
                    DeViolation(
                        violation_id="UNKNOWN",
                        severity="critical",
                        message=f"Result file not found: {result_file_path}",
                    )
                ],
            )
        except json.JSONDecodeError as e:
            return DeValidationResult(
                valid=False,
                violations=[
                    DeViolation(
                        violation_id="UNKNOWN",
                        severity="critical",
                        message=f"Invalid JSON: {str(e)}",
                    )
                ],
            )


# Convenience function
def validate_dry_execution_result(
    result_data: Dict[str, Any], intent_data: Optional[Dict[str, Any]] = None
) -> DeValidationResult:
    """
    便捷函数：验证 Dry Execution Result

    Args:
        result_data: DryExecutionResult dict
        intent_data: Optional ExecutionIntent dict

    Returns:
        DeValidationResult
    """
    validator = DryExecutorValidator()
    return validator.validate(result_data, intent_data)
