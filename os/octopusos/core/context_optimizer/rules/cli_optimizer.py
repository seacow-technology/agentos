from __future__ import annotations

import hashlib
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


_ANSI_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def deduplicate_lines(text: str, *, max_occurrences: int = 3) -> Tuple[str, Dict[str, Any]]:
    """
    Remove high-frequency duplicate lines while preserving some context.
    - Keep first `max_occurrences` occurrences of identical normalized lines.
    - Always keep empty lines as-is (but collapse >2 consecutive empties).
    """
    lines = text.splitlines()
    kept: List[str] = []
    counts: Counter[str] = Counter()
    removed = 0

    empty_streak = 0
    for line in lines:
        if not line.strip():
            empty_streak += 1
            if empty_streak <= 2:
                kept.append(line)
            else:
                removed += 1
            continue
        empty_streak = 0

        key = line.strip()
        counts[key] += 1
        if counts[key] <= max_occurrences:
            kept.append(line)
        else:
            removed += 1

    return "\n".join(kept) + ("\n" if text.endswith("\n") else ""), {
        "dedup_removed_lines": removed,
        "dedup_unique_lines": len(counts),
        "dedup_total_lines": len(lines),
    }


def _drop_progress_lines(lines: List[str]) -> Tuple[List[str], int]:
    """
    Heuristic removal of progress indicators/spinners and extremely noisy lines.
    """
    out: List[str] = []
    removed = 0
    for ln in lines:
        s = ln.strip()
        if not s:
            out.append(ln)
            continue
        if "\r" in ln:
            removed += 1
            continue
        # Common progress patterns.
        if re.search(r"\b(\d{1,3}%|\[\s*\d+/\d+\s*\])\b", s) and ("|" in s or "ETA" in s):
            removed += 1
            continue
        if re.search(r"\bDownloading\b|\bFetched\b|\bResolving\b|\bProgress\b", s) and re.search(r"\b(\d+%|\d+/\d+)\b", s):
            removed += 1
            continue
        out.append(ln)
    return out, removed


def extract_errors(text: str, *, max_lines: int = 80) -> Dict[str, Any]:
    lines = text.splitlines()
    error_like: List[str] = []

    patterns = [
        r"\bERROR\b",
        r"\bError\b",
        r"\bException\b",
        r"\bTraceback\b",
        r"\bFAILED\b",
        r"\bFAIL\b",
        r"\bpanic\b",
        r"\bassert\b",
        r"\bAssertionError\b",
        r"\bE\s+",
    ]
    rx = re.compile("|".join(f"(?:{p})" for p in patterns))

    for ln in lines:
        if rx.search(ln):
            error_like.append(ln)

    # Keep tail to preserve the most relevant stack trace endings.
    tail = error_like[-max_lines:] if len(error_like) > max_lines else error_like
    return {
        "error_lines_count": len(error_like),
        "error_lines_tail": tail,
    }


def extract_failed_tests(text: str, *, max_items: int = 50) -> Dict[str, Any]:
    lines = text.splitlines()
    failed: List[str] = []

    # pytest: "FAILED path::test - reason"
    for ln in lines:
        m = re.match(r"^\s*FAILED\s+([^\s]+)", ln)
        if m:
            failed.append(m.group(1))

    # cargo: "test foo::bar ... FAILED"
    for ln in lines:
        m = re.match(r"^\s*test\s+(.+?)\s+\.\.\.\s+FAILED\s*$", ln)
        if m:
            failed.append(m.group(1).strip())

    # jest/pnpm: "FAIL  path"
    for ln in lines:
        m = re.match(r"^\s*FAIL\s+([^\s]+)", ln)
        if m:
            failed.append(m.group(1))

    # De-dupe while preserving order.
    seen = set()
    uniq: List[str] = []
    for t in failed:
        if t in seen:
            continue
        seen.add(t)
        uniq.append(t)

    return {
        "failed_tests_count": len(uniq),
        "failed_tests": uniq[:max_items],
        "failed_tests_truncated": len(uniq) > max_items,
    }


def _normalize_failure_signature(message: str) -> str:
    s = message.strip()
    # Remove timestamps and obvious dynamic values to stabilize signatures.
    s = re.sub(r"\b\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:,\d+|\.\d+)?\b", "<ts>", s)
    s = re.sub(r"\b0x[0-9a-fA-F]+\b", "<hex>", s)
    s = re.sub(r"\b[0-9a-f]{8,}\b", "<id>", s)
    s = re.sub(r"\b\d+\b", "<n>", s)
    s = re.sub(r"\s+", " ", s)
    return s[:220]


