from __future__ import annotations

import json
import logging
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from octopusos.core.capability.registry import get_capability_registry
from octopusos.core.time import utc_now_ms


logger = logging.getLogger(__name__)

_ALLOWED_PROVIDERS = {"probe", "system", "mcp"}


@dataclass(frozen=True)
class SshProviderResolved:
    provider: str
    source: str
    allow_real: bool
    mcp_profile: Optional[str]
    effective_at_ms: int
    requires_restart: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "source": self.source,
            "allow_real": bool(self.allow_real),
            "mcp_profile": self.mcp_profile,
            "effective_at": int(self.effective_at_ms),
            "requires_restart": bool(self.requires_restart),
        }


_last_good_resolved: Optional[SshProviderResolved] = None
_last_good_sources: Optional[Dict[str, Any]] = None


def _default_file_path() -> Path:
    return Path(__file__).resolve().with_name("ssh_provider.default.json")


def _builtin_source() -> Dict[str, Any]:
    return {
        "version": 1,
        "ssh_provider": {"provider": "probe", "allow_real": False, "mcp_profile": None},
    }


def _load_json_file(path: Path) -> Dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return raw if isinstance(raw, dict) else {}


def _read_file_source() -> Dict[str, Any]:
    p = (os.getenv("OCTO_SSH_PROVIDER_PATH") or "").strip()
    path = Path(p) if p else _default_file_path()
    try:
        if not path.exists():
            return {}
        return _load_json_file(path)
    except Exception as e:
        logger.warning(f"Failed to read ssh provider config file: {e}")
        return {}


def _connect_registry_db() -> sqlite3.Connection:
    reg = get_capability_registry()
    conn = sqlite3.connect(str(reg.db_path), timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _read_db_source() -> Dict[str, Any]:
    conn: Optional[sqlite3.Connection] = None
    try:
        conn = _connect_registry_db()
        if not _table_exists(conn, "ssh_provider_config"):
            return {}
        row = conn.execute(
            "SELECT provider, allow_real, mcp_profile, updated_at, updated_by FROM ssh_provider_config WHERE id = 1"
        ).fetchone()
        if not row:
            return {}
        return {
            "version": 1,
            "ssh_provider": {
                "provider": str(row["provider"] or "").strip(),
                "allow_real": bool(int(row["allow_real"] or 0)),
                "mcp_profile": str(row["mcp_profile"]) if row["mcp_profile"] is not None else None,
            },
            "updated_at": int(row["updated_at"] or 0),
            "updated_by": str(row["updated_by"] or ""),
        }
    except Exception as e:
        logger.warning(f"Failed to read ssh provider config from db: {e}")
        return {}
    finally:
        if conn is not None:
            conn.close()


def _read_env_override() -> Dict[str, Any]:
    provider = (os.getenv("OCTO_SSH_PROVIDER") or "").strip().lower()
    if not provider or provider not in _ALLOWED_PROVIDERS:
        return {}
    # Env override only pins provider selection; allow_real remains managed by file/db.
    return {"provider": provider}


def _normalize_provider(value: Any) -> str:
    v = str(value or "").strip().lower()
    return v if v in _ALLOWED_PROVIDERS else "probe"


def _merge_sources() -> Tuple[SshProviderResolved, Dict[str, Any]]:
    builtin = _builtin_source()
    file_src = _read_file_source()
    db_src = _read_db_source()
    env_override = _read_env_override()

    # Extract candidate values with priority: builtin < file < db < env(provider-only)
    def _extract(src: Dict[str, Any]) -> Dict[str, Any]:
        sp = src.get("ssh_provider")
        if not isinstance(sp, dict):
            return {}
        return sp

    b = _extract(builtin)
    f = _extract(file_src)
    d = _extract(db_src)

    provider = _normalize_provider(b.get("provider"))
    source = "builtin"
    allow_real = bool(b.get("allow_real", False))
    mcp_profile = b.get("mcp_profile")

    if f:
        provider = _normalize_provider(f.get("provider", provider))
        allow_real = bool(f.get("allow_real", allow_real))
        mcp_profile = f.get("mcp_profile", mcp_profile)
        source = "file"

    if d:
        provider = _normalize_provider(d.get("provider", provider))
        allow_real = bool(d.get("allow_real", allow_real))
        mcp_profile = d.get("mcp_profile", mcp_profile)
        source = "db"

    if env_override:
        provider = _normalize_provider(env_override.get("provider", provider))
        source = "env"

    if provider == "probe":
        allow_real = False
        mcp_profile = None

    if provider != "mcp":
        mcp_profile = None

    eff = SshProviderResolved(
        provider=provider,
        source=source,
        allow_real=bool(allow_real),
        mcp_profile=str(mcp_profile) if mcp_profile is not None and str(mcp_profile).strip() else None,
        effective_at_ms=int(utc_now_ms()),
        requires_restart=False,
    )
    sources = {"builtin": builtin, "file": file_src, "db": db_src, "env": env_override}
    return eff, sources


def reload_ssh_provider_config() -> SshProviderResolved:
    """Reload ssh provider selection config and update last-known-good."""
    global _last_good_resolved, _last_good_sources
    eff, sources = _merge_sources()
    _last_good_resolved = eff
    _last_good_sources = sources
    return eff


def resolve_ssh_provider() -> SshProviderResolved:
    """Resolve current effective ssh provider selection."""
    global _last_good_resolved, _last_good_sources
    if _last_good_resolved is None or _last_good_sources is None:
        try:
            return reload_ssh_provider_config()
        except Exception as e:
            logger.warning(f"Failed to resolve ssh provider config: {e}")
            # Hard fail-safe: probe.
            _last_good_resolved = SshProviderResolved(
                provider="probe",
                source="builtin",
                allow_real=False,
                mcp_profile=None,
                effective_at_ms=int(utc_now_ms()),
                requires_restart=False,
            )
            _last_good_sources = {"builtin": _builtin_source(), "file": {}, "db": {}, "env": {}}
            return _last_good_resolved
    return _last_good_resolved


def get_ssh_provider_sources() -> Dict[str, Any]:
    """Return raw per-source inputs for UI diff/debug (best-effort)."""
    global _last_good_sources
    if _last_good_sources is None:
        reload_ssh_provider_config()
    return _last_good_sources or {}

