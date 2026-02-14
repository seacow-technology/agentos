"""SSH trust gate helpers.

We maintain our own trusted host fingerprint registry in BridgeOS (known_hosts table),
without touching the system's ~/.ssh/known_hosts file.

Probe mode:
- Deterministic fake fingerprint based on hostname:port (stable across runs).

Real mode:
- Fetch host public key via ssh-keyscan and compute SHA256 fingerprint using ssh-keygen.
- This is guarded by OCTO_SSH_REAL=1 via callers.
"""

from __future__ import annotations

import base64
import hashlib
import os
import sqlite3
import subprocess
from dataclasses import dataclass
from typing import Optional, Tuple

from octopusos.webui.api._ssh_config import ssh_default_timeout_ms, ssh_probe_only


@dataclass(frozen=True)
class HostFingerprint:
    fingerprint: str
    algo: str | None = None
    method: str | None = None  # "probe" or "ssh-keyscan"


def probe_fingerprint(hostname: str, port: int) -> HostFingerprint:
    # Openssh-like SHA256 fingerprint shape: "SHA256:<base64>"
    h = hashlib.sha256(f"{hostname}:{int(port)}".encode("utf-8")).digest()
    b64 = base64.b64encode(h).decode("ascii").rstrip("=")
    return HostFingerprint(fingerprint=f"SHA256:{b64}", algo="probe", method="probe")


def _run(cmd: list[str], *, timeout_ms: int) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        check=False,
        capture_output=True,
        text=True,
        timeout=max(0.1, timeout_ms / 1000.0),
    )


def real_fingerprint(hostname: str, port: int, *, timeout_ms: Optional[int] = None) -> HostFingerprint:
    """Fetch host key and compute its SHA256 fingerprint.

    This uses system OpenSSH tooling for minimal deps.
    """
    t = int(timeout_ms or ssh_default_timeout_ms())

    # ssh-keyscan prints one or more authorized_keys formatted lines:
    #   host ssh-ed25519 AAAAC3NzaC1...
    scan = _run(["ssh-keyscan", "-p", str(int(port)), "-T", str(max(1, int(t / 1000))), hostname], timeout_ms=t)
    if scan.returncode != 0 and not (scan.stdout or "").strip():
        raise RuntimeError(f"ssh-keyscan failed: rc={scan.returncode} stderr={scan.stderr.strip()[:200]}")

    key_line = None
    for line in (scan.stdout or "").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        # best-effort: first usable key line
        key_line = s
        break
    if not key_line:
        raise RuntimeError("ssh-keyscan returned no host keys")

    # Compute SHA256 fingerprint for that key line via ssh-keygen.
    # Output looks like:
    #   256 SHA256:xxxx host (ED25519)
    p = subprocess.Popen(
        ["ssh-keygen", "-lf", "-", "-E", "sha256"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        out, err = p.communicate(key_line + "\n", timeout=max(0.1, t / 1000.0))
    finally:
        try:
            p.kill()
        except Exception:
            pass
    if p.returncode != 0:
        raise RuntimeError(f"ssh-keygen fingerprint failed: rc={p.returncode} stderr={(err or '').strip()[:200]}")

    fp = None
    algo = None
    for token in (out or "").split():
        if token.startswith("SHA256:"):
            fp = token
            break
    # algo is in parens at end: "(ED25519)" etc.
    if "(" in (out or "") and ")" in (out or ""):
        try:
            algo = (out.split("(")[-1].split(")")[0] or "").strip().lower() or None
        except Exception:
            algo = None
    if not fp:
        raise RuntimeError(f"unexpected ssh-keygen output: {(out or '').strip()[:200]}")
    return HostFingerprint(fingerprint=fp, algo=algo, method="ssh-keyscan")


def get_fingerprint(hostname: str, port: int) -> HostFingerprint:
    # Centralized switch for callers.
    if ssh_probe_only():
        return probe_fingerprint(hostname, port)
    return real_fingerprint(hostname, port)


def is_trusted(
    conn: sqlite3.Connection, *, hostname: str, port: int, fingerprint: str
) -> Tuple[bool, Optional[str]]:
    """Return (trusted, mismatch_reason)."""
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT fingerprint FROM known_hosts WHERE host = ? AND port = ? ORDER BY created_at DESC LIMIT 1",
        (hostname, int(port)),
    ).fetchone()
    if not row:
        return False, None
    stored = str(row["fingerprint"])
    if stored.strip() == str(fingerprint).strip():
        return True, None
    # Stable error_code for UI and policy decisions.
    return False, "FINGERPRINT_MISMATCH"
