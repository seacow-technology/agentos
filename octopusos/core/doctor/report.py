"""
Doctor report formatting

Provides clean, actionable output with:
- Status icons (✅/⚠️/❌)
- Clear next steps
- Dry-run command preview
"""

from typing import List

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .checks import CheckResult, CheckStatus
from .fixes import FixResult

console = Console()


def print_report(checks: List[CheckResult], show_fix_commands: bool = True):
    """Print check results in a clean table"""
    console.print()
    console.print("[bold cyan]AgentOS 环境检查[/bold cyan]")
    console.print()

    # Create table
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("状态", width=6, justify="center")
    table.add_column("检查项", width=20)
    table.add_column("结果", width=50)

    pass_count = 0
    warn_count = 0
    fail_count = 0

    for check in checks:
        # Status icon
        if check.status == CheckStatus.PASS:
            icon = "✅"
            style = "green"
            pass_count += 1
        elif check.status == CheckStatus.WARN:
            icon = "⚠️"
            style = "yellow"
            warn_count += 1
        else:
            icon = "❌"
            style = "red"
            fail_count += 1

        # Summary
        summary = check.summary

        # Add details if present
        if check.details:
            summary += "\n" + "\n".join(f"  • {d}" for d in check.details)

        table.add_row(
            f"[{style}]{icon}[/{style}]",
            check.name,
            f"[{style}]{summary}[/{style}]"
        )

    console.print(table)
    console.print()

    # Summary
    total = len(checks)
    if fail_count == 0 and warn_count == 0:
        console.print(f"[bold green]✨ 所有检查通过！ ({pass_count}/{total})[/bold green]")
    else:
        console.print(f"[bold]总计:[/bold] {pass_count} 通过, {warn_count} 警告, {fail_count} 失败")

    console.print()

    # Show fix commands if requested
    if show_fix_commands and fail_count > 0:
        print_fix_commands(checks)


def print_fix_commands(checks: List[CheckResult]):
    """Print commands that would be executed with --fix"""
    console.print("[bold yellow]建议修复步骤:[/bold yellow]")
    console.print()

    has_fixes = False
    needs_admin = False

    for check in checks:
        if check.status == CheckStatus.FAIL and check.fix_cmd:
            has_fixes = True
            cmd_str = " ".join(check.fix_cmd)

            if check.needs_admin:
                needs_admin = True
                console.print(f"  [yellow]⚠ {check.name}:[/yellow] {cmd_str} [dim](需要管理员权限)[/dim]")
            else:
                console.print(f"  [cyan]• {check.name}:[/cyan] {cmd_str}")

    console.print()

    if has_fixes:
        console.print("[bold green]一键自动修复:[/bold green]")
        console.print()
        console.print("  [bold cyan]agentos doctor --fix[/bold cyan]")
        console.print()

        if needs_admin:
            console.print("[yellow]注意: 部分修复需要管理员权限（将跳过）[/yellow]")
            console.print()


def print_fix_summary(results: List[FixResult]):
    """Print fix results"""
    console.print()
    console.print("[bold cyan]修复结果[/bold cyan]")
    console.print()

    success_count = 0
    fail_count = 0

    for result in results:
        if result.success:
            icon = "✅"
            style = "green"
            success_count += 1
        else:
            icon = "❌"
            style = "red"
            fail_count += 1

        console.print(f"{icon} [{style}]{result.check_name}:[/{style}] {result.message}")

        if result.details:
            for detail in result.details:
                console.print(f"  [dim]{detail}[/dim]")

    console.print()

    if fail_count == 0:
        console.print("[bold green]✨ 所有修复完成！[/bold green]")
        console.print()
        console.print("[bold cyan]下一步:[/bold cyan]")
        console.print("  1. 重新运行检查: [cyan]agentos doctor[/cyan]")
        console.print("  2. 运行测试: [cyan]uv run pytest -q[/cyan]")
        console.print("  3. 启动 AgentOS: [cyan]uv run agentos --help[/cyan]")
    else:
        console.print(f"[yellow]部分修复失败 ({fail_count}/{len(results)})[/yellow]")
        console.print()
        console.print("[bold]建议:[/bold]")
        console.print("  • 检查网络连接")
        console.print("  • 查看上面的错误详情")
        console.print("  • 手动执行失败的命令")

    console.print()


def print_dry_run_summary(checks: List[CheckResult]):
    """Print what --fix would do (dry-run)"""
    failed = [c for c in checks if c.status == CheckStatus.FAIL]

    if not failed:
        console.print("[bold green]✨ 环境已就绪，无需修复！[/bold green]")
        return

    console.print()
    console.print("[bold yellow]--fix 将执行以下操作:[/bold yellow]")
    console.print()

    for check in failed:
        if check.fix_cmd:
            cmd_str = " ".join(check.fix_cmd)
            console.print(f"  [cyan]{check.name}:[/cyan]")
            console.print(f"    $ {cmd_str}")
            if check.needs_admin:
                console.print("    [yellow](需要管理员权限，将跳过)[/yellow]")
            console.print()

    console.print("[bold cyan]运行以下命令执行修复:[/bold cyan]")
    console.print()
    console.print("  [bold]agentos doctor --fix[/bold]")
    console.print()
