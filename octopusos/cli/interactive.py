"""Interactive CLI (REPL): codex/claude-style control plane for OctopusOS.

Design goals:
- Single prompt loop (no menu labyrinth)
- Slash commands (/help, /tasks, /approve, ...)
- Safe defaults: no implicit background services; explicit logs
"""

from __future__ import annotations

import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt
from rich.logging import RichHandler
from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn

from octopusos.config import load_settings, save_settings
from octopusos.core.task import TaskManager
from octopusos.core.time import utc_now_iso
from octopusos.i18n import set_language

console = Console()


def _cli_log_dir() -> Path:
    d = Path.home() / ".octopusos" / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _task_log_path(task_id: str) -> Path:
    return _cli_log_dir() / f"task-runner-{task_id}.log"


def _is_command(line: str) -> bool:
    s = (line or "").strip()
    return bool(s) and (s.startswith("/") or s.startswith(":"))


@dataclass(frozen=True)
class ParsedCommand:
    name: str
    args: list[str]


def _parse_command(line: str) -> ParsedCommand:
    s = (line or "").strip()
    if s.startswith("/"):
        s = s[1:]
    if s.startswith(":"):
        s = s[1:]
    parts = shlex.split(s)
    if not parts:
        return ParsedCommand(name="", args=[])
    return ParsedCommand(name=parts[0].lower(), args=parts[1:])


