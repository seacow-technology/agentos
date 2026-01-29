"""
Auto-fix implementations

Each fix function:
- Takes project_root and check_result
- Returns FixResult with success/failure
- Prints progress using rich
"""

import platform
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from .checks import CheckResult, CheckStatus

console = Console()


@dataclass
class FixResult:
    """Result of a fix attempt"""
    check_name: str
    success: bool
    message: str
    details: Optional[List[str]] = None


def apply_all_fixes(project_root: Path, failed_checks: List[CheckResult]) -> List[FixResult]:
    """Apply fixes for all failed checks"""
    results = []

    for check in failed_checks:
        if check.status == CheckStatus.PASS:
            continue

        # Skip checks that need admin without permission
        if check.needs_admin:
            results.append(FixResult(
                check_name=check.name,
                success=False,
                message=f"跳过 {check.name}（需要管理员权限）",
                details=["请手动安装或使用 sudo/管理员权限运行"]
            ))
            continue

        # Apply fix based on check name
        if check.name == "uv":
            result = fix_uv()
        elif check.name == "python-3.13":
            result = fix_python_313()
        elif check.name == "venv":
            result = fix_venv(project_root)
        elif check.name == "dependencies":
            result = fix_dependencies(project_root)
        elif check.name == "pytest":
            result = fix_pytest(project_root)
        else:
            result = FixResult(
                check_name=check.name,
                success=False,
                message=f"没有自动修复方案: {check.name}"
            )

        results.append(result)

    return results


# ============================================
# Fix Implementations
# ============================================

def fix_uv() -> FixResult:
    """Install uv"""
    console.print("[yellow]正在安装 uv...[/yellow]")

    system = platform.system()

    try:
        if system == "Windows":
            # Windows: PowerShell script
            cmd = [
                "powershell",
                "-ExecutionPolicy", "ByPass",
                "-c",
                "irm https://astral.sh/uv/install.ps1 | iex"
            ]
        else:
            # macOS/Linux: curl | sh
            cmd = ["sh", "-c", "curl -LsSf https://astral.sh/uv/install.sh | sh"]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120
        )

        if result.returncode == 0:
            return FixResult(
                check_name="uv",
                success=True,
                message="uv 安装成功",
                details=[
                    "请重新打开终端以刷新 PATH",
                    "或运行: source ~/.bashrc (Linux) / source ~/.zshrc (macOS)"
                ]
            )
        else:
            return FixResult(
                check_name="uv",
                success=False,
                message="uv 安装失败",
                details=[result.stderr.strip()]
            )

    except Exception as e:
        return FixResult(
            check_name="uv",
            success=False,
            message="uv 安装失败",
            details=[str(e)]
        )


def fix_python_313() -> FixResult:
    """Install Python 3.13 via uv"""
    console.print("[yellow]正在安装 Python 3.13...[/yellow]")

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("下载并安装 Python 3.13...", total=None)

            result = subprocess.run(
                ["uv", "python", "install", "3.13"],
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes
            )

            progress.update(task, completed=True)

        if result.returncode == 0:
            # Verify installation
            verify_result = subprocess.run(
                ["uv", "python", "find", "3.13"],
                capture_output=True,
                text=True,
                timeout=10
            )
            python_path = verify_result.stdout.strip()

            return FixResult(
                check_name="python-3.13",
                success=True,
                message="Python 3.13 安装成功",
                details=[f"路径: {python_path}"]
            )
        else:
            return FixResult(
                check_name="python-3.13",
                success=False,
                message="Python 3.13 安装失败",
                details=[result.stderr.strip()]
            )

    except Exception as e:
        return FixResult(
            check_name="python-3.13",
            success=False,
            message="Python 3.13 安装失败",
            details=[str(e)]
        )


def fix_venv(project_root: Path) -> FixResult:
    """Create/recreate .venv"""
    console.print("[yellow]正在创建虚拟环境...[/yellow]")

    try:
        result = subprocess.run(
            ["uv", "venv", "--python", "3.13"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode == 0:
            venv_path = project_root / ".venv"
            return FixResult(
                check_name="venv",
                success=True,
                message="虚拟环境创建成功",
                details=[f"路径: {venv_path}"]
            )
        else:
            return FixResult(
                check_name="venv",
                success=False,
                message="虚拟环境创建失败",
                details=[result.stderr.strip()]
            )

    except Exception as e:
        return FixResult(
            check_name="venv",
            success=False,
            message="虚拟环境创建失败",
            details=[str(e)]
        )


def fix_dependencies(project_root: Path) -> FixResult:
    """Install/sync dependencies"""
    console.print("[yellow]正在安装依赖...[/yellow]")

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("同步依赖（包含 dev 和 vector）...", total=None)

            result = subprocess.run(
                ["uv", "sync", "--all-extras"],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes
            )

            progress.update(task, completed=True)

        if result.returncode == 0:
            return FixResult(
                check_name="dependencies",
                success=True,
                message="依赖安装成功",
                details=["已安装所有依赖（包括 pytest）"]
            )
        else:
            return FixResult(
                check_name="dependencies",
                success=False,
                message="依赖安装失败",
                details=[result.stderr.strip()]
            )

    except Exception as e:
        return FixResult(
            check_name="dependencies",
            success=False,
            message="依赖安装失败",
            details=[str(e)]
        )


def fix_pytest(project_root: Path) -> FixResult:
    """Install pytest (via sync)"""
    # pytest is in dev dependencies, so just sync
    return fix_dependencies(project_root)
