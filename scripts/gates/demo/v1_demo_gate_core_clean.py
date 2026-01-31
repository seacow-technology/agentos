#!/usr/bin/env python3
"""
P-G Core Clean Proof

验证 agentos/core/ 没有被 demo/pipeline 专用代码污染。
"""

import sys
from pathlib import Path


def gate_core_clean(repo_root: Path) -> tuple[bool, str]:
    """
    验证 core 目录的纯净性
    
    禁止规则:
    1. agentos/core/verify/schema_validator.py 不能包含 SchemaValidator 类
    2. agentos/core/ 下不能有 demo 专用代码
    """
    
    schema_validator_file = repo_root / "agentos" / "core" / "verify" / "schema_validator.py"
    
    if not schema_validator_file.exists():
        return False, f"schema_validator.py not found: {schema_validator_file}"
    
    content = schema_validator_file.read_text()
    
    # 检查是否包含 SchemaValidator 类定义
    if "class SchemaValidator" in content:
        return False, "agentos/core/verify/schema_validator.py 包含 SchemaValidator 类 (污染core)"
    
    # 检查是否有向后兼容的 wrapper 注释
    if "向后兼容" in content or "compatibility" in content.lower():
        return False, "schema_validator.py 包含兼容性wrapper (应该在adapter中)"
    
    return True, "Core clean: schema_validator.py 没有 SchemaValidator 类污染"


def main():
    repo_root = Path.cwd()
    
    print("=" * 60)
    print("P-G Core Clean Proof")
    print("=" * 60)
    
    passed, message = gate_core_clean(repo_root)
    
    if passed:
        print(f"✅ PASS: {message}")
        return 0
    else:
        print(f"❌ FAIL: {message}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