def _extract_top_frame(lines: List[str], start_idx: int) -> Optional[str]:
    # Best-effort: scan the next few lines for a recognizable frame.
    for j in range(start_idx, min(len(lines), start_idx + 20)):
        ln = lines[j].strip()
        if not ln:
            continue
        if ln.startswith("File ") or ln.startswith("at ") or ln.startswith("test ") or ln.startswith("  File "):
            return ln[:240]
        if re.match(r"^\s*at\s+.+", lines[j]):
            return lines[j].strip()[:240]
    return None


def extract_primary_failures(text: str, *, max_items: int = 12) -> List[Dict[str, Any]]:
    """
    Extract multiple failures deterministically and preserve long-tail:
    - de-dupe by normalized signature
    - keep count of repeated occurrences
    """
    lines = text.splitlines()
    failures: List[Dict[str, Any]] = []
    counts: Counter[str] = Counter()
    first: Dict[str, Dict[str, Any]] = {}

    def add(kind: str, msg: str, idx: int) -> None:
        sig_base = f"{kind}:{_normalize_failure_signature(msg)}"
        counts[sig_base] += 1
        if sig_base in first:
            return
        first[sig_base] = {
            "type": kind,
            "signature": sig_base,
            "top_frame": _extract_top_frame(lines, idx + 1),
            "message": msg.strip()[:800],
        }

    # pytest failures
    for i, ln in enumerate(lines):
        m = re.match(r"^\s*FAILED\s+(.+)$", ln)
        if m:
            add("test_failed", m.group(1), i)

    # generic error lines
    for i, ln in enumerate(lines):
        if re.search(r"\b(ERROR|Exception|Traceback|panic)\b", ln):
            add("error", ln, i)

    # preserve insertion order and attach repeat counts
    for sig_base, item in first.items():
        item["count"] = int(counts.get(sig_base, 1))
        failures.append(item)
        if len(failures) >= max_items:
            break

    return failures

def summarize_git_status(text: str, *, max_items: int = 200) -> Dict[str, Any]:
    """
    Supports both `git status` human output and `--porcelain`.
    """
    lines = [ln.rstrip("\n") for ln in text.splitlines()]

    porcelain: List[str] = []
    for ln in lines:
        if re.match(r"^[ MADRCU?]{2}\s+", ln):
            porcelain.append(ln)

    changed_files: List[Dict[str, str]] = []
    if porcelain:
        for ln in porcelain[:max_items]:
            st = ln[:2]
            path = ln[3:].strip()
            changed_files.append({"status": st, "path": path})
        return {
            "git_status_format": "porcelain",
            "changed_files_count": len(porcelain),
            "changed_files": changed_files,
            "changed_files_truncated": len(porcelain) > max_items,
        }

    # Fallback: parse human lines like "modified: foo"
    human: List[Tuple[str, str]] = []
    for ln in lines:
        m = re.match(r"^\s*(modified|new file|deleted|renamed):\s+(.+)$", ln)
        if m:
            human.append((m.group(1), m.group(2)))
    for kind, path in human[:max_items]:
        changed_files.append({"status": kind, "path": path})
    return {
        "git_status_format": "human",
        "changed_files_count": len(human),
        "changed_files": changed_files,
        "changed_files_truncated": len(human) > max_items,
    }


def _count_warnings(text: str) -> int:
    # Good enough for CLI logs; we keep it strict (only "warning").
    return len(re.findall(r"\bwarning\b", text, flags=re.IGNORECASE))


@dataclass
class CliOptimizeInput:
    raw_text: str
    command: Optional[str] = None
    exit_code: Optional[int] = None
    duration_ms: Optional[int] = None


