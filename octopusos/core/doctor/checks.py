"""
Environment health checks

Each check returns:
- status: PASS/WARN/FAIL
- summary: One-line description
- details: Optional details (list of strings)
- fix_cmd: Command(s) to fix (for dry-run display)
"""

import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Optional


class CheckStatus(Enum):
    """Check result status"""
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


@dataclass
class CheckResult:
    """Single check result"""
    name: str
    status: CheckStatus
    summary: str
    details: Optional[List[str]] = None
    fix_cmd: Optional[List[str]] = None  # Commands for dry-run display
    needs_admin: bool = False  # Whether fix requires admin privileges


def run_all_checks(project_root: Path) -> List[CheckResult]:
    """Run all environment checks in order"""
    checks = [
        check_uv(),
        check_python_313(),
        check_venv(project_root),
        check_dependencies(project_root),
        check_pytest(),
        check_git(),
        check_basic_imports(),
        check_networkos_db(),
    ]
    return checks


# ============================================
# P0 Checks (Critical)
# ============================================

def check_uv() -> CheckResult:
    """Check if uv is installed"""
    uv_path = shutil.which("uv")

    if uv_path:
        try:
            result = subprocess.run(
                ["uv", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            version = result.stdout.strip()
            return CheckResult(
                name="uv",
                status=CheckStatus.PASS,
                summary=f"uv 已安装: {version}",
                details=[f"路径: {uv_path}"]
            )
        except Exception as e:
            return CheckResult(
                name="uv",
                status=CheckStatus.WARN,
                summary="uv 存在但无法执行",
                details=[str(e)]
            )

    # Not found - provide fix command
    system = platform.system()
    if system == "Windows":
        fix_cmd = ["powershell", "-c", "irm https://astral.sh/uv/install.ps1 | iex"]
    else:
        fix_cmd = ["curl", "-LsSf", "https://astral.sh/uv/install.sh", "|", "sh"]

    return CheckResult(
        name="uv",
        status=CheckStatus.FAIL,
        summary="uv 未安装",
        details=[
            "uv 是快速的 Python 包管理器，用于管理依赖和 Python 版本",
            f"系统: {system}"
        ],
        fix_cmd=fix_cmd,
        needs_admin=False  # uv installs to user directory by default
    )


def check_python_313() -> CheckResult:
    """Check if Python 3.13 is available (via uv or system)"""
    # First check if uv can find Python 3.13
    try:
        result = subprocess.run(
            ["uv", "python", "find", "3.13"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            python_path = result.stdout.strip()
            # Verify version
            version_result = subprocess.run(
                [python_path, "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            version = version_result.stdout.strip()
            return CheckResult(
                name="python-3.13",
                status=CheckStatus.PASS,
                summary=f"Python 3.13 Available: {version}",
                details=[f"路径: {python_path}"]
            )
    except FileNotFoundError:
        # uv not installed - will be caught by check_uv
        pass
    except Exception:
        pass

    # Check system Python
    try:
        result = subprocess.run(
            [sys.executable, "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        version = result.stdout.strip()
        if "3.13" in version or "3.14" in version:  # 3.14 is also OK
            return CheckResult(
                name="python-3.13",
                status=CheckStatus.PASS,
                summary=f"Python 3.13+ Available: {version}",
                details=[f"路径: {sys.executable}"]
            )
    except Exception:
        pass

    return CheckResult(
        name="python-3.13",
        status=CheckStatus.FAIL,
        summary="Python 3.13 未安装",
        details=[
            "AgentOS 要求 Python 3.13+",
            "将使用 uv 自动安装"
        ],
        fix_cmd=["uv", "python", "install", "3.13"],
        needs_admin=False
    )


def check_venv(project_root: Path) -> CheckResult:
    """Check if .venv exists and is valid"""
    venv_path = project_root / ".venv"

    if not venv_path.exists():
        return CheckResult(
            name="venv",
            status=CheckStatus.FAIL,
            summary=".venv 不存在",
            details=[f"期望路径: {venv_path}"],
            fix_cmd=["uv", "venv", "--python", "3.13"],
            needs_admin=False
        )

    # Check if Python executable exists
    if platform.system() == "Windows":
        python_exe = venv_path / "Scripts" / "python.exe"
    else:
        python_exe = venv_path / "bin" / "python"

    if not python_exe.exists():
        return CheckResult(
            name="venv",
            status=CheckStatus.FAIL,
            summary=".venv 存在但不完整",
            details=[f"缺少: {python_exe}"],
            fix_cmd=["uv", "venv", "--python", "3.13"],
            needs_admin=False
        )

    # Try to get Python version
    try:
        result = subprocess.run(
            [str(python_exe), "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        version = result.stdout.strip()
        return CheckResult(
            name="venv",
            status=CheckStatus.PASS,
            summary=f".venv 存在且Available: {version}",
            details=[f"路径: {venv_path}"]
        )
    except Exception as e:
        return CheckResult(
            name="venv",
            status=CheckStatus.WARN,
            summary=".venv 存在但 Python 不可执行",
            details=[str(e)],
            fix_cmd=["uv", "venv", "--python", "3.13"],
            needs_admin=False
        )


def check_dependencies(project_root: Path) -> CheckResult:
    """Check if dependencies are installed"""
    pyproject = project_root / "pyproject.toml"

    if not pyproject.exists():
        return CheckResult(
            name="dependencies",
            status=CheckStatus.WARN,
            summary="pyproject.toml 不存在",
            details=["无法验证依赖"]
        )

    # Check if we can import key dependencies
    venv_path = project_root / ".venv"
    if not venv_path.exists():
        return CheckResult(
            name="dependencies",
            status=CheckStatus.FAIL,
            summary="依赖未安装（.venv 不存在）",
            fix_cmd=["uv", "sync", "--all-extras"],
            needs_admin=False
        )

    # Try to check if sync is needed
    try:
        result = subprocess.run(
            ["uv", "sync", "--dry-run"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=30
        )
        # If dry-run shows changes needed, deps are not in sync
        if "Would install" in result.stdout or "would install" in result.stdout.lower():
            return CheckResult(
                name="dependencies",
                status=CheckStatus.FAIL,
                summary="依赖未同步或缺失",
                details=["运行 uv sync 查看详情"],
                fix_cmd=["uv", "sync", "--all-extras"],
                needs_admin=False
            )
    except Exception:
        # Can't determine - assume needs sync
        return CheckResult(
            name="dependencies",
            status=CheckStatus.WARN,
            summary="依赖状态未知",
            details=["建议运行 uv sync"],
            fix_cmd=["uv", "sync", "--all-extras"],
            needs_admin=False
        )

    return CheckResult(
        name="dependencies",
        status=CheckStatus.PASS,
        summary="依赖已安装且同步",
    )


# ============================================
# P1 Checks (Important)
# ============================================

def check_pytest() -> CheckResult:
    """Check if pytest is available"""
    try:
        result = subprocess.run(
            ["uv", "run", "pytest", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            version = result.stdout.strip().split("\n")[0]
            return CheckResult(
                name="pytest",
                status=CheckStatus.PASS,
                summary=f"pytest Available: {version}"
            )
    except Exception:
        pass

    return CheckResult(
        name="pytest",
        status=CheckStatus.FAIL,
        summary="pytest 不Available",
        details=[
            "pytest 在 dev 依赖中",
            "运行 uv sync --all-extras 安装"
        ],
        fix_cmd=["uv", "sync", "--all-extras"],
        needs_admin=False
    )


def check_git() -> CheckResult:
    """Check if git is available"""
    git_path = shutil.which("git")

    if git_path:
        try:
            result = subprocess.run(
                ["git", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            version = result.stdout.strip()
            return CheckResult(
                name="git",
                status=CheckStatus.PASS,
                summary=f"git 已安装: {version}"
            )
        except Exception:
            pass

    return CheckResult(
        name="git",
        status=CheckStatus.WARN,
        summary="git 未安装",
        details=[
            "git 是可选的，但推荐安装",
            "用于版本控制和部分功能"
        ],
        needs_admin=True  # System-level install
    )


def check_basic_imports() -> CheckResult:
    """Smoke test: try importing core modules"""
    try:
        # Use uv run to test in venv context
        result = subprocess.run(
            ["uv", "run", "python", "-c", "import agentos; import fastapi; import rich"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return CheckResult(
                name="imports",
                status=CheckStatus.PASS,
                summary="核心模块可导入"
            )
        else:
            return CheckResult(
                name="imports",
                status=CheckStatus.FAIL,
                summary="核心模块导入失败",
                details=[result.stderr.strip()],
                fix_cmd=["uv", "sync", "--all-extras"],
                needs_admin=False
            )
    except Exception as e:
        return CheckResult(
            name="imports",
            status=CheckStatus.FAIL,
            summary="无法测试模块导入",
            details=[str(e)],
            fix_cmd=["uv", "sync", "--all-extras"],
            needs_admin=False
        )


# ============================================
# Database Health Checks
# ============================================

def check_networkos_db() -> CheckResult:
    """Check NetworkOS database health"""
    try:
        from agentos.networkos.health import NetworkOSHealthCheck

        checker = NetworkOSHealthCheck()
        all_passed, results = checker.run_all_checks()

        if all_passed:
            return CheckResult(
                name="networkos",
                status=CheckStatus.PASS,
                summary="NetworkOS 数据库健康",
                details=[
                    f"通过检查: {results['summary']['passed_count']}/{results['summary']['passed_count']}"
                ]
            )

        # Get details of failed checks
        failed_details = []
        for check_name in results['summary']['checks_failed']:
            if check_name in results:
                failed_details.append(f"{check_name}: {results[check_name]['message']}")

        # Determine if it's a warning or failure
        # If DB doesn't exist yet, it's a warning (will be created on first use)
        if 'check_db_exists' in results['summary']['checks_failed']:
            return CheckResult(
                name="networkos",
                status=CheckStatus.WARN,
                summary="NetworkOS 数据库未初始化",
                details=[
                    "数据库将在首次使用时自动创建",
                    "或运行: agentos migrate"
                ]
            )

        # Other failures are more serious
        return CheckResult(
            name="networkos",
            status=CheckStatus.FAIL,
            summary=f"NetworkOS 数据库健康检查失败 ({results['summary']['failed_count']} 项)",
            details=failed_details,
            fix_cmd=["agentos", "migrate"],
            needs_admin=False
        )

    except ImportError as e:
        return CheckResult(
            name="networkos",
            status=CheckStatus.WARN,
            summary="无法导入 NetworkOS 健康检查模块",
            details=[str(e)],
            fix_cmd=["uv", "sync", "--all-extras"],
            needs_admin=False
        )
    except Exception as e:
        return CheckResult(
            name="networkos",
            status=CheckStatus.FAIL,
            summary="NetworkOS 健康检查异常",
            details=[str(e)]
        )
