"""Tool Verify - 工具结果验证

验证 result_pack 的 6 个 gates（TL-A 到 TL-F）。
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime, timezone


class ToolVerifier:
    """工具结果验证器"""
    
    def __init__(self):
        """初始化验证器"""
        pass
    
    def verify(
        self,
        result_pack: Dict[str, Any],
        task_pack: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, List[str]]:
        """
        验证 result_pack
        
        Args:
            result_pack: Tool result pack
            task_pack: Tool task pack（可选，用于额外验证）
        
        Returns:
            (is_valid, errors)
        """
        errors = []
        
        # Gate TL-A: Pack completeness
        if not self._check_pack_completeness(result_pack):
            errors.append("TL-A failed: Result pack incomplete")
        
        # Gate TL-C: Evidence required
        if not self._check_evidence_required(result_pack):
            errors.append("TL-C failed: Missing required evidence (diff, commits)")
        
        # Gate TL-D: Policy match（如果有 task_pack）
        if task_pack and not self._check_policy_match(result_pack, task_pack):
            errors.append("TL-D failed: Policy violations detected")
        
        # 其他基本验证
        if result_pack.get("status") == "failed" and "error" not in result_pack:
            errors.append("Failed status but no error message")
        
        return len(errors) == 0, errors
    
    def _check_pack_completeness(self, result_pack: Dict[str, Any]) -> bool:
        """Gate TL-A: 检查 result_pack 完整性"""
        required_fields = [
            "tool_result_pack_id",
            "tool_task_pack_id",
            "tool_type",
            "status"
        ]
        
        for field in required_fields:
            if field not in result_pack:
                return False
        
        return True
    
    def _check_evidence_required(self, result_pack: Dict[str, Any]) -> bool:
        """Gate TL-C: 检查必需的证据"""
        # 只有 success/partial_success 需要 evidence
        if result_pack.get("status") not in ["success", "partial_success"]:
            return True  # 失败的不强制要求
        
        # 检查 diffs
        if "diffs" not in result_pack:
            return False
        
        # 检查 artifacts
        if "artifacts" not in result_pack:
            return False
        
        artifacts = result_pack["artifacts"]
        
        # 至少要有 commits 记录
        if "commits" not in artifacts:
            return False
        
        return True
    
    def _check_policy_match(
        self,
        result_pack: Dict[str, Any],
        task_pack: Dict[str, Any]
    ) -> bool:
        """Gate TL-D: 检查是否符合 policy"""
        # 检查 policy_attestation
        if "policy_attestation" not in result_pack:
            return False
        
        attestation = result_pack["policy_attestation"]
        
        if not attestation.get("scope_compliant", False):
            return False
        
        if not attestation.get("red_lines_respected", False):
            return False
        
        # 检查 violations
        violations = attestation.get("violations", [])
        critical_violations = [
            v for v in violations
            if v.get("severity") in ["error", "critical"]
        ]
        
        if critical_violations:
            return False
        
        return True
    
    def generate_report(
        self,
        result_pack: Dict[str, Any],
        task_pack: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        生成验证报告
        
        Args:
            result_pack: Tool result pack
            task_pack: Tool task pack
        
        Returns:
            验证报告
        """
        is_valid, errors = self.verify(result_pack, task_pack)
        
        report = {
            "verify_report_version": "1.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tool_result_pack_id": result_pack.get("tool_result_pack_id"),
            "is_valid": is_valid,
            "errors": errors,
            "gates": {
                "TL-A_pack_completeness": self._check_pack_completeness(result_pack),
                "TL-C_evidence_required": self._check_evidence_required(result_pack),
                "TL-D_policy_match": self._check_policy_match(result_pack, task_pack) if task_pack else None
            },
            "summary": {
                "status": result_pack.get("status"),
                "tool_type": result_pack.get("tool_type"),
                "diffs_count": len(result_pack.get("diffs", [])),
                "commits_count": len(result_pack.get("artifacts", {}).get("commits", []))
            }
        }
        
        return report


def verify_tool_result(
    result_pack: Dict[str, Any],
    task_pack: Optional[Dict[str, Any]] = None
) -> Tuple[bool, List[str]]:
    """
    验证工具结果（便捷函数）
    
    Args:
        result_pack: Tool result pack
        task_pack: Tool task pack
    
    Returns:
        (is_valid, errors)
    """
    verifier = ToolVerifier()
    return verifier.verify(result_pack, task_pack)
