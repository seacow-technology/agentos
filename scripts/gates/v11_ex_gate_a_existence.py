#!/usr/bin/env python3
"""
EX Gate A - Executor 存在性检查

验证所有Phase 2核心文件存在
"""

import sys
from pathlib import Path

EXIT_CODE = 0
PROJECT_ROOT = Path(__file__).parent.parent.parent


def check_file(filepath: str, description: str):
    """检查单个文件是否存在"""
    global EXIT_CODE
    full_path = PROJECT_ROOT / filepath
    if full_path.exists():
        print(f"✓ {description}: {filepath}")
    else:
        print(f"✗ {description}: {filepath} - NOT FOUND")
        EXIT_CODE = 1


def main():
    global EXIT_CODE
    
    print("=" * 60)
    print("EX Gate A - Executor Existence Check")
    print("=" * 60)
    print()
    
    # Schemas (4个)
    print("[Schemas]")
    check_file("agentos/schemas/executor/execution_request.schema.json", "Execution Request Schema")
    check_file("agentos/schemas/executor/execution_result.schema.json", "Execution Result Schema")
    check_file("agentos/schemas/executor/run_tape.schema.json", "Run Tape Schema")
    check_file("agentos/schemas/executor/sandbox_policy.schema.json", "Sandbox Policy Schema")
    print()
    
    # Core 模块 (7个)
    print("[Core Modules]")
    check_file("agentos/core/executor/__init__.py", "Executor __init__")
    check_file("agentos/core/executor/allowlist.py", "Allowlist")
    check_file("agentos/core/executor/sandbox.py", "Sandbox")
    check_file("agentos/core/executor/rollback.py", "Rollback Manager")
    check_file("agentos/core/executor/lock.py", "Execution Lock")
    check_file("agentos/core/executor/review_gate.py", "Review Gate")
    check_file("agentos/core/executor/audit_logger.py", "Audit Logger")
    check_file("agentos/core/executor/executor_engine.py", "Executor Engine")
    print()
    
    # CLI
    print("[CLI]")
    check_file("agentos/cli/executor.py", "Executor CLI")
    print()
    
    # Fixtures目录
    print("[Fixtures]")
    fixtures_dir = PROJECT_ROOT / "fixtures/executor"
    if fixtures_dir.exists():
        print(f"✓ Fixtures directory: fixtures/executor")
    else:
        print(f"✗ Fixtures directory: fixtures/executor - NOT FOUND")
        EXIT_CODE = 1
    print()
    
    # 总结
    print("=" * 60)
    if EXIT_CODE == 0:
        print("✅ EX Gate A: ALL FILES EXIST")
    else:
        print("❌ EX Gate A: MISSING FILES")
    print("=" * 60)
    
    return EXIT_CODE


if __name__ == "__main__":
    sys.exit(main())
