#!/usr/bin/env python3
"""
Generate a human-readable report summarizing task pool progress and failures.

This intentionally stays lightweight: it reads the lock JSON and logs produced by long_run_driver.py.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text("utf-8"))


def _load_tasks(lock_data: Any) -> List[Dict[str, Any]]:
    items = lock_data.get("tasks") if isinstance(lock_data, dict) else lock_data
    return items if isinstance(items, list) else []


def _tail(path: Path, n: int = 80) -> str:
    if not path.exists():
        return ""
    lines = path.read_text("utf-8", errors="ignore").splitlines()
    return "\n".join(lines[-n:])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lock", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--logs-dir", default="frontend/reports/long_run_logs")
    ap.add_argument("--include-log-tail", type=int, default=80)
    args = ap.parse_args()

    lock_path = Path(args.lock).resolve()
    out_path = Path(args.out).resolve()
    logs_dir = Path(args.logs_dir).resolve()

    data = _read_json(lock_path)
    tasks = _load_tasks(data)
    c = Counter(str(t.get("status") or "") for t in tasks)

    lines: List[str] = []
    lines.append("# Reality Review Report")
    lines.append("")
    lines.append(f"- generated_at: `{_now_iso()}`")
    lines.append(f"- lock: `{lock_path}`")
    lines.append(f"- status_counts: `{dict(c)}`")
    lines.append("")

    def _task_line(t: Dict[str, Any]) -> str:
        tid = t.get("task_id")
        portal = t.get("portal")
        bucket = t.get("module_bucket") or t.get("module")
        st = t.get("status")
        return f"- `{tid}` `{portal}/{bucket}` `{st}`"

    blocked = [t for t in tasks if str(t.get("status")) == "blocked"]
    inprog = [t for t in tasks if str(t.get("status")) == "in_progress"]

    lines.append("## In Progress")
    lines.append("")
    if not inprog:
        lines.append("- (none)")
    else:
        for t in inprog:
            lines.append(_task_line(t))
            notes = str(t.get("notes") or "").strip().replace("\n", " ")
            if notes:
                lines.append(f"  - notes: `{notes[:240]}`")
    lines.append("")

    lines.append("## Blocked")
    lines.append("")
    if not blocked:
        lines.append("- (none)")
    else:
        for t in blocked:
            lines.append(_task_line(t))
            notes = str(t.get("notes") or "").strip().replace("\n", " ")
            if notes:
                lines.append(f"  - notes: `{notes[:240]}`")
            tid = str(t.get("task_id") or "")
            tail = _tail(logs_dir / f"{tid}.log", n=args.include_log_tail)
            if tail:
                lines.append("  - log_tail:")
                lines.append("")
                lines.append("```")
                lines.append(tail)
                lines.append("```")
    lines.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", "utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

