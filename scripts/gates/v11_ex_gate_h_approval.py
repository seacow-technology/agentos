#!/usr/bin/env python3
"""
EX Gate H - 审批验证

验证未审批的高风险执行会被拒绝
"""

import sys
from pathlib import Path
import tempfile

EXIT_CODE = 0
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def test_unapproved_execution_blocked():
    """测试未审批的执行被阻止"""
    global EXIT_CODE
    
    try:
        from agentos.core.executor import ReviewGate
        
        with tempfile.TemporaryDirectory() as tmpdir:
            approval_dir = Path(tmpdir) / "approvals"
            approval_dir.mkdir()
            
            gate = ReviewGate(approval_dir)
            
            # 创建需要审批的执行请求
            exec_request = {
                "execution_request_id": "exec_req_high_risk",
                "requires_review": True
            }
            
            # 检查是否需要审批
            if not gate.requires_review(exec_request):
                print("✗ Should require review")
                EXIT_CODE = 1
                return False
            
            print("✓ Execution requires review")
            
            # 检查审批状态（应该没有）
            approval = gate.check_approval("exec_req_high_risk")
            if approval is not None:
                print("✗ Should have no approval (unapproved)")
                EXIT_CODE = 1
                return False
            
            print("✓ No approval found (correctly blocked)")
            
            # 创建审批请求
            approval_req = gate.create_approval_request(
                "exec_req_high_risk",
                "High risk operations",
                {"operations": ["file_write", "git_commit"]}
            )
            
            print(f"✓ Approval request created: {approval_req['approval_request_id']}")
            
            # 仍然应该没有批准
            approval = gate.check_approval("exec_req_high_risk")
            if approval is not None:
                print("✗ Should still have no approval (not yet approved)")
                EXIT_CODE = 1
                return False
            
            print("✓ Still unapproved (pending state)")
            
            # 批准执行
            gate.approve("exec_req_high_risk", "test_approver", "Reviewed and approved")
            
            # 现在应该有批准
            approval = gate.check_approval("exec_req_high_risk")
            if approval is None:
                print("✗ Should have approval after approving")
                EXIT_CODE = 1
                return False
            
            print(f"✓ Execution approved by: {approval['approved_by']}")
            
            return True
            
    except Exception as e:
        print(f"✗ Approval test failed: {e}")
        import traceback
        traceback.print_exc()
        EXIT_CODE = 1
        return False


def main():
    global EXIT_CODE
    
    print("=" * 60)
    print("EX Gate H - Approval Verification")
    print("=" * 60)
    print()
    
    print("[Unapproved Execution Blocking]")
    test_unapproved_execution_blocked()
    print()
    
    print("=" * 60)
    if EXIT_CODE == 0:
        print("✅ EX Gate H: UNAPPROVED EXECUTION BLOCKED")
    else:
        print("❌ EX Gate H: APPROVAL VERIFICATION FAILED")
    print("=" * 60)
    
    return EXIT_CODE


if __name__ == "__main__":
    sys.exit(main())
