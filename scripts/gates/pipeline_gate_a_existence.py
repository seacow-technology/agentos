#!/usr/bin/env python3
"""
Pipeline Gate P-A: 存在性验证

检查:
- Runner脚本存在
- 文档存在
- 3个NL case存在
- 预期输出目录存在
"""

import sys
from pathlib import Path


def check_existence():
    """检查所有必需文件是否存在"""
    project_root = Path(__file__).parent.parent.parent
    
    print("=" * 70)
    print("Pipeline Gate P-A: 存在性验证")
    print("=" * 70)
    
    failures = []
    
    # 检查Runner脚本
    print("\n1. 检查Runner脚本...")
    runner_script = project_root / "scripts" / "pipeline" / "run_nl_to_pr_artifacts.py"
    if runner_script.exists():
        print(f"   ✅ Runner script exists: {runner_script}")
    else:
        print(f"   ❌ Runner script missing: {runner_script}")
        failures.append("Runner script")
    
    # 检查文档
    print("\n2. 检查文档...")
    docs = [
        "docs/pipeline/README.md",
        "docs/pipeline/RUNBOOK.md",
        "docs/pipeline/V10_PIPELINE_FREEZE_REPORT.md"
    ]
    
    for doc_path in docs:
        full_path = project_root / doc_path
        if full_path.exists():
            print(f"   ✅ {doc_path}")
        else:
            print(f"   ❌ {doc_path}")
            failures.append(doc_path)
    
    # 检查NL cases
    print("\n3. 检查NL cases...")
    nl_cases = [
        "examples/nl/nl_001.yaml",
        "examples/nl/nl_001.json",  # Also accept JSON
        "examples/nl/nl_002.yaml",
        "examples/nl/nl_002.json",
        "examples/nl/nl_003.yaml",
        "examples/nl/nl_003.json"
    ]
    
    for i in range(1, 4):
        yaml_path = project_root / f"examples/nl/nl_00{i}.yaml"
        json_path = project_root / f"examples/nl/nl_00{i}.json"
        if yaml_path.exists() or json_path.exists():
            print(f"   ✅ nl_00{i} (yaml or json)")
        else:
            print(f"   ❌ nl_00{i} (neither yaml nor json)")
            failures.append(f"nl_00{i}")
    
    # 检查预期输出目录（可选）
    print("\n4. 检查预期输出目录（可选）...")
    expected_dir = project_root / "examples" / "pipeline" / "expected"
    if expected_dir.exists():
        print(f"   ✅ Expected output directory exists")
        # 检查子目录
        for case in ["nl_001", "nl_002", "nl_003"]:
            case_dir = expected_dir / case
            if case_dir.exists():
                print(f"      ✅ {case}/")
            else:
                print(f"      ⚠️  {case}/ (will be generated)")
    else:
        print(f"   ⚠️  Expected output directory not yet created (will be generated)")
    
    # 总结
    print("\n" + "=" * 70)
    if failures:
        print(f"❌ Gate P-A FAILED: {len(failures)} missing items")
        for item in failures:
            print(f"   - {item}")
        return 1
    else:
        print("✅ Gate P-A PASSED: All required files exist")
        return 0


if __name__ == "__main__":
    sys.exit(check_existence())
