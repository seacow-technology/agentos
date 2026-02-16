#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def _load(lock_path: Path) -> list[dict]:
    d = json.loads(lock_path.read_text("utf-8"))
    tasks = d.get("tasks", d)
    return tasks if isinstance(tasks, list) else []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lock", action="append", default=[])
    args = ap.parse_args()
    locks = args.lock or [
        "frontend/reports/business_validation_lock.json",
        "frontend/reports/backend_validation_lock.json",
    ]

    for lock in locks:
        lock_path = Path(lock)
        if not lock_path.exists():
            print("=" * 80)
            print("lock:", lock, "(missing)")
            continue
        tasks = _load(lock_path)
        c = Counter((t.get("status") or "") for t in tasks)
        print("=" * 80)
        print("lock:", lock)
        print("status:", dict(c))
        for t in tasks:
            if t.get("status") in ("in_progress", "blocked"):
                tid = t.get("task_id")
                portal = t.get("portal")
                bucket = t.get("module_bucket") or t.get("module")
                st = t.get("status")
                print(f"- {tid} {portal}/{bucket} {st}")
                notes = (t.get("notes") or "").strip().replace("\n", " ")
                if notes:
                    print("  notes:", notes[:220])
    print("=" * 80)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

