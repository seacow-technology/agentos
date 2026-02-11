"""Executable MCP preflight checks."""

from __future__ import annotations

import platform
import shutil
import subprocess
from typing import Dict, List, Optional, Tuple

from octopusos.core.mcp.config import MCPServerConfig
from octopusos.core.mcp.preflight import PreflightAction, PreflightCheck, PreflightReport


def _run(cmd: List[str], env: Optional[Dict[str, str]] = None, timeout_s: int = 15) -> Tuple[int, str, str]:
    process = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout_s,
    )
    return process.returncode, (process.stdout or "").strip(), (process.stderr or "").strip()


def run_preflight_for_server(server_cfg: MCPServerConfig) -> PreflightReport:
    env = dict(server_cfg.env or {})
    package_id = env.get("OCTOPUSOS_MCP_PACKAGE_ID", "")

    checks: List[PreflightCheck] = []
    actions: List[PreflightAction] = []
    warnings: List[str] = []

    if package_id != "aws.mcp":
        cmd0 = server_cfg.command[0] if server_cfg.command else ""
        cmd_path = shutil.which(cmd0) if cmd0 and not cmd0.startswith("/") else (cmd0 if cmd0 else None)
        has_cmd = bool(cmd0 and cmd_path)
        checks.append(
            PreflightCheck(
                name="command_present",
                ok=has_cmd,
                details=f"command={server_cfg.command}, path={cmd_path}",
            )
        )
        npm_ok = True
        npm_detail = "not_npm_command"
        if server_cfg.command and server_cfg.command[0] in {"npx", "npm"}:
            package_name = ""
            for item in server_cfg.command[1:]:
                token = str(item)
                if token.startswith("@") or "/" in token:
                    package_name = token
                    break
            if package_name:
                code, out, err = _run(["npm", "view", package_name, "version"], timeout_s=15)
                npm_ok = code == 0 and bool((out or "").strip())
                npm_detail = out or err or f"exit={code}"
            else:
                npm_detail = "package_arg_not_found"
        checks.append(
            PreflightCheck(
                name="npm_package_exists",
                ok=npm_ok,
                details=npm_detail,
            )
        )
        return PreflightReport(ok=has_cmd and npm_ok, checks=checks, planned_actions=actions, warnings=warnings)

    cmd0 = server_cfg.command[0] if server_cfg.command else ""
    cmd_path = shutil.which(cmd0) if cmd0 and not cmd0.startswith("/") else (cmd0 if cmd0 else None)
    has_cmd = bool(cmd0 and cmd_path)
    checks.append(
        PreflightCheck(
            name="mcp_command_resolvable",
            ok=has_cmd,
            details=(f"command={cmd0}, path={cmd_path}" if has_cmd else f"command not found: {cmd0 or '<empty>'}"),
        )
    )
    if not has_cmd:
        if cmd0 == "aws-mcp":
            if shutil.which("uvx"):
                actions.append(
                    PreflightAction(
                        type="reconfigure",
                        tool="aws-mcp-launcher",
                        method="uvx",
                        commands=["switch command to: uvx awslabs.aws-api-mcp-server@latest"],
                        details="Legacy aws-mcp launcher not found; uvx is available for AWS MCP server.",
                    )
                )
            elif platform.system().lower() == "darwin":
                actions.append(
                    PreflightAction(
                        type="install",
                        tool="uv",
                        method="brew",
                        commands=["brew install uv"],
                        details="Install uv to provide uvx launcher for AWS MCP server.",
                    )
                )
            else:
                actions.append(
                    PreflightAction(
                        type="manual_install_required",
                        tool="aws-mcp-launcher",
                        method="manual",
                        commands=[],
                        details="Install uv (or another supported AWS MCP launcher) and reconfigure command.",
                    )
                )
        else:
            actions.append(
                PreflightAction(
                    type="manual_install_required",
                    tool="mcp-launcher",
                    method="manual",
                    commands=[],
                    details=f"Command '{cmd0 or '<empty>'}' is not executable in PATH.",
                )
            )
        return PreflightReport(ok=False, checks=checks, planned_actions=actions, warnings=warnings)

    aws_path = shutil.which("aws")
    has_aws = aws_path is not None
    checks.append(
        PreflightCheck(
            name="aws_cli_present",
            ok=has_aws,
            details=(f"aws at {aws_path}" if has_aws else "aws not found in PATH"),
        )
    )

    if not has_aws:
        if platform.system().lower() == "darwin":
            actions.append(
                PreflightAction(
                    type="install",
                    tool="aws-cli",
                    method="brew",
                    commands=["brew install awscli"],
                    details="aws not found; install via Homebrew",
                )
            )
        else:
            actions.append(
                PreflightAction(
                    type="manual_install_required",
                    tool="aws-cli",
                    method="manual",
                    commands=[],
                    details="auto-install is only implemented for macOS Homebrew",
                )
            )
        return PreflightReport(ok=False, checks=checks, planned_actions=actions, warnings=warnings)

    code, out, err = _run(["aws", "--version"], timeout_s=15)
    ok_ver = code == 0
    checks.append(
        PreflightCheck(
            name="aws_cli_version",
            ok=ok_ver,
            details=(out or err or f"exit={code}"),
        )
    )
    if not ok_ver:
        return PreflightReport(ok=False, checks=checks, planned_actions=actions, warnings=warnings)

    code, out, err = _run(["aws", "configure", "list-profiles"], timeout_s=15)
    list_ok = code == 0
    checks.append(
        PreflightCheck(
            name="aws_list_profiles",
            ok=list_ok,
            details=(out or err or f"exit={code}"),
        )
    )
    if not list_ok:
        return PreflightReport(ok=False, checks=checks, planned_actions=actions, warnings=warnings)

    profile = env.get("AWS_PROFILE") or "default"
    profiles = [line.strip() for line in out.splitlines() if line.strip()]
    has_profile = profile in profiles
    checks.append(
        PreflightCheck(
            name="aws_profile_exists",
            ok=has_profile,
            details=f"profile={profile}, available_count={len(profiles)}",
        )
    )
    if not has_profile:
        return PreflightReport(ok=False, checks=checks, planned_actions=actions, warnings=warnings)

    region = env.get("AWS_REGION")
    checks.append(
        PreflightCheck(
            name="aws_region_set",
            ok=bool(region),
            details=(f"region={region}" if region else "AWS_REGION is empty"),
        )
    )
    if not region:
        warnings.append("AWS_REGION is not set; AWS CLI default region resolution will be used.")

    return PreflightReport(ok=True, checks=checks, planned_actions=actions, warnings=warnings)
