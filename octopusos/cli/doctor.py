"""
agentos doctor - Environment health checker and auto-fixer

Usage:
    agentos doctor              # Check only (read-only)
    agentos doctor --fix        # Auto-fix issues
    agentos doctor --fix --python 3.13  # Specify Python version (optional)

Philosophy:
- Default: Read-only check + clear next steps
- --fix: One-click environment setup (zero decisions)
- Respects "local + minimal admin token" principle
- No admin token needed for project-level operations
"""

import sys
from pathlib import Path

import click
from rich.console import Console

from agentos.core.doctor import (
    run_all_checks,
    apply_all_fixes,
    print_report,
    print_fix_summary,
    CheckStatus,
)

console = Console()


@click.command()
@click.option(
    "--fix",
    is_flag=True,
    default=False,
    help="自动修复检测到的问题（默认只读检查）"
)
@click.option(
    "--python",
    default="3.13",
    help="指定 Python 版本（默认: 3.13）"
)
def doctor(fix: bool, python: str):
    """
    环境健康检查和自动修复

    默认只读检查，显示修复建议。
    使用 --fix 自动执行修复。

    示例：

        agentos doctor              # 检查环境
        agentos doctor --fix        # 一键修复
        agentos doctor --fix --python 3.13  # 指定 Python 版本
    """
    # Get project root (assume we're in agentos/cli, go up 2 levels)
    try:
        # Try to find project root by looking for pyproject.toml
        current = Path.cwd()
        project_root = current

        # Search up to 5 levels
        for _ in range(5):
            if (project_root / "pyproject.toml").exists():
                break
            if project_root.parent == project_root:
                # Reached filesystem root
                project_root = current
                break
            project_root = project_root.parent
        else:
            project_root = current
    except Exception:
        project_root = Path.cwd()

    console.print(f"[dim]项目根目录: {project_root}[/dim]")

    # Run checks
    checks = run_all_checks(project_root)

    # Print report
    print_report(checks, show_fix_commands=(not fix))

    # If not fixing, exit
    if not fix:
        # Exit with error code if any checks failed
        failed = any(c.status == CheckStatus.FAIL for c in checks)
        if failed:
            sys.exit(1)
        else:
            sys.exit(0)

    # Apply fixes
    console.print("[bold cyan]开始自动修复...[/bold cyan]")
    console.print()

    failed_checks = [c for c in checks if c.status == CheckStatus.FAIL]

    if not failed_checks:
        console.print("[bold green]✨ 所有检查通过，无需修复！[/bold green]")
        sys.exit(0)

    results = apply_all_fixes(project_root, failed_checks)

    # Print fix summary
    print_fix_summary(results)

    # Exit with error if any fixes failed
    any_failed = any(not r.success for r in results)
    sys.exit(1 if any_failed else 0)


if __name__ == "__main__":
    doctor()
