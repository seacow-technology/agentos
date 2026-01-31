#!/usr/bin/env python3
"""
Pipeline Gate P-D: 结构稳定性验证

检查 PR_ARTIFACTS.md 结构是否完整，支持两种状态：
1. SUCCESS状态：包含所有必需章节
2. BLOCKED状态：BLOCKERS.md存在且结构完整

验收标准：
- SUCCESS case: PR_ARTIFACTS.md包含所有必需章节
- BLOCKED case: BLOCKERS.md存在且有Reason/Questions/Solution
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
EXPECTED_DIR = PROJECT_ROOT / "examples" / "pipeline" / "expected"

# SUCCESS状态必需章节
REQUIRED_SECTIONS_SUCCESS = [
    "# PR Artifacts Summary",
    "## Summary",
    "## Risk Analysis",
    "## Commit Plan",
    "## Evidence Coverage",
    "## Open Questions",
    "## Verification",
    "### Checksums"
]

# BLOCKED状态必需章节
REQUIRED_SECTIONS_BLOCKED = [
    "# Pipeline Blocked",
    "## Reason",
    "## Questions",
    "## Solution"
]


def check_pr_artifacts_structure(file_path: Path) -> tuple[bool, list]:
    """检查PR_ARTIFACTS.md结构"""
    if not file_path.exists():
        return False, ["PR_ARTIFACTS.md not found"]
    
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    missing = []
    for section in REQUIRED_SECTIONS_SUCCESS:
        if section not in content:
            missing.append(section)
    
    return len(missing) == 0, missing


def check_blockers_structure(file_path: Path) -> tuple[bool, list]:
    """检查BLOCKERS.md结构"""
    if not file_path.exists():
        return False, ["BLOCKERS.md not found"]
    
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    missing = []
    for section in REQUIRED_SECTIONS_BLOCKED:
        if section not in content:
            missing.append(section)
    
    return len(missing) == 0, missing


def main():
    print("=" * 70)
    print("Pipeline Gate P-D: 结构稳定性验证")
    print("=" * 70)
    print()
    
    # 检查3个case
    cases = ["nl_001", "nl_002", "nl_003"]
    results = {}
    
    for case in cases:
        case_dir = EXPECTED_DIR / case
        print(f"Checking {case}...")
        
        # 先检查是否是BLOCKED状态
        blockers_file = case_dir / "BLOCKERS.md"
        if blockers_file.exists():
            # BLOCKED case - 检查BLOCKERS.md结构
            is_valid, missing = check_blockers_structure(blockers_file)
            if is_valid:
                results[case] = ("blocked_ok", [])
                print(f"   ✅ BLOCKERS.md structure complete")
            else:
                results[case] = ("blocked_incomplete", missing)
                print(f"   ❌ BLOCKERS.md structure incomplete:")
                for m in missing:
                    print(f"      - Missing: {m}")
        else:
            # SUCCESS case - 检查PR_ARTIFACTS.md结构
            pr_artifacts_file = case_dir / "04_pr_artifacts" / "PR_ARTIFACTS.md"
            is_valid, missing = check_pr_artifacts_structure(pr_artifacts_file)
            if is_valid:
                results[case] = ("success_ok", [])
                print(f"   ✅ PR_ARTIFACTS.md structure complete")
            else:
                results[case] = ("success_incomplete", missing)
                print(f"   ❌ PR_ARTIFACTS.md structure incomplete:")
                for m in missing:
                    print(f"      - Missing: {m}")
        
        print()
    
    # 汇总结果
    print("=" * 70)
    
    passed = sum(1 for status, _ in results.values() if status in ("success_ok", "blocked_ok"))
    total = len(results)
    
    if passed == total:
        print(f"✅ Gate P-D PASSED: All {total} cases have correct structure")
        for case, (status, _) in results.items():
            status_label = "SUCCESS structure" if status == "success_ok" else "BLOCKED structure"
            print(f"   - {case}: {status_label}")
        return 0
    else:
        print(f"❌ Gate P-D FAILED: {total - passed} cases with issues")
        for case, (status, missing) in results.items():
            if status not in ("success_ok", "blocked_ok"):
                print(f"   - {case}: {len(missing)} missing sections")
        return 1


if __name__ == "__main__":
    sys.exit(main())
