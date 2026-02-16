from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from .metrics import generate_report_json
from .rules.cli_optimizer import optimize_cli_text as _optimize_cli
from .rules.tool_optimizer import optimize_tool_trace_text as _optimize_tool
from .rules.ui_optimizer import optimize_ui_text as _optimize_ui


def optimize_cli_text(
    raw_text: str,
    *,
    command: Optional[str] = None,
    exit_code: Optional[int] = None,
    duration_ms: Optional[int] = None,
) -> Dict[str, Any]:
    return _optimize_cli(raw_text, command=command, exit_code=exit_code, duration_ms=duration_ms)


def optimize_ui_text(raw_text: str) -> Dict[str, Any]:
    return _optimize_ui(raw_text)


def optimize_tool_trace_text(raw_text: str) -> Dict[str, Any]:
    return _optimize_tool(raw_text)


def _read_text_best_effort(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _pick_real_cli_input(repo_root: Path) -> Tuple[str, Dict[str, Any]]:
    # Prefer large real CLI-like logs (more representative for token pressure).
    candidates = [
        repo_root / "reports" / "teams_deploy" / "webui_restart.log",
        # Real webui/playwright runs often include huge backend logs.
        *sorted((repo_root / "output" / "playwright" / "full-audit").glob("*/backend.log")),
        *sorted((repo_root / "output" / "playwright" / "full-audit").glob("*/frontend.log")),
        repo_root / "reports" / "growth_release_gate_pytest.log",
    ]
    for p in candidates:
        if p.exists():
            kind = "cli_log"
            if p.name.endswith("pytest.log"):
                kind = "pytest"
            elif p.name.endswith("backend.log"):
                kind = "webui_backend_log"
            elif p.name.endswith("frontend.log"):
                kind = "webui_frontend_log"
            return _read_text_best_effort(p), {"source_path": str(p), "kind": kind}

    # Fallback: generate large synthetic (1000+ lines) if missing.
    lines = []
    for i in range(1200):
        lines.append(f"[{i:04d}] INFO running test_case_{i%37} ... ok")
    lines.append("FAILED tests/unit/test_example.py::test_failure - AssertionError: expected 1 == 2")
    lines.append("Traceback (most recent call last):")
    lines.append("  File \"tests/unit/test_example.py\", line 1, in test_failure")
    lines.append("AssertionError: expected 1 == 2")
    return "\n".join(lines) + "\n", {"source_path": None, "kind": "synthetic"}


def _pick_real_ui_input(repo_root: Path) -> Tuple[str, Dict[str, Any]]:
    # Prefer large real Playwright/WebUI logs if present (more representative for UI noise).
    candidates = [
        *sorted((repo_root / "output" / "playwright" / "full-audit").glob("*/frontend.log")),
        *sorted((repo_root / "output" / "playwright" / "full-audit").glob("*/backend.log")),
        repo_root / "reports" / "webui_playwright_full_audit.md",
        repo_root / "reports" / "webui_full_audit_report.md",
    ]
    existing = [p for p in candidates if p.exists()]
    if existing:
        # Pick the largest file for a more realistic UI-heavy context scenario.
        p = max(existing, key=lambda x: x.stat().st_size if x.exists() else 0)
        kind = "ui_log"
        if p.suffix.lower() == ".md":
            kind = "md_report"
        elif p.name.endswith("frontend.log"):
            kind = "playwright_frontend_log"
        elif p.name.endswith("backend.log"):
            kind = "playwright_backend_log"
        return _read_text_best_effort(p), {"source_path": str(p), "kind": kind}

    # Fallback: synthetic but big.
    lines = []
    for i in range(1200):
        if i % 50 == 0:
            lines.append("[ERROR] Failed to load resource: the server responded with a status of 404 () @ https://example.com/favicon.ico:0")
        else:
            lines.append(f"[WARN] i18next is maintained with support from locize.com... ({i})")
    return "\n".join(lines) + "\n", {"source_path": None, "kind": "synthetic"}


def _pick_real_tool_input(repo_root: Path) -> Tuple[str, Dict[str, Any]]:
    """
    Try to extract one real session_run_events record from local ~/.octopusos store.
    If unavailable, fallback to a synthetic JSON trace.
    """
    try:
        import sqlite3

        db = Path.home() / ".octopusos" / "store" / "octopusos" / "db.sqlite"
        if db.exists():
            conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            try:
                rows = conn.execute(
                    "select event_json from session_run_events order by created_at desc limit 80"
                ).fetchall()
                texts = [r[0] for r in rows if r and isinstance(r[0], str) and r[0].strip()]
                if texts:
                    joined = "\n".join(texts) + "\n"
                    return joined, {"source_path": str(db), "kind": "sqlite.session_run_events.tail80"}
            finally:
                conn.close()
    except Exception:
        pass

    synthetic = {
        "type": "tool.call",
        "tool": "playwright",
        "request": {"url": "https://example.com", "timeout_ms": 30000, "headers": {"x": "y"}},
        "response": {"status": 200, "body": {"title": "Example Domain", "headers": {"server": "nginx"}}},
        "metadata": {"created_at": "2026-02-10T00:00:00Z", "trace_id": "abcd" * 10},
    }
    return json.dumps(synthetic, ensure_ascii=False), {"source_path": None, "kind": "synthetic"}


def generate_all_reports(
    *,
    repo_root: Path,
    model: str = "gpt-4o",
    output_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    output_dir = output_dir or (repo_root / "reports" / "token_optimization")
    output_dir.mkdir(parents=True, exist_ok=True)

    # -------------------------
    # CLI
    # -------------------------
    cli_raw, cli_src = _pick_real_cli_input(repo_root)
    cli_opt = optimize_cli_text(cli_raw, command=cli_src.get("kind"))
    cli_report = generate_report_json(
        kind="cli",
        raw_text=cli_raw,
        optimized_text=str(cli_opt["summary_text"]),
        model=model,
        structured=cli_opt.get("structured"),
        metadata={**(cli_opt.get("metadata") or {}), "source": cli_src},
        output_path=output_dir / "cli_report.json",
    )
    (output_dir / "cli_before.txt").write_text(cli_raw, encoding="utf-8", errors="replace")
    (output_dir / "cli_after.txt").write_text(str(cli_opt["summary_text"]), encoding="utf-8", errors="replace")

    # -------------------------
    # UI
    # -------------------------
    ui_raw, ui_src = _pick_real_ui_input(repo_root)
    ui_opt = optimize_ui_text(ui_raw)
    ui_report = generate_report_json(
        kind="ui",
        raw_text=ui_raw,
        optimized_text=str(ui_opt["summary_text"]),
        model=model,
        structured=ui_opt.get("structured"),
        metadata={**(ui_opt.get("metadata") or {}), "source": ui_src},
        output_path=output_dir / "ui_report.json",
    )
    (output_dir / "ui_before.txt").write_text(ui_raw, encoding="utf-8", errors="replace")
    (output_dir / "ui_after.txt").write_text(str(ui_opt["summary_text"]), encoding="utf-8", errors="replace")

    # -------------------------
    # Tool
    # -------------------------
    tool_raw, tool_src = _pick_real_tool_input(repo_root)
    tool_opt = optimize_tool_trace_text(tool_raw)
    tool_report = generate_report_json(
        kind="tool",
        raw_text=tool_raw,
        optimized_text=str(tool_opt["summary_text"]),
        model=model,
        structured=tool_opt.get("structured"),
        metadata={**(tool_opt.get("metadata") or {}), "source": tool_src},
        output_path=output_dir / "tool_report.json",
    )
    (output_dir / "tool_before.txt").write_text(tool_raw, encoding="utf-8", errors="replace")
    (output_dir / "tool_after.txt").write_text(str(tool_opt["summary_text"]), encoding="utf-8", errors="replace")

    # -------------------------
    # Aggregate
    # -------------------------
    def redp(r) -> float:
        return float(getattr(r.metrics, "reduction_percent"))

    cli_r = redp(cli_report)
    ui_r = redp(ui_report)
    tool_r = redp(tool_report)

    # Weighted by raw tokens (more representative than naive mean).
    total_raw = cli_report.metrics.raw_tokens + ui_report.metrics.raw_tokens + tool_report.metrics.raw_tokens
    if total_raw <= 0:
        weighted = 0.0
    else:
        weighted = (
            cli_r * cli_report.metrics.raw_tokens
            + ui_r * ui_report.metrics.raw_tokens
            + tool_r * tool_report.metrics.raw_tokens
        ) / total_raw

    aggregate = {
        "model": model,
        "cli_reduction_percent": cli_r,
        "ui_reduction_percent": ui_r,
        "tool_reduction_percent": tool_r,
        "weighted_average_percent": weighted,
        "raw_tokens_total": total_raw,
        "optimized_tokens_total": (
            cli_report.metrics.optimized_tokens
            + ui_report.metrics.optimized_tokens
            + tool_report.metrics.optimized_tokens
        ),
        "reports": {
            "cli": "cli_report.json",
            "ui": "ui_report.json",
            "tool": "tool_report.json",
        },
    }
    (output_dir / "aggregate_report.json").write_text(
        json.dumps(aggregate, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    return aggregate


if __name__ == "__main__":
    # Local dev entrypoint:
    #   python3 -m octopusos.core.context_optimizer.pipeline
    repo_root = Path(__file__).resolve().parents[4]
    out = generate_all_reports(repo_root=repo_root, model="gpt-4o")
    print(json.dumps(out, indent=2, ensure_ascii=False))
