#!/usr/bin/env python3
"""
Pipeline Gate P-B: 端到端可运行性验证

检查：
1. 能否找到所有 NL 输入文件（.txt格式）
2. Pipeline runner 对所有 case 运行成功（或正确 BLOCKED）
3. 输出目录结构完整

验收标准：
- 3个case都运行完成（success或blocked）
- 输出目录存在所有必需的子目录
- 对于blocked case，验证BLOCKERS.md存在

注意：此Gate使用uv确保可复现环境
"""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
NL_DIR = PROJECT_ROOT / "examples" / "pipeline" / "nl"
TEMP_OUT_DIR = PROJECT_ROOT / "outputs" / "pipeline" / "gate_b_test"


def main():
    print("=" * 70)
    print("Pipeline Gate P-B: 端到端可运行性验证")
    print("=" * 70)
    print()
    
    # 查找所有.txt输入
    txt_files = sorted(NL_DIR.glob("*.txt"))
    if not txt_files:
        print("❌ No .txt files found in examples/pipeline/nl/")
        return 1
    
    print(f"Found {len(txt_files)} NL cases (txt format)\n")
    
    # 运行每个case
    results = {}
    for txt_file in txt_files:
        case_name = txt_file.stem
        output_dir = TEMP_OUT_DIR / case_name
        
        print(f"\n{len(results)+1}. Running Pipeline for {case_name}...")
        
        cmd = [
            "uv", "run", "python", 
            str(PROJECT_ROOT / "scripts" / "pipeline" / "run_nl_to_pr_artifacts.py"),
            "--nl", str(txt_file),
            "--out", str(output_dir)
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=PROJECT_ROOT
            )
            
            # 检查是否正确BLOCKED（如果有question pack）
            if "Pipeline BLOCKED" in result.stdout or "BLOCKED" in result.stdout:
                # 验证BLOCKED结构
                blockers_file = output_dir / "BLOCKERS.md"
                if blockers_file.exists():
                    results[case_name] = "blocked_correctly"
                    print(f"   ✅ {case_name}: BLOCKED (with BLOCKERS.md)")
                else:
                    results[case_name] = "blocked_no_file"
                    print(f"   ❌ {case_name}: BLOCKED but missing BLOCKERS.md")
            
            # 检查是否成功完成
            elif result.returncode == 0 and "Pipeline Complete" in result.stdout:
                # 验证输出结构
                required_dirs = [
                    output_dir / "01_intent",
                    output_dir / "04_pr_artifacts",
                    output_dir / "audit"
                ]
                if all(d.exists() for d in required_dirs):
                    results[case_name] = "success"
                    print(f"   ✅ {case_name}: SUCCESS (complete output)")
                else:
                    results[case_name] = "incomplete_output"
                    print(f"   ❌ {case_name}: SUCCESS but incomplete output dirs")
            
            else:
                results[case_name] = "execution_failed"
                print(f"   ❌ {case_name}: execution failed")
                if result.stderr:
                    print(f"      Error: {result.stderr[:200]}")
        
        except subprocess.TimeoutExpired:
            results[case_name] = "timeout"
            print(f"   ❌ {case_name}: timeout")
        except Exception as e:
            results[case_name] = "error"
            print(f"   ❌ {case_name}: {e}")
    
    # 汇总结果
    print()
    print("=" * 70)
    
    success_count = sum(1 for v in results.values() if v in ("success", "blocked_correctly"))
    total = len(results)
    
    if success_count == total:
        print(f"✅ Gate P-B PASSED: All {total} cases ran correctly")
        for case, status in results.items():
            status_label = "SUCCESS" if status == "success" else "BLOCKED (正确)"
            print(f"   - {case}: {status_label}")
        return 0
    else:
        print(f"❌ Gate P-B FAILED: {total - success_count}/{total} cases failed")
        for case, status in results.items():
            if status not in ("success", "blocked_correctly"):
                print(f"   - {case}: {status}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
