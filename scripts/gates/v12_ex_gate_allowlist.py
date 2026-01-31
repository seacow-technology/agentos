#!/usr/bin/env python3
"""
Gate G-EX-ALLOWLIST: Allowlist Extension Requirements

Validates:
1. npm/pip install support
2. Environment variable operations
3. Risk level marking
4. Protected env vars cannot be modified
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def check_allowlist_package_ops():
    """Check npm/pip install support."""
    allowlist_file = project_root / "agentos" / "core" / "executor" / "allowlist.py"
    
    if not allowlist_file.exists():
        return False, "Allowlist file not found"
    
    content = allowlist_file.read_text()
    
    if "package_operations" not in content:
        return False, "Missing package_operations"
    
    if "npm_install" not in content or "pip_install" not in content:
        return False, "npm/pip install not supported"
    
    return True, "Package operations validated"


def check_allowlist_env_ops():
    """Check environment variable operations."""
    allowlist_file = project_root / "agentos" / "core" / "executor" / "allowlist.py"
    content = allowlist_file.read_text()
    
    if "env_operations" not in content:
        return False, "Missing env_operations"
    
    if "set_env" not in content or "_op_set_env" not in content:
        return False, "SET_ENV not implemented"
    
    if "unset_env" not in content or "_op_unset_env" not in content:
        return False, "UNSET_ENV not implemented"
    
    return True, "Environment operations validated"


def check_allowlist_risk_levels():
    """Check risk level marking."""
    allowlist_file = project_root / "agentos" / "core" / "executor" / "allowlist.py"
    content = allowlist_file.read_text()
    
    if "RiskLevel" not in content:
        return False, "RiskLevel enum not defined"
    
    required_levels = ["SAFE", "LOW", "MEDIUM", "HIGH"]
    for level in required_levels:
        if level not in content:
            return False, f"Missing risk level: {level}"
    
    if "get_risk_level" not in content:
        return False, "Missing get_risk_level method"
    
    return True, "Risk levels validated"


def check_allowlist_protected_vars():
    """Check protected env vars cannot be modified."""
    allowlist_file = project_root / "agentos" / "core" / "executor" / "allowlist.py"
    content = allowlist_file.read_text()
    
    if "_op_set_env" not in content:
        return False, "SET_ENV operation not found"
    
    # Check for forbidden list
    if "forbidden" not in content.lower():
        return False, "No forbidden env vars list"
    
    # Check for protection of critical vars
    protected_vars = ["PATH", "HOME"]
    has_protection = any(var in content for var in protected_vars)
    
    if not has_protection:
        return False, "Critical env vars not protected"
    
    return True, "Protected vars validated"


def main():
    print("🔒 Gate G-EX-ALLOWLIST: Allowlist Extension Requirements")
    print("=" * 60)
    
    checks = [
        ("Package Operations (npm/pip)", check_allowlist_package_ops),
        ("Environment Operations", check_allowlist_env_ops),
        ("Risk Level Marking", check_allowlist_risk_levels),
        ("Protected Variables", check_allowlist_protected_vars)
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
        print("✅ Gate G-EX-ALLOWLIST PASSED")
        return 0
    else:
        print("❌ Gate G-EX-ALLOWLIST FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
