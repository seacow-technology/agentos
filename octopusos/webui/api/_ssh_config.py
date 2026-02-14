"""SSH/SFTP execution config (probe vs real).

Hard rule:
- Default behavior must be probe-only (CI-safe).
- Only when OCTO_SSH_REAL=1 do we permit real network SSH/SFTP operations.
"""

from __future__ import annotations

import os


def _is_truthy(value: str | None) -> bool:
    v = (value or "").strip().lower()
    return v in {"1", "true", "yes", "on"}


def ssh_real_enabled() -> bool:
    # Explicit opt-in only.
    return _is_truthy(os.getenv("OCTO_SSH_REAL"))


def ssh_probe_only() -> bool:
    # Default to probe-only. Real gate overrides probe.
    if ssh_real_enabled():
        return False
    env = os.getenv("OCTO_SSH_PROBE_ONLY")
    if env is None or env.strip() == "":
        return True
    return _is_truthy(env)


def ssh_default_timeout_ms() -> int:
    raw = (os.getenv("OCTO_SSH_DEFAULT_TIMEOUT_MS") or "").strip()
    try:
        v = int(raw)
        if 100 <= v <= 600_000:
            return v
    except Exception:
        pass
    return 15_000


def ssh_max_concurrency() -> int:
    raw = (os.getenv("OCTO_SSH_MAX_CONCURRENCY") or "").strip()
    try:
        v = int(raw)
        if 1 <= v <= 64:
            return v
    except Exception:
        pass
    return 4


def ssh_real_allow_operators() -> bool:
    # In real mode we default to restricting common shell operators to reduce footguns.
    return _is_truthy(os.getenv("OCTO_SSH_REAL_ALLOW_OPERATORS"))


def ssh_real_command_allowlist() -> set[str]:
    """Optional allowlist for real exec.

    If empty, no allowlist is enforced.
    """
    raw = (os.getenv("OCTO_SSH_REAL_COMMAND_ALLOWLIST") or "").strip()
    if not raw:
        return set()
    out: set[str] = set()
    for part in raw.split(","):
        s = part.strip()
        if s:
            out.add(s)
    return out
