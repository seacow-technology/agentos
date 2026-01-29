"""
Doctor - Environment health checker and auto-fixer

Provides zero-decision environment setup:
- Check uv, Python 3.13, venv, dependencies
- Auto-fix with `--fix` flag
- Respects "local + minimal admin token" principle
"""

from .checks import run_all_checks, CheckResult, CheckStatus
from .fixes import apply_all_fixes, FixResult
from .report import print_report, print_fix_summary

__all__ = [
    "run_all_checks",
    "CheckResult",
    "CheckStatus",
    "apply_all_fixes",
    "FixResult",
    "print_report",
    "print_fix_summary",
]
