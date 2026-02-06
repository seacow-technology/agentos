"""
Review Gate - 审批门控

高风险执行需要人工审批
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from agentos.core.time import utc_now_iso



class ReviewGate:
    """审批门控"""
    
    def __init__(self, approval_dir: Path):
        """初始化审批门控"""
        self.approval_dir = Path(approval_dir)
        self.approval_dir.mkdir(parents=True, exist_ok=True)
    
    def requires_review(self, execution_request: Dict[str, Any]) -> bool:
        """
        判断执行是否需要审批
        
        Args:
            execution_request: 执行请求
        
        Returns:
            是否需要审批
        """
        return execution_request.get("requires_review", False)
    
    def create_approval_request(
        self,
        execution_request_id: str,
        reason: str,
        details: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        创建审批请求
        
        Args:
            execution_request_id: 执行请求ID
            reason: 需要审批的原因
            details: 详细信息
        
        Returns:
            审批请求
        """
        approval_request = {
            "approval_request_id": f"approval_{execution_request_id}",
            "execution_request_id": execution_request_id,
            "reason": reason,
            "details": details,
            "status": "pending",
            "created_at": utc_now_iso(),
            "approved_at": None,
            "approved_by": None
        }
        
        # 保存审批请求
        approval_file = self.approval_dir / f"{approval_request['approval_request_id']}.json"
        with open(approval_file, "w", encoding="utf-8") as f:
            json.dump(approval_request, f, indent=2)
        
        return approval_request
    
    def check_approval(self, execution_request_id: str) -> Optional[Dict[str, Any]]:
        """
        检查审批状态
        
        Args:
            execution_request_id: 执行请求ID
        
        Returns:
            审批信息，如果未审批返回None
        """
        approval_id = f"approval_{execution_request_id}"
        approval_file = self.approval_dir / f"{approval_id}.json"
        
        if not approval_file.exists():
            return None
        
        with open(approval_file, "r", encoding="utf-8") as f:
            approval_request = json.load(f)
        
        if approval_request["status"] == "approved":
            return approval_request
        
        return None
    
    def approve(
        self,
        execution_request_id: str,
        approved_by: str,
        notes: Optional[str] = None
    ) -> bool:
        """
        批准执行
        
        Args:
            execution_request_id: 执行请求ID
            approved_by: 批准人
            notes: 批准备注
        
        Returns:
            是否成功
        """
        approval_id = f"approval_{execution_request_id}"
        approval_file = self.approval_dir / f"{approval_id}.json"
        
        if not approval_file.exists():
            return False
        
        with open(approval_file, "r", encoding="utf-8") as f:
            approval_request = json.load(f)
        
        approval_request["status"] = "approved"
        approval_request["approved_at"] = utc_now_iso()
        approval_request["approved_by"] = approved_by
        if notes:
            approval_request["notes"] = notes
        
        with open(approval_file, "w", encoding="utf-8") as f:
            json.dump(approval_request, f, indent=2)
        
        return True
    
    def reject(
        self,
        execution_request_id: str,
        rejected_by: str,
        reason: str
    ) -> bool:
        """
        拒绝执行
        
        Args:
            execution_request_id: 执行请求ID
            rejected_by: 拒绝人
            reason: 拒绝原因
        
        Returns:
            是否成功
        """
        approval_id = f"approval_{execution_request_id}"
        approval_file = self.approval_dir / f"{approval_id}.json"
        
        if not approval_file.exists():
            return False
        
        with open(approval_file, "r", encoding="utf-8") as f:
            approval_request = json.load(f)
        
        approval_request["status"] = "rejected"
        approval_request["rejected_at"] = utc_now_iso()
        approval_request["rejected_by"] = rejected_by
        approval_request["rejection_reason"] = reason
        
        with open(approval_file, "w", encoding="utf-8") as f:
            json.dump(approval_request, f, indent=2)
        
        return True
    
    def list_pending_approvals(self) -> List[Dict[str, Any]]:
        """列出所有待审批的请求"""
        pending = []
        
        for approval_file in self.approval_dir.glob("approval_*.json"):
            with open(approval_file, "r", encoding="utf-8") as f:
                approval_request = json.load(f)
            
            if approval_request["status"] == "pending":
                pending.append(approval_request)
        
        return sorted(pending, key=lambda x: x["created_at"], reverse=True)
