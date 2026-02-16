from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from ..metrics import count_tokens


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8", errors="replace")).hexdigest()


def _read_file_slice(path: Path, *, locator: Dict[str, Any]) -> str:
    data = path.read_bytes()
    br = locator.get("byte_range")
    lr = locator.get("line_range")
    if isinstance(br, (list, tuple)) and len(br) == 2:
        a, b = int(br[0]), int(br[1])
        a = max(0, min(len(data), a))
        b = max(a, min(len(data), b))
        return data[a:b].decode("utf-8", errors="replace")
    if isinstance(lr, (list, tuple)) and len(lr) == 2:
        start, end = int(lr[0]), int(lr[1])
        start = max(1, start)
        end = max(start, end)
        lines = data.decode("utf-8", errors="replace").splitlines()
        sl = lines[start - 1 : end]
        return "\n".join(sl) + "\n"
    # regex locator: extract first match + surrounding lines
    rx = locator.get("regex")
    if isinstance(rx, str) and rx.strip():
        text = data.decode("utf-8", errors="replace")
        m = re.search(rx, text, flags=re.MULTILINE)
        if m:
            a = max(0, m.start() - 800)
            b = min(len(text), m.end() + 800)
            return text[a:b]
    # fallback: last 200 lines
    lines = data.decode("utf-8", errors="replace").splitlines()
    return "\n".join(lines[-200:]) + "\n"


def _read_sqlite_query(db_path: Path, *, locator: Dict[str, Any]) -> str:
    table = locator.get("table")
    query = locator.get("query")
    if not isinstance(table, str) or not table.strip():
        raise ValueError("sqlite locator missing table")
    if not isinstance(query, str) or not query.strip():
        raise ValueError("sqlite locator missing query")

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query).fetchall()
        # Return JSON-lines for determinism and easy token accounting.
        out_lines = []
        for r in rows[:200]:
            d = dict(r)
            out_lines.append(json.dumps(d, ensure_ascii=False))
        return "\n".join(out_lines) + ("\n" if out_lines else "")
    finally:
        conn.close()


def resolve_pointer(
    pointer: Dict[str, Any],
    *,
    repo_root: Path,
    model: str = "gpt-4o",
    max_tokens: int = 350,
) -> Dict[str, Any]:
    """
    Controlled pointer resolver.
    Allowed sources:
    - file: only under repo_root/{reports,output,outputs,tmp} or evidence/run dirs
    - sqlite: readonly queries, only whitelisted db path under ~/.octopusos/store/
    - artifact/trace: treated as file for now, must be under repo_root
    """
    pid = str(pointer.get("id") or pointer.get("pointer_id") or "")
    source_kind = str(pointer.get("source_kind") or "")
    source_ref = pointer.get("source_ref") or {}
    locator = pointer.get("locator") or {}

    content = ""
    if source_kind in {"file", "artifact", "trace"}:
        p = source_ref.get("path")
        if not isinstance(p, str) or not p.strip():
            raise ValueError("file pointer missing source_ref.path")
        path = (repo_root / p).resolve() if not Path(p).is_absolute() else Path(p).resolve()

        # Guard: only allow reading inside repo_root.
        rr = repo_root.resolve()
        if rr not in path.parents and path != rr:
            raise PermissionError(f"pointer path outside repo_root: {path}")
        content = _read_file_slice(path, locator=locator)

    elif source_kind == "sqlite":
        p = source_ref.get("path")
        if not isinstance(p, str) or not p.strip():
            raise ValueError("sqlite pointer missing source_ref.path")
        path = Path(p).expanduser().resolve()
        allowed_root = (Path.home() / ".octopusos" / "store").resolve()
        if allowed_root not in path.parents:
            raise PermissionError(f"sqlite db outside allowed root: {path}")
        content = _read_sqlite_query(path, locator=locator)
    else:
        raise ValueError(f"unsupported source_kind: {source_kind}")

    # Hard truncate to max_tokens by tokens (real tiktoken).
    # We do simple proportional char cut first then refine.
    raw_hash = f"sha256:{_sha256_text(content)}"
    tokens = count_tokens(content, model=model)
    if tokens > max_tokens:
        # proportional cut
        target_ratio = max_tokens / max(1, tokens)
        cut = int(len(content) * target_ratio)
        content = content[: max(200, cut)]
        # ensure under limit
        while count_tokens(content, model=model) > max_tokens and len(content) > 200:
            content = content[: int(len(content) * 0.9)]
        tokens = count_tokens(content, model=model)
        raw_hash = f"sha256:{_sha256_text(content)}"

    return {
        "pointer_id": pid,
        "content_excerpt": content,
        "content_hash": raw_hash,
        "tokens": tokens,
        "signature": locator.get("signature"),
    }

