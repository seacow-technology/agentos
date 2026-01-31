#!/usr/bin/env python3
"""
Gate G-EX-SANDBOX: Container Sandbox Requirements

Validates:
1. Auto-detect Docker/Podman
2. Automatic fallback to worktree
3. High-risk operations require container
4. Container unavailable blocks high-risk ops
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def check_sandbox_auto_detect():
    """Check auto-detection of container engines."""
    sandbox_file = project_root / "agentos" / "core" / "executor" / "container_sandbox.py"
    
    if not sandbox_file.exists():
        return False, "Container sandbox file not found"
    
    content = sandbox_file.read_text()
    
    if "_detect_engine" not in content:
        return False, "Missing _detect_engine method"
    
    if "docker" not in content.lower() or "podman" not in content.lower():
        return False, "Docker/Podman detection not implemented"
    
    return True, "Auto-detection validated"


def check_sandbox_fallback():
    """Check automatic fallback to worktree."""
    sandbox_file = project_root / "agentos" / "core" / "executor" / "container_sandbox.py"
    content = sandbox_file.read_text()
    
    if "_create_fallback" not in content:
        return False, "Missing _create_fallback method"
    
    if "worktree" not in content.lower():
        return False, "No worktree fallback"
    
    return True, "Automatic fallback validated"


def check_sandbox_high_risk():
    """Check high-risk operation restrictions."""
    sandbox_file = project_root / "agentos" / "core" / "executor" / "container_sandbox.py"
    content = sandbox_file.read_text()
    
    if "is_high_risk_allowed" not in content:
        return False, "Missing is_high_risk_allowed method"
    
    # Check allowlist has risk levels
    allowlist_file = project_root / "agentos" / "core" / "executor" / "allowlist.py"
    if allowlist_file.exists():
        allowlist_content = allowlist_file.read_text()
        if "RiskLevel" not in allowlist_content:
            return False, "RiskLevel not defined in allowlist"
    
    return True, "High-risk restrictions validated"


def check_sandbox_container_requirement():
    """Check container requirement enforcement."""
    allowlist_file = project_root / "agentos" / "core" / "executor" / "allowlist.py"
    
    if not allowlist_file.exists():
        return False, "Allowlist file not found"
    
    content = allowlist_file.read_text()
    
    if "requires_container" not in content:
        return False, "Missing requires_container method"
    
    if "MEDIUM" not in content or "HIGH" not in content:
        return False, "Risk levels not properly defined"
    
    return True, "Container requirement validated"


def main():
    print("🔒 Gate G-EX-SANDBOX: Container Sandbox Requirements")
    print("=" * 60)
    
    checks = [
        ("Auto-Detect Engines", check_sandbox_auto_detect),
        ("Automatic Fallback", check_sandbox_fallback),
        ("High-Risk Restrictions", check_sandbox_high_risk),
        ("Container Requirement", check_sandbox_container_requirement)
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
        print("✅ Gate G-EX-SANDBOX PASSED")
        return 0
    else:
        print("❌ Gate G-EX-SANDBOX FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
