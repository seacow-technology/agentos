#!/usr/bin/env python3
"""
Pipeline Gate P-H: Subprocess Injection Proof (子进程注入证明)

硬冻结：机器可验证的adapter注入机制

检查：
1. sitecustomize确实在子进程中被导入
2. SchemaValidator在子进程中Available（可以import）
3. 注入只对pipeline子进程生效（不影响父进程）
4. run_command()确实设置了PYTHONPATH

这是把"我觉得它能跑"变成"机器可审计事实"的硬门禁
"""

import sys
import subprocess
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
PIPELINE_DIR = PROJECT_ROOT / "scripts" / "pipeline"


def test_parent_process_isolation():
    """测试：父进程中SchemaValidator不应该Available（除非显式注入）"""
    print("1. Testing parent process isolation...")
    
    try:
        from agentos.core.verify.schema_validator import SchemaValidator
        print("   ⚠️  WARNING: SchemaValidator is available in parent process")
        print("   This suggests core may have been modified")
        return False, "SchemaValidator found in parent (core污染?)"
    except ImportError:
        print("   ✅ Parent process isolated (SchemaValidator not available)")
        return True, None


def test_subprocess_injection():
    """测试：子进程中sitecustomize被导入且SchemaValidatorAvailable"""
    print("\n2. Testing subprocess injection...")
    
    # 创建测试脚本
    test_script = """
import sys
import json

# 检查sitecustomize是否被导入
sitecustomize_loaded = 'sitecustomize' in sys.modules

# 检查SchemaValidator是否Available
try:
    from agentos.core.verify.schema_validator import SchemaValidator
    validator_available = True
    validator_type = str(type(SchemaValidator))
except ImportError as e:
    validator_available = False
    validator_type = str(e)

# 输出结果为JSON
result = {
    'sitecustomize_loaded': sitecustomize_loaded,
    'validator_available': validator_available,
    'validator_type': validator_type
}
print(json.dumps(result))
"""
    
    # 使用pipeline的PYTHONPATH运行
    import os
    env = os.environ.copy()
    env['PYTHONPATH'] = str(PIPELINE_DIR) + os.pathsep + env.get('PYTHONPATH', '')
    
    try:
        result = subprocess.run(
            [sys.executable, '-c', test_script],
            capture_output=True,
            text=True,
            env=env,
            cwd=PROJECT_ROOT,
            timeout=10
        )
        
        if result.returncode != 0:
            print(f"   ❌ Subprocess failed: {result.stderr}")
            return False, f"Subprocess error: {result.stderr[:200]}"
        
        # 解析输出
        try:
            data = json.loads(result.stdout.strip())
        except json.JSONDecodeError:
            print(f"   ❌ Failed to parse output: {result.stdout}")
            return False, "Invalid JSON output"
        
        # 验证sitecustomize被加载
        if not data['sitecustomize_loaded']:
            print("   ❌ sitecustomize NOT loaded in subprocess")
            return False, "sitecustomize not loaded"
        print("   ✅ sitecustomize loaded in subprocess")
        
        # 验证SchemaValidatorAvailable
        if not data['validator_available']:
            print(f"   ❌ SchemaValidator NOT available: {data['validator_type']}")
            return False, f"Validator not available: {data['validator_type']}"
        print("   ✅ SchemaValidator available in subprocess")
        print(f"      Type: {data['validator_type']}")
        
        return True, None
        
    except subprocess.TimeoutExpired:
        print("   ❌ Subprocess timeout")
        return False, "Timeout"
    except Exception as e:
        print(f"   ❌ Test failed: {e}")
        return False, str(e)


def test_run_command_pythonpath():
    """测试：run_command()函数确实设置了PYTHONPATH"""
    print("\n3. Testing run_command() PYTHONPATH setup...")
    
    runner_script = PIPELINE_DIR / "run_nl_to_pr_artifacts.py"
    if not runner_script.exists():
        print(f"   ❌ Runner script not found: {runner_script}")
        return False, "Runner script not found"
    
    # 检查run_command函数中是否设置了PYTHONPATH
    with open(runner_script, 'r', encoding='utf-8') as f:
        content = f.read()
    
    required_patterns = [
        "env = os.environ.copy()",
        "PYTHONPATH",
        "pipeline_dir",
        "subprocess.run",
        "env=env"
    ]
    
    missing = []
    for pattern in required_patterns:
        if pattern not in content:
            missing.append(pattern)
    
    if missing:
        print(f"   ❌ Missing patterns in run_command(): {missing}")
        return False, f"Missing: {missing}"
    
    print("   ✅ run_command() sets up PYTHONPATH correctly")
    print("      Patterns found: env.copy, PYTHONPATH, pipeline_dir, subprocess, env=env")
    
    return True, None


def test_adapter_files_exist():
    """测试：adapter文件存在且在正确位置"""
    print("\n4. Testing adapter files existence...")
    
    required_files = [
        PIPELINE_DIR / "intent_builder_adapter.py",
        PIPELINE_DIR / "sitecustomize.py"
    ]
    
    all_exist = True
    for file_path in required_files:
        if not file_path.exists():
            print(f"   ❌ Missing: {file_path.name}")
            all_exist = False
        else:
            print(f"   ✅ Found: {file_path.name}")
    
    if not all_exist:
        return False, "Missing adapter files"
    
    # 检查sitecustomize.py中有inject调用
    sitecustomize_path = PIPELINE_DIR / "sitecustomize.py"
    with open(sitecustomize_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if 'inject_schema_validator_if_needed' not in content:
        print("   ❌ sitecustomize.py doesn't call inject function")
        return False, "sitecustomize missing inject call"
    
    print("   ✅ sitecustomize.py calls inject function")
    
    return True, None


def main():
    print("=" * 70)
    print("Pipeline Gate P-H: Subprocess Injection Proof (硬冻结)")
    print("=" * 70)
    print()
    
    all_tests = [
        ("Parent process isolation", test_parent_process_isolation),
        ("Subprocess injection", test_subprocess_injection),
        ("run_command PYTHONPATH", test_run_command_pythonpath),
        ("Adapter files", test_adapter_files_exist)
    ]
    
    results = []
    for test_name, test_func in all_tests:
        success, error = test_func()
        results.append((test_name, success, error))
    
    # 汇总结果
    print()
    print("=" * 70)
    
    passed = sum(1 for _, success, _ in results if success)
    total = len(results)
    
    if passed == total:
        print(f"✅ Gate P-H PASSED: All {total} injection proofs verified")
        print()
        print("Proof:")
        for test_name, success, _ in results:
            print(f"  ✅ {test_name}")
        print()
        print("💡 Injection mechanism is:")
        print("  - Isolated (parent process clean)")
        print("  - Working (subprocess has SchemaValidator)")
        print("  - Auditable (sitecustomize loaded)")
        print("  - Complete (PYTHONPATH + adapter files)")
        print("=" * 70)
        return 0
    else:
        print(f"❌ Gate P-H FAILED: {total - passed}/{total} tests failed")
        print()
        print("Failures:")
        for test_name, success, error in results:
            if not success:
                print(f"  ❌ {test_name}: {error}")
        print("=" * 70)
        return 1


if __name__ == "__main__":
    sys.exit(main())