def generate_structured_summary(inp: CliOptimizeInput) -> Dict[str, Any]:
    raw = inp.raw_text
    no_ansi = strip_ansi(raw)

    # Remove progress noise before dedup so we don't waste dedup budget.
    lines = no_ansi.splitlines()
    lines, progress_removed = _drop_progress_lines(lines)
    cleaned = "\n".join(lines) + ("\n" if no_ansi.endswith("\n") else "")

    deduped, dedup_meta = deduplicate_lines(cleaned, max_occurrences=2)
    errs = extract_errors(deduped)
    failed = extract_failed_tests(deduped)
    git = summarize_git_status(deduped)

    warning_count = _count_warnings(deduped)
    # Count failures from pre-dedup stream to retain long-tail frequency signals.
    primary_failures = extract_primary_failures(cleaned)

    # Verdict logic (redline):
    # - If any primary failures exist => fail
    # - Else if exit_code is non-zero (and known) => fail
    # - Else pass
    if primary_failures:
        verdict = "fail"
    elif inp.exit_code not in (0, None):
        verdict = "fail"
    else:
        verdict = "pass"

    structured: Dict[str, Any] = {
        "command": inp.command,
        "exit_code": inp.exit_code,
        "verdict": verdict,
        "duration_ms": inp.duration_ms,
        "warnings_count": warning_count,
        "errors": errs,
        "failed_tests": failed,
        "primary_failures": primary_failures,
        "git_status": git,
    }
    meta: Dict[str, Any] = {
        "raw_sha256": _sha256_text(raw),
        "lines_raw": len(raw.splitlines()),
        "lines_after_strip_ansi": len(no_ansi.splitlines()),
        "lines_after_progress_drop": len(cleaned.splitlines()),
        "lines_after_dedup": len(deduped.splitlines()),
        "progress_removed_lines": progress_removed,
        **dedup_meta,
    }

    def _build_verbose_summary() -> str:
        summary_lines: List[str] = []
        summary_lines.append("## CLI Execution Summary")
        if inp.command:
            summary_lines.append(f"- command: {inp.command}")
        if inp.exit_code is not None:
            summary_lines.append(f"- exit_code: {inp.exit_code}")
        if inp.duration_ms is not None:
            summary_lines.append(f"- duration_ms: {inp.duration_ms}")
        summary_lines.append(f"- warnings_count: {warning_count}")

        ft = failed.get("failed_tests") or []
        if ft:
            summary_lines.append(f"- failed_tests_count: {failed.get('failed_tests_count')}")
            for t in ft[:20]:
                summary_lines.append(f"  - {t}")

        err_tail = errs.get("error_lines_tail") or []
        if err_tail:
            summary_lines.append("")
            summary_lines.append("## Error Tail")
            for ln in err_tail[-40:]:
                summary_lines.append(ln)

        if not err_tail and not ft:
            tail = deduped.splitlines()[-40:]
            summary_lines.append("")
            summary_lines.append("## Output Tail")
            summary_lines.extend(tail)

        return "\n".join(summary_lines).strip() + "\n"

    def _build_compact_summary() -> str:
        """
        Guarantee we don't expand small logs: emit only the highest-signal parts.
        """
        out: List[str] = []
        if inp.exit_code is not None:
            out.append(f"exit_code={inp.exit_code}")
        if inp.duration_ms is not None:
            out.append(f"duration_ms={inp.duration_ms}")
        out.append(f"warnings={warning_count}")

        ft = failed.get("failed_tests") or []
        if ft:
            out.append(f"failed_tests={failed.get('failed_tests_count')}")
            for t in ft[:20]:
                out.append(f"- {t}")

        err_tail = errs.get("error_lines_tail") or []
        if err_tail:
            out.append("error_tail:")
            out.extend(err_tail[-30:])
        else:
            # Keep only a very small tail for passing logs.
            out.append("tail:")
            out.extend(deduped.splitlines()[-20:])
        return "\n".join(out).strip() + "\n"

    summary_text = _build_verbose_summary()
    raw_bytes = len(raw.encode("utf-8", errors="replace"))
    summary_bytes = len(summary_text.encode("utf-8", errors="replace"))
    if summary_bytes >= raw_bytes:
        summary_text = _build_compact_summary()

    return {
        "summary_text": summary_text,
        "structured": structured,
        "metadata": meta,
    }


def optimize_cli_text(
    raw_text: str,
    *,
    command: Optional[str] = None,
    exit_code: Optional[int] = None,
    duration_ms: Optional[int] = None,
) -> Dict[str, Any]:
    inp = CliOptimizeInput(raw_text=raw_text, command=command, exit_code=exit_code, duration_ms=duration_ms)
    return generate_structured_summary(inp)
