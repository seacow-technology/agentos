#!/usr/bin/env python3
"""
Long-run driver (LLM-in-the-loop).

This script coordinates:
- a lock file (task pool state)
- a plan file (human readable)
- task briefs (md) passed to Codex via --codex-cmd
- optional build + optional e2e commands

Design goals:
- deterministic, resumable
- evidence-first: always write logs and brief artifacts
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text("utf-8"))


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", "utf-8")


def _append_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(text)


def _run_cmd(
    cmd: str,
    *,
    cwd: Path,
    env: Optional[Dict[str, str]] = None,
    log_path: Optional[Path] = None,
    timeout_s: Optional[int] = None,
) -> Tuple[int, str]:
    merged_env = os.environ.copy()
    if env:
        merged_env.update({k: str(v) for k, v in env.items()})

    # Use shell=True to keep --codex-cmd templates easy, but log + show exact command.
    p = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        env=merged_env,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    out: List[str] = []
    started = time.time()
    while True:
        line = p.stdout.readline() if p.stdout else ""
        if line:
            out.append(line)
            if log_path:
                _append_text(log_path, line)
        if p.poll() is not None:
            break
        if timeout_s is not None and (time.time() - started) > timeout_s:
            try:
                p.terminate()
            except Exception:
                pass
            return 124, "".join(out) + "\n[TIMEOUT]\n"
        time.sleep(0.02)
    rc = int(p.returncode or 0)
    return rc, "".join(out)


@dataclass
class Task:
    raw: Dict[str, Any]

    @property
    def task_id(self) -> str:
        return str(self.raw.get("task_id") or "")

    @property
    def status(self) -> str:
        return str(self.raw.get("status") or "todo")

    @property
    def portal(self) -> str:
        return str(self.raw.get("portal") or "")

    @property
    def bucket(self) -> str:
        return str(self.raw.get("module_bucket") or self.raw.get("module") or "")


def _load_tasks(lock_data: Any) -> List[Task]:
    items = lock_data.get("tasks") if isinstance(lock_data, dict) else lock_data
    if not isinstance(items, list):
        return []
    out: List[Task] = []
    for x in items:
        if isinstance(x, dict):
            out.append(Task(raw=x))
    return out


def _pick_next(tasks: List[Task]) -> Optional[Task]:
    # Simple priority ordering: explicit numeric "priority" desc, then stable list order.
    best: Optional[Task] = None
    best_pri = -10_000
    for t in tasks:
        if t.status != "todo":
            continue
        pri_raw = t.raw.get("priority", 0)
        try:
            pri = int(pri_raw)
        except Exception:
            pri = 0
        if best is None or pri > best_pri:
            best = t
            best_pri = pri
    return best


def _claim_task(lock_path: Path, task_id: str, worker: str) -> Dict[str, Any]:
    data = _read_json(lock_path)
    tasks = _load_tasks(data)
    changed = False
    for t in tasks:
        if t.task_id == task_id:
            t.raw["status"] = "in_progress"
            t.raw["worker"] = worker
            t.raw["claimed_at"] = _now_iso()
            t.raw["updated_at"] = _now_iso()
            # Avoid stale notes leaking into a fresh run.
            if "notes" in t.raw:
                t.raw.pop("notes", None)
            changed = True
            break
    if not changed:
        raise RuntimeError(f"task not found: {task_id}")
    _write_json(lock_path, data)
    return data


def _update_task_status(
    lock_path: Path,
    task_id: str,
    status: str,
    *,
    notes: Optional[str] = None,
) -> None:
    data = _read_json(lock_path)
    tasks = _load_tasks(data)
    for t in tasks:
        if t.task_id == task_id:
            t.raw["status"] = status
            t.raw["updated_at"] = _now_iso()
            if notes is not None:
                t.raw["notes"] = notes
            break
    _write_json(lock_path, data)


def _render_task_brief(task: Task, *, plan_path: Path) -> str:
    # Keep this concise. Real tasks should include explicit acceptance commands.
    portal = task.portal or "unknown"
    bucket = task.bucket or "unknown"
    title = task.raw.get("title") or f"{portal}/{bucket}"
    scope = task.raw.get("scope") or ""
    acceptance = task.raw.get("acceptance") or ""
    hints = task.raw.get("hints") or ""
    return "\n".join(
        [
            f"# Task: {task.task_id}",
            "",
            f"- title: {title}",
            f"- portal: {portal}",
            f"- bucket: {bucket}",
            "",
            "## Context",
            f"- plan: {plan_path}",
            "",
            "## Scope",
            scope.strip() or "(not provided)",
            "",
            "## Hard Constraints",
            "- Do not invent endpoints; use only repo evidence.",
            "- If backend gap is confirmed, disable UI action with clear message and mark BLOCKED with evidence.",
            "- Do not change auth flows, CI workflows, or mass-format.",
            "- Do not manually edit anything under publish/webui-v2/.",
            "",
            "## Acceptance",
            acceptance.strip() or "(not provided)",
            "",
            "## Hints / Known Gaps",
            hints.strip() or "(none)",
            "",
        ]
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=float, default=1.0)
    ap.add_argument("--lock", required=True)
    ap.add_argument("--plan", required=True)
    ap.add_argument("--worker", default=os.environ.get("USER", "codex"))
    # Codex CLI reads prompt from stdin when PROMPT is '-' (or omitted).
    # Keep this as a shell template; {file} is the task brief markdown.
    ap.add_argument(
        "--codex-cmd",
        default="codex exec --full-auto -C . - < {file}",
    )
    ap.add_argument("--max-fix-iterations", type=int, default=3)
    ap.add_argument("--with-build", action="store_true")
    ap.add_argument("--with-playwright", action="store_true")
    ap.add_argument("--build-cmd", default="")
    ap.add_argument("--playwright-cmd", default="")
    ap.add_argument("--cwd", default=str(Path.cwd()))
    args = ap.parse_args()

    lock_path = Path(args.lock).resolve()
    plan_path = Path(args.plan).resolve()
    cwd = Path(args.cwd).resolve()

    end_ts = time.time() + args.hours * 3600.0
    logs_dir = cwd / "frontend" / "reports" / "long_run_logs"
    briefs_dir = cwd / "frontend" / "reports" / "task_briefs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    briefs_dir.mkdir(parents=True, exist_ok=True)

    if not lock_path.exists():
        raise SystemExit(f"missing lock: {lock_path}")
    if not plan_path.exists():
        raise SystemExit(f"missing plan: {plan_path}")

    while time.time() < end_ts:
        data = _read_json(lock_path)
        tasks = _load_tasks(data)
        task = _pick_next(tasks)
        if not task:
            print("no todo tasks left")
            return 0

        _claim_task(lock_path, task.task_id, args.worker)

        brief_path = briefs_dir / f"{task.task_id}.md"
        brief_text = _render_task_brief(task, plan_path=plan_path)
        brief_path.write_text(brief_text, "utf-8")

        task_log = logs_dir / f"{task.task_id}.log"
        task_log.write_text(f"[{_now_iso()}] claimed {task.task_id}\n", "utf-8")

        # 1) Run Codex to implement/fix.
        codex_cmd = args.codex_cmd.format(file=str(brief_path))
        _append_text(task_log, f"\n[{_now_iso()}] codex_cmd: {codex_cmd}\n\n")
        rc, _out = _run_cmd(codex_cmd, cwd=cwd, log_path=task_log, timeout_s=None)
        if rc != 0:
            _update_task_status(lock_path, task.task_id, "blocked", notes=f"codex failed rc={rc}")
            continue

        # 2) Optional build gate.
        if args.with_build:
            build_cmd = args.build_cmd.strip()
            if not build_cmd:
                build_cmd = (
                    "npm --prefix apps/webui run build && "
                    "bash apps/desktop-electron/scripts/sync-webui-dist.sh && "
                    "npm --prefix apps/desktop-electron run build"
                )
            _append_text(task_log, f"\n[{_now_iso()}] build_cmd: {build_cmd}\n\n")
            rc, _out = _run_cmd(build_cmd, cwd=cwd, log_path=task_log, timeout_s=30 * 60)
            if rc != 0:
                _update_task_status(lock_path, task.task_id, "in_progress", notes=f"build failed rc={rc}")
                # Fix loop
                for i in range(args.max_fix_iterations):
                    _append_text(task_log, f"\n[{_now_iso()}] fix-iteration {i+1}/{args.max_fix_iterations}\n")
                    rc2, _ = _run_cmd(codex_cmd, cwd=cwd, log_path=task_log, timeout_s=None)
                    if rc2 != 0:
                        continue
                    rc3, _ = _run_cmd(build_cmd, cwd=cwd, log_path=task_log, timeout_s=30 * 60)
                    if rc3 == 0:
                        rc = 0
                        break
                if rc != 0:
                    _update_task_status(lock_path, task.task_id, "blocked", notes="build still failing after fixes")
                    continue

        # 3) Optional playwright gate.
        if args.with_playwright:
            pw_cmd = args.playwright_cmd.strip()
            if not pw_cmd:
                # Prefer a task-specific smoke runner if present. These scripts are expected
                # to generate evidence bundles under frontend/reports/e2e_endpoint_evidence/.
                smoke = cwd / "frontend" / "scripts" / f"{task.task_id}_smoke.js"
                if smoke.exists():
                    pw_cmd = f"node {shlex.quote(str(smoke))}"
                else:
                    # Fallback to generic suite (may require env like BASE_URL / E2E_API_ORIGIN).
                    pw_cmd = "npm --prefix apps/webui run e2e"
            _append_text(task_log, f"\n[{_now_iso()}] playwright_cmd: {pw_cmd}\n\n")
            rc, _out = _run_cmd(pw_cmd, cwd=cwd, log_path=task_log, timeout_s=60 * 60)
            if rc != 0:
                _update_task_status(lock_path, task.task_id, "in_progress", notes=f"playwright failed rc={rc}")
                for i in range(args.max_fix_iterations):
                    _append_text(task_log, f"\n[{_now_iso()}] fix-iteration {i+1}/{args.max_fix_iterations}\n")
                    rc2, _ = _run_cmd(codex_cmd, cwd=cwd, log_path=task_log, timeout_s=None)
                    if rc2 != 0:
                        continue
                    rc3, _ = _run_cmd(pw_cmd, cwd=cwd, log_path=task_log, timeout_s=60 * 60)
                    if rc3 == 0:
                        rc = 0
                        break
                if rc != 0:
                    _update_task_status(lock_path, task.task_id, "blocked", notes="playwright still failing after fixes")
                    continue
            # Evidence-first: require a task-scoped evidence bundle if playwright passed.
            evidence_path = cwd / "frontend" / "reports" / "e2e_endpoint_evidence" / f"{task.task_id}.json"
            if not evidence_path.exists():
                _update_task_status(
                    lock_path,
                    task.task_id,
                    "blocked",
                    notes=f"playwright passed but evidence missing: {evidence_path}",
                )
                continue

        _update_task_status(lock_path, task.task_id, "done", notes="PASS")
        _append_text(task_log, f"\n[{_now_iso()}] PASS\n")

    print("time budget reached")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
