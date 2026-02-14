"""Local encrypted secret store for BridgeOS keychain.

This is intentionally minimal:
- Secrets are encrypted at rest using Fernet (AES-128-CBC + HMAC).
- A random master key is stored in the BridgeOS store directory with 0600 perms.

Notes:
- This is not a substitute for OS keychain integration. It provides a baseline
  that keeps plaintext out of SQLite and logs, and is fully local.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet

from octopusos.webui.api._db_bridgeos import bridgeos_db_path


def _key_path() -> Path:
    # Store alongside the bridgeos db, but as a separate protected file.
    return bridgeos_db_path().parent / "bridgeos_secrets.key"


def _read_key_bytes(path: Path) -> Optional[bytes]:
    try:
        raw = path.read_bytes()
        raw = raw.strip()
        return raw or None
    except Exception:
        return None


def _write_key_bytes(path: Path, key: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Best-effort 0600 for the key file.
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, key + b"\n")
    finally:
        os.close(fd)


def get_or_create_master_key() -> bytes:
    path = _key_path()
    key = _read_key_bytes(path)
    if key:
        return key
    key = Fernet.generate_key()
    _write_key_bytes(path, key)
    return key


def encrypt_secret(secret: str) -> str:
    f = Fernet(get_or_create_master_key())
    token = f.encrypt(secret.encode("utf-8"))
    return token.decode("ascii")


def decrypt_secret(token: str) -> str:
    f = Fernet(get_or_create_master_key())
    raw = f.decrypt(token.encode("ascii"))
    return raw.decode("utf-8", errors="replace")

