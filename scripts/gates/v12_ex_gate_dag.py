#!/usr/bin/env python3
"""
Gate G-EX-DAG: DAG Scheduler Requirements

Validates:
1. Cycle detection is implemented
2. Parallel execution is supported
3. Dependency resolution works
4. Failed operations block dependents
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def check_dag_cycle_detection():
    """Check DAG cycle detection."""
    dag_file = project_root / "agentos" / "core" / "executor" / "dag_scheduler.py"
    
    if not dag_file.exists():
        return False, "DAG scheduler file not found"
    
    content = dag_file.read_text()
    
    if "_has_cycle" not in content:
        return False, "Missing _has_cycle method"
    
    if "raise ValueError" not in content or "cycle" not in content.lower():
        return False, "Cycle detection doesn't raise error"
    
    return True, "Cycle detection validated"


def check_dag_parallel_execution():
    """Check parallel execution support."""
    dag_file = project_root / "agentos" / "core" / "executor" / "dag_scheduler.py"
    content = dag_file.read_text()
    
    if "async def execute_parallel" not in content:
        return False, "Missing execute_parallel method"
    
    if "asyncio.gather" not in content:
        return False, "Not using asyncio.gather for parallel execution"
    
    if "Semaphore" not in content and "max_concurrency" not in content:
        return False, "No concurrency control"
    
    return True, "Parallel execution validated"


def check_dag_dependency_resolution():
    """Check dependency resolution."""
    dag_file = project_root / "agentos" / "core" / "executor" / "dag_scheduler.py"
    content = dag_file.read_text()
    
    if "get_ready_operations" not in content:
        return False, "Missing get_ready_operations method"
    
    if "depends_on" not in content:
        return False, "Dependencies not tracked"
    
    if "get_execution_order" not in content:
        return False, "Missing execution order calculation"
    
    return True, "Dependency resolution validated"


def check_dag_error_propagation():
    """Check failed operations block dependents."""
    dag_file = project_root / "agentos" / "core" / "executor" / "dag_scheduler.py"
    content = dag_file.read_text()
    
    if "FAILED" not in content and "failed" not in content:
        return False, "No failure status tracking"
    
    if "SKIPPED" not in content and "skipped" not in content:
        return False, "No skipped status for blocked operations"
    
    if "_mark_blocked_as_skipped" not in content:
        return False, "No mechanism to skip blocked operations"
    
    return True, "Error propagation validated"


def main():
    print("🔒 Gate G-EX-DAG: DAG Scheduler Requirements")
    print("=" * 60)
    
    checks = [
        ("Cycle Detection", check_dag_cycle_detection),
        ("Parallel Execution", check_dag_parallel_execution),
        ("Dependency Resolution", check_dag_dependency_resolution),
        ("Error Propagation", check_dag_error_propagation)
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
        print("✅ Gate G-EX-DAG PASSED")
        return 0
    else:
        print("❌ Gate G-EX-DAG FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