class InteractiveREPL:
    def __init__(self) -> None:
        self.task_manager = TaskManager()
        self.settings = load_settings()
        set_language(self.settings.language)
        self.current_task_id: Optional[str] = getattr(self.settings, "interactive_current_task_id", None)
        self._last_empty_hint_key: Optional[str] = None
        self._pending_cancel_task_id: Optional[str] = None
        self._pending_cancel_deadline_monotonic: float = 0.0

    def run(self) -> None:
        console.print(
            Panel(
                "[bold]OctopusOS[/bold] interactive\n"
                "Enter a request to create/run a task.\n"
                "Commands: /help",
                border_style="cyan",
            )
        )

        while True:
            try:
                suffix = self._prompt_suffix()
                line = Prompt.ask(f"[bold cyan]octopusos{suffix}[/bold cyan]").strip()
            except EOFError:
                console.print("\n[dim]bye[/dim]")
                return
            except KeyboardInterrupt:
                self._on_prompt_interrupt()
                continue

            if not line:
                self._on_empty_input()
                continue

            try:
                if _is_command(line):
                    self._handle_command(_parse_command(line))
                    continue
            except EOFError:
                console.print("\n[dim]bye[/dim]")
                return

            # Plain input = new task
            self._last_empty_hint_key = None
            self._create_and_run(line)

    def _handle_command(self, cmd: ParsedCommand) -> None:
        name = cmd.name
        args = cmd.args

        if name in ("q", "quit", "exit"):
            raise EOFError()

        if name in ("h", "help", "?"):
            self._print_help()
            return

        if name in ("current",):
            self._current()
            return

        if name in ("use", "focus"):
            if not args:
                console.print("[red]usage: /use <task_id>[/red]")
                return
            self._use(task_id=args[0])
            return

        if name in ("clear",):
            self._clear_current()
            return

        if name in ("tasks", "ls"):
            limit = 20
            if args:
                try:
                    limit = int(args[0])
                except ValueError:
                    console.print("[red]invalid limit[/red]")
                    return
            self._list_tasks(limit=limit)
            return

        if name in ("show", "open"):
            opts = self._parse_show_args(args)
            resolved = self._resolve_task_id(
                explicit=opts.get("task_id"),
                prefer_current=True,
                auto_pick_statuses=None,
            )
            if not resolved:
                console.print("[yellow]No current task.[/yellow] Use /tasks or /use <id>.")
                return
            self._set_current(resolved)

            events_n = opts.get("events")
            if isinstance(events_n, int) and events_n > 0:
                self._show_events(task_id=resolved, n=events_n)
            elif opts.get("full"):
                self._show_full(task_id=resolved)
            else:
                self._show_card(task_id=resolved)
            return

        if name in ("approve",):
            resolved = self._resolve_task_id(
                explicit=args[0] if args else None,
                prefer_current=True,
                auto_pick_statuses=["awaiting_approval"],
            )
            if not resolved:
                console.print("[yellow]No task awaiting approval.[/yellow] Use /tasks or /use <id>.")
                return
            self._set_current(resolved)
            advanced = self._approve(task_id=resolved)
            if not advanced:
                return

            # Minimal, deterministic echo: confirm we advanced state before running.
            self._print_state_line(task_id=resolved, status_override="executing", updated_override="now")

            # Continue execution in foreground (progress will take over).
            self._run_task_foreground(resolved, use_real_pipeline=self.settings.interactive_use_real_pipeline)
            return

        if name in ("resume",):
            task_id = args[0] if args else None
            self._resume(task_id=task_id)
            return

        if name in ("retry",):
            task_id = args[0] if args else None
            self._retry(task_id=task_id)
            return

        if name in ("plan",):
            resolved = self._resolve_task_id(
                explicit=args[0] if args else None,
                prefer_current=True,
                auto_pick_statuses=["awaiting_approval", "planning"],
            )
            if not resolved:
                console.print("[yellow]No task found for plan view.[/yellow] Use /tasks or /use <id>.")
                return
            self._set_current(resolved)
            self._view_plan(task_id=resolved)
            return

        if name in ("logs", "tail"):
            resolved = self._resolve_task_id(
                explicit=args[0] if args else None,
                prefer_current=True,
                auto_pick_statuses=[
                    "created",
                    "intent_processing",
                    "planning",
                    "awaiting_approval",
                    "executing",
                    "verifying",
                    "failed",
                    "blocked",
                ],
            )
            if not resolved:
                console.print("[yellow]No task for logs.[/yellow] Use /tasks or /use <id>.")
                return
            self._set_current(resolved)
            self._tail_logs(task_id=resolved)
            return

        if name in ("cancel", "stop"):
            resolved = self._resolve_task_id(
                explicit=args[0] if args else None,
                prefer_current=True,
                auto_pick_statuses=[
                    "paused",
                    "created",
                    "intent_processing",
                    "planning",
                    "awaiting_approval",
                    "executing",
                    "verifying",
                ],
            )
            if not resolved:
                console.print("[yellow]No task to cancel.[/yellow] Use /tasks or /use <id>.")
                return
            reason = " ".join(args[1:]).strip() if len(args) > 1 else "User requested cancellation"
            self._set_current(resolved)
            self._cancel(task_id=resolved, reason=reason)
            return

        if name in ("interrupt", "pause"):
            resolved = self._resolve_task_id(
                explicit=args[0] if args else None,
                prefer_current=True,
                auto_pick_statuses=[
                    "executing",
                    "verifying",
                    "planning",
                    "intent_processing",
                    "created",
                ],
            )
            if not resolved:
                console.print("[yellow]No task to interrupt.[/yellow] Use /tasks or /use <id>.")
                return
            reason = " ".join(args[1:]).strip() if len(args) > 1 else "user_interrupt"
            self._set_current(resolved)
            self._pause(task_id=resolved, reason=reason, last_known_status=None)
            console.print("[yellow]paused[/yellow] (use /resume or /cancel)")
            return

        if name in ("set",):
            self._set(args)
            return

        console.print("[yellow]unknown command[/yellow] (try /help)")

    def _print_help(self) -> None:
        console.print(
            Panel(
                "\n".join(
                    [
                        "[bold]Commands[/bold]",
                        "/help                     show this help",
                        "/current                  show current task",
                        "/use <task_id>             set current task",
                        "/clear                    clear current task",
                        "/tasks [limit]             list recent tasks",
                        "/show [task_id] [--full] [--events N]  show a task (default: short run card)",
                        "/approve [task_id]         approve awaiting_approval task and resume runner",
                        "/resume [task_id]          run a task in foreground (auto-pick latest runnable task if omitted)",
                        "/retry [task_id]           reset failed task to created and run again (auto-pick latest failed task if omitted)",
                        "/plan [task_id]            print open_plan artifact summary (if present)",
                        "/logs [task_id]            tail task runner log",
                        "/cancel [task_id] [reason] cancel a task (best-effort)",
                        "/interrupt [task_id]       pause a task (Ctrl+C during run does the same)",
                        "/set pipeline real|sim     set default pipeline mode for this REPL",
                        "/exit                      exit",
                        "",
                        "[bold]Usage[/bold]",
                        "Type a request (no slash) to create and run a task.",
                    ]
                ),
                border_style="cyan",
            )
        )

    def _set(self, args: list[str]) -> None:
        if len(args) < 2:
            console.print("[red]usage: /set pipeline real|sim[/red]")
            return
        key = args[0].lower()
        value = args[1].lower()
        if key != "pipeline":
            console.print("[red]only pipeline is supported[/red]")
            return
        if value not in ("real", "sim", "simulated"):
            console.print("[red]pipeline must be real|sim[/red]")
            return
        self.settings.interactive_use_real_pipeline = value == "real"
        save_settings(self.settings)
        console.print(
            f"[green]ok[/green] pipeline default = {'real' if self.settings.interactive_use_real_pipeline else 'sim'}"
        )

    def _list_tasks(self, *, limit: int) -> None:
        tasks = self.task_manager.list_tasks(limit=limit)
        if not tasks:
            console.print("[yellow]no tasks[/yellow]")
            return

        # Put current task first (codex/claude "run list" feel), but keep the rest ordered as-is.
        if self.current_task_id:
            for i, t in enumerate(tasks):
                if t.task_id == self.current_task_id:
                    if i != 0:
                        tasks.insert(0, tasks.pop(i))
                    break

        table = Table(title=f"Tasks (latest {min(limit, len(tasks))})", show_header=True, header_style="bold")
        table.add_column("", style="magenta", no_wrap=True)  # ▶ ● ⏸ ✖ ✓ …
        table.add_column("id", style="cyan", no_wrap=True)
        table.add_column("status", style="green", no_wrap=True)
        table.add_column("title")
        for t in tasks:
            is_cur = bool(self.current_task_id and t.task_id == self.current_task_id)
            current_marker = "\u25b6" if is_cur else ""  # ▶
            badge = self._badge_for_status(str(t.status or ""))
            marker = f"{current_marker} {badge}".strip()

            task_id_short = f"T-{t.task_id[:8]}"
            task_id_cell = f"[bold]{task_id_short}[/bold]" if is_cur else task_id_short

            status_val = str(t.status or "")
            status_cell = f"[bold]{status_val}[/bold]" if is_cur else status_val

            title_val = (t.title or "").strip()
            age = self._format_age(t.updated_at) if t.updated_at else "?"
            title_core = title_val[:80]
            title_cell = f"{title_core} [dim]{age}[/dim]".rstrip()
            if is_cur:
                title_cell = f"[bold]{title_cell}[/bold]"

            table.add_row(marker, task_id_cell, status_cell, title_cell)
        console.print(table)

    def _badge_for_status(self, status: str) -> str:
        s = (status or "").strip().lower()
        if s in ("executing", "verifying"):
            return "\u25cf"  # ● running
        if s == "paused":
            return "\u23f8"  # ⏸ paused
        if s == "failed":
            return "\u2716"  # ✖ failed
        if s in ("succeeded", "done"):
            return "\u2713"  # ✓ done
        if s in ("planning", "intent_processing"):
            return "\u2026"  # … working (non-running)
        return ""

    def _prompt_suffix(self) -> str:
        """Prompt suffix for current task: [xxxxxxxx●] / [xxxxxxxx⏸] / [xxxxxxxx]."""
        if not self.current_task_id:
            return ""

        short = self._short_id(self.current_task_id)
        symbol = ""

        # Only show running/paused to avoid noisy/stale prompt state.
        try:
            task = self.task_manager.get_task(self.current_task_id)
            if not task:
                # Persisted current may point to a deleted/missing task.
                self._set_current(None)
                return ""
            status = str(task.status or "").strip().lower()
            if status in ("executing", "verifying"):
                symbol = "\u25cf"  # ●
            elif status == "paused":
                symbol = "\u23f8"  # ⏸
        except Exception:
            symbol = ""

        return f"[{short}{symbol}]"

    def _show_task(self, *, task_id: str) -> None:
        # Backwards-compat shim: keep old name as full view.
        self._show_full(task_id=task_id)

    def _show_card(self, *, task_id: str) -> None:
        """Short run card (1-3 lines)."""
        try:
            task = self.task_manager.get_task(task_id)
        except Exception as e:
            console.print(f"[red]not found[/red]: {e}")
            return

        status = str(task.status or "unknown")
        phase = self._phase_for_status(status)
        updated = self._format_age(task.updated_at) if task.updated_at else "?"
        short = self._short_id(task.task_id)

        marker = "\u25b6" if self.current_task_id == task.task_id else ""
        line1 = f"{marker} T-{short}  status={status}  phase={phase}  updated={updated}"
        owner = (task.created_by or "local").strip() or "local"
        title = (task.title or "").strip()
        if title:
            line2 = f"title: {title}  (owner: {owner})"
            console.print(line1)
            console.print(line2)
        else:
            console.print(line1)

        # Third line only for actionable next step / error pointers.
        if status == "awaiting_approval":
            console.print("reason: needs approval (/plan, /approve)")
        elif status == "paused":
            console.print("reason: paused (/resume, /cancel)")
        elif status in ("failed", "blocked"):
            # Keep compact; full details are in /logs or /show --events.
            reason = (task.exit_reason or "").strip()
            if reason:
                console.print(f"error: {reason} (see /logs)")
            else:
                console.print("error: see /logs")

    def _print_state_line(
        self,
        *,
        task_id: str,
        status_override: Optional[str] = None,
        updated_override: Optional[str] = None,
    ) -> None:
        """Single-line compact echo for key actions (never more than 1 line)."""
        short = self._short_id(task_id)
        status = status_override or "unknown"
        try:
            task = self.task_manager.get_task(task_id)
            status = status_override or str(task.status or status)
            short = self._short_id(task.task_id)
            updated = updated_override or (self._format_age(task.updated_at) if task.updated_at else "?")
        except Exception:
            updated = updated_override or "?"
        phase = self._phase_for_status(status)
        console.print(f"\u25b6 T-{short}  status={status}  phase={phase}  updated={updated}")

    def _show_full(self, *, task_id: str) -> None:
        """Full view (bounded to ~1 screen)."""
        try:
            task = self.task_manager.get_task(task_id)
        except Exception as e:
            console.print(f"[red]not found[/red]: {e}")
            return

        trace = None
        try:
            trace = self.task_manager.get_trace(task_id)
        except Exception:
            trace = None

        lines = [
            f"[cyan]id[/cyan]      {task.task_id}",
            f"[cyan]status[/cyan]  {task.status}",
            f"[cyan]phase[/cyan]   {self._phase_for_status(task.status)}",
            f"[cyan]title[/cyan]   {task.title}",
            f"[cyan]owner[/cyan]   {(task.created_by or 'local')}",
            f"[cyan]created[/cyan] {task.created_at}",
            f"[cyan]updated[/cyan] {task.updated_at}",
            f"[cyan]exit_reason[/cyan] {task.exit_reason or '-'}",
        ]

        # Show a small tail of lineage/audits as "pointers", not dumps.
        if trace and trace.timeline:
            lines.append("")
            lines.append("[bold]last timeline[/bold]")
            for entry in trace.timeline[-8:]:
                ts = entry.timestamp[:19] if entry.timestamp else "?"
                ph = entry.phase or "-"
                lines.append(f"- {ts} {entry.kind} ({ph}) {entry.ref_id}")
        if trace and trace.audits:
            lines.append("")
            lines.append("[bold]last audits[/bold]")
            for audit in trace.audits[-6:]:
                ts = str(audit.get("created_at", "?"))[:19]
                lvl = str(audit.get("level", "info"))
                ev = str(audit.get("event_type", ""))
                lines.append(f"- {ts} {lvl} {ev}")

        console.print(Panel("\n".join(lines), title="task", border_style="cyan"))

    def _show_events(self, *, task_id: str, n: int) -> None:
        """Recent events view (lineage + audits merged, last N)."""
        try:
            trace = self.task_manager.get_trace(task_id)
        except Exception as e:
            console.print(f"[red]trace failed[/red]: {e}")
            return
        if not trace:
            console.print("[yellow]no trace[/yellow]")
            return

        events: list[tuple[str, str]] = []
        for entry in trace.timeline or []:
            ts = entry.timestamp or ""
            label = f"lineage {entry.kind} phase={entry.phase or '-'} ref={entry.ref_id}"
            events.append((ts, label))
        for audit in trace.audits or []:
            ts = str(audit.get("created_at") or "")
            label = f"audit {audit.get('level','info')} {audit.get('event_type','')}"
            events.append((ts, label))

        # Sort by timestamp string (ISO lexicographic works).
        events.sort(key=lambda x: x[0])
        tail = events[-max(1, n):]
        if not tail:
            console.print("[yellow]no events[/yellow]")
            return
        for ts, label in tail:
            ts_short = (ts or "?")[:19]
            console.print(f"{ts_short}  {label}")

    def _parse_show_args(self, args: list[str]) -> dict[str, Any]:
        # Accept:
        # - /show [task_id]
        # - /show --full [task_id]
        # - /show --events N [task_id]
        # - /show [task_id] --full
        # - /show [task_id] --events N
        task_id: Optional[str] = None
        full = False
        events: Optional[int] = None

        it = iter(args)
        for tok in it:
            if tok == "--full":
                full = True
                continue
            if tok == "--events":
                try:
                    raw = next(it)
                except StopIteration:
                    raw = ""
                try:
                    events = int(raw)
                except ValueError:
                    events = 10
                continue
            if tok.startswith("--"):
                # Unknown flag: ignore to keep REPL forgiving.
                continue
            if task_id is None:
                task_id = tok
            else:
                # Extra positional args ignored.
                pass

        return {"task_id": task_id, "full": full, "events": events}

    def _phase_for_status(self, status: Optional[str]) -> str:
        s = str(status or "").strip().lower()
        if s in ("planning", "awaiting_approval"):
            return "PLANNING"
        if s in ("intent_processing",):
            return "INTENT"
        if s in ("executing",):
            return "EXECUTING"
        if s in ("verifying",):
            return "VERIFYING"
        if s in ("created",):
            return "CREATED"
        if s in ("succeeded",):
            return "DONE"
        if s in ("failed",):
            return "FAILED"
        if s in ("blocked",):
            return "BLOCKED"
        if s in ("canceled",):
            return "CANCELED"
        if s in ("paused",):
            return "PAUSED"
        return "UNKNOWN"

    def _format_age(self, iso_ts: str) -> str:
        # Return compact age like 2m/1h/3d.
        from datetime import datetime, timezone

        raw = str(iso_ts or "").strip()
        if not raw:
            return "?"
        try:
            # Handle trailing Z
            if raw.endswith("Z"):
                raw = raw[:-1] + "+00:00"
            dt = datetime.fromisoformat(raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            delta = now - dt.astimezone(timezone.utc)
            sec = int(delta.total_seconds())
            if sec < 0:
                sec = 0
            if sec < 60:
                return f"{sec}s"
            if sec < 3600:
                return f"{sec//60}m"
            if sec < 86400:
                return f"{sec//3600}h"
            return f"{sec//86400}d"
        except Exception:
            return "?"

    def _create_and_run(self, nl_request: str) -> None:
        # Keep legacy TaskManager-based tasks for now; the goal here is UX.
        task = self.task_manager.create_task(
            title=nl_request[:100],
            metadata={
                "nl_request": nl_request,
                "current_stage": "created",
                "created_at": utc_now_iso(),
                "interactive": {"pipeline": "real" if self.settings.interactive_use_real_pipeline else "sim"},
            },
            created_by="interactive_repl",
        )
        self.task_manager.add_lineage(
            task_id=task.task_id,
            kind="nl_request",
            ref_id=task.task_id,
            phase="creation",
            metadata={"request": nl_request},
        )

        console.print(f"[green]task created[/green] {task.task_id}")
        self._set_current(task.task_id)
        self._run_task_foreground(task.task_id, use_real_pipeline=self.settings.interactive_use_real_pipeline)

    def _run_task_foreground(self, task_id: str, *, use_real_pipeline: bool) -> None:
        # Foreground execution (codex/claude style): stream logs to terminal.
        # We also tee logs into a per-task file for later inspection.
        import logging
        from contextlib import contextmanager
        import threading

        from octopusos.core.runner.task_runner import TaskRunner

        log_path = _task_log_path(task_id)

        @contextmanager
        def _stream_logs():
            root = logging.getLogger()
            old_level = root.level
            root.setLevel(logging.INFO)

            rich_handler = RichHandler(
                console=console,
                rich_tracebacks=True,
                show_time=True,
                show_path=False,
            )
            # Keep the UI compact; full logs are written to file.
            rich_handler.setLevel(logging.ERROR)
            file_handler = logging.FileHandler(log_path, encoding="utf-8")
            file_handler.setFormatter(
                logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
            )
            root.addHandler(rich_handler)
            root.addHandler(file_handler)
            try:
                yield
            finally:
                try:
                    root.removeHandler(rich_handler)
                    root.removeHandler(file_handler)
                except Exception:
                    pass
                root.setLevel(old_level)

        policy_path = Path("policies/sandbox_policy.json")
        effective_policy = policy_path if policy_path.exists() else None

        console.print(
            f"[dim]running[/dim] {task_id} (pipeline={'real' if use_real_pipeline else 'sim'})"
        )
        console.print(f"[dim]logs[/dim] {log_path}")
        self._set_current(task_id)

        runner = TaskRunner(
            repo_path=Path("."),
            policy_path=effective_policy,
            use_real_pipeline=use_real_pipeline,
        )
        last_status: Optional[str] = None
        try:
            with _stream_logs():
                exc: list[BaseException] = []

                def _run():
                    try:
                        runner.run_task(task_id)
                    except BaseException as e:  # noqa: BLE001
                        exc.append(e)

                t = threading.Thread(target=_run, name=f"task-runner-{task_id}", daemon=True)
                t.start()

                # Single-line progress UI driven by task.status changes.
                stage_order = [
                    "created",
                    "intent_processing",
                    "planning",
                    "awaiting_approval",
                    "executing",
                    "verifying",
                    "succeeded",
                    "failed",
                    "canceled",
                    "blocked",
                ]
                stage_index = {s: i for i, s in enumerate(stage_order)}
                total = 6  # created->...->verifying is the "work" path; terminals handled separately.

                last_status: Optional[str] = None
                last_printed: Optional[str] = None

                progress = Progress(
                    TextColumn("[bold cyan]{task.fields[task_id]}[/bold cyan]"),
                    BarColumn(bar_width=28),
                    TextColumn("{task.fields[status]}"),
                    TimeElapsedColumn(),
                    console=console,
                    transient=True,
                )
                task_progress = progress.add_task(
                    "",
                    total=total,
                    task_id=task_id[:12],
                    status="starting",
                )

                with progress:
                    while t.is_alive():
                        try:
                            task = self.task_manager.get_task(task_id)
                            last_status = task.status
                        except Exception:
                            last_status = last_status or "unknown"

                        # Map status to a progress position.
                        pos = stage_index.get(last_status or "", 0)
                        if last_status in ("succeeded", "failed", "canceled", "blocked"):
                            progress.update(task_progress, completed=total, status=last_status)
                        elif last_status == "verifying":
                            progress.update(task_progress, completed=total - 1, status=last_status)
                        elif last_status == "executing":
                            progress.update(task_progress, completed=total - 2, status=last_status)
                        elif last_status == "awaiting_approval":
                            progress.update(task_progress, completed=total - 3, status=last_status)
                        elif last_status == "planning":
                            progress.update(task_progress, completed=2, status=last_status)
                        elif last_status == "intent_processing":
                            progress.update(task_progress, completed=1, status=last_status)
                        else:
                            progress.update(task_progress, completed=0, status=last_status or "created")

                        # For very important transitions, emit one compact line after progress stops.
                        if last_status != last_printed and last_status in ("awaiting_approval", "succeeded", "failed", "blocked", "canceled"):
                            last_printed = last_status

                        time.sleep(0.15)

                t.join(timeout=0.1)
                if exc:
                    raise exc[0]

                # Print a compact terminal summary line.
                final = last_status or "unknown"
                if final == "awaiting_approval":
                    console.print("[yellow]paused[/yellow] awaiting approval (use /plan and /approve)")
                elif final == "paused":
                    console.print("[yellow]paused[/yellow] (use /resume or /cancel)")
                elif final == "succeeded":
                    console.print("[green]done[/green]")
                elif final == "failed":
                    console.print("[red]failed[/red] (see /logs)")
                elif final == "blocked":
                    console.print("[red]blocked[/red] (see /logs)")
                elif final == "canceled":
                    console.print("[yellow]canceled[/yellow]")
        except KeyboardInterrupt:
            # Codex-style: Ctrl+C pauses (does not cancel).
            # We rely on a minimal runner change (status == paused => exit loop next tick).
            # If the user hits Ctrl+C again quickly at the prompt, we cancel.
            # Best-effort: use the most recent observed status as resume hint.
            self._pause(task_id=task_id, reason="user_interrupt", last_known_status=last_status)
            self._pending_cancel_task_id = task_id
            self._pending_cancel_deadline_monotonic = time.monotonic() + 1.0
            console.print("[yellow]paused[/yellow] (Ctrl+C again to cancel)")
            return

    def _approve(self, *, task_id: str) -> bool:
        # This is the legacy control-plane approval used by pause_gate.
        # Return True only if we advanced awaiting_approval -> executing.
        try:
            task = self.task_manager.get_task(task_id)
        except Exception as e:
            console.print(f"[red]not found[/red]: {e}")
            return False

        if str(task.status) != "awaiting_approval":
            console.print(f"[yellow]Task is not awaiting approval[/yellow] (status={task.status}).")
            return False

        try:
            self.task_manager.add_lineage(
                task_id=task_id,
                kind="approval",
                ref_id="approved",
                phase="awaiting_approval",
                metadata={"action": "approved", "approved_by": "cli_user", "approved_at": utc_now_iso()},
            )
            self.task_manager.add_audit(
                task_id=task_id,
                event_type="task_approved",
                level="info",
                payload={"action": "approved", "checkpoint": "open_plan", "approved_by": "cli_user"},
            )
            self.task_manager.update_task_status(task_id, "executing")
        except Exception as e:
            console.print(f"[red]approve failed[/red]: {e}")
            return False

        try:
            after = self.task_manager.get_task(task_id).status
        except Exception:
            after = "executing"

        if str(after) != "executing":
            console.print(f"[yellow]Approval did not advance state[/yellow] (status={after}).")
            return False
        return True

    def _view_plan(self, *, task_id: str) -> None:
        # Reuse the legacy open_plan artifact convention recorded in lineage.
        try:
            trace = self.task_manager.get_trace(task_id)
        except Exception as e:
            console.print(f"[red]trace failed[/red]: {e}")
            return

        artifact_entries = [
            entry
            for entry in (trace.timeline or [])
            if entry.kind == "artifact"
            and entry.metadata
            and entry.metadata.get("artifact_kind") == "open_plan"
        ]
        if not artifact_entries:
            console.print("[yellow]no open_plan artifact found[/yellow]")
            return

        latest = artifact_entries[-1]
        rel = str(latest.ref_id)
        artifact_path = Path("store") / rel
        if not artifact_path.exists():
            console.print(f"[red]artifact missing[/red]: {artifact_path}")
            return

        import json

        try:
            data = json.loads(artifact_path.read_text(encoding="utf-8"))
        except Exception as e:
            console.print(f"[red]failed to read artifact[/red]: {e}")
            return

        summary_lines = [
            f"[cyan]task_id[/cyan] {data.get('task_id')}",
            f"[cyan]generated_at[/cyan] {data.get('generated_at')}",
            f"[cyan]pipeline_status[/cyan] {data.get('pipeline_status')}",
            f"[cyan]summary[/cyan] {data.get('pipeline_summary')}",
            f"[cyan]path[/cyan] {artifact_path}",
        ]
        console.print(Panel("\n".join(summary_lines), title="open_plan", border_style="cyan"))

    def _tail_logs(self, *, task_id: str) -> None:
        path = _task_log_path(task_id)
        if not path.exists():
            console.print(f"[yellow]log not found[/yellow]: {path}")
            return
        console.print(f"[dim]tailing[/dim] {path}  (Ctrl+C to stop)")
        try:
            subprocess.call(["tail", "-n", "200", "-f", str(path)])
        except KeyboardInterrupt:
            console.print("")

    def _cancel(self, *, task_id: str, reason: str) -> None:
        try:
            self.task_manager.update_task_status(task_id, "canceled")
            self.task_manager.add_audit(
                task_id=task_id,
                event_type="task_canceled",
                level="warn",
                payload={"reason": reason, "canceled_by": "cli_user"},
            )
            self.task_manager.add_lineage(
                task_id=task_id,
                kind="cancel",
                ref_id="canceled",
                phase="cli",
                metadata={"reason": reason, "canceled_at": utc_now_iso()},
            )
        except Exception as e:
            console.print(f"[red]cancel failed[/red]: {e}")
            return
        console.print(f"[yellow]canceled[/yellow] {task_id}")

    def _pause(self, *, task_id: str, reason: str, last_known_status: Optional[str]) -> None:
        try:
            task = self.task_manager.get_task(task_id)
            if not task:
                console.print("[yellow]task not found[/yellow]")
                return

            if not task.metadata:
                task.metadata = {}

            phase = self._phase_for_status(last_known_status or task.status)
            now_iso = utc_now_iso()
            now_ms = int(time.time() * 1000)

            # Minimal but structured pause metadata (recoverable + auditable).
            resume_hint = {
                "last_known_status": (last_known_status or task.status),
                "paused_at_phase": phase,
            }

            task.metadata.update(
                {
                    "pause_requested": True,
                    "paused_at_phase": phase,
                    "paused_at_step": "unknown",
                    "paused_at_ts": now_ms,
                    "paused_reason": reason,
                    "resume_hint": resume_hint,
                }
            )

            task.status = "paused"
            self.task_manager.update_task(task)

            self.task_manager.add_audit(
                task_id=task_id,
                event_type="task_paused",
                level="warn",
                payload={
                    "reason": reason,
                    "paused_at_phase": phase,
                    "paused_at_step": "unknown",
                    "paused_at_ts": now_ms,
                    "resume_hint": resume_hint,
                },
            )
            self.task_manager.add_lineage(
                task_id=task_id,
                kind="pause",
                ref_id="paused",
                phase="cli",
                metadata={"reason": reason, "paused_at": now_iso, "resume_hint": resume_hint},
            )
        except Exception as e:
            console.print(f"[red]pause failed[/red]: {e}")

    def _resume(self, *, task_id: Optional[str]) -> None:
        # Pick task:
        # - explicit > current > latest paused > latest runnable > latest awaiting_approval
        resolved = None
        if task_id:
            resolved = task_id
        elif self.current_task_id:
            resolved = self.current_task_id
        else:
            tasks = self.task_manager.list_tasks(limit=100)
            pick = next((t for t in tasks if t.status == "paused"), None)
            if not pick:
                pick = next(
                    (t for t in tasks if t.status in ("created", "intent_processing", "planning", "executing", "verifying")),
                    None,
                )
            if not pick:
                pick = next((t for t in tasks if t.status == "awaiting_approval"), None)
            resolved = pick.task_id if pick else None

        if not resolved:
            console.print("[yellow]no runnable tasks found[/yellow]")
            return

        task_id = resolved
        self._set_current(task_id)

        task = self.task_manager.get_task(task_id)
        if task.status == "paused":
            resume_hint = task.metadata.get("resume_hint") if isinstance(task.metadata, dict) else None
            last_status = None
            if isinstance(resume_hint, dict):
                last_status = resume_hint.get("last_known_status")
            last_status = str(last_status or "").strip()
            if not last_status or last_status == "paused":
                console.print("[yellow]cannot resume[/yellow]: missing resume_hint (try /retry or /show --events)")
                return

            # Restore status to the last known value (do not guess).
            try:
                task.status = last_status
                self.task_manager.update_task(task)
                self.task_manager.add_audit(
                    task_id=task_id,
                    event_type="task_resumed",
                    level="info",
                    payload={"resume_hint": resume_hint, "actor": "cli_user"},
                )
                self.task_manager.add_lineage(
                    task_id=task_id,
                    kind="resume",
                    ref_id="resumed",
                    phase="cli",
                    metadata={"resume_hint": resume_hint, "resumed_at": utc_now_iso()},
                )
            except Exception as e:
                console.print(f"[red]resume failed[/red]: {e}")
                return

            self._run_task_foreground(task_id, use_real_pipeline=self.settings.interactive_use_real_pipeline)
            return

        if task.status == "awaiting_approval":
            console.print("[yellow]task is awaiting approval[/yellow] (use /approve)")
            return
        if task.status in ("succeeded", "canceled"):
            console.print(f"[yellow]task is terminal[/yellow] ({task.status})")
            return
        if task.status == "failed":
            console.print("[yellow]task failed[/yellow] (use /retry)")
            return
        self._run_task_foreground(task_id, use_real_pipeline=self.settings.interactive_use_real_pipeline)

    def _on_prompt_interrupt(self) -> None:
        now = time.monotonic()
        if self._pending_cancel_task_id:
            if now <= self._pending_cancel_deadline_monotonic:
                task_id = self._pending_cancel_task_id
                self._pending_cancel_task_id = None
                self._pending_cancel_deadline_monotonic = 0.0
                self._set_current(task_id)
                self._cancel(task_id=task_id, reason="double_ctrl_c")
                return
            # Expired window; clear the pending cancel request.
            self._pending_cancel_task_id = None
            self._pending_cancel_deadline_monotonic = 0.0

        # If already paused, don't spam; just remind once.
        if self.current_task_id:
            try:
                task = self.task_manager.get_task(self.current_task_id)
                if task and task.status == "paused":
                    console.print("\n[dim]Already paused. Use /resume or /cancel.[/dim]")
                    return
            except Exception:
                pass

        console.print("")  # Keep prompt responsive; no exit.

    def _retry(self, *, task_id: Optional[str]) -> None:
        resolved = None
        if self.current_task_id:
            try:
                cur = self.task_manager.get_task(self.current_task_id)
                if cur and cur.status == "failed":
                    resolved = cur.task_id
            except Exception:
                resolved = None
        if not resolved:
            resolved = self._resolve_task_id(
                explicit=task_id,
                prefer_current=False,
                auto_pick_statuses=["failed"],
            )
        if not resolved:
            console.print("[yellow]no failed tasks found[/yellow]")
            return
        task_id = resolved
        self._set_current(task_id)

        task = self.task_manager.get_task(task_id)
        if task.status != "failed":
            console.print(f"[yellow]task is not failed[/yellow] (status={task.status})")
            return

        # Best-effort reset for legacy runner state machine.
        try:
            self.task_manager.update_task_status(task_id, "created")
            self.task_manager.add_lineage(
                task_id=task_id,
                kind="retry",
                ref_id="retry",
                phase="cli",
                metadata={"retried_at": utc_now_iso(), "retried_by": "cli_user"},
            )
            self.task_manager.add_audit(
                task_id=task_id,
                event_type="task_retried",
                level="warn",
                payload={"actor": "cli_user"},
            )
        except Exception as e:
            console.print(f"[red]retry failed[/red]: {e}")
            return

        self._run_task_foreground(task_id, use_real_pipeline=self.settings.interactive_use_real_pipeline)

    def _short_id(self, task_id: Optional[str]) -> str:
        if not task_id:
            return ""
        s = str(task_id)
        return s[:8]

    def _set_current(self, task_id: Optional[str]) -> None:
        self.current_task_id = task_id
        self.settings.interactive_current_task_id = task_id
        save_settings(self.settings)
        self._last_empty_hint_key = None

    def _clear_current(self) -> None:
        self._set_current(None)
        console.print("[dim]current cleared[/dim]")

    def _use(self, *, task_id: str) -> None:
        try:
            task = self.task_manager.get_task(task_id)
        except Exception as e:
            console.print(f"[red]not found[/red]: {e}")
            return
        self._set_current(task.task_id)
        console.print(f"[green]current[/green] {task.task_id} ({task.status})")

    def _current(self) -> None:
        if not self.current_task_id:
            console.print("[dim]no current task[/dim]")
            return
        try:
            task = self.task_manager.get_task(self.current_task_id)
        except Exception as e:
            console.print(f"[yellow]current task missing[/yellow]: {e}")
            return
        console.print(
            Panel(
                "\n".join(
                    [
                        f"[cyan]id[/cyan]      {task.task_id}",
                        f"[cyan]status[/cyan]  {task.status}",
                        f"[cyan]title[/cyan]   {task.title}",
                        f"[cyan]updated[/cyan] {task.updated_at}",
                    ]
                ),
                title="current",
                border_style="cyan",
            )
        )

    def _resolve_task_id(
        self,
        *,
        explicit: Optional[str],
        prefer_current: bool,
        auto_pick_statuses: Optional[list[str]],
    ) -> Optional[str]:
        if explicit:
            return explicit
        if prefer_current and self.current_task_id:
            return self.current_task_id
        if not auto_pick_statuses:
            return None
        tasks = self.task_manager.list_tasks(limit=100)
        pick = next((t for t in tasks if t.status in auto_pick_statuses), None)
        return pick.task_id if pick else None

    def _on_empty_input(self) -> None:
        # Low-noise quick help:
        # - If current exists: do nothing.
        # - If no current and tasks exist: show a single-line tip (once per session state).
        # - If no tasks: show compact help (once per session state).
        if self.current_task_id:
            return

        try:
            has_any_tasks = bool(self.task_manager.list_tasks(limit=1))
        except Exception:
            has_any_tasks = False

        if has_any_tasks:
            key = "tip"
            if self._last_empty_hint_key != key:
                console.print("[dim]Tip: use /tasks, /use <id>, or type a request to create a task.[/dim]")
                self._last_empty_hint_key = key
            return

        key = "help"
        if self._last_empty_hint_key == key:
            return

        console.print(
            Panel(
                "\n".join(
                    [
                        "No tasks yet.",
                        "Type a request to create one, or use:",
                        "  /help   /tasks   /use <task_id>",
                    ]
                ),
                border_style="cyan",
            )
        )
        self._last_empty_hint_key = key


def interactive_main() -> None:
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        console.print("[red]interactive mode requires a TTY[/red]")
        raise SystemExit(1)
    InteractiveREPL().run()


if __name__ == "__main__":
    interactive_main()
