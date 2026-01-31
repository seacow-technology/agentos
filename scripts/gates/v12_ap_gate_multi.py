#!/usr/bin/env python3
"""
Gate G-AP-MULTI: Multi-Round AnswerPack Requirements

Validates:
1. Multi-round depth ≤ 3 (RED LINE - prevent infinite loops)
2. Follow-up questions tracked with dependencies
3. full_auto mode prohibits follow-up questions
4. Question budget enforced across rounds
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def check_multi_depth_limit():
    """Check max depth limit is enforced."""
    multi_file = project_root / "agentos" / "core" / "answers" / "multiround.py"
    
    if not multi_file.exists():
        return False, "Multi-round file not found"
    
    content = multi_file.read_text()
    
    # Check MAX_DEPTH constant
    if "MAX_DEPTH = 3" not in content and "MAX_DEPTH=3" not in content:
        return False, "MAX_DEPTH constant not set to 3"
    
    # Check depth enforcement
    if "current_depth >= " not in content:
        return False, "Depth not being checked"
    
    # Check error on exceeding depth
    if "Maximum depth" not in content:
        return False, "No error message for depth exceeded"
    
    # Check start_round enforces limit
    if "start_round" in content:
        if "raise ValueError" not in content and "raise" not in content:
            return False, "start_round should raise error when depth exceeded"
    
    return True, "Depth limit (≤3) enforced"


def check_multi_dependencies():
    """Check follow-up dependencies are tracked."""
    multi_file = project_root / "agentos" / "core" / "answers" / "multiround.py"
    content = multi_file.read_text()
    
    # Check dependency tracking structure
    if "question_dependencies" not in content:
        return False, "Missing question_dependencies tracking"
    
    # Check triggered_by tracking
    if '"triggered_by"' not in content:
        return False, "Missing triggered_by field"
    
    # Check dependencies are stored
    if "self.question_dependencies[" not in content:
        return False, "Dependencies not being stored"
    
    return True, "Dependencies tracked"


def check_multi_full_auto_block():
    """Check full_auto mode blocks follow-up questions."""
    multi_file = project_root / "agentos" / "core" / "answers" / "multiround.py"
    content = multi_file.read_text()
    
    # Check for execution_mode check
    if "execution_mode" not in content:
        return False, "execution_mode not checked"
    
    # Check full_auto is blocked
    if '"full_auto"' not in content and "'full_auto'" not in content:
        return False, "full_auto mode not checked"
    
    # Should return False for full_auto
    if "should_generate_followup" in content:
        # Look for full_auto check in that method
        lines = content.split("\n")
        in_method = False
        found_check = False
        
        for line in lines:
            if "def should_generate_followup" in line:
                in_method = True
            elif in_method and "def " in line:
                break
            elif in_method and "full_auto" in line and "return False" in line:
                found_check = True
                break
        
        if not found_check:
            return False, "full_auto not properly blocked in should_generate_followup"
    
    return True, "full_auto mode blocks follow-up"


def check_multi_budget_enforcement():
    """Check question budget is enforced across rounds."""
    multi_file = project_root / "agentos" / "core" / "answers" / "multiround.py"
    content = multi_file.read_text()
    
    # Check budget is tracked
    if "question_budget" not in content and "budget_remaining" not in content:
        return False, "Question budget not tracked"
    
    # Check budget prevents follow-up
    if "should_generate_followup" in content:
        if "budget_remaining" not in content:
            return False, "Budget not checked in should_generate_followup"
        
        if "<= 0" not in content and "== 0" not in content:
            return False, "Budget exhaustion not checked"
    
    return True, "Budget enforced across rounds"


def check_multi_context_building():
    """Check context is built from previous rounds."""
    multi_file = project_root / "agentos" / "core" / "answers" / "multiround.py"
    content = multi_file.read_text()
    
    # Check rounds are tracked
    if "self.rounds" not in content:
        return False, "Rounds not tracked"
    
    # Check context building
    if "get_full_context" not in content and "_build_context" not in content:
        return False, "Missing context building method"
    
    # Check previous questions/answers included
    if "previous_questions" not in content or "previous_answers" not in content:
        return False, "Previous rounds not included in context"
    
    return True, "Context built from previous rounds"


def check_multi_consolidation():
    """Check multi-round answers can be consolidated."""
    multi_file = project_root / "agentos" / "core" / "answers" / "multiround.py"
    content = multi_file.read_text()
    
    # Check consolidation method exists
    if "get_final_answer_pack" not in content:
        return False, "Missing get_final_answer_pack method"
    
    # Check answers are merged
    if "consolidated" not in content:
        return False, "Answers not being consolidated"
    
    # Check multi_round metadata
    if '"multi_round": True' not in content and "'multi_round': True" not in content:
        return False, "multi_round flag not set in metadata"
    
    return True, "Multi-round consolidation supported"


def main():
    """Run G-AP-MULTI gate checks."""
    print("🔒 Gate G-AP-MULTI: Multi-Round Requirements")
    print("=" * 60)
    
    checks = [
        ("Depth Limit ≤ 3 (RED LINE)", check_multi_depth_limit),
        ("Dependency Tracking", check_multi_dependencies),
        ("full_auto Mode Blocks Follow-up", check_multi_full_auto_block),
        ("Question Budget Enforcement", check_multi_budget_enforcement),
        ("Context Building", check_multi_context_building),
        ("Answer Consolidation", check_multi_consolidation)
    ]
    
    all_passed = True
    
    for name, check_func in checks:
        passed, message = check_func()
        status = "✓" if passed else "✗"
        print(f"{status} {name}: {message}")
        
        if not passed:
            all_passed = False
    
    print("=" * 60)
    
    if all_passed:
        print("✅ Gate G-AP-MULTI PASSED")
        return 0
    else:
        print("❌ Gate G-AP-MULTI FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
